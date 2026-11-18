"""Disk retention boundaries owned entirely by OneTool."""

import json
import logging
from pathlib import Path

from fastmcp.tools import ToolResult

from onetool.results import ResultFiles, encoded


def test_exact_inline_boundary_and_directory_eviction(tmp_path: Path) -> None:
    result = ToolResult(content="small")
    files = ResultFiles(logging.getLogger("test.results"), len(encoded(result)))
    assert files.bound(result) is result
    assert files.directory is None
    files.cap = 1024
    files.directory_limit = 6000
    one = files.bound(ToolResult(content="a" * 3500))
    first = Path(one.structured_content["path"])
    two = files.bound(ToolResult(content="b" * 3500, is_error=True))
    second = Path(two.structured_content["path"])
    assert not first.exists() and second.exists()
    assert len(encoded(one)) <= files.cap and len(encoded(two)) <= files.cap
    assert two.is_error
    assert json.loads(second.read_text())["is_error"] is True
    files.close()
    assert not second.parent.exists()


def test_hard_limit_does_not_retain_or_invite_replay() -> None:
    files = ResultFiles(logging.getLogger("test.results"), 1024)
    result = files.bound(ToolResult(content="x" * (16 * 1024 * 1024)))
    assert result.is_error and files.directory is None
    assert "Do not replay" in result.content[0].text
