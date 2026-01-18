"""Worker pool for managing persistent tool subprocesses.

Manages worker lifecycle (spawn, call, reap) for external tools that run
in isolated processes with their own dependencies via PEP 723.

Workers communicate via JSON-RPC over stdin/stdout.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class Worker:
    """A persistent worker subprocess."""

    tool_path: Path
    process: subprocess.Popen[str]
    last_used: float = field(default_factory=time.time)
    call_count: int = 0

    def is_alive(self) -> bool:
        """Check if the worker process is still running."""
        return self.process.poll() is None

    def refresh(self) -> None:
        """Update last_used timestamp."""
        self.last_used = time.time()
        self.call_count += 1


class WorkerPool:
    """Manages a pool of persistent worker processes.

    Workers are spawned on first call and reused for subsequent calls.
    Idle workers are reaped after a configurable timeout.
    """

    def __init__(
        self,
        idle_timeout: float = 600.0,
        sdk_path: Path | None = None,
    ) -> None:
        """Initialize the worker pool.

        Args:
            idle_timeout: Seconds of inactivity before reaping worker (default: 10 min)
            sdk_path: Path to ot_sdk package (for --with injection)
        """
        self.idle_timeout = idle_timeout
        self.sdk_path = sdk_path or self._find_sdk_path()
        self._workers: dict[Path, Worker] = {}
        self._lock = threading.Lock()
        self._reaper_thread: threading.Thread | None = None
        self._shutdown = threading.Event()

    def _find_sdk_path(self) -> Path:
        """Find the ot_sdk package path."""
        # Try relative to this file (development)
        dev_path = Path(__file__).parent.parent.parent / "ot_sdk"
        if dev_path.exists():
            return dev_path

        # Fall back to installed package location
        import ot_sdk

        return Path(ot_sdk.__file__).parent

    def _start_reaper(self) -> None:
        """Start the background reaper thread if not already running."""
        if self._reaper_thread is not None and self._reaper_thread.is_alive():
            return

        self._shutdown.clear()
        self._reaper_thread = threading.Thread(
            target=self._reaper_loop,
            daemon=True,
            name="worker-reaper",
        )
        self._reaper_thread.start()

    def _reaper_loop(self) -> None:
        """Background loop that reaps idle workers."""
        while not self._shutdown.wait(timeout=60.0):  # Check every minute
            self._reap_idle_workers()

    def _reap_idle_workers(self) -> None:
        """Terminate workers that have been idle too long."""
        now = time.time()
        to_reap: list[Path] = []

        with self._lock:
            for tool_path, worker in self._workers.items():
                idle_time = now - worker.last_used
                if idle_time > self.idle_timeout:
                    to_reap.append(tool_path)
                elif not worker.is_alive():
                    # Worker crashed, remove from pool
                    to_reap.append(tool_path)
                    logger.warning(f"Worker for {tool_path.name} crashed, removing")

            for tool_path in to_reap:
                worker = self._workers.pop(tool_path)
                if worker.is_alive():
                    logger.info(
                        f"Reaping idle worker {tool_path.name} "
                        f"(idle {now - worker.last_used:.0f}s, {worker.call_count} calls)"
                    )
                    worker.process.terminate()
                    try:
                        worker.process.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        worker.process.kill()

    def _spawn_worker(
        self,
        tool_path: Path,
        _config: dict[str, Any],
        _secrets: dict[str, str],
    ) -> Worker:
        """Spawn a new worker process for a tool.

        Args:
            tool_path: Path to the tool Python file
            _config: Configuration dict (reserved for future use)
            _secrets: Secrets dict (reserved for future use)

        Returns:
            New Worker instance
        """
        # Build uv run command
        cmd = [
            "uv",
            "run",
            str(tool_path),
        ]

        logger.debug(f"Spawning worker: {' '.join(cmd)}")

        # Restricted env: PATH + PYTHONPATH only (not full os.environ)
        # PYTHONPATH includes ot_sdk's parent so "from ot_sdk import ..." works
        sdk_parent = str(self.sdk_path.parent)  # src/ directory
        existing_pythonpath = os.environ.get("PYTHONPATH", "")
        pythonpath = (
            f"{sdk_parent}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else sdk_parent
        )
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": pythonpath,
        }
        # Pass through OT_CWD for path resolution
        if ot_cwd := os.environ.get("OT_CWD"):
            env["OT_CWD"] = ot_cwd

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            env=env,
        )

        worker = Worker(tool_path=tool_path, process=process)
        return worker

    def call(
        self,
        tool_path: Path,
        function: str,
        kwargs: dict[str, Any],
        config: dict[str, Any] | None = None,
        secrets: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> Any:
        """Call a function in a worker process.

        Spawns a new worker if needed, or reuses an existing one.
        Handles worker crashes by respawning.

        Args:
            tool_path: Path to the tool Python file
            function: Function name to call
            kwargs: Keyword arguments for the function
            config: Configuration dict to pass to worker
            secrets: Secrets dict to pass to worker
            timeout: Call timeout in seconds

        Returns:
            Result from the function

        Raises:
            RuntimeError: If worker fails or returns an error
        """
        tool_path = tool_path.resolve()
        config = config or {}
        secrets = secrets or {}

        # Ensure reaper is running
        self._start_reaper()

        with self._lock:
            worker = self._workers.get(tool_path)

            # Check if we need a new worker
            if worker is None or not worker.is_alive():
                if worker is not None:
                    logger.warning(f"Worker for {tool_path.name} died, respawning")
                worker = self._spawn_worker(tool_path, config, secrets)
                self._workers[tool_path] = worker

            worker.refresh()

        # Build JSON-RPC request
        request = {
            "function": function,
            "kwargs": kwargs,
            "config": config,
            "secrets": secrets,
        }
        request_line = json.dumps(request) + "\n"

        # Send request
        try:
            if worker.process.stdin is None:
                raise RuntimeError("Worker stdin is None")
            worker.process.stdin.write(request_line)
            worker.process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            # Worker died during write
            with self._lock:
                self._workers.pop(tool_path, None)
            raise RuntimeError(f"Worker for {tool_path.name} died: {e}") from e

        # Read response with timeout
        try:
            if worker.process.stdout is None:
                raise RuntimeError("Worker stdout is None")

            # Use a simple readline with overall timeout
            # NOTE: select.select() on file objects only works on Unix.
            # For Windows support, consider using threading or asyncio.
            ready, _, _ = select.select([worker.process.stdout], [], [], timeout)
            if not ready:
                raise TimeoutError(f"Worker call timed out after {timeout}s")

            response_line = worker.process.stdout.readline()
            if not response_line:
                # Worker closed stdout (crashed)
                with self._lock:
                    self._workers.pop(tool_path, None)
                raise RuntimeError(f"Worker for {tool_path.name} closed unexpectedly")

            response = json.loads(response_line)

        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON from worker: {e}") from e
        except TimeoutError:
            # Kill the worker and remove from pool
            with self._lock:
                w = self._workers.pop(tool_path, None)
                if w:
                    w.process.kill()
            raise

        # Check for error in response
        if response.get("error"):
            raise RuntimeError(response["error"])

        return response.get("result")

    def shutdown(self) -> None:
        """Shut down all workers and stop the reaper thread."""
        self._shutdown.set()

        with self._lock:
            for tool_path, worker in list(self._workers.items()):
                if worker.is_alive():
                    logger.info(f"Shutting down worker {tool_path.name}")
                    worker.process.terminate()
                    try:
                        worker.process.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        worker.process.kill()
            self._workers.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dict with pool stats (worker count, total calls, etc.)
        """
        with self._lock:
            workers_info = []
            for tool_path, worker in self._workers.items():
                workers_info.append(
                    {
                        "tool": tool_path.name,
                        "alive": worker.is_alive(),
                        "calls": worker.call_count,
                        "idle_seconds": time.time() - worker.last_used,
                    }
                )

            return {
                "worker_count": len(self._workers),
                "idle_timeout": self.idle_timeout,
                "workers": workers_info,
            }


# Global worker pool instance (lazy initialized)
_pool: WorkerPool | None = None


def get_worker_pool() -> WorkerPool:
    """Get or create the global worker pool."""
    global _pool
    if _pool is None:
        _pool = WorkerPool()
    return _pool


def shutdown_worker_pool() -> None:
    """Shut down the global worker pool."""
    global _pool
    if _pool is not None:
        _pool.shutdown()
        _pool = None
