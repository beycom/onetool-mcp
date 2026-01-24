"""Unit tests for Python execution engine.

Tests the executor without LLM involvement:
- Parsing (arguments, nested calls, multiline, literals)
- Execution (variables, loops, conditionals, comprehensions, functions)
- Return value handling (expression, print, function return, edge cases)
- Import handling
- Error detection
- Exception handling
- Infinite loop/recursion detection

Migrated from demo/bench/python_exec.yaml to provide:
- Faster feedback (seconds vs minutes)
- Deterministic results (no LLM variance)
- No API costs
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

import pytest

if TYPE_CHECKING:
    pass


# =============================================================================
# PARSING - How function signatures are parsed
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestParseArguments:
    """Test parsing of keyword and positional arguments."""

    def test_string_reverse(self, executor: Callable[[str], str]) -> None:
        """String slice reversal."""
        result = executor('"bar"[::-1]')
        assert result == "rab"

    def test_arithmetic(self, executor: Callable[[str], str]) -> None:
        """Basic arithmetic expression."""
        result = executor("17 + 25")
        assert result == "42"

    def test_power(self, executor: Callable[[str], str]) -> None:
        """Power operator."""
        result = executor("2 ** 3")
        assert result == "8"

    def test_join_list(self, executor: Callable[[str], str]) -> None:
        """String join with list."""
        result = executor('"".join(["foo", " ", "bar", " ", "baz"])')
        assert result == "foo bar baz"


@pytest.mark.unit
@pytest.mark.core
class TestParseNested:
    """Test parsing of nested function invocations."""

    def test_method_chaining(self, executor: Callable[[str], str]) -> None:
        """Method chaining with slice and upper."""
        result = executor('"foo"[::-1].upper()')
        assert result == "OOF"

    def test_slice_after_sort(self, executor: Callable[[str], str]) -> None:
        """Slice after sorted call."""
        result = executor("sorted([5, 2, 8, 1, 9, 3])[:3]")
        assert result == "[1,2,3]"


@pytest.mark.unit
@pytest.mark.core
class TestParseMultiline:
    """Test parsing expressions split across lines."""

    def test_multiline_dict(self, executor: Callable[[str], str]) -> None:
        """Multi-line dictionary literal."""
        code = """{"foo": "hello".upper(),
"bar": "WORLD".lower()}"""
        result = executor(code)
        assert "foo" in result
        assert "bar" in result

    def test_multiline_list(self, executor: Callable[[str], str]) -> None:
        """Multi-line list literal."""
        code = """sorted([3,
1, 2])"""
        result = executor(code)
        assert "1" in result
        assert "2" in result
        assert "3" in result


@pytest.mark.unit
@pytest.mark.core
class TestParseLiterals:
    """Test parsing of complex literal types."""

    def test_sorted_list(self, executor: Callable[[str], str]) -> None:
        """Sorted list literal."""
        result = executor("sorted([3, 1, 4, 1, 5, 9, 2, 6])")
        assert result == "[1,1,2,3,4,5,6,9]"

    def test_nested_comprehension(self, executor: Callable[[str], str]) -> None:
        """Flatten nested list via comprehension."""
        result = executor(
            "[x for sublist in [[1, 2], [3, 4], [5, 6]] for x in sublist]"
        )
        assert result == "[1,2,3,4,5,6]"

    def test_float_multiplication(self, executor: Callable[[str], str]) -> None:
        """Float multiplication."""
        result = executor("2.5 * 5")
        assert result == "12.5"

    def test_bool_keyword_arg(self, executor: Callable[[str], str]) -> None:
        """Boolean keyword argument."""
        result = executor('sorted(["foo", "bar", "baz"], reverse=True)')
        assert "baz" in result
        assert "bar" in result
        assert "foo" in result


# =============================================================================
# EXECUTION - How multi-statement code is executed
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestExecVariables:
    """Test execution with variable assignments."""

    def test_simple_variable(self, executor: Callable[[str], str]) -> None:
        """Simple variable assignment and method call."""
        code = """foo = "foo bar"
