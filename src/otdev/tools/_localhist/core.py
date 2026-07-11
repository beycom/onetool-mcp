"""Core localhist operations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from otdev.tools._localhist.config import (
    Config,
    SnapshotKind,
    load_config,
    project_context,
    relpath,
    resolve_paths,
    validate_project_path,
)
from otdev.tools._localhist.git import GitRunner, LocalhistGitError

if TYPE_CHECKING:
    from pathlib import Path

    from otdev.tools._localhist.config import Paths

LOCALHIST_USER_NAME = "OneTool"
LOCALHIST_USER_EMAIL = "localhist@onetool"
MAX_DIFF_BYTES = 1_000_000
MAX_SHOW_BYTES = 1_000_000


def _error(exc: Exception) -> dict[str, object]:
    return {"ok": False, "error": str(exc)}


def _gitignore_entry(config: Config, paths: Paths) -> str | None:
    if paths.git_dir == paths.project_root or paths.project_root not in paths.git_dir.parents:
        return None
    try:
        return paths.git_dir.relative_to(paths.project_root).as_posix().rstrip("/") + "/"
    except ValueError:
        return config.git_dir.rstrip("/") + "/"


def _ensure_nested_gitignore(paths: Paths) -> bool:
    gitignore = paths.git_dir / ".gitignore"
    before = gitignore.read_text() if gitignore.exists() else ""
    after = "*\n!.gitignore\n"
    if before == after:
        return False
    gitignore.parent.mkdir(parents=True, exist_ok=True)
    gitignore.write_text(after)
    return True


def _required_info_excludes(config: Config, paths: Paths) -> list[str]:
    # These directories hold Git metadata, localhist's own database, and
    # localhist runtime state. They are repository machinery, not project
    # content, so snapshots must never stage them.
    rules = [".git/", ".onetool/state/localhist/"]
    entry = _gitignore_entry(config, paths)
    if entry is not None:
        rules.append(entry)
    return rules


def _protected_force_include_prefixes(config: Config, paths: Paths) -> list[str]:
    # Force-includes are applied with `git add -f`, so they can override the
    # localhist-owned excludes above. Keep the same storage paths on a separate
    # denylist so users cannot accidentally snapshot repository internals.
    prefixes = _required_info_excludes(config, paths)
    for path in (paths.git_dir, paths.project_root / ".git", paths.state_dir):
        if path == paths.work_tree or paths.work_tree in path.parents:
            prefixes.append(path.relative_to(paths.work_tree).as_posix().rstrip("/") + "/")
    return list(dict.fromkeys(prefixes))


def _normalize_force_include_rule(rule: str) -> str:
    clean = rule.strip()
    if not clean:
        return ""
    if clean.startswith(":"):
        # Git pathspec magic can express broad matches like `:(glob).git/**`.
        # Force-includes are intentionally plain paths so protected-prefix
        # checks remain exact and reviewable.
        raise ValueError("force-include rules must be literal project-relative paths")
    normalized = PurePosixPath(clean.lstrip("/")).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized in {"", "."} or normalized.startswith("../"):
        raise ValueError(f"force-include rule must stay inside the work tree: {rule}")
    return normalized


def _validate_force_include_rules(config: Config, paths: Paths, rules: list[str]) -> list[str]:
    protected = _protected_force_include_prefixes(config, paths)
    validated: list[str] = []
    for rule in rules:
        normalized = _normalize_force_include_rule(rule)
        if not normalized:
            continue
        for prefix in protected:
            directory = prefix.rstrip("/")
            if normalized == directory or normalized.startswith(prefix):
                raise ValueError(f"force-include rule targets protected localhist path: {rule}")
        validated.append(normalized)
    return validated


def _literal_pathspec_prefix(pathspec: str) -> str:
    parts: list[str] = []
    for part in PurePosixPath(pathspec).parts:
        if any(char in part for char in "*?["):
            break
        parts.append(part)
    return PurePosixPath(*parts).as_posix() if parts else ""


def _validate_snapshot_pathspecs(
    config: Config,
    paths: Paths,
    pathspecs: str | list[str] | None,
) -> list[str]:
    if pathspecs is None:
        return []
    raw_pathspecs = [pathspecs] if isinstance(pathspecs, str) else pathspecs
    protected = _protected_force_include_prefixes(config, paths)
    validated: list[str] = []
    for raw in raw_pathspecs:
        clean = raw.strip()
        if not clean:
            raise ValueError("paths entries must not be empty")
        if clean.startswith(":"):
            raise ValueError("paths entries must not use Git pathspec magic")
        normalized = PurePosixPath(clean).as_posix()
        if PurePosixPath(normalized).is_absolute() or clean.startswith("/"):
            raise ValueError(f"paths entries must be project-relative: {raw}")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized in {"", "."}:
            raise ValueError("paths entries must not target the whole work tree")
        if ".." in PurePosixPath(normalized).parts:
            raise ValueError(f"paths entries must stay inside the work tree: {raw}")
        literal_prefix = _literal_pathspec_prefix(normalized)
        for prefix in protected:
            directory = prefix.rstrip("/")
            if (
                normalized == directory
                or normalized.startswith(prefix)
                or literal_prefix == directory
                or literal_prefix.startswith(prefix)
            ):
                raise ValueError(f"paths entry targets protected localhist path: {raw}")
        validated.append(normalized.rstrip("/"))
    return list(dict.fromkeys(validated))


def _append_info_exclude(paths: Path, patterns: list[str]) -> int:
    exclude = _info_file(paths, "exclude")
    added = _append_rules(exclude, patterns)["added"]
    return added if isinstance(added, int) else 0


def _ensure_force_include_file(paths: Paths) -> Path:
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    if not paths.force_include_file.exists():
        paths.force_include_file.write_text("")
    return paths.force_include_file


def _info_file(git_dir: Path, name: str) -> Path:
    info = git_dir / "info"
    info.mkdir(parents=True, exist_ok=True)
    path = info / name
    if not path.exists():
        path.write_text("")
    return path


def _append_rules(path: Path, rules: list[str]) -> dict[str, object]:
    lines = path.read_text().splitlines() if path.exists() else []
    before = "\n".join(lines).rstrip() + ("\n" if lines else "")
    added_rules: list[str] = []
    unchanged_rules: list[str] = []
    for rule in rules:
        clean = rule.strip()
        if clean and clean not in lines:
            lines.append(clean)
            added_rules.append(clean)
        elif clean:
            unchanged_rules.append(clean)
    after = "\n".join(lines).rstrip() + ("\n" if lines else "")
    path.write_text(after)
    return {
        "added": len(added_rules),
        "added_rules": added_rules,
        "unchanged_rules": unchanged_rules,
        "before": before,
        "after": after,
        "changed": before != after,
    }


def _read_rules(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _repo_info(config: Config) -> dict[str, str]:
    paths = resolve_paths(config)
    exclude = paths.git_dir / "info" / "exclude"
    return {
        "project_root": str(paths.project_root),
        "git_dir": str(paths.git_dir),
        "work_tree": str(paths.work_tree),
        "state_dir": str(paths.state_dir),
        "exclude_file": str(exclude),
        "force_include_file": str(paths.force_include_file),
        "inspect_command": (
            f"GIT_DIR={paths.git_dir} GIT_WORK_TREE={paths.work_tree} git status"
        ),
    }


def _commit_details(git: GitRunner, ref: str = "HEAD") -> dict[str, str]:
    output = git.run(
        "log",
        "-1",
        "--format=%H%x00%h%x00%ct%x00%s%x00%B",
        ref,
    )
    full, short, timestamp, subject, body = [*output.split("\x00", 4), ""][:5]
    kind = ""
    for line in body.splitlines():
        if line.startswith("Localhist-Kind: "):
            kind = line.removeprefix("Localhist-Kind: ").strip()
            break
    return {
        "hash": full,
        "short_hash": short,
        "timestamp": timestamp,
        "subject": subject,
        "kind": kind,
    }


def _status_output(git: GitRunner, path: str | None = None) -> str:
    args = ["status", "--porcelain", "--untracked-files=all"]
    if path is not None:
        args.extend(["--", path])
    return git.run_list(args)


def repository_dirty_signature() -> str | None:
    """Return a stable signature for the current dirty worktree state."""

    config = load_config()
    paths = resolve_paths(config)
    if not (paths.git_dir / "HEAD").exists():
        return None
    git = GitRunner(paths)
    return git.run_stdout_sha256(["status", "--porcelain", "--untracked-files=all"])


def _dirty_counts_from_status(output: str) -> dict[str, int]:
    tracked = 0
    untracked = 0
    for line in output.splitlines():
        if line.startswith("??"):
            untracked += 1
        else:
            tracked += 1
    return {"tracked": tracked, "untracked": untracked, "total": tracked + untracked}


def _status_entries_from_status(output: str, *, limit: int | None = None) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in output.splitlines():
        if limit is not None and len(entries) >= limit:
            break
        status = line[:2]
        path = line[3:]
        entries.append({"status": status, "path": path})
    return entries


def _resolve_commit(git: GitRunner, ref: str) -> str:
    return git.run("rev-parse", "--verify", f"{ref}^{{commit}}").strip()


def _format_timestamp(timestamp: str, date_format: str) -> str:
    return datetime.fromtimestamp(int(timestamp), tz=UTC).astimezone().strftime(date_format)


def _parse_log_entries(
    output: str,
    *,
    date_format: str,
    path: str | None = None,
    follow: bool | None = None,
) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for record in output.split("\x1e"):
        if not record.strip():
            continue
        full, short, timestamp, subject, body = [*record.strip("\n").split("\x00", 4), ""][:5]
        kind = ""
        for body_line in body.splitlines():
            if body_line.startswith("Localhist-Kind: "):
                kind = body_line.removeprefix("Localhist-Kind: ").strip()
                break
        entry: dict[str, object] = {
            "hash": full,
            "short_hash": short,
            "timestamp": timestamp,
            "date": _format_timestamp(timestamp, date_format),
            "subject": subject,
            "kind": kind,
        }
        if path is not None:
            entry["path"] = path
            entry["follow"] = follow
        entries.append(entry)
    return entries


def init_repository() -> dict[str, object]:
    """Initialize the local-history Git database."""

    try:
        config = load_config()
        paths = resolve_paths(config)
        already_initialized = (paths.git_dir / "HEAD").exists()
        git = GitRunner(paths)
        if not already_initialized:
            paths.git_dir.mkdir(parents=True, exist_ok=True)
            git.init_database()
            git.run("config", "core.bare", "false")
            git.run("config", "core.worktree", str(paths.work_tree))
        git.run("config", "user.name", LOCALHIST_USER_NAME)
        git.run("config", "user.email", LOCALHIST_USER_EMAIL)
        git.run("config", "commit.gpgsign", "false")
        ignore_added = _ensure_nested_gitignore(paths)
        exclude_added = _append_info_exclude(paths.git_dir, _required_info_excludes(config, paths))
        _ensure_force_include_file(paths)
        return {
            "ok": True,
            "initialized": True,
            "created": not already_initialized,
            "already_initialized": already_initialized,
            "exclude_entries_added": exclude_added,
            "gitignore_updated": ignore_added,
            **_repo_info(config),
        }
    except Exception as exc:
        return _error(exc)


def status_repository(
    *,
    path: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> dict[str, object]:
    """Return Git-like local-history working-tree status."""

    try:
        if limit is not None and limit < 1:
            return {"ok": False, "error": "limit must be >= 1"}
        config = load_config()
        paths = resolve_paths(config)
        rel = relpath(validate_project_path(path, paths), paths) if path is not None else None
        if not (paths.git_dir / "HEAD").exists():
            return {
                "ok": True,
                "initialized": False,
                "has_commits": False,
                "dirty": {"tracked": 0, "untracked": 0, "total": 0},
                "files": [],
                "total_files": 0,
                "truncated": False,
            }
        git = GitRunner(paths)
        status_output = _status_output(git, rel)
        all_files = _status_entries_from_status(status_output)
        if status is not None:
            if status not in {"tracked", "untracked", "modified", "deleted", "added"}:
                return {"ok": False, "error": "status must be tracked, untracked, modified, deleted, or added"}
            all_files = [entry for entry in all_files if _status_category(entry["status"]) == status]
        total_files = len(all_files)
        files = all_files[:limit] if limit is not None else all_files
        return {
            "ok": True,
            "initialized": True,
            "has_commits": git.has_commits(),
            "dirty": _dirty_counts_from_status(status_output),
            "files": files,
            "path": rel,
            "status_filter": status,
            "total_files": total_files,
            "truncated": len(files) < total_files,
        }
    except Exception as exc:
        return _error(exc)


def _status_category(raw: str) -> str:
    if raw.startswith("??"):
        return "untracked"
    if "D" in raw:
        return "deleted"
    if "A" in raw:
        return "added"
    if "M" in raw:
        return "modified"
    return "tracked"


def info_repository() -> dict[str, object]:
    """Return local-history repository metadata and configuration."""

    try:
        config = load_config()
        paths = resolve_paths(config)
        initialized = (paths.git_dir / "HEAD").exists()
        result: dict[str, object] = {
            "ok": True,
            "initialized": initialized,
            "config": config.model_dump(),
            **_repo_info(config),
        }
        exclude = paths.git_dir / "info" / "exclude"
        result["exclude_rules"] = _read_rules(exclude)
        result["force_include_rules"] = _read_rules(paths.force_include_file)
        if not initialized:
            result["has_commits"] = False
            result["head"] = None
            result["branch"] = None
            return result
        git = GitRunner(paths)
        has_commits = git.has_commits()
        result["has_commits"] = has_commits
        if has_commits:
            result["head"] = _commit_details(git)
            result["branch"] = git.run("branch", "--show-current").strip()
        else:
            result["head"] = None
            result["branch"] = None
        return result
    except Exception as exc:
        return _error(exc)


def _pathspec_matches_scope(rule: str, scoped_paths: list[str]) -> bool:
    rule_clean = rule.rstrip("/")
    for scoped in scoped_paths:
        scoped_clean = scoped.rstrip("/")
        scoped_has_glob = any(char in scoped_clean for char in "*?[")
        rule_has_glob = any(char in rule_clean for char in "*?[")
        rule_literal_prefix = _literal_pathspec_prefix(rule_clean)
        if (
            rule_clean == scoped_clean
            or rule_clean.startswith(scoped_clean + "/")
            or scoped_clean.startswith(rule_clean + "/")
            or (scoped_has_glob and PurePosixPath(rule_clean).match(scoped_clean))
            or (rule_has_glob and PurePosixPath(scoped_clean).match(rule_clean))
            or (
                rule_has_glob
                and rule_literal_prefix
                and (
                    scoped_clean == rule_literal_prefix
                    or scoped_clean.startswith(rule_literal_prefix + "/")
                )
            )
        ):
            return True
    return False


def _stage_snapshot(
    git: GitRunner,
    config: Config,
    paths: Paths,
    *,
    scoped_paths: list[str],
) -> None:
    # Repair required excludes on every snapshot, not only init. If a project
    # .gitignore or localhist exclude file is edited between autosaves, staging
    # still must not recurse into Git/localhist storage.
    _append_info_exclude(paths.git_dir, _required_info_excludes(config, paths))
    if scoped_paths:
        # A scoped path can be fully ignored and later recovered by a matching
        # force-include. Let normal staging fail quietly in that case.
        git.run_pathspec_file(["add", "-A"], scoped_paths, check=False)
    else:
        git.run("add", "-A", "--", ".")
    force_rules = _read_rules(paths.force_include_file)
    if scoped_paths:
        force_rules = [
            rule for rule in force_rules if _pathspec_matches_scope(rule, scoped_paths)
        ]
    if force_rules:
        git.run_pathspec_file(["add", "-f"], force_rules)


def create_snapshot(
    *,
    message: str,
    kind: SnapshotKind,
    pathspecs: str | list[str] | None = None,
) -> dict[str, object]:
    """Create a local-history snapshot."""

    if not message.strip():
        return {"ok": False, "error": "message is required"}
    config = load_config()
    paths = resolve_paths(config)
    if not (paths.git_dir / "HEAD").exists():
        init_result = init_repository()
        if not init_result.get("ok"):
            return init_result
    scoped_paths = _validate_snapshot_pathspecs(config, paths, pathspecs)
    git = GitRunner(paths)
    git.run("reset")
    _stage_snapshot(git, config, paths, scoped_paths=scoped_paths)
    status = git.run("diff", "--cached", "--name-only")
    if not status.strip():
        return {
            "ok": True,
            "created": False,
            "reason": "no_changes",
            "changed_count": 0,
            "paths": scoped_paths,
            **_repo_info(config),
        }
    commit_message = f"{message.strip()}\n\nLocalhist-Kind: {kind or 'manual'}"
    git.run("commit", "-m", commit_message)
    details = _commit_details(git)
    return {
        "ok": True,
        "created": True,
        "commit": details,
        "changed_count": len(status.splitlines()),
        "paths": scoped_paths,
        **_repo_info(config),
    }


def save_snapshot(
    *,
    message: str,
    kind: SnapshotKind,
    paths: str | list[str] | None = None,
) -> dict[str, object]:
    """Save a manual or restore snapshot."""

    try:
        return create_snapshot(message=message, kind=kind, pathspecs=paths)
    except Exception as exc:
        return _error(exc)


def save_snapshot_for_project(*, project_root: Path, message: str, kind: SnapshotKind) -> dict[str, object]:
    """Save a snapshot with path and config resolved for a specific project."""

    with project_context(project_root):
        return save_snapshot(message=message, kind=kind)


def list_log(*, limit: int, date_format: str = "%Y-%m-%d %H:%M:%S %Z") -> dict[str, object]:
    """List local-history commits."""

    try:
        if limit < 1:
            return {"ok": False, "error": "limit must be >= 1"}
        config = load_config()
        paths = resolve_paths(config)
        if not (paths.git_dir / "HEAD").exists():
            return {"ok": True, "initialized": False, "entries": []}
        git = GitRunner(paths)
        if not git.has_commits():
            return {"ok": True, "initialized": True, "entries": []}
        output = git.run(
            "log",
            f"-{limit}",
            "--format=%x1e%H%x00%h%x00%ct%x00%s%x00%B",
        )
        entries = _parse_log_entries(output, date_format=date_format)
        return {"ok": True, "initialized": True, "entries": entries}
    except Exception as exc:
        return _error(exc)


def list_history(
    *,
    path: str,
    limit: int,
    follow: bool,
    date_format: str = "%Y-%m-%d %H:%M:%S %Z",
) -> dict[str, object]:
    """List local-history commits that touched one path."""

    try:
        if limit < 1:
            return {"ok": False, "error": "limit must be >= 1"}
        config = load_config()
        paths = resolve_paths(config)
        rel = relpath(validate_project_path(path, paths), paths)
        if not (paths.git_dir / "HEAD").exists():
            return {"ok": True, "initialized": False, "path": rel, "follow": follow, "entries": []}
        git = GitRunner(paths)
        if not git.has_commits():
            return {"ok": True, "initialized": True, "path": rel, "follow": follow, "entries": []}
        args = ["log", f"-{limit}", "--format=%x1e%H%x00%h%x00%ct%x00%s%x00%B"]
        if follow:
            args.append("--follow")
        args.extend(["--", rel])
        output = git.run_list(args)
        entries = _parse_log_entries(output, date_format=date_format, path=rel, follow=follow)
        return {"ok": True, "initialized": True, "path": rel, "follow": follow, "entries": entries}
    except Exception as exc:
        return _error(exc)


def _validate_ref(git: GitRunner, ref: str) -> str | None:
    if not git.ref_exists(ref):
        return f"ref not found: {ref}"
    return None


def diff_snapshot(*, ref: str, against: str | None, path: str | None) -> dict[str, object]:
    """Return a diff for a local-history ref."""

    try:
        config = load_config()
        paths = resolve_paths(config)
        git = GitRunner(paths)
        if error := _validate_ref(git, ref):
            return {"ok": False, "error": error}
        mode = "snapshot"
        if against is None:
            args = ["diff", f"{ref}^!", "--"]
        elif against == "worktree":
            mode = "worktree"
            args = ["diff", ref, "--"]
        else:
            if error := _validate_ref(git, against):
                return {"ok": False, "error": error}
            mode = "ref"
            args = ["diff", ref, against, "--"]
        if path is not None:
            target = validate_project_path(path, paths)
            args.append(relpath(target, paths))
        output, truncated = git.run_limited(args, max_bytes=MAX_DIFF_BYTES)
        return {
            "ok": True,
            "ref": ref,
            "against": against,
            "mode": mode,
            "diff": output,
            "truncated": truncated,
            "max_bytes": MAX_DIFF_BYTES,
            "bytes_returned": len(output.encode()),
        }
    except Exception as exc:
        return _error(exc)


def show_file(
    *,
    ref: str,
    path: str,
    offset: int = 1,
    limit: int | None = None,
    tail: int | None = None,
) -> dict[str, object]:
    """Return file content from a local-history ref."""

    try:
        if offset < 1:
            return {"ok": False, "error": "offset must be >= 1"}
        if limit is not None and limit < 1:
            return {"ok": False, "error": "limit must be >= 1"}
        if tail is not None and tail < 1:
            return {"ok": False, "error": "tail must be >= 1"}
        if tail is not None and limit is not None:
            return {"ok": False, "error": "tail cannot be combined with limit"}
        config = load_config()
        paths = resolve_paths(config)
        target = validate_project_path(path, paths)
        rel = relpath(target, paths)
        git = GitRunner(paths)
        if error := _validate_ref(git, ref):
            return {"ok": False, "error": error}
        window = git.run_line_window(
            ["show", f"{ref}:{rel}"],
            offset=offset,
            limit=limit,
            tail=tail,
            max_bytes=MAX_SHOW_BYTES,
        )
        return {
            "ok": True,
            "ref": ref,
            "path": rel,
            "content": window["content"],
            "total_lines": window["total_lines"],
            "returned_lines": window["returned_lines"],
            "offset": window["offset"],
            "limit": limit,
            "tail": tail,
            "has_more": window["has_more"],
            "truncated": window["truncated"],
            "max_bytes": MAX_SHOW_BYTES,
            "bytes_returned": window["bytes_returned"],
        }
    except Exception as exc:
        return _error(exc)


def _paths_changed_against_head(git: GitRunner, rel_paths: list[str]) -> bool:
    try:
        output = git.run_list(["status", "--porcelain", "--", *rel_paths])
    except LocalhistGitError:
        return False
    return bool(output.strip())


def restore_paths(
    *,
    ref: str,
    paths: list[str],
    dry_run: bool,
) -> dict[str, object]:
    """Restore selected paths from a snapshot."""

    try:
        if not paths:
            return {"ok": False, "error": "restore requires explicit paths"}
        config = load_config()
        resolved = resolve_paths(config)
        rel_paths = [relpath(validate_project_path(item, resolved), resolved) for item in paths]
        git = GitRunner(resolved)
        if error := _validate_ref(git, ref):
            return {"ok": False, "error": error}
        resolved_ref = _resolve_commit(git, ref)
        changed = git.run_list(["diff", "--name-only", resolved_ref, "--", *rel_paths]).splitlines()
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "ref": resolved_ref,
                "requested_ref": ref,
                "paths": rel_paths,
                "would_change": changed,
            }
        pre_restore_snapshot = None
        if _paths_changed_against_head(git, rel_paths):
            pre_restore_snapshot = create_snapshot(
                message=f"pre-restore safety before {resolved_ref}",
                kind="restore",
            )
        git.run_pathspec_file(["checkout", resolved_ref], rel_paths)
        audit_snapshot = create_snapshot(message=f"restore from {resolved_ref}", kind="restore")
        return {
            "ok": True,
            "dry_run": False,
            "ref": resolved_ref,
            "requested_ref": ref,
            "paths": rel_paths,
            "changed": changed,
            "pre_restore_snapshot": pre_restore_snapshot,
            "restore_snapshot": audit_snapshot,
        }
    except Exception as exc:
        return _error(exc)


def append_exclude_rules(*, rules: list[str]) -> dict[str, object]:
    """Append localhist-only exclude rules."""

    try:
        config = load_config()
        paths = resolve_paths(config)
        if not (paths.git_dir / "HEAD").exists():
            init_result = init_repository()
            if not init_result.get("ok"):
                return init_result
        exclude = _info_file(paths.git_dir, "exclude")
        mutation = _append_rules(exclude, rules)
        return {
            "ok": True,
            **mutation,
            "rules": _read_rules(exclude),
            "config_file": str(exclude),
            "initialized": True,
            **_repo_info(config),
        }
    except Exception as exc:
        return _error(exc)


def append_force_include_rules(*, rules: list[str]) -> dict[str, object]:
    """Append force-include pathspec rules."""

    try:
        config = load_config()
        paths = resolve_paths(config)
        if not (paths.git_dir / "HEAD").exists():
            init_result = init_repository()
            if not init_result.get("ok"):
                return init_result
        force_include = _ensure_force_include_file(paths)
        mutation = _append_rules(force_include, _validate_force_include_rules(config, paths, rules))
        return {
            "ok": True,
            **mutation,
            "rules": _read_rules(force_include),
            "config_file": str(force_include),
            "initialized": True,
            **_repo_info(config),
        }
    except Exception as exc:
        return _error(exc)
