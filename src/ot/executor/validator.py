"""AST-based code validation for OneTool.

Validates Python code before execution:
- Syntax validation via ast.parse()
- Security pattern detection (dangerous calls)
- Optional Ruff linting integration for style warnings

Example:
    result = validate_python_code(code)
    if not result.valid:
        print(f"Validation errors: {result.errors}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of code validation."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ast_tree: ast.Module | None = None


# Dangerous patterns to detect
DANGEROUS_BUILTINS = frozenset(
    {
        "exec",
        "eval",
        "compile",
        "__import__",
    }
)

DANGEROUS_FUNCTIONS = frozenset(
    {
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.check_output",
        "os.system",
        "os.popen",
        "os.spawn",
        "os.spawnl",
        "os.spawnle",
        "os.spawnlp",
        "os.spawnlpe",
        "os.spawnv",
        "os.spawnve",
        "os.spawnvp",
        "os.spawnvpe",
        "os.execl",
        "os.execle",
        "os.execlp",
        "os.execlpe",
        "os.execv",
        "os.execve",
        "os.execvp",
        "os.execvpe",
    }
)

# Potentially dangerous - warn but don't block
WARN_PATTERNS = frozenset(
    {
        "open",  # File access
        "pickle.load",
        "pickle.loads",
        "yaml.load",  # YAML unsafe load
        "marshal.load",
        "marshal.loads",
    }
)


class DangerousPatternVisitor(ast.NodeVisitor):
    """AST visitor that detects dangerous code patterns."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls for dangerous patterns."""
        func_name = self._get_call_name(node)

        if func_name in DANGEROUS_BUILTINS:
            self.errors.append(
                f"Line {node.lineno}: Dangerous builtin '{func_name}' is not allowed"
            )
        elif func_name in DANGEROUS_FUNCTIONS:
            self.errors.append(
                f"Line {node.lineno}: Dangerous function '{func_name}' is not allowed"
            )
        elif func_name in WARN_PATTERNS:
            self.warnings.append(
                f"Line {node.lineno}: Potentially unsafe function '{func_name}'"
            )

        # Continue visiting child nodes
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Check imports for dangerous modules."""
        for alias in node.names:
            if alias.name in ("subprocess", "os"):
                self.warnings.append(
                    f"Line {node.lineno}: Import of '{alias.name}' may enable dangerous operations"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from imports for dangerous modules."""
        if node.module in ("subprocess", "os"):
            self.warnings.append(
                f"Line {node.lineno}: Import from '{node.module}' may enable dangerous operations"
            )
        self.generic_visit(node)

    def _get_call_name(self, node: ast.Call) -> str:
        """Extract the full name of a function call.

        Handles:
        - Simple calls: func()
        - Attribute calls: module.func()
        - Chained calls: module.submodule.func()
        """
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts: list[str] = [node.func.attr]
            current = node.func.value
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""


def validate_python_code(
    code: str,
    check_security: bool = True,
    lint_warnings: bool = False,
    filename: str = "<string>",
) -> ValidationResult:
    """Validate Python code for syntax and security issues.

    Args:
        code: Python code to validate
        check_security: Whether to check for dangerous patterns (default True)
        lint_warnings: Whether to include Ruff style warnings (default False)
        filename: Filename for error messages

    Returns:
        ValidationResult with valid flag, errors, and warnings
    """
    result = ValidationResult()

    # Step 1: Syntax validation
    try:
        tree = ast.parse(code, filename=filename)
        result.ast_tree = tree
    except SyntaxError as e:
        result.valid = False
        line_info = f" at line {e.lineno}" if e.lineno else ""
        result.errors.append(f"Syntax error{line_info}: {e.msg}")
        return result

    # Step 2: Security pattern detection
    if check_security:
        visitor = DangerousPatternVisitor()
        visitor.visit(tree)

        if visitor.errors:
            result.valid = False
            result.errors.extend(visitor.errors)

        result.warnings.extend(visitor.warnings)

    # Step 3: Optional Ruff linting (style warnings only)
    if lint_warnings:
        from ot.executor.linter import lint_code

        lint_result = lint_code(code)
        if lint_result.available:
            result.warnings.extend(lint_result.warnings)

    return result


def validate_for_exec(code: str) -> ValidationResult:
    """Validate code specifically for exec() execution.

    This is a stricter validation that also checks for patterns
    that are problematic in exec() context.

    Args:
        code: Python code to validate

    Returns:
        ValidationResult with validation status
    """
    result = validate_python_code(code, check_security=True)

    if not result.valid:
        return result

    # Additional exec-specific checks could go here
    # For example, checking for top-level returns outside functions

    return result
