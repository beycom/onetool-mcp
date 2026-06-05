"""AST-based code validation for OneTool.

Validates Python code before execution:
- Syntax validation via ast.parse()
- Allowlist-based security validation (dangerous calls, imports, builtins)
- Optional Ruff linting integration for style warnings

Security Model:
    Block everything by default, explicitly allow what's safe.
    Configuration via security.yaml with three categories:
    - builtins: Allowed builtin functions and types
    - imports: Allowed modules for import statements
    - calls: Blocked/warned qualified function calls

    Tool namespaces (ot.*, brave.*, etc.) are auto-allowed.

Configuration:
    security:
      builtins:
        allow: [str, int, list, print, ...]
      imports:
        allow: [json, re, math, ...]
        warn: [yaml]
      calls:
        block: [pickle.*, yaml.load]
        warn: [random.seed]

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
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ot.config.models import SecurityConfig


@dataclass
class ValidationResult:
    """Result of code validation."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ast_tree: ast.Module | None = None


# =============================================================================
# Fallback Defaults (used when config is unavailable)
# =============================================================================
# These are minimal safe defaults used only when security.yaml cannot be loaded.
# In normal operation, the full allowlists come from security.yaml.

FALLBACK_ALLOWED_BUILTINS = frozenset({
    # Type constructors
    "str", "int", "float", "bool", "bytes", "list", "dict", "set", "tuple",
    # Type checking
    "isinstance", "issubclass", "type", "callable",
    # Iteration
    "len", "iter", "next", "range", "enumerate", "zip", "reversed", "sorted",
    # Math
    "min", "max", "sum", "abs", "round", "pow",
    # Sequence operations
    "all", "any", "filter", "map",
    # String/repr
    "repr", "format", "print",
    # Exceptions
    "Exception", "ValueError", "TypeError", "KeyError",
})

FALLBACK_ALLOWED_IMPORTS = frozenset({
    "json", "re", "math", "datetime", "collections", "typing",
    "itertools", "functools", "copy", "dataclasses",
})

FALLBACK_WARNED_IMPORTS = frozenset({
    "yaml",
})

FALLBACK_ALLOWED_DUNDERS = frozenset({
    "__format__", "__sanitize__", "__compact__", "__force_context__", "__display__",
})

# Cache stdlib module names for performance (checked per qualified call)
# Python 3.10+ has sys.stdlib_module_names; older versions get empty set
try:
    STDLIB_MODULE_NAMES: frozenset[str] = frozenset(sys.stdlib_module_names)
except AttributeError:
    STDLIB_MODULE_NAMES = frozenset()


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


@lru_cache(maxsize=1)
def _get_security_config() -> SecurityConfig | None:
    """Get security configuration from global config.

    Results are cached for performance. Cache is cleared on ot.reload().

    Returns:
        SecurityConfig if available, None otherwise.
    """
    try:
        from ot.config.loader import get_config

        config = get_config()
        return config.security
    except Exception:
        # Config not loaded yet or error - use fallback defaults
        return None


@lru_cache(maxsize=1)
def _get_tool_namespaces() -> frozenset[str]:
    """Get all tool pack namespaces for auto-allow.

    Tool namespaces (ot.*, brave.*, file.*, etc.) are auto-allowed
    since they're the whole point of OneTool.

    Results are cached for performance (registry doesn't change during session).

    Returns:
        Frozenset of namespace patterns like "ot.*", "brave.*"
    """
    try:
        from ot.executor.tool_loader import load_tool_registry
        from ot.proxy import get_proxy_manager

        registry = load_tool_registry()
        proxy = get_proxy_manager()

        # Collect all pack names
        namespaces = set(registry.packs.keys())
        namespaces.update(proxy.servers)

        # Convert to wildcard patterns
        return frozenset(f"{ns}.*" for ns in namespaces)
    except Exception:
        # Registry not loaded - return minimal set
        return frozenset({"ot.*"})


