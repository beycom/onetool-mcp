"""Unit tests for onetool direct run: format injection, command resolution, tcp probe."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer


@pytest.mark.unit
@pytest.mark.core
class TestCommandWithMeta:
    """Tests for _build_command_with_meta (format + sanitize injection)."""

    def _meta(self, command: str, fmt: str, sanitize: bool) -> str:
        from onetool.cli_commands.direct_app import _build_command_with_meta
        return _build_command_with_meta(command, fmt, sanitize)

    def test_injects_format_json_h(self) -> None:
        result = self._meta("ot.debug()", "json_h", False)
        assert "__format__ = 'json_h'" in result
        assert "ot.debug()" in result

    def test_injects_sanitize_false(self) -> None:
        result = self._meta("ot.debug()", "json_h", False)
        assert "__sanitize__ = False" in result

    def test_injects_sanitize_true(self) -> None:
        result = self._meta("ot.debug()", "json", True)
        assert "__sanitize__ = True" in result

    def test_original_command_preserved(self) -> None:
        cmd = "brave.search(query='test')"
        result = self._meta(cmd, "raw", False)
        assert cmd in result

    def test_prefix_comes_before_command(self) -> None:
        result = self._meta("ot.debug()", "raw", False)
        prefix_end = result.index("\n")
        assert "ot.debug()" in result[prefix_end:]


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
        result = _resolve_command_source(str(script))
        assert result == "ot.debug()"

    def test_py_file_nonexistent_returns_as_is(self) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source
        result = _resolve_command_source("/does/not/exist/script.py")
        assert result == "/does/not/exist/script.py"

    def test_py_file_empty_returns_none(self, tmp_path: Path) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source
        script = tmp_path / "empty.py"
        script.write_text("   ")
        result = _resolve_command_source(str(script))
        assert result is None

    def test_non_py_extension_not_treated_as_file(self, tmp_path: Path) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source
        # A .txt file with .py-like content should be returned as-is (not read)
        txt = tmp_path / "cmd.txt"
        txt.write_text("ot.debug()")
        result = _resolve_command_source(str(txt))
        assert result == str(txt)


@pytest.mark.unit
@pytest.mark.core
class TestTcpProbe:
    """Tests for _tcp_probe helper."""

    def test_probe_unreachable_port(self) -> None:
        from onetool.cli_commands.direct_app import _tcp_probe
        assert _tcp_probe("127.0.0.1", 1, timeout=0.05) is False

    def test_probe_timeout_returns_false(self) -> None:
        from onetool.cli_commands.direct_app import _tcp_probe
        assert _tcp_probe("127.0.0.1", 19999, timeout=0.01) is False


@pytest.mark.unit
@pytest.mark.core
class TestValidFormats:
    """Tests for format validation in direct_run."""

    def test_valid_formats_accepted(self) -> None:
        from onetool.cli_commands.direct_app import _VALID_FORMATS
        assert "json_h" in _VALID_FORMATS
        assert "json" in _VALID_FORMATS
        assert "yml" in _VALID_FORMATS
        assert "yml_h" in _VALID_FORMATS
        assert "raw" in _VALID_FORMATS

    def test_old_text_format_not_valid(self) -> None:
        from onetool.cli_commands.direct_app import _VALID_FORMATS
        assert "text" not in _VALID_FORMATS

    def test_old_yaml_format_not_valid(self) -> None:
        from onetool.cli_commands.direct_app import _VALID_FORMATS
        assert "yaml" not in _VALID_FORMATS


@pytest.mark.unit
@pytest.mark.core
class TestResolveSecretsPath:
    """Tests for _resolve_secrets_path precedence."""

    def test_explicit_secrets_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from onetool.cli_commands.direct_app import _resolve_secrets_path

        config = tmp_path / "onetool.yaml"
        config.write_text("version: 2\n")
        explicit = tmp_path / "explicit.yaml"
        explicit.write_text("KEY: x\n")
        env_file = tmp_path / "env.yaml"
        env_file.write_text("KEY: y\n")
        (tmp_path / "secrets.yaml").write_text("KEY: z\n")
        monkeypatch.setenv("OT_SECRETS_FILE", str(env_file))

        assert _resolve_secrets_path(config, explicit) == explicit

    def test_env_used_when_no_explicit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from onetool.cli_commands.direct_app import _resolve_secrets_path

        config = tmp_path / "onetool.yaml"
        config.write_text("version: 2\n")
        env_file = tmp_path / "env.yaml"
        env_file.write_text("KEY: y\n")
        (tmp_path / "secrets.yaml").write_text("KEY: z\n")
        monkeypatch.setenv("OT_SECRETS_FILE", str(env_file))

        assert _resolve_secrets_path(config, None) == env_file

    def test_config_dir_secrets_used_when_no_explicit_or_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from onetool.cli_commands.direct_app import _resolve_secrets_path

        config = tmp_path / "onetool.yaml"
        config.write_text("version: 2\n")
        candidate = tmp_path / "secrets.yaml"
        candidate.write_text("KEY: z\n")
        monkeypatch.delenv("OT_SECRETS_FILE", raising=False)

        assert _resolve_secrets_path(config, None) == candidate


@pytest.mark.unit
@pytest.mark.core
class TestNeedsLocalHostRebind:
    """Tests for local host context mismatch detection."""

    def test_remote_host_never_rebinds(self) -> None:
        from onetool.cli_commands.direct_app import _needs_local_host_rebind

        assert _needs_local_host_rebind(
            host="example.internal",
            port=8765,
            resolved_config=Path("/tmp/onetool.yaml"),
            resolved_secrets=Path("/tmp/secrets.yaml"),
        ) is False

    def test_no_config_does_not_rebind(self) -> None:
        from onetool.cli_commands.direct_app import _needs_local_host_rebind

        assert _needs_local_host_rebind(
            host="127.0.0.1",
            port=8765,
            resolved_config=None,
            resolved_secrets=Path("/tmp/secrets.yaml"),
        ) is False

    def test_mismatch_rebinds(self) -> None:
        from onetool.cli_commands.direct_app import _needs_local_host_rebind

        with (
            patch("onetool.cli_commands.direct_app._read_pid_file", return_value={
                "pid": 123,
                "config": "/tmp/onetool.yaml",
                "secrets": None,
            }),
            patch("onetool.cli_commands.direct_app._is_process_alive", return_value=True),
        ):
            assert _needs_local_host_rebind(
                host="127.0.0.1",
                port=8765,
                resolved_config=Path("/tmp/onetool.yaml"),
                resolved_secrets=Path("/tmp/secrets.yaml"),
            ) is True

    def test_equivalent_paths_do_not_rebind(self, tmp_path: Path) -> None:
        from onetool.cli_commands.direct_app import _needs_local_host_rebind

        cfg = tmp_path / "onetool.yaml"
        sec = tmp_path / "secrets.yaml"
        cfg.write_text("version: 2\n")
        sec.write_text("KEY: value\n")

        with (
            patch("onetool.cli_commands.direct_app._read_pid_file", return_value={
                "pid": 123,
                "config": str(cfg.resolve()),
                "secrets": str(sec.resolve()),
            }),
            patch("onetool.cli_commands.direct_app._is_process_alive", return_value=True),
        ):
            assert _needs_local_host_rebind(
                host="127.0.0.1",
                port=8765,
                resolved_config=Path(str(cfg)),
                resolved_secrets=Path(str(sec)),
            ) is False


@pytest.mark.unit
@pytest.mark.core
class TestDirectRunAutoHost:
    def test_auto_host_starts_when_missing(self, tmp_path: Path) -> None:
        from onetool.cli_commands.direct_app import direct_run

        config = tmp_path / "onetool.yaml"
        config.write_text("version: 2\n")

        class _Host:
            enabled = True
            port = 8765
            timeout = 120

        class _Direct:
            host = _Host()

        class _Cfg:
            direct = _Direct()

        with (
            patch("onetool.cli_commands.direct_app._resolve_command_source", return_value="ot.version()"),
            patch("onetool.cli_commands.direct_app._resolve_secrets_path", return_value=None),
            patch("onetool.cli_commands.direct_app._tcp_probe", return_value=False),
            patch("onetool.cli_commands.direct_app._start_host") as mock_start,
            patch("onetool.cli_commands.direct_app._run_via_server", return_value=("ok", True)),
            patch("ot.config.loader.get_config", return_value=_Cfg()),
        ):
            with pytest.raises(typer.Exit) as e:
                direct_run(command="ot.version()", config=config, no_host=False)

        assert e.value.exit_code == 0
        mock_start.assert_called_once()
