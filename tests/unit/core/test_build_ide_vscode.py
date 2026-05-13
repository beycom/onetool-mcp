"""Tests for the VS Code extension build helper."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest


def _load_build_module() -> ModuleType:
    script_path = Path(__file__).parents[3] / "scripts" / "build_ide_vscode.py"
    spec = importlib.util.spec_from_file_location("build_ide_vscode", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
@pytest.mark.core
class TestBuildIdeVscode:
    def test_generate_build_version_uses_base_dev_timestamp(self) -> None:
        module = _load_build_module()

        result = module.generate_build_version(
            now=datetime(2026, 5, 13, 8, 15, 30, tzinfo=UTC)
        )

        assert result == "1.0.0-dev.20260513081530"

    def test_generate_build_version_increments_existing_same_or_newer_build(self) -> None:
        module = _load_build_module()

        result = module.generate_build_version(
            now=datetime(2026, 5, 13, 8, 15, 30, tzinfo=UTC),
            current_version="1.0.0-dev.20260513081531",
        )

        assert result == "1.0.0-dev.20260513081532"

    def test_set_extension_version_updates_package_and_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = _load_build_module()
        package_json = tmp_path / "package.json"
        package_lock = tmp_path / "package-lock.json"
        package_json.write_text(
            json.dumps(
                {
                    "name": "onetool-ide-vscode",
                    "publisher": "beycom",
                    "version": "1.0.0",
                }
            )
        )
        package_lock.write_text(
            json.dumps(
                {
                    "name": "onetool-ide-vscode",
                    "version": "1.0.0",
                    "packages": {"": {"version": "1.0.0"}},
                }
            )
        )
        monkeypatch.setattr(module, "PACKAGE_JSON", package_json)
        monkeypatch.setattr(module, "PACKAGE_LOCK", package_lock)

        module.set_extension_version("1.0.0-dev.20260513081530")

        package = json.loads(package_json.read_text())
        lock = json.loads(package_lock.read_text())
        assert package["version"] == "1.0.0-dev.20260513081530"
        assert package["name"] == "onetool-ide-vscode"
        assert package["publisher"] == "beycom"
        assert lock["version"] == "1.0.0-dev.20260513081530"
        assert lock["packages"][""]["version"] == "1.0.0-dev.20260513081530"

    def test_icon_source_lives_in_docs_assets(self) -> None:
        module = _load_build_module()

        assert module.SOURCE_ICON == Path(__file__).parents[3] / "docs" / "assets" / "logo.png"
        assert module.SOURCE_ICON.exists()