foo.upper()"""
        result = executor(code)
        assert result == "FOO BAR"

    def test_chained_variables(self, executor: Callable[[str], str]) -> None:
        """Multiple variable assignments with computation."""
        code = """foo = 7
bar = 3
baz = foo + bar
baz ** 2"""
        result = executor(code)
        assert result == "100"

    def test_variable_reassign(self, executor: Callable[[str], str]) -> None:
        """Variable reassignment."""
        code = """foo = 2
foo = foo * 3
foo = foo * 4
foo"""
        result = executor(code)
        assert result == "24"


@pytest.mark.unit
@pytest.mark.core
class TestExecLoops:
    """Test for loop constructs."""

    def test_accumulator(self, executor: Callable[[str], str]) -> None:
        """Loop with accumulator."""
        code = """foo = 0
for bar in [1, 2, 3, 4, 5]:
    foo = foo + bar
foo"""
        result = executor(code)
        assert result == "15"

    def test_range_factorial(self, executor: Callable[[str], str]) -> None:
        """Loop with range (factorial-like)."""
        code = """foo = 1
for bar in range(1, 6):
    foo = foo * bar
foo"""
        result = executor(code)
        assert result == "120"

    def test_build_list(self, executor: Callable[[str], str]) -> None:
        """Loop building list with append."""
        code = """parts = []
for item in ["foo", "bar", "baz"]:
    parts.append(item)
"-".join(parts)"""
        result = executor(code)
        assert result == "foo-bar-baz"


@pytest.mark.unit
@pytest.mark.core
class TestExecConditionals:
    """Test if/else logic."""

    def test_if_block(self, executor: Callable[[str], str]) -> None:
        """If/else block."""
        code = """foo = 5
if foo > 3:
    bar = foo * 2
else:
    bar = foo
bar"""
        result = executor(code)
        assert result == "10"

    def test_ternary(self, executor: Callable[[str], str]) -> None:
        """Ternary conditional expression."""
        code = """foo = "foobar"
foo.upper() if len(foo) > 3 else foo"""
        result = executor(code)
        assert result == "FOOBAR"


@pytest.mark.unit
@pytest.mark.core
class TestExecComprehensions:
    """Test list and dict comprehensions."""

    def test_list_comprehension(self, executor: Callable[[str], str]) -> None:
        """List comprehension with squares."""
        result = executor("[foo ** 2 for foo in [1, 2, 3, 4, 5]]")
        assert result == "[1,4,9,16,25]"

    def test_filtered_comprehension(self, executor: Callable[[str], str]) -> None:
        """List comprehension with filter."""
        result = executor("[foo ** 2 for foo in [1, 2, 3, 4, 5] if foo % 2 == 0]")
        assert result == "[4,16]"

    def test_dict_comprehension(self, executor: Callable[[str], str]) -> None:
        """Dict comprehension."""
        result = executor('{item: item.upper() for item in ["foo", "bar", "baz"]}')
        assert "foo" in result
        assert "FOO" in result
        assert "bar" in result
        assert "BAR" in result


@pytest.mark.unit
@pytest.mark.core
class TestExecFunctions:
    """Test user-defined functions."""

    def test_simple_function(self, executor: Callable[[str], str]) -> None:
        """Simple function definition and call."""
        code = """def double(x):
    return x * 2
double(5)"""
        result = executor(code)
        assert result == "10"

    def test_multi_arg_function(self, executor: Callable[[str], str]) -> None:
        """Function with multiple arguments."""
        code = """def combine(foo, bar):
    return foo + bar
combine("foo", "bar")"""
        result = executor(code)
        assert result == "foobar"

    def test_default_arg_function(self, executor: Callable[[str], str]) -> None:
        """Function with default argument."""
        code = """def repeat_text(foo, times=3):
    return foo * times
