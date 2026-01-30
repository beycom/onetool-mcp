"""AST-based code validation for OneTool.

Validates Python code before execution:
- Syntax validation via ast.parse()
- Security pattern detection (dangerous calls)
- Optional Ruff linting integration for style warnings

Security patterns are configurable via onetool.yaml and support wildcards:

    security:
      validate_code: true
      enabled: true
      blocked: [exec, eval, compile, __import__, subprocess.*, os.system]
      warned: [subprocess, os, open, pickle.*, yaml.load]

Pattern matching logic (automatic based on pattern structure):
- Patterns WITHOUT dots (e.g., 'exec', 'subprocess') match:
  * Builtin function calls: exec(), eval()
  * Import statements: import subprocess, from os import system
- Patterns WITH dots (e.g., 'subprocess.*', 'os.system') match:
  * Qualified function calls: subprocess.run(), os.system()

Wildcard patterns use fnmatch syntax:
- '*' matches any characters (e.g., 'subprocess.*' matches 'subprocess.run')
- '?' matches a single character
- '[seq]' matches any character in seq

Example:
    result = validate_python_code(code)
    if not result.valid:
        print(f"Validation errors: {result.errors}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")
"""

from __future__ import annotations

import ast
import fnmatch
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ot.config.loader import SecurityConfig


