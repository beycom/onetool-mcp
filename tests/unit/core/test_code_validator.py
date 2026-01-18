"""Unit tests for code validator.

Tests the AST-based code validation for syntax and security patterns.
"""

from __future__ import annotations

import pytest

from ot.executor.validator import (
    DANGEROUS_BUILTINS,
    DANGEROUS_FUNCTIONS,
    WARN_PATTERNS,
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
# Dangerous Builtin Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_exec_detected() -> None:
    """exec() call returns valid=False."""
    result = validate_python_code("exec('print(1)')")
    assert result.valid is False
    assert any("exec" in e for e in result.errors)


@pytest.mark.unit
@pytest.mark.core
def test_eval_detected() -> None:
    """eval() call returns valid=False."""
    result = validate_python_code("x = eval('1 + 2')")
    assert result.valid is False
    assert any("eval" in e for e in result.errors)


@pytest.mark.unit
@pytest.mark.core
def test_compile_detected() -> None:
    """compile() call returns valid=False."""
    result = validate_python_code("code = compile('x=1', '', 'exec')")
    assert result.valid is False
    assert any("compile" in e for e in result.errors)


@pytest.mark.unit
@pytest.mark.core
def test_dunder_import_detected() -> None:
    """__import__() returns valid=False."""
    result = validate_python_code("os = __import__('os')")
    assert result.valid is False
    assert any("__import__" in e for e in result.errors)


@pytest.mark.unit
@pytest.mark.core
def test_nested_dangerous_builtin() -> None:
    """Dangerous call in nested context detected."""
    code = """
def run_code(s):
    return eval(s)
"""
    result = validate_python_code(code)
    assert result.valid is False
    assert any("eval" in e for e in result.errors)


# =============================================================================
# Dangerous Function Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_subprocess_run_detected() -> None:
    """subprocess.run() returns valid=False."""
    result = validate_python_code("subprocess.run(['ls'])")
    assert result.valid is False
    assert any("subprocess.run" in e for e in result.errors)


@pytest.mark.unit
@pytest.mark.core
def test_subprocess_popen_detected() -> None:
    """subprocess.Popen() returns valid=False."""
    result = validate_python_code("p = subprocess.Popen(['ls'])")
    assert result.valid is False
    assert any("subprocess.Popen" in e for e in result.errors)


@pytest.mark.unit
@pytest.mark.core
def test_os_system_detected() -> None:
    """os.system() returns valid=False."""
    result = validate_python_code("os.system('ls')")
    assert result.valid is False
    assert any("os.system" in e for e in result.errors)


@pytest.mark.unit
@pytest.mark.core
def test_os_popen_detected() -> None:
    """os.popen() returns valid=False."""
    result = validate_python_code("os.popen('ls')")
    assert result.valid is False
    assert any("os.popen" in e for e in result.errors)


@pytest.mark.unit
@pytest.mark.core
def test_os_exec_family_detected() -> None:
    """os.execl/v/etc. detected."""
    result = validate_python_code("os.execl('/bin/ls', 'ls')")
    assert result.valid is False
    assert any("os.execl" in e for e in result.errors)


# =============================================================================
# Warning Pattern Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_open_generates_warning() -> None:
    """open() adds warning but valid=True."""
    result = validate_python_code("f = open('file.txt')")
    assert result.valid is True  # Warning, not error
    assert any("open" in w for w in result.warnings)


@pytest.mark.unit
@pytest.mark.core
def test_pickle_load_warning() -> None:
    """pickle.load() adds warning."""
    result = validate_python_code("data = pickle.load(f)")
    assert result.valid is True
    assert any("pickle.load" in w for w in result.warnings)


@pytest.mark.unit
@pytest.mark.core
def test_yaml_load_warning() -> None:
    """yaml.load() adds warning."""
    result = validate_python_code("data = yaml.load(f)")
    assert result.valid is True
    assert any("yaml.load" in w for w in result.warnings)


@pytest.mark.unit
@pytest.mark.core
def test_marshal_load_warning() -> None:
    """marshal.load() adds warning."""
    result = validate_python_code("data = marshal.load(f)")
    assert result.valid is True
    assert any("marshal.load" in w for w in result.warnings)


# =============================================================================
# Import Warning Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_import_subprocess_warning() -> None:
    """import subprocess adds warning."""
    result = validate_python_code("import subprocess")
    assert result.valid is True
    assert any("subprocess" in w for w in result.warnings)


@pytest.mark.unit
@pytest.mark.core
def test_import_os_warning() -> None:
    """import os adds warning."""
    result = validate_python_code("import os")
    assert result.valid is True
    assert any("os" in w for w in result.warnings)


@pytest.mark.unit
@pytest.mark.core
def test_from_subprocess_import_warning() -> None:
    """from subprocess import adds warning."""
    result = validate_python_code("from subprocess import run")
    assert result.valid is True
    assert any("subprocess" in w for w in result.warnings)


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
def test_chained_attribute_detection() -> None:
    """os.path.join() not flagged as dangerous (safe function)."""
    result = validate_python_code("p = os.path.join('a', 'b')")
    # os.path.join is not in DANGEROUS_FUNCTIONS
    assert result.valid is True
    # But importing os still generates a warning
    # (the code doesn't import os, just uses it)


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
# Pattern Set Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_dangerous_builtins_set() -> None:
    """DANGEROUS_BUILTINS contains expected patterns."""
    assert "exec" in DANGEROUS_BUILTINS
    assert "eval" in DANGEROUS_BUILTINS
    assert "compile" in DANGEROUS_BUILTINS
    assert "__import__" in DANGEROUS_BUILTINS


@pytest.mark.unit
@pytest.mark.core
def test_dangerous_functions_set() -> None:
    """DANGEROUS_FUNCTIONS contains expected patterns."""
    assert "subprocess.run" in DANGEROUS_FUNCTIONS
    assert "subprocess.Popen" in DANGEROUS_FUNCTIONS
    assert "os.system" in DANGEROUS_FUNCTIONS


@pytest.mark.unit
@pytest.mark.core
def test_warn_patterns_set() -> None:
    """WARN_PATTERNS contains expected patterns."""
    assert "open" in WARN_PATTERNS
    assert "pickle.load" in WARN_PATTERNS
    assert "yaml.load" in WARN_PATTERNS