repeat_text("foo")"""
        result = executor(code)
        assert result == "foofoofoo"

    def test_nested_call_function(self, executor: Callable[[str], str]) -> None:
        """Function with nested operations."""
        code = """def reverse_upper(foo):
    bar = foo[::-1]
    return bar.upper()
reverse_upper("foobar")"""
        result = executor(code)
        assert result == "RABOOF"

    def test_complex_return(self, executor: Callable[[str], str]) -> None:
        """Function returning dict."""
        code = """def analyze(foo):
    bar = foo[::-1]
    baz = len(foo)
    return {"original": foo, "reversed": bar, "length": baz}
analyze("foobar")"""
        result = executor(code)
        assert "original" in result
        assert "foobar" in result
        assert "reversed" in result
        assert "raboof" in result
        assert "length" in result
        assert "6" in result


# =============================================================================
# RETURN VALUE HANDLING - How results are captured
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestReturnExpression:
    """Test return via final expression."""

    def test_expression_call(self, executor: Callable[[str], str]) -> None:
        """Expression with method chain."""
        result = executor('("foo" * 2)[::-1]')
        assert result == "oofoof"

    def test_expression_bare(self, executor: Callable[[str], str]) -> None:
        """Bare variable as final expression."""
        code = """foo = 2 * 12
foo"""
        result = executor(code)
        assert result == "24"

    def test_expression_literal(self, executor: Callable[[str], str]) -> None:
        """Dict literal as final expression."""
        code = """foo = "hello"
bar = "world"
{"foo": foo, "bar": bar}"""
        result = executor(code)
        assert "foo" in result
        assert "bar" in result


@pytest.mark.unit
@pytest.mark.core
class TestReturnPrint:
    """Test return via print() output."""

    def test_print_simple(self, executor: Callable[[str], str]) -> None:
        """Simple print statement."""
        result = executor('print("foobar")')
        assert "foobar" in result

    def test_print_multi(self, executor: Callable[[str], str]) -> None:
        """Multiple print statements."""
        code = """print("foo")
print("bar")
print("baz")"""
        result = executor(code)
        assert re.search(r"(?s)foo.*bar.*baz", result)

    def test_print_formatted(self, executor: Callable[[str], str]) -> None:
        """Formatted print with f-string."""
        code = """foo = 42
bar = 24
print(f"foo: {foo}, bar: {bar}")"""
        result = executor(code)
        assert "foo: 42, bar: 24" in result

    def test_print_with_result(self, executor: Callable[[str], str]) -> None:
        """Print followed by expression result."""
        code = """print("processing...")
foo = 10 + 20
foo"""
        result = executor(code)
        assert "processing" in result
        assert "30" in result


@pytest.mark.unit
@pytest.mark.core
class TestReturnFunction:
    """Test return via function return statement."""

    def test_func_simple(self, executor: Callable[[str], str]) -> None:
        """Simple function return."""
        code = """def get_answer():
    return 42
get_answer()"""
        result = executor(code)
        assert result == "42"

    def test_func_computed(self, executor: Callable[[str], str]) -> None:
        """Function with computed return."""
        code = """def transform(foo, bar):
    a = foo[::-1]
    b = bar[::-1]
    return (a + " " + b).upper()
transform("foo", "bar")"""
        result = executor(code)
        assert result == "OOF RAB"

    def test_func_early_return(self, executor: Callable[[str], str]) -> None:
        """Function with early return."""
        code = """def check_size(foo):
    if foo < 10:
        return "small"
    return "large"
check_size(5)"""
        result = executor(code)
        assert result == "small"


@pytest.mark.unit
@pytest.mark.core
class TestReturnEdgeCases:
    """Test edge case return values."""

    def test_empty_string(self, executor: Callable[[str], str]) -> None:
        """Empty string reversal."""
        result = executor('""[::-1]')
        # Empty string result - executor returns empty or success message
        assert result == "" or "executed" in result.lower()

    def test_empty_list(self, executor: Callable[[str], str]) -> None:
        """Empty list sorted."""
        result = executor("sorted([])")
        assert result == "[]"

    def test_none_assignment(self, executor: Callable[[str], str]) -> None:
        """Assignment without return value."""
        code = """foo = 5
