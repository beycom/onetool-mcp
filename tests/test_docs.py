"""Executable documentation examples and local links."""

import json
import os
import re
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from test_gateway import connected, execute, stdio

from onetool.config import load_config

ROOT = Path(__file__).parent.parent


def documents() -> list[Path]:
    paths = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "dev-guides").rglob("*.md")),
    ]
    skill = ROOT / "planning/skills/ot-ref/SKILL.md"
    if skill.is_file():
        paths.append(skill)
    return paths


async def test_python_and_native_request_examples(tmp_path: Path) -> None:
    count = 0
    async with connected(tmp_path, {"servers": {"alpha": stdio(), "beta": stdio()}}) as (
        client,
        _,
        _,
    ):
        for path in documents():
            for language, code in re.findall(r"```(python|json)\n(.*?)```", path.read_text(), re.S):
                if language == "python":
                    result = await execute(client, code)
                else:
                    request = json.loads(code)
                    result = await client.call_tool(request["tool"], request["arguments"])
                assert not result.is_error, (path, result)
                count += 1
    assert count >= 5  # Packaged source excludes the private skill's extra example.


def test_yaml_examples_and_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIXTURE_TOKEN", "owned-doc-secret")
    for path in documents():
        text = path.read_text()
        for number, yaml in enumerate(re.findall(r"```yaml\n(.*?)```", text, re.S)):
            candidate = tmp_path / f"{path.stem}-{number}.yaml"
            candidate.write_text(yaml)
            load_config(candidate)
        base = ROOT if "planning" in path.parts else path.parent
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if target.startswith(("https://", "http://", "#")):
                continue
            relative, _, anchor = target.partition("#")
            destination = base / relative
            private = Path(os.path.abspath(destination)).is_relative_to(ROOT / "planning")
            if private and not (ROOT / "planning").exists():
                continue
            assert destination.is_file(), (path, target)
            if anchor:
                headings = re.findall(r"^#+ (.+)$", destination.read_text(), re.M)
                anchors = {
                    re.sub(r"[^a-z0-9 -]", "", item.lower()).replace(" ", "-") for item in headings
                }
                assert anchor in anchors, (path, target)


async def test_documented_fixture_config_runs() -> None:
    config = ROOT / "examples/fixtures.yaml"
    env = {"PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]}
    transport = StdioTransport(
        sys.executable, ["-m", "onetool", "serve", "--config", str(config)], env=env
    )
    try:
        async with Client(transport) as client:
            assert (
                await execute(client, 'return await call_tool("alpha_add", {"a":2,"b":3})')
            ).data == {"value": 5}
    finally:
        await transport.close()
