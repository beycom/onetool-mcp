# Python style

Target Python 3.12 or newer. `pyproject.toml` is authoritative: Ruff uses a 100-character line length and rules E, F, I, UP, B and ASYNC; mypy runs in strict mode. Run `just lint` and `just typecheck` rather than maintaining alternate flags.

Use type annotations for production functions. Keep `Any` at upstream/JSON boundaries and narrow values before using them. Prefer ordinary functions and small concrete classes. Module-level constants/types are fine; module-level runtime objects, connections and mutable stores are not.

Use `from __future__ import annotations` when deferred annotations help, especially cross-module ownership. Keep import cycles under TYPE_CHECKING. Explain a narrow type-ignore when an upstream public method lacks annotations; do not silence a whole module.

Write a short docstring describing behavior or ownership. Add Args/Returns/Raises only when they explain a non-obvious contract. Comments should explain a boundary or decision, not repeat the statement below them. Use familiar terminology consistently and preserve exact public identifiers.

Prefer standard-library argparse and logging. Delete unused APIs, names and code instead of adding compatibility branches. Keep asynchronous work asynchronous; do not introduce a second sync facade, thread bridge or service locator.
