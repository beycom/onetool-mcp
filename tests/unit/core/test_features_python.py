"""Unit tests for Python construct execution.

Tests complex Python constructs with the execution engine:
- Loops with range and enumerate
- Conditionals with complex logic
- List comprehensions with filtering
- Method chaining

These tests complement test_python_exec.py by focusing on constructs
commonly used in OneTool code that combines tool calls with Python logic.
Migrated from demo/bench/features.yaml Python construct tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pytest

if TYPE_CHECKING:
    pass


@pytest.mark.unit
@pytest.mark.core
class TestPythonLoops:
    """Test loop constructs with various patterns."""

    def test_range_loop_with_accumulator(self, executor: Callable[[str], str]) -> None:
        """Loop with range accumulating values."""
        code = """results = []
for i in range(5):
    results.append(f"item{i}")
",".join(results)"""
        result = executor(code)
        assert result == "item0,item1,item2,item3,item4"

    def test_enumerate_loop(self, executor: Callable[[str], str]) -> None:
        """Loop with enumerate for index and value."""
        code = """items = ["a", "b", "c"]
results = []
for i, item in enumerate(items):
    results.append(f"{i}:{item}")
",".join(results)"""
        result = executor(code)
        assert result == "0:a,1:b,2:c"

    def test_nested_loop(self, executor: Callable[[str], str]) -> None:
        """Nested loop producing combinations."""
        code = """results = []
for i in range(2):
    for j in range(2):
        results.append(f"{i},{j}")
";".join(results)"""
        result = executor(code)
        assert result == "0,0;0,1;1,0;1,1"


@pytest.mark.unit
@pytest.mark.core
class TestPythonConditionals:
    """Test conditional logic patterns."""

    def test_conditional_transform(self, executor: Callable[[str], str]) -> None:
        """Transform values based on condition."""
        code = """results = []
for i in range(5):
    if i % 2 == 0:
        results.append(f"even:{i}")
    else:
        results.append(f"odd:{i}")
",".join(results)"""
        result = executor(code)
        assert result == "even:0,odd:1,even:2,odd:3,even:4"

    def test_conditional_filter(self, executor: Callable[[str], str]) -> None:
        """Filter values using condition."""
        code = """numbers = list(range(10))
evens = []
for n in numbers:
    if n % 2 == 0:
        evens.append(n)
evens"""
        result = executor(code)
        assert result == "[0, 2, 4, 6, 8]"

    def test_nested_conditional(self, executor: Callable[[str], str]) -> None:
        """Nested if/elif/else logic."""
        code = """def categorise(n):
    if n < 0:
        return "negative"
    elif n == 0:
        return "zero"
    elif n < 10:
        return "small"
    else:
        return "large"
[categorise(n) for n in [-5, 0, 5, 15]]"""
        result = executor(code)
        assert "negative" in result
        assert "zero" in result
        assert "small" in result
        assert "large" in result


@pytest.mark.unit
@pytest.mark.core
class TestPythonComprehensions:
    """Test list and dict comprehension patterns."""

    def test_simple_comprehension(self, executor: Callable[[str], str]) -> None:
        """Simple list comprehension with transform."""
        code = """[x.upper() for x in ["foo", "bar", "baz"]]"""
        result = executor(code)
        assert "FOO" in result
        assert "BAR" in result
        assert "BAZ" in result

    def test_filtered_comprehension(self, executor: Callable[[str], str]) -> None:
        """List comprehension with filter."""
        code = """[x for x in range(10) if x % 3 == 0]"""
        result = executor(code)
        assert result == "[0, 3, 6, 9]"

    def test_dict_comprehension(self, executor: Callable[[str], str]) -> None:
        """Dict comprehension creating key-value pairs."""
        code = """{f"key{i}": i*2 for i in range(3)}"""
        result = executor(code)
        assert "key0" in result
        assert "key1" in result
        assert "key2" in result


@pytest.mark.unit
@pytest.mark.core
class TestPythonChains:
    """Test method chaining patterns."""

    def test_string_chain(self, executor: Callable[[str], str]) -> None:
        """Chain string operations."""
        code = """"hello world".upper().replace(" ", "-")"""
        result = executor(code)
        assert result == "HELLO-WORLD"

    def test_reverse_upper_chain(self, executor: Callable[[str], str]) -> None:
        """Reverse and uppercase a string."""
        code = """"foobar"[::-1].upper()"""
        result = executor(code)
        assert result == "RABOOF"

    def test_list_chain(self, executor: Callable[[str], str]) -> None:
        """Chain list operations with sorted."""
        code = """sorted([3, 1, 4, 1, 5])[:3]"""
        result = executor(code)
        assert result == "[1, 1, 3]"

    def test_complex_chain(self, executor: Callable[[str], str]) -> None:
        """Complex chain with multiple operations."""
        code = """text = "Hello World"
result = {
    "original": text,
    "upper": text.upper(),
    "reversed": text[::-1],
    "length": len(text)
}
f"original:{result['original']},upper:{result['upper']},length:{result['length']}" """
        result = executor(code)
        assert "Hello World" in result
        assert "HELLO WORLD" in result
        assert "11" in result