class AllowlistValidator(ast.NodeVisitor):
    """AST visitor that validates code against allowlists.

    Security model: Block everything by default, allow what's explicitly listed.
    Tool namespaces are auto-allowed.

    Categories:
    - builtins: Allowed builtin function calls
    - imports: Allowed module imports
    - calls: Blocked/warned qualified function calls

    Tracks import aliases and from-imports to prevent bypass attacks:
    - `import subprocess as sp; sp.run()` - alias tracked
    - `from subprocess import run; run()` - function tracked
    """

    def __init__(
        self,
        allowed_builtins: frozenset[str],
        allowed_imports: frozenset[str],
        warned_imports: frozenset[str],
        blocked_calls: frozenset[str],
        warned_calls: frozenset[str],
        allowed_calls: frozenset[str],
        tool_namespaces: frozenset[str],
        allowed_dunders: frozenset[str],
    ) -> None:
        """Initialize validator with allowlists.

        Args:
            allowed_builtins: Allowed builtin functions and types
            allowed_imports: Allowed module imports
            warned_imports: Imports that trigger warnings but are allowed
            blocked_calls: Blocked qualified function calls
            warned_calls: Qualified calls that trigger warnings
            allowed_calls: Explicitly allowed qualified calls
            tool_namespaces: Auto-allowed tool namespace patterns (e.g., "ot.*")
            allowed_dunders: Allowed magic variables (e.g., "__format__")
        """
        self.errors: list[str] = []
        self.warnings: list[str] = []

        self.allowed_builtins = allowed_builtins
        self.allowed_imports = allowed_imports
        self.warned_imports = warned_imports
        self.blocked_calls = blocked_calls
        self.warned_calls = warned_calls
        self.allowed_calls = allowed_calls
        self.tool_namespaces = tool_namespaces
        self.allowed_dunders = allowed_dunders

        # Track import aliases: alias_name -> original_module
        # e.g., "import subprocess as sp" -> {"sp": "subprocess"}
        self._import_aliases: dict[str, str] = {}

        # Track from-imports from blocked modules: function_name -> original_module
        # e.g., "from subprocess import run" -> {"run": "subprocess"}
        self._from_imports: dict[str, str] = {}

    def _is_tool_namespace(self, name: str) -> bool:
        """Check if a qualified name is in an auto-allowed tool namespace."""
        return _matches_pattern(name, self.tool_namespaces) is not None

    def _is_allowed_dunder(self, name: str) -> bool:
        """Check if a name is an allowed magic variable."""
        return name in self.allowed_dunders

    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls against allowlists."""
        # First check for __builtins__ bypass via getattr/hasattr
        if self._is_builtins_bypass_call(node):
            self.errors.append(
                f"Line {node.lineno}: Access to '__builtins__' via getattr/hasattr is not allowed "
                f"(potential security bypass)"
            )
            self.generic_visit(node)
            return

        func_name = self._get_call_name(node)

        if not func_name:
            self.generic_visit(node)
            return

        is_qualified = "." in func_name

        if is_qualified:
            # Qualified call (e.g., json.loads, subprocess.run)
            self._check_qualified_call(func_name, node.lineno)
        else:
            # Simple call (builtin like print, len, etc.)
            self._check_builtin_call(func_name, node.lineno)

        self.generic_visit(node)

    def _is_builtins_bypass_call(self, node: ast.Call) -> bool:
        """Check if this is an attempt to bypass via getattr(__builtins__, ...).

        Detects patterns like:
        - getattr(__builtins__, 'exec')
        - hasattr(__builtins__, 'exec')
        """
        func_name = self._get_call_name(node)
        if func_name not in ("getattr", "hasattr"):
            return False

        # Check if first argument is __builtins__
        return (
            bool(node.args)
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "__builtins__"
        )

    def _check_builtin_call(self, func_name: str, lineno: int) -> None:
        """Check if a builtin call is allowed.

        Also checks for from-import bypass:
        `from subprocess import run; run()` - run is tracked as from subprocess

        Only checks known dangerous builtins. User-defined functions
        (like functions defined in the same code) are allowed.
        """
        # Check for from-import bypass first
        # e.g., "from subprocess import run; run()" -> func_name is "run"
        if func_name in self._from_imports:
            source_module = self._from_imports[func_name]
            # Check if the source module is allowed
            if _matches_pattern(source_module, self.allowed_imports) is None:
                self.errors.append(
                    f"Line {lineno}: Call to '{func_name}' is not allowed "
                    f"(imported from blocked module '{source_module}'). "
                    f"Use ot.security(check='{source_module}') to check security rules."
                )
                return
            # Module is allowed, check if specific call is blocked
            qualified_name = f"{source_module}.{func_name}"
            if pattern := _matches_pattern(qualified_name, self.blocked_calls):
                self.errors.append(
                    f"Line {lineno}: Call to '{func_name}' is blocked "
                    f"(matches '{pattern}' via 'from {source_module} import'). "
                    f"Use ot.security(check='{qualified_name}') to check security rules."
                )
                return
            # Allowed module, not blocked call - allow
            return

        # Allowed dunders pass through
        if self._is_allowed_dunder(func_name):
            return

        # Check against allowed builtins
        if _matches_pattern(func_name, self.allowed_builtins) is not None:
            return

        # Check if this is a known dangerous builtin that we explicitly block
        # User-defined functions (not in Python's builtins) are allowed
        try:
            import builtins
            if not hasattr(builtins, func_name):
                # Not a builtin - allow user-defined functions
                return
        except (ImportError, AttributeError):
            pass

        # Not allowed - block
        self.errors.append(
            f"Line {lineno}: Builtin '{func_name}' is not allowed. "
            f"Use ot.security(check='{func_name}') to check security rules."
        )

    def _check_qualified_call(self, func_name: str, lineno: int) -> None:
        """Check if a qualified call is allowed.

        Also resolves import aliases:
        `import subprocess as sp; sp.run()` -> resolves sp to subprocess

        Only checks known dangerous patterns. Method calls on variables
        (like results.append()) are allowed by default since we can't
        statically determine if 'results' is a dangerous module.
        """
        # Resolve import aliases first
        # e.g., "import subprocess as sp; sp.run()" -> func_name is "sp.run"
        # We need to resolve "sp" to "subprocess"
        parts = func_name.split(".")
        module_part = parts[0]
        original_module = self._import_aliases.get(module_part, module_part)

        # If alias was resolved, reconstruct the full name
        if original_module != module_part:
            resolved_name = ".".join([original_module, *parts[1:]])
        else:
            resolved_name = func_name

        # Tool namespaces are auto-allowed
        if self._is_tool_namespace(resolved_name):
            return

        # Explicitly allowed calls pass through
        if _matches_pattern(resolved_name, self.allowed_calls) is not None:
            return

        # Check blocked patterns first - these are explicitly dangerous
        if pattern := _matches_pattern(resolved_name, self.blocked_calls):
            if original_module != module_part:
                # Alias was used - include both in error message
                self.errors.append(
                    f"Line {lineno}: Call '{func_name}' is blocked "
                    f"('{module_part}' is alias for '{original_module}', matches '{pattern}'). "
                    f"Use ot.security(check='{resolved_name}') to check security rules."
                )
            else:
                self.errors.append(
                    f"Line {lineno}: Call '{func_name}' is blocked (matches '{pattern}'). "
                    f"Use ot.security(check='{func_name}') to check security rules."
                )
            return

        # Check warned patterns
        if pattern := _matches_pattern(resolved_name, self.warned_calls):
            self.warnings.append(
                f"Line {lineno}: Call '{resolved_name}' may be unsafe (matches '{pattern}')"
            )
            return

        # Check if the module part is in allowed imports
        # e.g., for json.loads, check if "json" is allowed
        if _matches_pattern(original_module, self.allowed_imports) is not None:
            # Module is allowed, so its functions are implicitly allowed
            return

        # For method calls on variables (not known modules), allow by default
        # We can't statically determine if 'results.append()' is dangerous
        # vs 'os.system()' without runtime type information.
        # Only block if explicitly in blocked_calls or if module_part is
        # a known dangerous import that's not allowed.
        #
        # Check if module_part looks like a known stdlib module that
        # should be blocked (e.g., os, subprocess, pickle)
        # Uses cached STDLIB_MODULE_NAMES for performance
        if STDLIB_MODULE_NAMES and original_module in STDLIB_MODULE_NAMES:
            if original_module != module_part:
                self.errors.append(
                    f"Line {lineno}: Module '{original_module}' "
                    f"(aliased as '{module_part}') is not in allowed imports. "
                    f"Use ot.security(check='{original_module}') to check security rules."
                )
            else:
                self.errors.append(
                    f"Line {lineno}: Module '{original_module}' is not in allowed imports. "
                    f"Use ot.security(check='{original_module}') to check security rules."
                )
            return

        # Not a known stdlib module - allow method calls on variables

    def visit_Import(self, node: ast.Import) -> None:
        """Check import statements against allowlists.

        Also tracks aliases for bypass prevention:
        `import subprocess as sp` -> tracks sp -> subprocess
        """
        for alias in node.names:
            module_name = alias.name
            self._check_import(module_name, node.lineno)

            # Track alias if present (e.g., "import subprocess as sp")
            # This prevents bypass via: import blocked as alias; alias.func()
            if alias.asname:
                self._import_aliases[alias.asname] = module_name
            else:
                # Even without alias, track the module name for consistency
                # e.g., "import subprocess" -> subprocess.run() uses "subprocess"
                self._import_aliases[module_name] = module_name

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from imports against allowlists.

        Also tracks imported names for bypass prevention:
        `from subprocess import run` -> tracks run -> subprocess
        `from subprocess import run as r` -> tracks r -> subprocess
        """
        if node.module:
            self._check_import(node.module, node.lineno)

            # Track all imported names from this module
            # This prevents bypass via: from blocked import func; func()
            for alias in node.names:
                if alias.name == "*":
                    # Star imports are dangerous - we can't track what's imported
                    # The module check above will already block if not allowed
                    self.warnings.append(
                        f"Line {node.lineno}: Star import from '{node.module}' - "
                        f"cannot track imported names for security validation"
                    )
                    continue

                # Use the alias name if present, otherwise the original name
                local_name = alias.asname if alias.asname else alias.name
                # Map local name -> (module, original_name)
                self._from_imports[local_name] = node.module

        self.generic_visit(node)

    def _check_import(self, module_name: str, lineno: int) -> None:
        """Check if a module import is allowed."""
        # Check allowed imports
        if _matches_pattern(module_name, self.allowed_imports) is not None:
            return

        # Check warned imports
        if pattern := _matches_pattern(module_name, self.warned_imports):
            self.warnings.append(
                f"Line {lineno}: Import of '{module_name}' may enable "
                f"unsafe operations (matches '{pattern}')"
            )
            return

        # Not allowed - block
        self.errors.append(
            f"Line {lineno}: Import of '{module_name}' is not allowed. "
            f"Use ot.security(check='{module_name}') to check security rules."
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        """Check assignments to magic variables."""
        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id.startswith("__")
                and target.id.endswith("__")
                and not self._is_allowed_dunder(target.id)
            ):
                self.errors.append(
                    f"Line {node.lineno}: Assignment to '{target.id}' is not allowed"
                )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Block subscript access to __builtins__.

        Prevents bypass via: __builtins__['exec']('code')
        """
        # Check if subscripting __builtins__
        if isinstance(node.value, ast.Name) and node.value.id == "__builtins__":
            self.errors.append(
                f"Line {node.lineno}: Access to '__builtins__' is not allowed "
                f"(potential security bypass)"
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

    Security validation uses allowlist-based rules from security.yaml.
    If config is not available, minimal fallback defaults are used.

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

    # Step 2: Security validation
    if check_security:
        security_config = _get_security_config()

        if security_config is not None and not security_config.enabled:
            # Security disabled in config - skip validation
            visitor = None
        elif security_config is not None:
            # Use config-driven allowlists
            visitor = AllowlistValidator(
                allowed_builtins=security_config.get_allowed_builtins(),
                allowed_imports=security_config.get_allowed_imports(),
                warned_imports=security_config.get_warned_imports(),
                blocked_calls=security_config.get_blocked_calls(),
                warned_calls=security_config.get_warned_calls(),
                allowed_calls=security_config.get_allowed_calls(),
                tool_namespaces=_get_tool_namespaces(),
                allowed_dunders=security_config.get_allowed_dunders(),
            )
        else:
            # No config - use fallback defaults
            visitor = AllowlistValidator(
                allowed_builtins=FALLBACK_ALLOWED_BUILTINS,
                allowed_imports=FALLBACK_ALLOWED_IMPORTS,
                warned_imports=FALLBACK_WARNED_IMPORTS,
                blocked_calls=frozenset(),
                warned_calls=frozenset(),
                allowed_calls=frozenset(),
                tool_namespaces=_get_tool_namespaces(),
                allowed_dunders=FALLBACK_ALLOWED_DUNDERS,
            )

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


# =============================================================================
# Security Introspection (used by ot.security())
# =============================================================================


def get_security_status(pattern: str) -> dict[str, str | bool]:
    """Check the security status of a specific pattern.

    Used by ot.security(check=pattern) for agent introspection.

    Args:
        pattern: Pattern to check (e.g., "os", "json.loads", "pickle.*")

    Returns:
        Dict with 'pattern', 'status' (allowed/blocked/warned), 'category',
        and 'reason' explaining why.
    """
    security_config = _get_security_config()
    tool_namespaces = _get_tool_namespaces()

    is_qualified = "." in pattern

    if is_qualified:
        # Check if it's a tool namespace
        if _matches_pattern(pattern, tool_namespaces):
            namespace = pattern.split(".")[0]
            return {
                "pattern": pattern,
                "status": "allowed",
                "category": "tool_namespace",
                "reason": f"Tool namespace '{namespace}' is auto-allowed",
            }

        if security_config:
            # Check explicitly allowed calls
            if _matches_pattern(pattern, security_config.get_allowed_calls()):
                return {
                    "pattern": pattern,
                    "status": "allowed",
                    "category": "calls",
                    "reason": "Explicitly allowed in security.yaml calls.allow",
                }

            # Check blocked calls
            if match := _matches_pattern(pattern, security_config.get_blocked_calls()):
                return {
                    "pattern": pattern,
                    "status": "blocked",
                    "category": "calls",
                    "reason": f"Blocked by pattern '{match}' in security.yaml calls.block",
                }

            # Check warned calls
            if match := _matches_pattern(pattern, security_config.get_warned_calls()):
                return {
                    "pattern": pattern,
                    "status": "warned",
                    "category": "calls",
                    "reason": f"Warned by pattern '{match}' in security.yaml calls.warn",
                }

            # Check if module part is allowed
            module_part = pattern.split(".")[0]
            if _matches_pattern(module_part, security_config.get_allowed_imports()):
                return {
                    "pattern": pattern,
                    "status": "allowed",
                    "category": "imports",
                    "reason": f"Module '{module_part}' is in allowed imports",
                }

        # Default: blocked
        return {
            "pattern": pattern,
            "status": "blocked",
            "category": "calls",
            "reason": "Not in any allowlist (default: block)",
        }

    else:
        # Unqualified name - check builtins and imports
        if security_config:
            # Check allowed builtins
            if _matches_pattern(pattern, security_config.get_allowed_builtins()):
                return {
                    "pattern": pattern,
                    "status": "allowed",
                    "category": "builtins",
                    "reason": "In security.yaml builtins.allow",
                }

            # Check allowed imports
            if _matches_pattern(pattern, security_config.get_allowed_imports()):
                return {
                    "pattern": pattern,
                    "status": "allowed",
                    "category": "imports",
                    "reason": "In security.yaml imports.allow",
                }

            # Check warned imports
            if match := _matches_pattern(pattern, security_config.get_warned_imports()):
                return {
                    "pattern": pattern,
                    "status": "warned",
                    "category": "imports",
                    "reason": f"Warned by pattern '{match}' in security.yaml imports.warn",
                }

            # Check allowed dunders
            if pattern in security_config.get_allowed_dunders():
                return {
                    "pattern": pattern,
                    "status": "allowed",
                    "category": "dunders",
                    "reason": "In security.yaml dunders.allow",
                }

        # Default: blocked
        return {
            "pattern": pattern,
            "status": "blocked",
            "category": "builtins",
            "reason": "Not in any allowlist (default: block)",
        }


def get_security_summary() -> dict[str, Any]:
    """Get a summary of the current security configuration.

    Used by ot.security() for agent introspection.

    Returns:
        Dict with counts and sample items for each category.
    """
    security_config = _get_security_config()
    tool_namespaces = _get_tool_namespaces()

    if security_config is None:
        return {
            "status": "fallback",
            "message": "Using fallback defaults (security.yaml not loaded)",
            "builtins_allowed": len(FALLBACK_ALLOWED_BUILTINS),
            "imports_allowed": len(FALLBACK_ALLOWED_IMPORTS),
            "tool_namespaces": sorted(tool_namespaces),
        }

    builtins = security_config.get_allowed_builtins()
    imports = security_config.get_allowed_imports()
    warned_imports = security_config.get_warned_imports()
    blocked_calls = security_config.get_blocked_calls()
    warned_calls = security_config.get_warned_calls()
    dunders = security_config.get_allowed_dunders()

    return {
        "status": "configured",
        "enabled": security_config.enabled,
        "builtins": {
            "allowed_count": len(builtins),
            "sample": sorted(builtins)[:10],
        },
        "imports": {
            "allowed_count": len(imports),
            "warned_count": len(warned_imports),
            "sample_allowed": sorted(imports)[:10],
            "warned": sorted(warned_imports),
        },
        "calls": {
            "blocked_count": len(blocked_calls),
            "warned_count": len(warned_calls),
            "blocked": sorted(blocked_calls),
            "warned": sorted(warned_calls),
        },
        "dunders": {
            "allowed": sorted(dunders),
        },
        "tool_namespaces": sorted(tool_namespaces),
    }


def reset() -> None:
    """Clear validator caches for reload.

    Use this as part of the config reload flow to force security config
    and tool namespaces to be reloaded on next access.
    """
    _get_security_config.cache_clear()
    _get_tool_namespaces.cache_clear()