@dataclass
class ValidationResult:
    """Result of code validation."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ast_tree: ast.Module | None = None


# =============================================================================
# Default Security Patterns
# =============================================================================
# These are used when config is not available. Patterns use fnmatch wildcards.
#
# Pattern matching is determined by structure:
# - No dot in pattern → matches builtins (calls) AND imports
# - Dot in pattern → matches qualified function calls only
#
# This two-category design (blocked/warned) replaces the previous four-category
# design (blocked_builtins, blocked_functions, warned_functions, warned_imports).
# The validator automatically determines the match type based on pattern structure.
# =============================================================================

DEFAULT_BLOCKED = frozenset(
    {
        # Builtins - arbitrary code execution risk (no dots = match calls + imports)
        "exec",
        "eval",
        "compile",
        "__import__",
        # Qualified functions - command injection (dots = match calls only)
        "subprocess.*",  # All subprocess functions
        "os.system",  # Shell command execution
        "os.popen",  # Shell command execution
        "os.spawn*",  # spawnl, spawnle, spawnv, etc.
        "os.exec*",  # execl, execle, execv, etc.
    }
)

DEFAULT_WARNED = frozenset(
    {
        # Module imports - enables dangerous operations (no dots = match imports)
        "subprocess",
        "os",
        # Qualified functions - file access, deserialization (dots = match calls)
        "open",  # File access (common but risky)
        "pickle.*",  # Deserialization attacks
        "yaml.load",  # Unsafe YAML deserialization
        "marshal.*",  # Object deserialization
    }
)


def _matches_pattern(name: str, patterns: frozenset[str]) -> str | None:
    """Check if a name matches any pattern in the set.

    Supports both exact matches and fnmatch wildcards.

    Args:
        name: The function/module name to check
        patterns: Set of patterns (may contain wildcards)

    Returns:
        The matching pattern if found, None otherwise
    """
    # Fast path: exact match
    if name in patterns:
        return name

    # Check wildcard patterns
    for pattern in patterns:
        if ("*" in pattern or "?" in pattern or "[" in pattern) and fnmatch.fnmatch(
            name, pattern
        ):
            return pattern

    return None


def _has_dot(pattern: str) -> bool:
    """Check if a pattern contains a dot (qualified name).

    Used to determine matching strategy:
    - No dot: match builtins and imports
    - Has dot: match qualified function calls
    """
    return "." in pattern


def _get_security_config() -> SecurityConfig | None:
    """Get security configuration from global config.

    Returns:
        SecurityConfig if available, None otherwise.
    """
    try:
        from ot.config.loader import get_config

        config = get_config()
        return config.security
    except Exception:
        # Config not loaded yet or error - use defaults
        return None


class DangerousPatternVisitor(ast.NodeVisitor):
    """AST visitor that detects dangerous code patterns.

    Patterns are configurable via onetool.yaml security section.
    Supports fnmatch wildcards (*, ?, [seq]).

    Pattern matching is automatic based on structure:
    - Patterns without dots match builtins and imports
    - Patterns with dots match qualified function calls

    Two-tier priority: allow > warned > blocked
    """

    def __init__(
        self,
        blocked: frozenset[str] | None = None,
        warned: frozenset[str] | None = None,
    ) -> None:
        """Initialize visitor with security patterns.

        Args:
            blocked: Patterns that block execution (cause errors)
            warned: Patterns that generate warnings (allow execution)
        """
        self.errors: list[str] = []
        self.warnings: list[str] = []

        # Use provided patterns or defaults
        blocked_all = blocked or DEFAULT_BLOCKED
        warned_all = warned or DEFAULT_WARNED

        # Split patterns by type for efficient matching
        # Patterns without dots → match builtins and imports
        # Patterns with dots → match qualified calls
        self.blocked_simple = frozenset(p for p in blocked_all if not _has_dot(p))
        self.blocked_qualified = frozenset(p for p in blocked_all if _has_dot(p))
        self.warned_simple = frozenset(p for p in warned_all if not _has_dot(p))
        self.warned_qualified = frozenset(p for p in warned_all if _has_dot(p))

    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls for dangerous patterns.

        Priority order: blocked > warned (allow handled at setup)
        """
        func_name = self._get_call_name(node)

        if not func_name:
            self.generic_visit(node)
            return

        # Determine which pattern sets to check based on call type
        is_qualified = "." in func_name

        if is_qualified:
            # Qualified call (e.g., subprocess.run) - check qualified patterns
            # Priority: blocked > warned
            if pattern := _matches_pattern(func_name, self.blocked_qualified):
                self.errors.append(
                    f"Line {node.lineno}: Dangerous function '{func_name}' is not "
                    f"allowed (matches '{pattern}')"
                )
            elif pattern := _matches_pattern(func_name, self.warned_qualified):
                self.warnings.append(
                    f"Line {node.lineno}: Potentially unsafe function '{func_name}' "
                    f"(matches '{pattern}')"
                )
        else:
            # Simple call (e.g., exec) - check simple patterns (builtins)
            # Priority: blocked > warned
            if pattern := _matches_pattern(func_name, self.blocked_simple):
                self.errors.append(
                    f"Line {node.lineno}: Dangerous builtin '{func_name}' is not "
                    f"allowed (matches '{pattern}')"
                )
            elif pattern := _matches_pattern(func_name, self.warned_simple):
                self.warnings.append(
                    f"Line {node.lineno}: Potentially unsafe function '{func_name}' "
                    f"(matches '{pattern}')"
                )

        # Continue visiting child nodes
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Check imports for dangerous modules."""
        for alias in node.names:
            # Check simple patterns (no dots) against import names
            if pattern := _matches_pattern(alias.name, self.blocked_simple):
                self.errors.append(
                    f"Line {node.lineno}: Import of '{alias.name}' is not allowed "
                    f"(matches '{pattern}')"
                )
            elif pattern := _matches_pattern(alias.name, self.warned_simple):
                self.warnings.append(
                    f"Line {node.lineno}: Import of '{alias.name}' may enable "
                    f"dangerous operations (matches '{pattern}')"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from imports for dangerous modules."""
        if node.module:
            # Check simple patterns against the module name
            if pattern := _matches_pattern(node.module, self.blocked_simple):
                self.errors.append(
                    f"Line {node.lineno}: Import from '{node.module}' is not allowed "
                    f"(matches '{pattern}')"
                )
            elif pattern := _matches_pattern(node.module, self.warned_simple):
                self.warnings.append(
                    f"Line {node.lineno}: Import from '{node.module}' may enable "
                    f"dangerous operations (matches '{pattern}')"
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

    Security patterns are loaded from onetool.yaml configuration.
    If config is not available, built-in defaults are used.
    Patterns support fnmatch wildcards (*, ?, [seq]).

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
        # Load patterns from config or use defaults
        security_config = _get_security_config()

        if security_config is not None and security_config.enabled:
            # Merge config patterns with defaults (additive behavior)
            # This prevents accidental removal of critical security patterns
            allow_set = frozenset(security_config.allow)
            warned_set = frozenset(security_config.warned)

            # Pattern priority (highest to lowest):
            # 1. allow - completely exempt, no action
            # 2. warned (user) - downgrades blocked defaults to warnings
            # 3. blocked - prevents execution
            # 4. warned (default) - generates warnings
            #
            # This lets users:
            # - Add to blocked/warned (extends defaults)
            # - Downgrade blocked→warned (e.g., warned: [os.popen])
            # - Exempt entirely (e.g., allow: [open])
            blocked = (DEFAULT_BLOCKED | set(security_config.blocked)) - allow_set - warned_set
            warned = (DEFAULT_WARNED | set(security_config.warned)) - allow_set

            visitor = DangerousPatternVisitor(
                blocked=frozenset(blocked),
                warned=frozenset(warned),
            )
        elif security_config is not None and not security_config.enabled:
            # Security disabled in config - skip validation
            visitor = None
        else:
            # No config - use defaults
            visitor = DangerousPatternVisitor()

        if visitor is not None:
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
