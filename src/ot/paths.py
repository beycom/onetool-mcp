"""Path resolution for OneTool directories.

OneTool uses an explicit config-file model:
- The "ot dir" is ``config_path.parent`` — all relative paths resolve there.
- There is no global ``~/.onetool/`` directory or environment-variable fallback.
- Pass ``--config <file>`` to every command to specify the config location.

Each .onetool/ directory uses subdirectories to organise files by purpose:
- tools/ — Custom tool packs
- runtime/ — Logs, stats, sessions, and reports
- data/ — Tool-owned config-scoped data stores
- templates/ — Editable overrides for packaged templates

Directories are created lazily on first use via ``ensure_ot_dir()``.
Only explicitly user-editable templates in ot.config.global_templates are copied
to the ot dir on init.
"""

from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path

# Subdirectory names within .onetool/
RUNTIME_SUBDIR = "runtime"
DATA_SUBDIR = "data"
TEMPLATES_SUBDIR = "templates"
TOOLS_SUBDIR = "tools"

INIT_TEMPLATE_FILES = (
    "onetool.yaml",
    "secrets-template.yaml",
    "servers.yaml",
    "snippets.yaml",
    "prompts.yaml",
    "security.yaml",
    "diagram.yaml",
)
INIT_TEMPLATE_DIRS = {
    "diagram-templates": "templates/diagram",
}

# Package containing global templates (copied to ot dir on init)
GLOBAL_TEMPLATES_PACKAGE = "ot.config.global_templates"


def _resolve_package_dir(package_name: str, description: str) -> Path:
    """Resolve a package to a filesystem directory path.

    Uses importlib.resources to access package data. Works correctly across:
    - Regular pip/uv install (wheel)
    - Editable install (uv tool install -e .)
    - Development mode

    Args:
        package_name: Dotted package name (e.g., "ot.config.global_templates")
        description: Human-readable description for error messages

    Returns:
        Path to package directory (read-only package data)

    Raises:
        FileNotFoundError: If package is not found or not on filesystem
    """
    try:
        files = resources.files(package_name)
    except (ModuleNotFoundError, TypeError) as e:
        raise FileNotFoundError(
            f"{description} package not found: {package_name}. "
            "Ensure onetool is properly installed."
        ) from e

    # Try multiple approaches to get a filesystem path from the Traversable.
    # importlib.resources returns different types depending on install mode:
    # - Regular install: pathlib.Path-like object
    # - Editable install: MultiplexedPath (internal type)
    # - Zipped package: ZipPath (would need extraction)

    # Approach 1: Direct _path attribute (MultiplexedPath in editable installs)
    if hasattr(files, "_path"):
        path = Path(files._path)
        if path.is_dir():
            return path

    # Approach 2: String conversion (works for regular Path-like objects)
    path_str = str(files)

    # Skip if it looks like a repr() output rather than a path
    if not path_str.startswith(("MultiplexedPath(", "<", "{")):
        path = Path(path_str)
        if path.is_dir():
            return path

    # Approach 3: Extract path from MultiplexedPath repr as last resort
    if path_str.startswith("MultiplexedPath("):
        import re

        match = re.search(r"'([^']+)'", path_str)
        if match:
            path = Path(match.group(1))
            if path.is_dir():
                return path

    # If we get here, the package exists but isn't on a real filesystem
    # (e.g., inside a zipfile). This is not supported.
    raise FileNotFoundError(
        f"{description} directory exists but is not on filesystem: {path_str}. "
        "OneTool requires installation from an unpacked wheel, not a zipfile."
    )


def get_global_templates_dir() -> Path:
    """Get the global templates directory path.

    Global templates are user-facing config files with commented examples,
    copied to the ot dir on init. These provide documentation and examples
    for configuration. Also contains packaged resource subdirectories like
    diagram-templates/ and tool_templates/.

    Returns:
        Path to global templates directory (read-only package data)

    Raises:
        FileNotFoundError: If global templates package is not found or not on filesystem
    """
    return _resolve_package_dir(GLOBAL_TEMPLATES_PACKAGE, "Global templates")


def get_config_dir() -> Path:
    """Return the OT config directory (.onetool/).

    Single point of access for config._config_dir. Use this instead of
    get_config()._config_dir at call sites.

    Returns:
        Path to the .onetool config directory
    """
    from ot.config.loader import get_config

    return get_config()._config_dir


def _validate_relative_fragment(value: str, *, label: str) -> Path:
    """Return a clean relative path fragment for OneTool-owned subtrees."""
    path = Path(value)
    if not value or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} must be a non-empty relative path fragment: {value!r}")
    return path


def get_ot_runtime_dir(kind: str) -> Path:
    """Return a runtime directory under OT_DIR/runtime/."""
    return get_config_dir() / RUNTIME_SUBDIR / _validate_relative_fragment(kind, label="runtime kind")


def get_ot_data_dir(kind: str) -> Path:
    """Return a tool-owned data directory under OT_DIR/data/."""
    return get_config_dir() / DATA_SUBDIR / _validate_relative_fragment(kind, label="data kind")


def get_ot_template_dir(kind: str) -> Path:
    """Return an editable template override directory under OT_DIR/templates/."""
    return get_config_dir() / TEMPLATES_SUBDIR / _validate_relative_fragment(kind, label="template kind")


def get_project_state_dir(pack: str) -> Path:
    """Return a project-local pack state directory under CWD/.onetool/state/."""
    return get_effective_cwd() / ".onetool" / "state" / _validate_relative_fragment(pack, label="pack")


def get_project_artifact_dir(kind: str) -> Path:
    """Return a generated artifact directory under the effective project CWD."""
    return get_effective_cwd() / _validate_relative_fragment(kind, label="artifact kind")


