"""Unit tests for the whiteboard session module (session.py).

Tests cover: load/save round-trip, CWD key derivation, named boards,
edge_keys serialisation, list_boards, and clear_board.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from otdev.tools._excalidraw import session as _sess


def _empty_state() -> dict[str, Any]:
    return {
        "shapes": {},
        "edges": [],
        "groups": {},
        "edge_keys": set(),
        "canvas_max_y": 60.0,
    }


@pytest.mark.unit
@pytest.mark.tools
class TestSessionLoadSave:
    def test_save_then_load_shapes(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            state = _empty_state()
            state["shapes"]["a"] = {"label": "A", "classes": []}
            _sess.save(state)
            loaded = _sess.load()

        assert "a" in loaded["shapes"]
        assert loaded["shapes"]["a"]["label"] == "A"

    def test_save_then_load_edges(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            state = _empty_state()
            state["edges"] = [{"id": "edge-a-b", "src": "a", "dst": "b", "label": ""}]
            _sess.save(state)
            loaded = _sess.load()

        assert len(loaded["edges"]) == 1
        assert loaded["edges"][0]["id"] == "edge-a-b"

    def test_save_then_load_edge_keys_as_set_of_tuples(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            state = _empty_state()
            state["edge_keys"] = {("a", "b", "", None, "arrow")}
            _sess.save(state)
            loaded = _sess.load()

        assert isinstance(loaded["edge_keys"], set)
        assert ("a", "b", "", None, "arrow") in loaded["edge_keys"]

    def test_edge_keys_serialised_as_list_of_lists(self, tmp_path: Any) -> None:
        """edge_keys must be stored as list-of-lists in JSON (sets aren't JSON-serialisable)."""
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            state = _empty_state()
            state["edge_keys"] = {("a", "b", "", None, "arrow")}
            _sess.save(state)
            path = _sess.session_path(None)
            raw = json.loads(path.read_text(encoding="utf-8"))

        assert isinstance(raw["edge_keys"], list)
        assert isinstance(raw["edge_keys"][0], list)

    def test_save_then_load_canvas_max_y(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            state = _empty_state()
            state["canvas_max_y"] = 350.5
            _sess.save(state)
            loaded = _sess.load()

        assert loaded["canvas_max_y"] == pytest.approx(350.5)

    def test_save_then_load_groups(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            state = _empty_state()
            state["groups"]["g1"] = {"label": "Group1", "members": ["a", "b"]}
            _sess.save(state)
            loaded = _sess.load()

        assert "g1" in loaded["groups"]
        assert loaded["groups"]["g1"]["label"] == "Group1"
        assert "a" in loaded["groups"]["g1"]["members"]

    def test_load_missing_file_returns_empty_state(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            loaded = _sess.load()

        assert loaded["shapes"] == {}
        assert loaded["edges"] == []
        assert loaded["groups"] == {}
        assert isinstance(loaded["edge_keys"], set)
        assert loaded["canvas_max_y"] == pytest.approx(60.0)

    def test_load_corrupted_file_returns_empty_state(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            path = _sess.session_path(None)
            path.write_text("not valid json", encoding="utf-8")
            loaded = _sess.load()

        assert loaded["shapes"] == {}

    def test_load_partial_state_fills_defaults(self, tmp_path: Any) -> None:
        """Forward-compat: if file lacks a key, defaults are filled in."""
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            path = _sess.session_path(None)
            path.write_text(json.dumps({"shapes": {"x": {"label": "X", "classes": []}}}), encoding="utf-8")
            loaded = _sess.load()

        assert "x" in loaded["shapes"]
        assert loaded["edges"] == []
        assert loaded["groups"] == {}
        assert loaded["canvas_max_y"] == pytest.approx(60.0)


@pytest.mark.unit
@pytest.mark.tools
class TestCwdKeyDerivation:
    def test_cwd_key_is_12_hex_chars(self) -> None:
        key = _sess.cwd_key()
        assert len(key) == 12
        assert all(c in "0123456789abcdef" for c in key)

    def test_cwd_key_is_deterministic(self) -> None:
        assert _sess.cwd_key() == _sess.cwd_key()

    def test_cwd_key_matches_sha256_prefix(self) -> None:
        cwd = os.path.realpath(os.getcwd())
        expected = hashlib.sha256(cwd.encode()).hexdigest()[:12]
        assert _sess.cwd_key() == expected

    def test_cwd_key_uses_effective_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        expected = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:12]
        assert _sess.cwd_key() == expected

    def test_whiteboard_dir_is_project_state(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        assert _sess._whiteboard_dir() == tmp_path / ".onetool" / "state" / "whiteboard"

    def test_different_cwd_gives_different_key(self, tmp_path: Any) -> None:
        cwd = os.path.realpath(os.getcwd())
        cwd_key = hashlib.sha256(cwd.encode()).hexdigest()[:12]
        other_key = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:12]
        assert cwd_key != other_key


@pytest.mark.unit
@pytest.mark.tools
class TestNamedBoards:
    def test_named_board_uses_board_name_as_filename(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            path = _sess.session_path("myboard")

        assert path == tmp_path / "myboard.json"

    def test_default_board_uses_cwd_key(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            path = _sess.session_path(None)

        expected = tmp_path / f"{_sess.cwd_key()}.json"
        assert path == expected

    def test_save_load_named_board(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            state = _empty_state()
            state["shapes"]["z"] = {"label": "Z", "classes": []}
            _sess.save(state, board="arch")
            loaded = _sess.load(board="arch")

        assert "z" in loaded["shapes"]

    def test_named_board_invalid_name_raises(self, tmp_path: Any) -> None:
        """Board names with spaces, dots, or path separators must be rejected."""
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            for bad in ("bad name", "bad.board", "../evil", "a/b"):
                with pytest.raises(ValueError, match="Invalid board name"):
                    _sess.session_path(bad)

    def test_named_board_valid_names_accepted(self, tmp_path: Any) -> None:
        """Letters, digits, hyphens, and underscores are all valid."""
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            for good in ("myboard", "Board-1", "arch_v2", "A"):
                path = _sess.session_path(good)
                assert path.parent == tmp_path

    def test_named_board_isolated_from_default(self, tmp_path: Any) -> None:
        """Named board and CWD board are completely independent."""
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            state_named = _empty_state()
            state_named["shapes"]["named"] = {"label": "Named", "classes": []}
            _sess.save(state_named, board="arch")

            state_default = _empty_state()
            state_default["shapes"]["default"] = {"label": "Default", "classes": []}
            _sess.save(state_default, board=None)

            loaded_named = _sess.load(board="arch")
            loaded_default = _sess.load(board=None)

        assert "named" in loaded_named["shapes"]
        assert "default" not in loaded_named["shapes"]
        assert "default" in loaded_default["shapes"]
        assert "named" not in loaded_default["shapes"]


@pytest.mark.unit
@pytest.mark.tools
class TestListBoards:
    def test_list_boards_empty_returns_empty_list(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            boards = _sess.list_boards()

        assert boards == []

    def test_list_boards_returns_saved_boards(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            state = _empty_state()
            state["shapes"]["a"] = {"label": "A", "classes": []}
            _sess.save(state, board="proj1")
            _sess.save(_empty_state(), board="proj2")

            boards = _sess.list_boards()

        names = [b["name"] for b in boards]
        assert "proj1" in names
        assert "proj2" in names

    def test_list_boards_includes_shape_count(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            state = _empty_state()
            state["shapes"]["a"] = {"label": "A", "classes": []}
            state["shapes"]["b"] = {"label": "B", "classes": []}
            _sess.save(state, board="two_shapes")
            boards = _sess.list_boards()

        board = next(b for b in boards if b["name"] == "two_shapes")
        assert board["shape_count"] == 2

    def test_list_boards_includes_mtime(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save(_empty_state(), board="t")
            boards = _sess.list_boards()

        board = next(b for b in boards if b["name"] == "t")
        assert board["mtime"] > 0


@pytest.mark.unit
@pytest.mark.tools
class TestClearBoard:
    def test_clear_board_deletes_session_file(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save(_empty_state(), board="tbd")
            assert (tmp_path / "tbd.json").exists()
            _sess.clear_board("tbd")
            assert not (tmp_path / "tbd.json").exists()

    def test_clear_board_missing_board_returns_not_found(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            msg = _sess.clear_board("nonexistent")

        assert "not" in msg or "no board" in msg.lower()

    def test_clear_board_none_clears_cwd_board(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save(_empty_state())
            cwd_path = _sess.session_path(None)
            assert cwd_path.exists()
            _sess.clear_board(None)
            assert not cwd_path.exists()

    def test_clear_board_returns_confirmation(self, tmp_path: Any) -> None:
        with patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save(_empty_state(), board="x")
            msg = _sess.clear_board("x")

        assert "x" in msg or "cleared" in msg
