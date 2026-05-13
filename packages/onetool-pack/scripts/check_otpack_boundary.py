"""AST scanner to enforce the otpack import boundary.

Rules:
- Only otpack/config.py and otpack/logging.py may import from ot.*
- In those two files, ot.* imports must be inside try/except blocks
- All other otpack modules must have zero ot.* imports

Usage:
    python scripts/check_otpack_boundary.py
    # Exits 0 on pass, 1 on violations
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


FORBIDDEN_ROOTS = ("ot", "ottools", "otutil", "otdev")


def get_ot_imports(tree: ast.Module) -> list[tuple[int, str]]:
    """Find all top-level ot.* imports in an AST.

    Returns list of (line_number, import_string) for bare ot.* imports
    (not wrapped in try/except).

    Args:
        tree: Parsed AST module

    Returns:
        List of (lineno, import_repr) for violations
    """
    violations: list[tuple[int, str]] = []

    # Walk top-level statements only (not inside try/except)
    for node in tree.body:
        _check_node_for_bare_ot_imports(node, violations)

    return violations


def _is_ot_import(node: ast.stmt) -> tuple[bool, str]:
    """Check if a statement imports OneTool runtime packages.

    Returns (is_ot_import, repr_string).
    """
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name in FORBIDDEN_ROOTS or alias.name.startswith(
                tuple(f"{root}." for root in FORBIDDEN_ROOTS)
            ):
                return True, f"import {alias.name}"
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module in FORBIDDEN_ROOTS or module.startswith(
            tuple(f"{root}." for root in FORBIDDEN_ROOTS)
        ):
            names = ", ".join(a.name for a in node.names)
            return True, f"from {module} import {names}"
    return False, ""


def _check_node_for_bare_ot_imports(
    node: ast.stmt, violations: list[tuple[int, str]]
) -> None:
    """Check a single statement (not inside try) for ot.* imports."""
    if isinstance(node, ast.Try):
        # Imports inside try/except are allowed (the shim pattern)
        return

    is_ot, repr_str = _is_ot_import(node)
    if is_ot:
        violations.append((node.lineno, repr_str))
        return

    # Recurse into function/class bodies to catch nested bare imports
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for child in node.body:
            _check_node_for_bare_ot_imports(child, violations)
    elif isinstance(node, ast.ClassDef):
        for child in node.body:
            _check_node_for_bare_ot_imports(child, violations)
    elif isinstance(node, (ast.If, ast.With, ast.AsyncWith)):
        for child in ast.walk(node):
            if child is node:
                continue
            if isinstance(child, ast.stmt):
                is_ot, repr_str = _is_ot_import(child)
                if is_ot:
                    violations.append((child.lineno, repr_str))


def check_file(path: Path, *, allow_ot_imports: bool) -> list[str]:
    """Check a single file for boundary violations.

    Args:
        path: Path to Python file
        allow_ot_imports: If True, ot.* imports are allowed (but only inside try/except)

    Returns:
        List of error strings (empty = no violations)
    """
    source = path.read_text()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        return [f"{path}: SyntaxError: {e}"]

    errors: list[str] = []

    if allow_ot_imports:
        # These files may have ot.* imports, but only inside try/except
        # The get_ot_imports function already handles this
        for line_no, repr_str in get_ot_imports(tree):
            errors.append(f"{path}:{line_no}: forbidden bare ot.* import: {repr_str}")
    else:
        # No ot.* imports allowed at all
        for node in ast.walk(tree):
            is_ot, repr_str = _is_ot_import(node)  # type: ignore[arg-type]
            if is_ot:
                errors.append(
                    f"{path}:{node.lineno}: forbidden ot.* import: {repr_str}"
                )

    return errors


def main() -> int:
    """Run the boundary check.

    Returns:
        0 on success, 1 on violations
    """
    # Locate the otpack source directory
    script_dir = Path(__file__).parent
    src_dir = script_dir.parent / "src" / "otpack"

    if not src_dir.exists():
        print(f"ERROR: otpack src directory not found: {src_dir}", file=sys.stderr)
        return 1

    # Files allowed to have ot.* imports (inside try/except only)
    allowed_files = {"config.py", "logging.py"}

    all_errors: list[str] = []
    py_files = sorted(src_dir.glob("*.py"))

    for py_file in py_files:
        allow = py_file.name in allowed_files
        errors = check_file(py_file, allow_ot_imports=allow)
        all_errors.extend(errors)

    if all_errors:
        print("otpack boundary violations:", file=sys.stderr)
        for error in all_errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    print(f"✓ otpack boundary OK ({len(py_files)} files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