bar = 10"""
        result = executor(code)
        # No explicit return - should indicate execution or return None
        assert re.search(r"(?i)none|null|no.*value|executed", result)


# =============================================================================
# IMPORT HANDLING - How imports are processed
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestImportPatterns:
    """Test different import patterns."""

    def test_import_basic(self, executor: Callable[[str], str]) -> None:
        """Basic import statement."""
        code = """import math
math.pi"""
        result = executor(code)
        assert re.search(r"3\.14", result)

    def test_import_from(self, executor: Callable[[str], str]) -> None:
        """From import statement."""
        code = """from datetime import datetime
datetime.now().year"""
        result = executor(code)
        assert re.search(r"\d{4}", result)

    def test_import_alias(self, executor: Callable[[str], str]) -> None:
        """Import with alias."""
        code = """import math as m
round(m.e, 2)"""
        result = executor(code)
        assert re.search(r"2\.72", result)


@pytest.mark.unit
@pytest.mark.core
class TestImportUsage:
    """Test using imported modules."""

    def test_json_loads(self, executor: Callable[[str], str]) -> None:
        """JSON parsing."""
        code = """import json
json.loads('{"foo": 1, "bar": 2}')"""
        result = executor(code)
        assert "foo" in result
        assert "1" in result

    def test_re_findall(self, executor: Callable[[str], str]) -> None:
        """Regex findall."""
        code = """import re
re.findall(r'[a-z]+', "123foo456bar789")"""
        result = executor(code)
        assert "foo" in result
        assert "bar" in result

    def test_hashlib_sha256(self, executor: Callable[[str], str]) -> None:
        """Hashlib SHA256."""
        code = """import hashlib
hashlib.sha256(b"foobar").hexdigest()"""
        result = executor(code)
        assert re.search(r"[a-f0-9]{64}", result)


# =============================================================================
# ERROR DETECTION - How errors are reported
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestErrorIndentation:
    """Test indentation error detection."""

    def test_inconsistent_indent(self, executor: Callable[[str], str]) -> None:
        """Inconsistent indentation."""
        code = """for foo in [1, 2, 3]:
  bar = foo
    baz = foo"""
        with pytest.raises(ValueError, match=r"(?i)indent|error|syntax"):
            executor(code)

    def test_missing_indent(self, executor: Callable[[str], str]) -> None:
        """Missing indentation after colon."""
        code = """if True:
"foo".upper()"""
        with pytest.raises(ValueError, match=r"(?i)indent|error|syntax"):
            executor(code)


@pytest.mark.unit
@pytest.mark.core
class TestErrorBrackets:
    """Test bracket error detection."""

    def test_unclosed_bracket(self, executor: Callable[[str], str]) -> None:
        """Unclosed bracket."""
        with pytest.raises(ValueError, match=r"(?i)error|syntax|EOF"):
            executor("(5 + 10")

    def test_extra_bracket(self, executor: Callable[[str], str]) -> None:
        """Extra closing bracket."""
        with pytest.raises(ValueError, match=r"(?i)error|syntax"):
            executor("(5 + 10))")


@pytest.mark.unit
@pytest.mark.core
class TestErrorNames:
    """Test name error detection."""

    def test_undefined_name(self, executor: Callable[[str], str]) -> None:
        """Undefined variable name."""
        with pytest.raises(ValueError, match=r"(?i)error|name|defined"):
            executor("undefined_var + 1")

    def test_wrong_case_builtin(self, executor: Callable[[str], str]) -> None:
        """Wrong case for builtin."""
        with pytest.raises(ValueError, match=r"(?i)error|name|defined"):
            executor('Print("foo")')


# =============================================================================
# EXCEPTIONS - Throwing and handling errors
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestExceptionRaise:
    """Test exception raising."""

    def test_raise_simple(self, executor: Callable[[str], str]) -> None:
        """Simple exception raise."""
        with pytest.raises(
            ValueError, match=r"(?i)error|exception|something went wrong"
        ):
            executor('raise Exception("something went wrong")')

    def test_raise_valueerror(self, executor: Callable[[str], str]) -> None:
        """ValueError with message."""
        code = """foo = -1
