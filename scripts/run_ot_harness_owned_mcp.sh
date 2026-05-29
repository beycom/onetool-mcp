#!/usr/bin/env bash
set -euo pipefail

experiment="${1:-packages/ot-harness/experiments/terminal-bench-owned-mcp/experiment.yaml}"
port="18768"
path="/mcp"
host="0.0.0.0"
url="http://127.0.0.1:${port}${path}"
pid=""

cleanup() {
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
        kill "${pid}" 2>/dev/null || true
        wait "${pid}" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ot-harness MCP port ${port} is already in use; refusing to touch an existing server." >&2
    exit 1
fi

start_server() {
    local ot_cwd="$1"

    if [[ -n "${ot_cwd}" ]]; then
        OT_CWD="${ot_cwd}" uv run onetool serve \
            --config .onetool/onetool.yaml \
            --secrets .onetool/secrets.yaml \
            --transport http \
            --host "${host}" \
            --port "${port}" \
            --path "${path}" \
            > "tmp/ot-harness-owned-mcp-${port}.log" 2>&1 &
    else
        uv run onetool serve \
            --config .onetool/onetool.yaml \
            --secrets .onetool/secrets.yaml \
            --transport http \
            --host "${host}" \
            --port "${port}" \
            --path "${path}" \
            > "tmp/ot-harness-owned-mcp-${port}.log" 2>&1 &
    fi
    pid="$!"
}

wait_ready() {
    for _ in {1..60}; do
        if MCP_URL="${url}" uv run python - <<'PY' >/dev/null 2>&1
import asyncio
import os

from fastmcp import Client


async def main() -> None:
    async with Client(os.environ["MCP_URL"], timeout=10) as client:
        await client.call_tool("run", {"command": "ot.status()"})


asyncio.run(main())
PY
        then
            return 0
        fi
        if ! kill -0 "${pid}" 2>/dev/null; then
            echo "ot-harness-owned MCP server exited before becoming reachable." >&2
            cat "tmp/ot-harness-owned-mcp-${port}.log" >&2 || true
            exit 1
        fi
        sleep 1
    done

    echo "ot-harness-owned MCP server did not become reachable." >&2
    cat "tmp/ot-harness-owned-mcp-${port}.log" >&2 || true
    exit 1
}

print_ready() {
    MCP_URL="${url}" uv run python - <<'PY'
import asyncio
import os

from fastmcp import Client


async def main() -> None:
    async with Client(os.environ["MCP_URL"], timeout=10) as client:
        result = await client.call_tool("run", {"command": "ot.status()"})
        print(f"ot-harness-owned MCP ready at {os.environ['MCP_URL']}")
        print(result.content[0].text[:500])


asyncio.run(main())
PY
}

stop_server() {
    cleanup
    pid=""
}

run_trial() {
    local trial_json="$1"
    local needs_mcp
    local ot_cwd
    local config_path

    needs_mcp="$(jq -r '.variant_metadata.mcp != null' "${trial_json}")"
    ot_cwd="$(jq -r '.variant_metadata.workspace_mount.source // ""' "${trial_json}")"
    config_path="$(jq -r '.config_path' "${trial_json}")"

    if [[ "${needs_mcp}" == "true" ]]; then
        if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
            echo "ot-harness MCP port ${port} is already in use before ${trial_json}; refusing to touch an existing server." >&2
            exit 1
        fi
        start_server "${ot_cwd}"
        wait_ready
        print_ready
    fi

    harbor run --config "${config_path}"

    if [[ "${needs_mcp}" == "true" ]]; then
        stop_server
    fi
}

uv run ot-harness validate "${experiment}"

while IFS= read -r generated_dir; do
    if [[ -n "${generated_dir}" ]]; then
        rm -rf "${generated_dir}"
    fi
done < <(
    EXPERIMENT="${experiment}" uv run python - <<'PY'
import os
from pathlib import Path

from ot_harness.config import load_experiment

experiment = load_experiment(Path(os.environ["EXPERIMENT"]))
print(experiment.output_root / experiment.name)
if experiment.workspace_mount.root is not None:
    print(experiment.workspace_mount.root)
PY
)

uv run ot-harness run "${experiment}" --dry-run

while IFS= read -r trial_json; do
    run_trial "${trial_json}"
done < <(
    EXPERIMENT="${experiment}" uv run python - <<'PY'
import os
from pathlib import Path

from ot_harness.config import load_experiment
from ot_harness.harbor import build_trials

experiment = load_experiment(Path(os.environ["EXPERIMENT"]))
for trial in build_trials(experiment):
    print(trial.run_dir / "ot-harness-trial.json")
PY
)
