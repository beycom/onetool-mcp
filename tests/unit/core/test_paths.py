"""Unit tests for paths module."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestGetTemplateFiles:
    """Tests for get_template_files()."""

    def test_returns_list_of_tuples(self) -> None:
        """Returns list of (source_path, dest_name) tuples."""
        from ot.paths import get_template_files

        result = get_template_files()

        assert isinstance(result, list)
        if result:  # May be empty in some test environments
            for item in result:
                assert isinstance(item, tuple)
                assert len(item) == 2
                assert isinstance(item[0], Path)
                assert isinstance(item[1], str)

    def test_strips_template_suffix(self) -> None:
        """Dest names have -template suffix stripped."""
        from ot.paths import get_template_files

        result = get_template_files()

        for source_path, dest_name in result:
            # If source has -template, dest should not
            if "-template.yaml" in source_path.name:
                assert "-template" not in dest_name
                assert dest_name.endswith(".yaml")


@pytest.mark.unit
@pytest.mark.core
class TestCreateBackup:
    """Tests for create_backup()."""

    def test_creates_bak_file(self, tmp_path: Path) -> None:
        """First backup creates file.bak."""
        from ot.paths import create_backup

        original = tmp_path / "test.yaml"
        original.write_text("content")

        backup = create_backup(original)

        assert backup.name == "test.yaml.bak"
        assert backup.exists()
        assert backup.read_text() == "content"

    def test_creates_numbered_backup(self, tmp_path: Path) -> None:
        """Subsequent backup creates file.bak.1."""
        from ot.paths import create_backup

        original = tmp_path / "test.yaml"
        original.write_text("content1")

        # Create first backup manually
        first_backup = tmp_path / "test.yaml.bak"
        first_backup.write_text("old content")

        # Create numbered backup
        backup = create_backup(original)

        assert backup.name == "test.yaml.bak.1"
        assert backup.exists()
        assert backup.read_text() == "content1"

    def test_increments_backup_number(self, tmp_path: Path) -> None:
        """Backups increment: .bak, .bak.1, .bak.2, etc."""
        from ot.paths import create_backup

        original = tmp_path / "test.yaml"
        original.write_text("content")

        # Create .bak and .bak.1 manually
        (tmp_path / "test.yaml.bak").write_text("v1")
        (tmp_path / "test.yaml.bak.1").write_text("v2")

        backup = create_backup(original)

        assert backup.name == "test.yaml.bak.2"


@pytest.mark.unit
@pytest.mark.core
class TestPathHelpers:
    """Tests for canonical OneTool file layout helpers."""

    def test_project_state_and_artifact_dirs_use_effective_cwd(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from ot.paths import get_project_artifact_dir, get_project_state_dir

        monkeypatch.setenv("OT_CWD", str(tmp_path))

        assert get_project_state_dir("localhist") == tmp_path / ".onetool" / "state" / "localhist"
        assert get_project_artifact_dir("arch") == tmp_path / "arch"

    def test_ot_scoped_helpers_use_config_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from ot.config.models import OneToolConfig
        from ot.paths import get_ot_data_dir, get_ot_runtime_dir, get_ot_template_dir

        config = OneToolConfig()
        config._config_dir = tmp_path / ".onetool"
        monkeypatch.setattr("ot.config.loader.get_config", lambda: config)

        assert get_ot_runtime_dir("logs") == tmp_path / ".onetool" / "runtime" / "logs"
        assert get_ot_data_dir("mem") == tmp_path / ".onetool" / "data" / "mem"
        assert get_ot_template_dir("arch") == tmp_path / ".onetool" / "templates" / "arch"


@pytest.mark.unit
@pytest.mark.core
class TestEnsureOtDir:
    """Tests for ensure_ot_dir()."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Creates ot dir at config_path.parent."""
        from ot.paths import ensure_ot_dir

        config_path = tmp_path / ".onetool" / "onetool.yaml"
        result = ensure_ot_dir(config_path, quiet=True)

        assert result == tmp_path / ".onetool"
        assert result.exists()

    def test_creates_only_init_subdirectories(self, tmp_path: Path) -> None:
        """Creates init-owned subdirectories and leaves runtime dirs lazy."""
        from ot.paths import ensure_ot_dir

        config_path = tmp_path / ".onetool" / "onetool.yaml"
        ensure_ot_dir(config_path, quiet=True)

        ot_dir = tmp_path / ".onetool"
        assert (ot_dir / "tools").exists()
        assert not (ot_dir / "logs").exists()
        assert not (ot_dir / "stats").exists()
        assert not (ot_dir / "runtime").exists()

    def test_copies_yaml_files(self, tmp_path: Path) -> None:
        """Copies YAML template files flat into ot dir."""
        from ot.paths import ensure_ot_dir

        config_path = tmp_path / ".onetool" / "onetool.yaml"
        ensure_ot_dir(config_path, quiet=True)

        ot_dir = tmp_path / ".onetool"
        assert (ot_dir / "onetool.yaml").exists()
        assert (ot_dir / "secrets.yaml").exists()
        assert not (ot_dir / "skills.md").exists()

    def test_copies_only_explicit_template_dirs(self, tmp_path: Path) -> None:
        """Copies editable template overrides, not package-only resources."""
        from ot.paths import ensure_ot_dir

        config_path = tmp_path / ".onetool" / "onetool.yaml"
        ensure_ot_dir(config_path, quiet=True)

        ot_dir = tmp_path / ".onetool"
        assert (ot_dir / "templates" / "diagram").is_dir()
        assert not (ot_dir / "templates" / "arch").exists()
        assert not (ot_dir / "arch-templates").exists()
        assert not (ot_dir / "diagram-templates").exists()
        assert not (ot_dir / "skills").exists()
        assert not (ot_dir / "tool_templates").exists()
        assert not (ot_dir / "__pycache__").exists()

    def test_existing_dir_preserves_existing_files(self, tmp_path: Path) -> None:
        """Existing files are preserved when force=False."""
        from ot.paths import ensure_ot_dir

        ot_dir = tmp_path / ".onetool"
        ot_dir.mkdir()
        marker = ot_dir / "marker.txt"
        marker.write_text("existing")

        config_path = ot_dir / "onetool.yaml"
        ensure_ot_dir(config_path, quiet=True, force=False)

        assert marker.exists()