if foo < 0:
    raise ValueError(f"foo must be positive, got {foo}")"""
        with pytest.raises(ValueError, match=r"(?i)valueerror|invalid|foo"):
            executor(code)

    def test_raise_typeerror(self, executor: Callable[[str], str]) -> None:
        """TypeError from type check."""
        code = """def process(foo):
    if not isinstance(foo, str):
        raise TypeError(f"expected str, got {type(foo).__name__}")
    return foo.upper()
process(42)"""
        with pytest.raises(ValueError, match=r"(?i)typeerror|type|expected"):
            executor(code)

    def test_raise_custom(self, executor: Callable[[str], str]) -> None:
        """Custom exception class."""
        code = """class FooError(Exception):
    pass
raise FooError("bar is invalid")"""
        with pytest.raises(ValueError, match=r"(?i)fooerror|bar is invalid"):
            executor(code)


@pytest.mark.unit
@pytest.mark.core
class TestExceptionRuntime:
    """Test runtime exceptions."""

    def test_division_by_zero(self, executor: Callable[[str], str]) -> None:
        """Division by zero."""
        code = """foo = 42
bar = 0
foo / bar"""
        with pytest.raises(ValueError, match=r"(?i)zero|division|error"):
            executor(code)

    def test_index_error(self, executor: Callable[[str], str]) -> None:
        """Index out of range."""
        code = """foo = ["a", "b", "c"]
foo[10]"""
        with pytest.raises(ValueError, match=r"(?i)index|range|error"):
            executor(code)

    def test_key_error(self, executor: Callable[[str], str]) -> None:
        """Missing dictionary key."""
        code = """foo = {"bar": 1}
foo["baz"]"""
        with pytest.raises(ValueError, match=r"(?i)key|error|baz"):
            executor(code)

    def test_attribute_error(self, executor: Callable[[str], str]) -> None:
        """Non-existent attribute."""
        code = """foo = "bar"
foo.nonexistent()"""
        with pytest.raises(ValueError, match=r"(?i)attribute|error|nonexistent"):
            executor(code)


# =============================================================================
# INFINITE LOOPS - Timeout and loop detection
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.slow  # These tests may take longer due to recursion depth
class TestInfiniteLoops:
    """Test infinite loop/recursion handling."""

    def test_infinite_recursion(self, executor: Callable[[str], str]) -> None:
        """Infinite recursion detection."""
        code = """def foo(bar):
    return foo(bar + 1)
foo(0)"""
        with pytest.raises(
            ValueError, match=r"(?i)recursion|depth|stack|overflow|maximum"
        ):
            executor(code)

    def test_mutual_recursion(self, executor: Callable[[str], str]) -> None:
        """Mutual recursion detection."""
        code = """def foo(x):
    return bar(x + 1)
def bar(x):
    return foo(x + 1)
foo(0)"""
        with pytest.raises(
            ValueError, match=r"(?i)recursion|depth|stack|overflow|maximum"
        ):
            executor(code)


# =============================================================================
# STRING LITERAL EDGE CASES
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestStringLiterals:
    """Test string literal handling edge cases."""

    def test_string_with_comma(self, executor: Callable[[str], str]) -> None:
        """String containing comma does not break parsing."""
        code = """items = ["a", "b", "c"]
results = []
for i, item in enumerate(items):
    results.append(f"{i}:{item}")
",".join(results)"""
        result = executor(code)
        assert result == "0:a,1:b,2:c"
