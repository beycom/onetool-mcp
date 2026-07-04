"""Tests for `onetool init mcp-config` per-client output (p15)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


def _run(capsys, **kwargs) -> str:  # noqa: ANN001, ANN003
    from onetool.cli import init_mcp_config

    init_mcp_config(client=kwargs.get("client"), config=kwargs.get("config"), secrets=kwargs.get("secrets"))
    captured = capsys.readouterr()
    return captured.out + captured.err


def _first_json_block(text: str) -> dict:
    """Extract the first {...} JSON object from mixed console output."""
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                return json.loads(text[start : i + 1])
    raise AssertionError("no JSON block found")


@pytest.mark.unit
@pytest.mark.core
class TestMcpConfigOutput:
    def test_claude_code_uses_mcpservers(self, capsys, tmp_path: Path) -> None:
        cfg = tmp_path / "onetool.yaml"
        cfg.write_text("version: 2\n")
        text = _run(capsys, client="claude-code", config=cfg)
        block = _first_json_block(text)
        assert "mcpServers" in block
        assert block["mcpServers"]["onetool"]["args"][:3] == ["serve", "--config", str(cfg.resolve())]

    def test_vscode_uses_servers_with_type_stdio(self, capsys, tmp_path: Path) -> None:
        cfg = tmp_path / "onetool.yaml"
        cfg.write_text("version: 2\n")
        text = _run(capsys, client="vscode", config=cfg)
        block = _first_json_block(text)
        assert "servers" in block
        assert "mcpServers" not in block
        assert block["servers"]["onetool"]["type"] == "stdio"

    def test_only_vscode_has_type_field(self, capsys, tmp_path: Path) -> None:
        cfg = tmp_path / "onetool.yaml"
        cfg.write_text("version: 2\n")
        for client in ("claude-desktop", "cursor"):
            block = _first_json_block(_run(capsys, client=client, config=cfg))
            assert "type" not in block["mcpServers"]["onetool"]

    def test_no_placeholder_paths(self, capsys, tmp_path: Path) -> None:
        cfg = tmp_path / "onetool.yaml"
        cfg.write_text("version: 2\n")
        text = _run(capsys, client="claude-code", config=cfg)
        assert "yourname" not in text
        assert "/path/to/" not in text

    def test_secrets_omitted_when_missing(self, capsys, tmp_path: Path) -> None:
        cfg = tmp_path / "onetool.yaml"
        cfg.write_text("version: 2\n")  # no secrets.yaml alongside
        block = _first_json_block(_run(capsys, client="claude-code", config=cfg))
        assert "--secrets" not in block["mcpServers"]["onetool"]["args"]

    def test_secrets_included_when_present(self, capsys, tmp_path: Path) -> None:
        cfg = tmp_path / "onetool.yaml"
        cfg.write_text("version: 2\n")
        (tmp_path / "secrets.yaml").write_text("K: v\n")
        block = _first_json_block(_run(capsys, client="claude-code", config=cfg))
        assert "--secrets" in block["mcpServers"]["onetool"]["args"]

    def test_no_client_prints_all_four(self, capsys, tmp_path: Path) -> None:
        cfg = tmp_path / "onetool.yaml"
        cfg.write_text("version: 2\n")
        text = _run(capsys, client=None, config=cfg)
        for client in ("claude-code", "claude-desktop", "cursor", "vscode"):
            assert re.search(rf"#\s*{re.escape(client)}", text)

    def test_bad_client_exits(self, capsys, tmp_path: Path) -> None:
        import typer

        with pytest.raises(typer.Exit):
            _run(capsys, client="notaclient", config=tmp_path / "onetool.yaml")
