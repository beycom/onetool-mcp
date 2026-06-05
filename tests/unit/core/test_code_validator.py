"""Unit tests for code validator.

Tests the AST-based allowlist validation for syntax and security patterns.
"""

from __future__ import annotations

import pytest

from ot.executor.validator import (
    FALLBACK_ALLOWED_BUILTINS,
    FALLBACK_ALLOWED_IMPORTS,
    get_security_status,
    get_security_summary,
    validate_for_exec,
    validate_python_code,
)

# =============================================================================
# Syntax Validation Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_valid_python_passes() -> None:
    """Simple valid code returns valid=True."""
    result = validate_python_code("x = 1 + 2")
    assert result.valid is True
    assert result.errors == []


@pytest.mark.unit
@pytest.mark.core
def test_valid_multiline_code() -> None:
    """Multi-line code parses correctly."""
    code = """
def greet(name):
    return f"Hello, {name}!"

result = greet("World")
"""
    result = validate_python_code(code)
    assert result.valid is True
    assert result.errors == []


@pytest.mark.unit
@pytest.mark.core
def test_syntax_error_detected() -> None:
    """Invalid syntax returns valid=False."""
    result = validate_python_code("def foo(")
    assert result.valid is False
    assert len(result.errors) == 1
    assert "Syntax error" in result.errors[0]


@pytest.mark.unit
@pytest.mark.core
def test_syntax_error_has_line_number() -> None:
    """Error message includes line number."""
    code = """x = 1
y = 2
def broken(
"""
    result = validate_python_code(code)
    assert result.valid is False
    assert "line" in result.errors[0].lower()


@pytest.mark.unit
@pytest.mark.core
def test_empty_code_is_valid() -> None:
    """Empty string is valid Python."""
    result = validate_python_code("")
    assert result.valid is True
    assert result.errors == []


# =============================================================================
# Allowlist Tests - Allowed Builtins
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_allowed_builtins_pass() -> None:
    """Builtins in the allowlist pass validation."""
    # These should all be in FALLBACK_ALLOWED_BUILTINS
    allowed_code = [
        "x = len([1, 2, 3])",
        "y = str(123)",
        "z = list(range(10))",
        "a = isinstance(x, int)",
        "b = sorted([3, 1, 2])",
        "print('hello')",
    ]
    for code in allowed_code:
        result = validate_python_code(code)
        assert result.valid is True, f"'{code}' should be allowed: {result.errors}"


@pytest.mark.unit
@pytest.mark.core
def test_blocked_builtins_fail() -> None:
    """Builtins NOT in the allowlist are blocked."""
    # These should NOT be in FALLBACK_ALLOWED_BUILTINS
    blocked_code = [
        ("exec('print(1)')", "exec"),
        ("eval('1 + 2')", "eval"),
        ("compile('x=1', '', 'exec')", "compile"),
        ("__import__('os')", "__import__"),
        ("open('file.txt')", "open"),
        ("input('Enter: ')", "input"),
        ("breakpoint()", "breakpoint"),
    ]
    for code, name in blocked_code:
        result = validate_python_code(code)
        assert result.valid is False, f"'{name}' should be blocked"
        assert any(name in e for e in result.errors), f"Error should mention '{name}'"


@pytest.mark.unit
@pytest.mark.core
def test_dynamic_attribute_builtins_allowed() -> None:
    """Dynamic attribute access builtins are allowed per security config.

    These are explicitly allowed in security.yaml under "Object introspection"
    as they're commonly needed for legitimate operations.
    """
    allowed = ["getattr", "setattr", "delattr", "hasattr"]
    for builtin in allowed:
        result = validate_python_code(f"x = {builtin}(obj, 'attr')")
        assert result.valid is True, f"{builtin}() should be allowed"


# =============================================================================
# Allowlist Tests - Imports
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_allowed_imports_pass() -> None:
    """Imports in the allowlist pass validation."""
    allowed_imports = [
        "import json",
        "import re",
        "import math",
        "import datetime",
        "import collections",
        "from json import loads",
        "from re import match",
    ]
    for code in allowed_imports:
        result = validate_python_code(code)
        assert result.valid is True, f"'{code}' should be allowed: {result.errors}"