def get_effective_cwd() -> Path:
    """Get the effective working directory.

    Returns OT_CWD if set, else Path.cwd(). This provides a single point
    of control for working directory resolution across all CLIs.

    Returns:
        Resolved Path for working directory
    """
    env_cwd = os.getenv("OT_CWD")
    if env_cwd:
        return Path(env_cwd).resolve()
    return Path.cwd()


def get_template_files() -> list[tuple[Path, str]]:
    """Get list of template files that would be copied to ot dir on init.

    Returns:
        List of (source_path, dest_name) tuples for each template file.
        dest_name has -template suffix stripped (e.g., secrets-template.yaml -> secrets.yaml)
    """
    try:
        templates_dir = get_global_templates_dir()
        result = []
        for name in INIT_TEMPLATE_FILES:
            config_file = templates_dir / name
            if not config_file.is_file():
                continue
            dest_name = config_file.name.replace("-template.yaml", ".yaml")
            result.append((config_file, dest_name))
        return result
    except FileNotFoundError:
        return []


def create_backup(file_path: Path) -> Path:
    """Create a numbered backup of a file.

    Creates backups as file.bak, file.bak.1, file.bak.2, etc.

    Args:
        file_path: Path to the file to backup

    Returns:
        Path to the created backup file
    """
    backup_base = file_path.with_suffix(file_path.suffix + ".bak")

    # Find the next available backup number
    if not backup_base.exists():
        backup_path = backup_base
    else:
        n = 1
        while True:
            backup_path = backup_base.with_suffix(f".bak.{n}")
            if not backup_path.exists():
                break
            n += 1

    import shutil

    shutil.copy2(file_path, backup_path)
    return backup_path


def ensure_ot_dir(config_path: Path, quiet: bool = False, force: bool = False) -> Path:
    """Ensure the OneTool directory exists at config_path.parent.

    Creates config_path.parent with the tools/ subdirectory, copies explicit
    user-editable config files from global_templates into it, and copies
    explicit editable template override directories under templates/.

    Args:
        config_path: Path to the onetool.yaml config file (directory is config_path.parent)
        quiet: Suppress creation messages
        force: Overwrite existing files (for reset functionality)

    Returns:
        Path to ot dir (config_path.parent)
    """
    import shutil

    ot_dir = config_path.parent

    import stat

    ot_dir.mkdir(parents=True, exist_ok=True)
    subdirs = [TOOLS_SUBDIR]
    for subdir in subdirs:
        (ot_dir / subdir).mkdir(exist_ok=True)

    copied_items: list[str] = []
    try:
        templates_dir = get_global_templates_dir()
        for name in INIT_TEMPLATE_FILES:
            config_file = templates_dir / name
            if not config_file.is_file():
                continue
            dest_name = config_file.name.replace("-template.yaml", ".yaml")
            dest = ot_dir / dest_name
            if not dest.exists() or force:
                shutil.copy(config_file, dest)
                if dest_name == "secrets.yaml":
                    dest.chmod(stat.S_IRUSR | stat.S_IWUSR)
                copied_items.append(dest_name)

        for src_name, dest_name in INIT_TEMPLATE_DIRS.items():
            template_subdir = templates_dir / src_name
            if not template_subdir.is_dir():
                continue
            dest_subdir = ot_dir / dest_name
            if not dest_subdir.exists() or force:
                if dest_subdir.exists():
                    shutil.rmtree(dest_subdir)
                dest_subdir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(template_subdir, dest_subdir)
                copied_items.append(f"{dest_name}/")
    except FileNotFoundError:
        # Global templates not available (dev environment without package install)
        pass

    if not quiet:
        # Use stderr to avoid interfering with MCP stdout
        action = "Resetting" if force else "Creating"
        print(f"{action} {ot_dir}/", file=sys.stderr)
        for subdir in subdirs:
            print(f"  ✓ {subdir}/", file=sys.stderr)
        for item_name in copied_items:
            print(f"  ✓ {item_name}", file=sys.stderr)

    return ot_dir


def get_logs_dir(base_dir: Path) -> Path:
    """Get the logs directory path within an ot dir.

    Args:
        base_dir: Base ot directory (config_path.parent)

    Returns:
        Path to logs/ subdirectory
    """
    return base_dir / RUNTIME_SUBDIR / "logs"


def get_stats_dir(base_dir: Path) -> Path:
    """Get the stats directory path within an ot dir.

    Args:
        base_dir: Base ot directory (config_path.parent)

    Returns:
        Path to stats/ subdirectory
    """
    return base_dir / RUNTIME_SUBDIR / "stats"


def expand_path(path: str) -> Path:
    """Expand ~ in a path.

    Only expands ~ to home directory. Does NOT expand ${VAR} patterns.
    Use ~/path instead of ${HOME}/path.

    Args:
        path: Path string potentially containing ~

    Returns:
        Expanded absolute Path
    """
    return Path(path).expanduser().resolve()


def resolve_cwd_path(path: str) -> Path:
    """Resolve a path relative to the project working directory (OT_CWD).

    Use this for reading/writing files in the user's project.
    This is the internal version for in-process tools - uses OT_CWD env var directly.

    Args:
        path: Path string (relative, absolute, or with ~)

    Returns:
        Resolved absolute Path

    Behaviour:
        - ~ paths: expanded to home directory
        - Absolute paths: returned unchanged
        - Relative paths: resolved relative to get_effective_cwd()

    Example:
        >>> resolve_cwd_path("data/file.txt")
        PosixPath('/project/data/file.txt')
        >>> resolve_cwd_path("/tmp/output.txt")
        PosixPath('/tmp/output.txt')
        >>> resolve_cwd_path("~/output.txt")
        PosixPath('/home/user/output.txt')
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (get_effective_cwd() / p).resolve()
