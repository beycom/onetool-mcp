# CLI Patterns

Reusable CLI patterns for Python projects using Typer and Rich.

## CLI Overview

| CLI | Package | Purpose |
|-----|---------|---------|
| `onetool` | `src/onetool/` | MCP server, setup, configuration |

Treat the table above as the project profile. The patterns below should be reusable across Python CLIs by swapping in the local command name, package path, and shared utility module.

## Shared Utilities

Use shared CLI utilities for common console setup, app creation, and version handling. In this repository those utilities live in `ot._cli`:

```python
from ot._cli import console, create_cli, version_callback
```

| Utility | Purpose |
|---------|---------|
| `create_cli()` | Create Typer app with standard settings |
| `console` | Rich console for formatted output |
| `version_callback()` | Standard `--version` flag handler |

## Required Patterns

### 1. Create CLI with Shared Utilities

```python
from ot._cli import create_cli, version_callback

app = create_cli(
    "onetool",
    "OneTool MCP server.",
    no_args_is_help=False,  # onetool runs server by default
)
```

### 2. Version Flag

```python
@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version", "-v",
        callback=version_callback("onetool", __version__),
        is_eager=True,
    ),
) -> None:
    """OneTool MCP server."""
    pass
```

### 3. Logging Setup

```python
from ot.logging import configure_logging

def cli() -> None:
    configure_logging(log_name="onetool")
    app()
```

## Output Formatting

### Rich Console

```python
from ot._cli import console

console.print("[green]✓[/green] Success")
console.print("[red]Error:[/red] Failed")
console.print("[yellow]Warning:[/yellow] Check this")
```

### Progress Indicators

| Symbol | Meaning |
|--------|---------|
| ✓ | Success/complete |
| ✗ | Failure/error |
| ● | Active/in-progress |
| ○ | Pending/inactive |

### Tables

```python
from rich.table import Table

table = Table(title="Tools")
table.add_column("Pack", style="bold")
table.add_column("Functions")
table.add_row("brave", "search, news")
console.print(table)
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |

## Common Flag Patterns

### Documentation Examples

Use **long flags** by default in documentation examples (`--config`, `--format`, `--port`).
Short flags (`-c`, `-f`, `-p`) are only used when an example is specifically demonstrating the
short form — for instance, in a "Flags" reference table that lists both forms side-by-side.

```bash
# CORRECT — long flags in examples
onetool direct run --port 8765 "ot.packs()" --format json

# WRONG — short flags in examples
onetool direct run -p 8765 "ot.packs()" -f json
```

The one permitted exception: a flags reference table that lists both forms:

| Flag | Short | Description |
|------|-------|-------------|
| `--config PATH` | `-c` | Path to `onetool.yaml` |

### Config Flag

```python
config: Path | None = typer.Option(
    None,
    "--config", "-c",
    help="Path to configuration file.",
    exists=True,
)
```

### JSON Output

```python
output_json: Annotated[
    bool,
    typer.Option("--json", help="Output as JSON"),
] = False

if output_json:
    console.print(json.dumps({"items": items}))
```

### Confirmation Prompts

```python
yes: Annotated[
    bool,
    typer.Option("--yes", "-y", help="Skip confirmation"),
] = False

if not yes:
    if not typer.confirm(f"Delete '{name}'?"):
        raise typer.Exit(0)
```

## Testing CLIs

```python
from typer.testing import CliRunner

runner = CliRunner()

def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0

def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "OneTool" in result.stdout
```

## pyproject.toml Entry Points

```toml
[project.scripts]
onetool = "onetool.cli:cli"
```