@pytest.mark.unit
@pytest.mark.core
def test_blocked_imports_fail() -> None:
    """Imports NOT in the allowlist are blocked."""
    blocked_imports = [
        ("import os", "os"),
        ("import sys", "sys"),
        ("import subprocess", "subprocess"),
        ("import socket", "socket"),
        ("import pickle", "pickle"),
        ("from os import path", "os"),
        ("from subprocess import run", "subprocess"),
    ]
    for code, name in blocked_imports:
        result = validate_python_code(code)
        assert result.valid is False, f"'{name}' import should be blocked"
        assert any(name in e for e in result.errors), f"Error should mention '{name}'"


@pytest.mark.unit
@pytest.mark.core
def test_yaml_import_warned() -> None:
    """yaml import generates a warning (in FALLBACK_WARNED_IMPORTS)."""
    result = validate_python_code("import yaml")
    # yaml is in warned imports, so it passes but with warning
    assert result.valid is True
    assert any("yaml" in w for w in result.warnings)


@pytest.mark.unit
@pytest.mark.core
def test_star_import_warned() -> None:
    """Star imports generate warnings about tracking."""
    result = validate_python_code("from json import *")
    assert result.valid is True  # Allowed module
    assert any("Star import" in w for w in result.warnings)


# =============================================================================
# Allowlist Tests - Qualified Calls
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_allowed_module_calls_pass() -> None:
    """Calls to allowed modules pass validation."""
    allowed_calls = [
        "data = json.loads('{}')",
        "pattern = re.compile('test')",
        "x = math.sqrt(4)",
    ]
    for code in allowed_calls:
        result = validate_python_code(code)
        assert result.valid is True, f"'{code}' should be allowed: {result.errors}"


@pytest.mark.unit
@pytest.mark.core
def test_blocked_calls_fail() -> None:
    """Calls to modules not in allowlist are blocked."""
    # pickle and marshal are not in imports.allow, so they're blocked
    blocked_calls = [
        ("pickle.load(f)", "pickle"),
        ("pickle.loads(data)", "pickle"),
        ("marshal.loads(data)", "marshal"),
    ]
    for code, pattern in blocked_calls:
        result = validate_python_code(code)
        assert result.valid is False, f"'{pattern}' call should be blocked"
        assert any(pattern in e for e in result.errors), f"Error should mention '{pattern}'"


@pytest.mark.unit
@pytest.mark.core
def test_unallowed_module_calls_blocked() -> None:
    """Calls to modules not in allowlist are blocked."""
    blocked_calls = [
        ("subprocess.run(['ls'])", "subprocess"),
        ("os.system('ls')", "os"),
        ("socket.socket()", "socket"),
    ]
    for code, module in blocked_calls:
        result = validate_python_code(code)
        assert result.valid is False, f"'{module}.*' calls should be blocked"


# =============================================================================
# Security Check Toggle Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_security_check_disabled() -> None:
    """Dangerous code passes with check_security=False."""
    result = validate_python_code("exec('print(1)')", check_security=False)
    assert result.valid is True
    assert result.errors == []


@pytest.mark.unit
@pytest.mark.core
def test_security_check_enabled_by_default() -> None:
    """Default is check_security=True."""
    result = validate_python_code("exec('print(1)')")
    assert result.valid is False


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_chained_attribute_safe_module() -> None:
    """json.loads() not flagged as dangerous (safe module)."""
    result = validate_python_code("data = json.loads('{}')")
    assert result.valid is True
    assert result.errors == []


@pytest.mark.unit
@pytest.mark.core
def test_multiple_issues_collected() -> None:
    """All errors collected in one pass."""
    code = """
exec('x = 1')
eval('2 + 2')
"""
    result = validate_python_code(code)
    assert result.valid is False
    assert len(result.errors) >= 2
    assert any("exec" in e for e in result.errors)
    assert any("eval" in e for e in result.errors)


@pytest.mark.unit
@pytest.mark.core
def test_ast_tree_returned() -> None:
    """ValidationResult includes ast_tree for valid code."""
    result = validate_python_code("x = 1")
    assert result.valid is True
    assert result.ast_tree is not None


@pytest.mark.unit
@pytest.mark.core
def test_ast_tree_none_on_syntax_error() -> None:
    """ValidationResult has no ast_tree on syntax error."""
    result = validate_python_code("def broken(")
    assert result.valid is False
    assert result.ast_tree is None


