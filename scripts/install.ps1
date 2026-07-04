# OneTool bootstrap installer (Windows / PowerShell).
#
# Wraps `uv` — it never replaces it. Installs uv if missing, installs OneTool as a
# uv tool, initialises config, and prints ready-to-paste MCP client config.
#
# Inspect before running:
#   irm https://onetool.beycom.online/install.ps1 -OutFile install.ps1
#   Get-FileHash install.ps1 -Algorithm SHA256   # compare against install.ps1.sha256
#   .\install.ps1
#
# Overrides: $env:ONETOOL_EXTRAS (default: all), $env:ONETOOL_CONFIG_DIR
#            (default: $env:USERPROFILE\.onetool).
$ErrorActionPreference = "Stop"

$extras = if ($env:ONETOOL_EXTRAS) { $env:ONETOOL_EXTRAS } else { "all" }
$configDir = if ($env:ONETOOL_CONFIG_DIR) { $env:ONETOOL_CONFIG_DIR } else { "$env:USERPROFILE\.onetool" }
$configFile = Join-Path $configDir "onetool.yaml"

Write-Host "OneTool installer - extras=[$extras], config dir=$configDir"

# 1. Ensure uv is available.
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "==> uv not found; installing uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2. Install OneTool as a uv tool.
Write-Host "==> Installing onetool-mcp[$extras]..."
uv tool install "onetool-mcp[$extras]"

# 3. Initialise config (non-interactive).
Write-Host "==> Initialising config at $configDir..."
onetool init --config "$configDir"

# 4. Print ready-to-paste MCP client config with resolved paths.
Write-Host "==> MCP client configuration:"
onetool init mcp-config --config "$configFile"

# 5. Closing guidance.
Write-Host ""
Write-Host "Done. Next:"
Write-Host "  - Verify:   onetool init validate --config $configFile"
Write-Host "  - For extensions / encrypted secrets, re-run interactively in a terminal:"
Write-Host "      onetool init --config $configDir"
