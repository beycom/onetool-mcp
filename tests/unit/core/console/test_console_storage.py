"""Tests for Console instance storage lifecycle."""

from __future__ import annotations

import pytest

from ot.console.storage import (
    cleanup_console_instance,
    console_instance_dir,
    console_instances_dir,
    initialize_console_storage,
)


@pytest.mark.unit
@pytest.mark.core
class TestConsoleStorageLifecycle:
    """Console body directories remain scoped to a live runtime instance."""

    def test_startup_sweeps_sibling_instances(self) -> None:
        instances = console_instances_dir()
        stale = instances / "mcp-stale" / "messages"
        stale.mkdir(parents=True)
        (stale / "old.json").write_text("{}", encoding="utf-8")

        initialize_console_storage(instance_id="mcp-current")

        assert not (instances / "mcp-stale").exists()
        assert console_instance_dir(instance_id="mcp-current").is_dir()

    def test_cleanup_removes_current_instance(self) -> None:
        initialize_console_storage(instance_id="mcp-current")

        cleanup_console_instance(instance_id="mcp-current")

        assert not console_instance_dir(instance_id="mcp-current").exists()

    def test_sweep_preserves_sibling_with_live_owner(self) -> None:
        import os

        instances = console_instances_dir()
        live = instances / "mcp-live"
        live.mkdir(parents=True)
        (live / "pid").write_text(str(os.getpid()), encoding="utf-8")
        (live / "messages").mkdir()

        initialize_console_storage(instance_id="mcp-current")

        assert live.is_dir(), "sibling owned by a live process must survive the sweep"
        assert (live / "messages").is_dir()

    def test_sweep_removes_sibling_with_dead_owner(self) -> None:
        instances = console_instances_dir()
        dead = instances / "mcp-dead"
        dead.mkdir(parents=True)
        # PID unlikely to be alive: max pid space on macOS/Linux is far below this
        (dead / "pid").write_text("999999999", encoding="utf-8")

        initialize_console_storage(instance_id="mcp-current")

        assert not dead.exists()

    def test_sweep_removes_sibling_with_garbage_pid_file(self) -> None:
        instances = console_instances_dir()
        garbage = instances / "mcp-garbage"
        garbage.mkdir(parents=True)
        (garbage / "pid").write_text("not-a-pid", encoding="utf-8")

        initialize_console_storage(instance_id="mcp-current")

        assert not garbage.exists()

    def test_initialize_writes_own_pid_file(self) -> None:
        import os

        initialize_console_storage(instance_id="mcp-current")

        pid_file = console_instance_dir(instance_id="mcp-current") / "pid"
        assert pid_file.read_text(encoding="utf-8") == str(os.getpid())
