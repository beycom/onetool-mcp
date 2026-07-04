#!/bin/sh
# OneTool bootstrap installer (macOS/Linux).
#
# Wraps `uv` — it never replaces it. Installs uv if missing, installs OneTool as a
# uv tool, initialises config, and prints ready-to-paste MCP client config.
#
# Inspect before running:
#   curl -LsSf https://onetool.beycom.online/install.sh -o install.sh
#   shasum -a 256 -c install.sh.sha256
#   sh install.sh
#
# Overrides: ONETOOL_EXTRAS (default: all), ONETOOL_CONFIG_DIR (default: ~/.onetool).
set -eu

EXTRAS="${ONETOOL_EXTRAS:-all}"
CONFIG_DIR="${ONETOOL_CONFIG_DIR:-$HOME/.onetool}"
CONFIG_FILE="$CONFIG_DIR/onetool.yaml"

echo "OneTool installer — extras=[$EXTRAS], config dir=$CONFIG_DIR"

# 1. Ensure uv is available (install it if missing, then load its env hook).
if ! command -v uv >/dev/null 2>&1; then
    echo "==> uv not found; installing uv…"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Make uv usable in the rest of this script without a new shell.
    if [ -f "$HOME/.local/bin/env" ]; then
        # shellcheck disable=SC1091
        . "$HOME/.local/bin/env"
    fi
    export PATH="$HOME/.local/bin:$PATH"
fi

# 2. Install OneTool as a uv tool.
echo "==> Installing onetool-mcp[$EXTRAS]…"
uv tool install "onetool-mcp[$EXTRAS]"

# 3. Initialise config (non-interactive; re-run in a terminal for extensions/secrets).
echo "==> Initialising config at $CONFIG_DIR…"
onetool init --config "$CONFIG_DIR"

# 4. Print ready-to-paste MCP client config with resolved paths.
echo "==> MCP client configuration:"
onetool init mcp-config --config "$CONFIG_FILE"

# 5. Closing guidance.
cat <<EOF

Done. Next:
  - Verify:   onetool init validate --config $CONFIG_FILE
  - For extensions / encrypted secrets, re-run interactively in a terminal:
      onetool init --config $CONFIG_DIR
EOF
