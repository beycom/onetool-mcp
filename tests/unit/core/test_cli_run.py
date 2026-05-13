"""Unit tests for `onetool direct run` client behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer


@pytest.mark.unit
@pytest.mark.core
class TestResolveCommandSource:
    """Tests for _resolve_command_source."""

    def test_none_returns_none(self) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source

        assert _resolve_command_source(None) is None

    def test_regular_string_returned_as_is(self) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source

        assert _resolve_command_source("ot.debug()") == "ot.debug()"

    def test_py_file_existing_returns_contents(self, tmp_path: Path) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source

        script = tmp_path / "test.py"
        script.write_text("ot.debug()")

        assert _resolve_command_source(str(script)) == "ot.debug()"

    def test_py_file_nonexistent_returns_as_is(self) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source

        assert _resolve_command_source("/does/not/exist/script.py") == "/does/not/exist/script.py"


@pytest.mark.unit
@pytest.mark.core
class TestDirectRunClient:
    """Tests for direct_run as an authenticated client only."""

    def test_direct_help_lists_only_run_subcommand(self) -> None:
        from typer.testing import CliRunner

        from onetool.cli_commands.direct_app import direct_app

        result = CliRunner().invoke(direct_app, ["--help"])

        assert result.exit_code == 0
        assert "run" in result.output
        for removed in ("repl", "list", "search", "servers"):
            assert removed not in result.output

    def test_resolve_ot_dir_defaults_to_home_onetool(self) -> None:
        from onetool.cli_commands.direct_app import _resolve_ot_dir

        with patch("ot.paths.expand_path", return_value=Path("/home/user/.onetool")) as expand_path:
            assert _resolve_ot_dir(None) == Path("/home/user/.onetool")

        expand_path.assert_called_once_with("~/.onetool")

    def test_resolve_ot_dir_rejects_relative_path(self) -> None:
        from onetool.cli_commands.direct_app import _resolve_ot_dir

        with pytest.raises(typer.Exit) as exc_info:
            _resolve_ot_dir(Path(".onetool"))

        assert exc_info.value.exit_code == 2

    def test_missing_port_fails_before_probe(self) -> None:
        from onetool.cli_commands.direct_app import direct_run

        with (
            patch("onetool.cli_commands.direct_app._tcp_probe") as mock_probe,
            pytest.raises(typer.Exit) as exc_info,
        ):
            direct_run(command="ot.version()")

        assert exc_info.value.exit_code == 2
        mock_probe.assert_not_called()

    def test_unreachable_port_fails_without_running_in_process(self) -> None:
        from onetool.cli_commands.direct_app import direct_run

        with (
            patch("onetool.cli_commands.direct_app._tcp_probe", return_value=False),
            patch("onetool.cli_commands.direct_app._run_via_server") as mock_run,
            pytest.raises(typer.Exit) as exc_info,
        ):
            direct_run(command="ot.version()", port=8765)

        assert exc_info.value.exit_code == 1
        mock_run.assert_not_called()

    def test_signed_health_and_run_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        from onetool.cli_commands.direct_app import direct_run

        ot_dir = Path("/tmp/project/.onetool")
        with (
            patch("onetool.cli_commands.direct_app._resolve_ot_dir", return_value=ot_dir),
            patch("onetool.cli_commands.direct_app._tcp_probe", return_value=True),
            patch(
                "onetool.cli_commands.direct_app._signed_health_probe",
                return_value={"protocol_version": 1, "status": "ok"},
            ) as mock_health,
            patch(
                "onetool.cli_commands.direct_app._signed_ready_probe",
                return_value={"protocol_version": 1, "ready": True},
            ) as mock_ready,
            patch(
                "onetool.cli_commands.direct_app._run_via_server",
                return_value=("ok", True),
            ) as mock_run,
            pytest.raises(typer.Exit) as exc_info,
        ):
            direct_run(command="ot.version()", port=8765, fmt="raw", sanitize=True)

        assert exc_info.value.exit_code == 0
        assert capsys.readouterr().out == "ok\n"
        mock_health.assert_called_once_with("127.0.0.1", 8765, ot_dir=ot_dir, timeout=5)
        mock_ready.assert_called_once_with("127.0.0.1", 8765, ot_dir=ot_dir, timeout=5)
        mock_run.assert_called_once_with(
            "ot.version()",
            "127.0.0.1",
            8765,
            fmt="raw",
            sanitize=True,
            ot_dir=ot_dir,
            timeout=120,
        )

    def test_protocol_mismatch_fails_before_run(self) -> None:
        from onetool.cli_commands.direct_app import direct_run

        with (
            patch("onetool.cli_commands.direct_app._resolve_ot_dir", return_value=Path("/tmp/project/.onetool")),
            patch("onetool.cli_commands.direct_app._tcp_probe", return_value=True),
            patch(
                "onetool.cli_commands.direct_app._signed_health_probe",
                return_value={"protocol_version": 2, "status": "ok"},
            ),
            patch("onetool.cli_commands.direct_app._run_via_server") as mock_run,
            pytest.raises(typer.Exit) as exc_info,
        ):
            direct_run(command="ot.version()", port=8765)

        assert exc_info.value.exit_code == 1
        mock_run.assert_not_called()


@pytest.mark.unit
@pytest.mark.core
class TestRunRequestShape:
    """Tests for the direct API request contract."""

    def test_run_via_server_sends_compact_protocol_body(self) -> None:
        import json

        from onetool.cli_commands.direct_app import _run_via_server
        from ot.direct_auth import RUN_PATH

        body = b'{"protocol_version":1,"result":"ok","success":true}'
        captured: dict[str, object] = {}

        class _Resp:
            def __init__(self) -> None:
                self.status = 200
                self.headers: dict[str, str] = {}

            def __enter__(self) -> _Resp:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return body

        def _urlopen(req: object, timeout: int) -> _Resp:
            captured["timeout"] = timeout
            captured["data"] = req.data  # type: ignore[attr-defined]
            return _Resp()

        ot_dir = Path("/tmp/project/.onetool")
        with (
            patch("urllib.request.urlopen", side_effect=_urlopen),
            patch("ot.direct_auth.signed_headers", return_value={"X-Test": "signed"}) as signed_headers,
            patch("ot.direct_auth.verify_response") as verify_response,
        ):
            assert _run_via_server(
                "ot.version()",
                "127.0.0.1",
                8765,
                fmt="json_h",
                sanitize=False,
                ot_dir=ot_dir,
                timeout=99,
            ) == ("ok", True)

        payload = json.loads(captured["data"])
        assert captured["timeout"] == 99
        assert payload == {
            "protocol_version": 1,
            "operation": "run",
            "command": "ot.version()",
            "format": "json_h",
            "sanitize": False,
        }
        signed_headers.assert_called_once_with(
            method="POST",
            path=RUN_PATH,
            body=captured["data"],
            base_dir=ot_dir,
        )
        verify_response.assert_called_once_with(
            path=RUN_PATH,
            body=body,
            headers={},
            status_code=200,
            base_dir=ot_dir,
        )
