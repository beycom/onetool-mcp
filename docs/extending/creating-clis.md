# Creating CLIs

**Consistent. Beautiful. Five patterns.**

OneTool CLIs share utilities for configuration, output, and logging. Follow these patterns for a unified experience.

## CLI Naming

All CLIs follow the `ot-<purpose>` pattern:

| CLI | Purpose |
|-----|---------|
| `onetool` | Setup, configuration, upgrade |
| `ot-serve` | MCP server |
| `ot-bench` | Benchmark harness |

## Required Patterns

### 1. Use Shared CLI Utilities

```python
from ot._cli import console, create_cli, version_callback

app = create_cli(
    "ot-example",
    "Example CLI description.",
    no_args_is_help=True,
)
```

### 2. Load Environment Variables

```python
from onetool.paths import load_env

load_env()  # Must be before app creation

app = create_cli(...)
```

### 3. Version Flag

```python
@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version", "-v",
            callback=version_callback("ot-example", __version__),
            is_eager=True,
        ),
    ] = None,
) -> None:
    """CLI description."""
```

### 4. JSON Output

```python
@app.command()
def list_items(
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    if output_json:
        console.print(json.dumps({"items": items}))
    else:
        # Rich table output
```

### 5. Config Flag

```python
config: Path | None = typer.Option(
    None,
    "--config", "-c",
    help="Path to configuration file.",
    exists=True,
)
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |

## Package Structure

```
src/
├── ot/              # Shared library
│   ├── _cli.py      # CLI utilities
│   └── config/      # Configuration
├── ot_serve/        # ot-serve CLI
│   ├── __init__.py  # __version__ = "..."
│   └── cli.py       # Entry point
└── ot_example/      # Your CLI
```

### pyproject.toml Entry Points

```toml
[project.scripts]
ot-example = "ot_example.cli:cli"
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

table = Table(title="Items")
table.add_column("Name", style="bold")
table.add_column("Status")
table.add_row("item-1", "[green]active[/green]")
console.print(table)
```

## Common Patterns

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

### Dry Run

```python
dry_run: Annotated[
    bool,
    typer.Option("--dry-run", help="Preview changes"),
] = False
```

### Subcommand Groups

```python
config_app = typer.Typer(help="Configuration commands")
app.add_typer(config_app, name="config")

@config_app.command()
def show():
    """Show current configuration."""
```

## Multi-Command CLIs

For CLIs with multiple subcommands (like `ot-bench`):

### Structure

```text
src/ot_example/
├── __init__.py          # Package with __version__
├── cli.py               # Main entry point
├── commands/            # Subcommand implementations
│   ├── __init__.py
│   ├── run.py           # @app.command() for 'run'
│   └── report.py        # @app.command() for 'report'
└── core.py              # Shared business logic
```

### Main Entry Point

```python
# src/ot_example/cli.py
from __future__ import annotations

import typer
import ot
from ot._cli import create_cli, version_callback

app = create_cli(
    "ot-example",
    "Multi-command CLI description.",
    no_args_is_help=True,  # Show help when no command provided
)

@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version", "-v",
        callback=version_callback("ot-example", ot.__version__),
        is_eager=True,
    ),
) -> None:
    """CLI main help text."""
    pass

# Import subcommands to auto-register them
from ot_example.commands import run, report  # noqa: E402, F401

def cli() -> None:
    app()

if __name__ == "__main__":
    cli()
```

### Subcommand Module

```python
# src/ot_example/commands/run.py
from __future__ import annotations

import typer
from typing import Annotated

from ot_example.cli import app
from ot.logging import LogSpan

@app.command()
def run(
    target: Annotated[str, typer.Argument(help="Target to run")],
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Run the specified target."""
    with LogSpan(span="cli.run", target=target) as s:
        # Implementation
        s.add("result", "success")
```

## Interactive TUI CLIs

For interactive menu-driven CLIs (like `ot-browse`), use argparse with a controller class:

```python
# src/ot_example/app.py
from __future__ import annotations

import argparse
import asyncio

from ot._cli import console
from ot.logging import configure_logging
from ot._tui import ask_select

class AppController:
    """Interactive CLI controller."""

    def __init__(self, config) -> None:
        self.config = config

    async def run(self) -> None:
        """Main event loop."""
        try:
            while True:
                choice = await ask_select(
                    "Action:",
                    ["process", "view", "quit"],
                )
                if choice == "quit":
                    break
                await self._handle_action(choice)
        except KeyboardInterrupt:
            pass
        finally:
            console.print("[dim]Goodbye[/dim]")

    async def _handle_action(self, action: str) -> None:
        handlers = {
            "process": self._process,
            "view": self._view,
        }
        if handler := handlers.get(action):
            await handler()

    async def _process(self) -> None:
        console.print("Processing...")

    async def _view(self) -> None:
        console.print("Viewing...")

def main() -> None:
    configure_logging(log_name="example")

    parser = argparse.ArgumentParser(description="Interactive example CLI")
    parser.add_argument("--config", "-c", help="Config file path")
    args = parser.parse_args()

    controller = AppController(args.config)
    asyncio.run(controller.run())

if __name__ == "__main__":
    main()
```

## Logging

```python
from ot.logging import configure_logging, LogSpan

def cli() -> None:
    configure_logging(log_name="example")
    app()

@app.command()
def process(name: str) -> None:
    with LogSpan(span="cli.process", item=name) as s:
        # ... do work ...
        s.add("result", "success")
```

## Testing

```python
from typer.testing import CliRunner

runner = CliRunner()

def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0

def test_json_output():
    result = runner.invoke(app, ["list", "--json"])
    data = json.loads(result.stdout)
    assert "items" in data
```

## Checklist

- [ ] Use `create_cli()` from `ot._cli`
- [ ] Call `load_env()` at module level
- [ ] Add `--version` / `-v` flag
- [ ] Add `--config` / `-c` if configurable
- [ ] Add `--json` for data commands
- [ ] Add `--yes` / `-y` for destructive commands
- [ ] Use Rich console for output
- [ ] Use LogSpan for operations
- [ ] Add entry point to pyproject.toml
- [ ] Write tests using CliRunner