# =============================================================================
# validate_for_exec Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_validate_for_exec_valid() -> None:
    """validate_for_exec passes for safe code."""
    result = validate_for_exec("x = 1 + 2")
    assert result.valid is True


@pytest.mark.unit
@pytest.mark.core
def test_validate_for_exec_blocks_dangerous() -> None:
    """validate_for_exec blocks dangerous patterns."""
    result = validate_for_exec("exec('x = 1')")
    assert result.valid is False


# =============================================================================
# Fallback Pattern Set Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_fallback_allowed_builtins() -> None:
    """FALLBACK_ALLOWED_BUILTINS contains expected safe builtins."""
    # Type constructors
    assert "str" in FALLBACK_ALLOWED_BUILTINS
    assert "int" in FALLBACK_ALLOWED_BUILTINS
    assert "list" in FALLBACK_ALLOWED_BUILTINS
    assert "dict" in FALLBACK_ALLOWED_BUILTINS
    # Type checking
    assert "isinstance" in FALLBACK_ALLOWED_BUILTINS
    # Iteration
    assert "len" in FALLBACK_ALLOWED_BUILTINS
    assert "range" in FALLBACK_ALLOWED_BUILTINS
    # Math
    assert "min" in FALLBACK_ALLOWED_BUILTINS
    assert "max" in FALLBACK_ALLOWED_BUILTINS


@pytest.mark.unit
@pytest.mark.core
def test_fallback_allowed_imports() -> None:
    """FALLBACK_ALLOWED_IMPORTS contains expected safe modules."""
    assert "json" in FALLBACK_ALLOWED_IMPORTS
    assert "re" in FALLBACK_ALLOWED_IMPORTS
    assert "math" in FALLBACK_ALLOWED_IMPORTS
    assert "datetime" in FALLBACK_ALLOWED_IMPORTS


# =============================================================================
# Security Introspection Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_get_security_status_allowed_builtin() -> None:
    """get_security_status returns allowed for safe builtins."""
    status = get_security_status("len")
    assert status["status"] == "allowed"
    assert status["category"] == "builtins"


@pytest.mark.unit
@pytest.mark.core
def test_get_security_status_blocked_builtin() -> None:
    """get_security_status returns blocked for dangerous builtins."""
    status = get_security_status("exec")
    assert status["status"] == "blocked"


@pytest.mark.unit
@pytest.mark.core
def test_get_security_status_allowed_import() -> None:
    """get_security_status returns allowed for safe imports."""
    status = get_security_status("json")
    assert status["status"] == "allowed"
    assert status["category"] == "imports"


@pytest.mark.unit
@pytest.mark.core
def test_get_security_status_blocked_import() -> None:
    """get_security_status returns blocked for dangerous imports."""
    status = get_security_status("os")
    assert status["status"] == "blocked"


@pytest.mark.unit
@pytest.mark.core
def test_get_security_status_blocked_call() -> None:
    """get_security_status returns blocked for dangerous calls."""
    status = get_security_status("pickle.load")
    assert status["status"] == "blocked"
    assert status["category"] == "calls"


@pytest.mark.unit
@pytest.mark.core
def test_get_security_status_allowed_module_call() -> None:
    """get_security_status returns allowed for calls to allowed modules."""
    status = get_security_status("json.loads")
    assert status["status"] == "allowed"


@pytest.mark.unit
@pytest.mark.core
def test_get_security_summary() -> None:
    """get_security_summary returns expected structure."""
    summary = get_security_summary()
    # Should have status field
    assert "status" in summary
    # If configured, should have category counts
    if summary["status"] == "configured":
        assert "builtins" in summary
        assert "imports" in summary
        assert "calls" in summary


# =============================================================================
# Magic Variable (Dunder) Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_allowed_dunders_pass() -> None:
    """Allowed magic variables pass validation."""
    allowed = [
        "__format__ = 'json'",
        "__sanitize__ = False",
        "__display__ = True",
    ]
    for code in allowed:
        result = validate_python_code(code)
        assert result.valid is True, f"'{code}' should be allowed: {result.errors}"


@pytest.mark.unit
@pytest.mark.core
def test_blocked_dunders_fail() -> None:
    """Non-allowed magic variables are blocked."""
    blocked = [
        "__class__ = str",
        "__dict__ = {}",
        "__name__ = 'foo'",
    ]
    for code in blocked:
        result = validate_python_code(code)
        assert result.valid is False, f"'{code}' should be blocked"
