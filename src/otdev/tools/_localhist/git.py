"""Git command wrapper for localhist."""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections import deque
from contextlib import suppress
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from otdev.tools._localhist.config import Paths


class LocalhistGitError(RuntimeError):
    """Raised when a git command fails."""


class GitRunner:
    """Run git commands against an independent database and work tree."""

    def __init__(self, paths: Paths) -> None:
        self.paths = paths

    def run(
        self, *args: str, check: bool = True, extra_env: dict[str, str] | None = None
    ) -> str:
        """Run git with explicit GIT_DIR and GIT_WORK_TREE."""

        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.paths.work_tree,
                env={
                    **os.environ,
                    "GIT_DIR": str(self.paths.git_dir),
                    "GIT_WORK_TREE": str(self.paths.work_tree),
                    **(extra_env or {}),
                },
                check=check,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise LocalhistGitError(message) from exc
        except OSError as exc:
            raise LocalhistGitError(str(exc)) from exc
        return result.stdout

    def run_list(self, args: Sequence[str], *, check: bool = True) -> str:
        """Run git from a prebuilt argument sequence."""

        return self.run(*args, check=check)

    def run_limited(self, args: Sequence[str], *, max_bytes: int) -> tuple[str, bool]:
        """Run git and return stdout capped at max_bytes."""

        if max_bytes < 1:
            raise ValueError("max_bytes must be >= 1")
        try:
            proc = subprocess.Popen(
                ["git", *args],
                cwd=self.paths.work_tree,
                env={
                    **os.environ,
                    "GIT_DIR": str(self.paths.git_dir),
                    "GIT_WORK_TREE": str(self.paths.work_tree),
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise LocalhistGitError(str(exc)) from exc
        stdout = bytearray()
        truncated = False
        assert proc.stdout is not None
        while chunk := proc.stdout.read(min(65536, max_bytes + 1 - len(stdout))):
            stdout.extend(chunk)
            if len(stdout) > max_bytes:
                truncated = True
                proc.kill()
                break
        stderr = proc.stderr.read() if proc.stderr is not None else b""
        return_code = proc.wait()
        if return_code != 0 and not truncated:
            message = (
                stderr.decode(errors="replace").strip()
                or f"git exited with {return_code}"
            )
            raise LocalhistGitError(message)
        data = bytes(stdout[:max_bytes])
        return data.decode(errors="replace"), truncated

    def run_stdout_sha256(self, args: Sequence[str]) -> str | None:
        """Run git and return a SHA-256 digest of stdout without buffering it."""

        try:
            proc = subprocess.Popen(
                ["git", *args],
                cwd=self.paths.work_tree,
                env={
                    **os.environ,
                    "GIT_DIR": str(self.paths.git_dir),
                    "GIT_WORK_TREE": str(self.paths.work_tree),
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise LocalhistGitError(str(exc)) from exc
        digest = sha256()
        has_output = False
        assert proc.stdout is not None
        while chunk := proc.stdout.read(65536):
            has_output = True
            digest.update(chunk)
        stderr = proc.stderr.read() if proc.stderr is not None else b""
        return_code = proc.wait()
        if return_code != 0:
            message = (
                stderr.decode(errors="replace").strip()
                or f"git exited with {return_code}"
            )
            raise LocalhistGitError(message)
        if not has_output:
            return None
        return digest.hexdigest()

    def run_line_window(
        self,
        args: Sequence[str],
        *,
        offset: int,
        limit: int | None,
        tail: int | None,
        max_bytes: int,
    ) -> dict[str, object]:
        """Run git and return a bounded line window from stdout."""

        if max_bytes < 1:
            raise ValueError("max_bytes must be >= 1")
        try:
            proc = subprocess.Popen(
                ["git", *args],
                cwd=self.paths.work_tree,
                env={
                    **os.environ,
                    "GIT_DIR": str(self.paths.git_dir),
                    "GIT_WORK_TREE": str(self.paths.work_tree),
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
            )
        except OSError as exc:
            raise LocalhistGitError(str(exc)) from exc
        assert proc.stdout is not None
        selected: list[str] = []
        tail_lines: deque[str] = deque(maxlen=tail or 0)
        total_lines = 0
        returned_offset = offset
        returned_bytes = 0
        truncated = False
        has_more = False
        for line in proc.stdout:
            total_lines += 1
            if tail is not None:
                tail_lines.append(line)
                continue
            if total_lines < offset:
                continue
            if limit is not None and len(selected) >= limit:
                has_more = True
                proc.kill()
                break
            next_bytes = len(line.encode())
            if returned_bytes + next_bytes > max_bytes:
                truncated = True
                has_more = True
                proc.kill()
                break
            selected.append(line)
            returned_bytes += next_bytes
        if tail is not None:
            selected = list(tail_lines)
            returned_offset = max(total_lines - len(selected) + 1, 1)
            returned_bytes = len("".join(selected).encode())
        stderr = proc.stderr.read() if proc.stderr is not None else ""
        return_code = proc.wait()
        if return_code != 0 and not (truncated or has_more):
            message = stderr.strip() or f"git exited with {return_code}"
            raise LocalhistGitError(message)
        return {
            "content": "".join(selected),
            "total_lines": total_lines,
            "returned_lines": len(selected),
            "offset": returned_offset,
            "has_more": has_more,
            "truncated": truncated,
            "bytes_returned": returned_bytes,
        }

    def run_pathspec_file(
        self,
        args: Sequence[str],
        pathspecs: Sequence[str],
        *,
        check: bool = True,
    ) -> str:
        """Run git with pathspecs passed through a temporary NUL-delimited file."""

        info_dir = self.paths.git_dir / "info"
        info_dir.mkdir(parents=True, exist_ok=True)
        pathspec_file = ""
        try:
            with tempfile.NamedTemporaryFile(
                "wb",
                dir=info_dir,
                prefix="pathspec-",
                delete=False,
            ) as handle:
                pathspec_file = handle.name
                handle.write(b"\0".join(item.encode() for item in pathspecs))
                handle.write(b"\0")
            return self.run_list(
                [
                    args[0],
                    "--pathspec-file-nul",
                    "--pathspec-from-file",
                    pathspec_file,
                    *args[1:],
                ],
                check=check,
            )
        finally:
            if pathspec_file:
                with suppress(FileNotFoundError):
                    Path(pathspec_file).unlink()

    def init_database(self) -> str:
        """Create the independent Git database."""

        try:
            result = subprocess.run(
                ["git", "init", "--bare", str(self.paths.git_dir)],
                cwd=self.paths.work_tree,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise LocalhistGitError(message) from exc
        except OSError as exc:
            raise LocalhistGitError(str(exc)) from exc
        return result.stdout

    def ref_exists(self, ref: str) -> bool:
        """Return whether a ref resolves in the local-history repository."""

        try:
            self.run("rev-parse", "--verify", f"{ref}^{{commit}}")
        except LocalhistGitError:
            return False
        return True

    def has_commits(self) -> bool:
        """Return whether the repository has at least one commit."""

        return self.ref_exists("HEAD")
