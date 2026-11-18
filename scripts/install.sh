#!/bin/sh
# Install uv and OneTool with a uv-managed Python. Optional argument: local wheel.
set -eu
artifact=${1:-onetool-mcp>=4.0.0rc1,<5}
installer=$(mktemp)
trap 'rm -f "$installer"' EXIT HUP INT TERM
curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh -o "$installer"
UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh "$installer"
"$HOME/.local/bin/uv" tool install --managed-python --python 3.12 -- "$artifact"
printf 'Installed OneTool. Add %s/.local/bin to PATH.\n' "$HOME"
