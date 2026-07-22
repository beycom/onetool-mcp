"""Schema-v2 workspace conversion, initialization, and deterministic bundling."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any

from .load import load_workspace
from .write import workspace_payload, write_workspace

if TYPE_CHECKING:
    from .models import ArchitectureWorkspace, Presentation

_FIXED_ZIP_TIME = (2000, 1, 1, 0, 0, 0)
_PORTABLE_DIRS = ("views", "styles", "assets", "assets/icons", "assets/attachments")


class PortableWorkspaceError(ValueError):
    """Raised when a portable workspace operation is unsafe or invalid."""


def semantic_payload(workspace: ArchitectureWorkspace) -> dict[str, Any]:
    """Return format-independent authored workspace semantics.

    Presentation settings, including the filename-derived title, are deliberately
    outside the portable YAML/Excel contract.
    """
    return workspace_payload(workspace)


def convert_workspace(
    *, source: Path, destination: Path, presentation: Presentation | None = None
) -> str:
    """Convert via production loading and verify semantic equivalence after writing."""
    loaded = load_workspace(source, presentation=presentation)
    content_hash = write_workspace(path=destination, workspace=loaded.workspace)
    converted = load_workspace(destination, presentation=presentation)
    if semantic_payload(converted.workspace) != semantic_payload(loaded.workspace):
        destination.unlink(missing_ok=True)
        raise PortableWorkspaceError("Converted workspace failed semantic equivalence")
    return content_hash


def _template_path() -> Path:
    return Path(__file__).with_name("templates") / "solution.yaml"


def initialize_workspace(*, output: Path) -> list[tuple[Path, str]]:
    """Create the canonical paired solution workspace and safe local folders."""
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise PortableWorkspaceError(f"Workspace destination must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for directory in _PORTABLE_DIRS:
        (output / directory).mkdir(parents=True, exist_ok=True)

    template = load_workspace(_template_path()).workspace
    yaml_path = output / "architecture.yaml"
    excel_path = output / "architecture.xlsx"
    artifacts = [
        (yaml_path, write_workspace(path=yaml_path, workspace=template)),
        (excel_path, write_workspace(path=excel_path, workspace=template)),
    ]
    clean_theme = output / "styles" / "clean.yaml"
    clean_theme.write_text(
        "schema_version: 1\nid: clean\nname: Clean\nextends: null\n",
        encoding="utf-8",
    )
    view_source = output / "views" / "platform-delivery.c4"
    view_source.write_text(
        "views {\n"
        "  dynamic view platform_delivery {\n"
        "    title 'Platform delivery flow'\n"
        "    @{B} -> @{C} 'Deliver ledger update'\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    for path in (clean_theme, view_source):
        artifacts.append((path, hashlib.sha256(path.read_bytes()).hexdigest()))
    return artifacts


def _contained(*, root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PortableWorkspaceError(
            f"Bundle source escapes workspace: {candidate}"
        ) from exc
    return resolved


def _manifest_owned(*, root: Path) -> tuple[list[Path], list[Path]]:
    manifests = [
        path
        for path in (root / "manifest.json", root / ".onetool/manifest.json")
        if path.is_file()
    ]
    owned: list[Path] = []
    for manifest in manifests:
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PortableWorkspaceError(
                f"Invalid artifact manifest '{manifest}': {exc}"
            ) from exc
        artifacts = payload.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise PortableWorkspaceError(
                f"Manifest artifacts must be a list: {manifest}"
            )
        for artifact in artifacts:
            if not isinstance(artifact, dict) or not isinstance(
                artifact.get("path"), str
            ):
                raise PortableWorkspaceError(
                    f"Manifest artifact requires a path: {manifest}"
                )
            path = _contained(root=root, candidate=root / artifact["path"])
            if path.is_file():
                owned.append(path)
    return manifests, owned


def _bundle_sources(
    *, input_path: Path, include_generated: bool
) -> tuple[Path, list[Path]]:
    resolved = input_path.resolve()
    if resolved.is_file():
        root = resolved.parent
        files = [resolved]
    elif resolved.is_dir():
        root = resolved
        files = [path for path in root.iterdir() if path.is_file()]
    else:
        raise PortableWorkspaceError(f"Workspace input does not exist: {resolved}")
    for directory in ("views", "styles", "assets"):
        candidate = root / directory
        if candidate.is_dir():
            files.extend(path for path in candidate.rglob("*") if path.is_file())
    manifests, generated = _manifest_owned(root=root)
    generated_set = set(generated)
    files = [path for path in files if path not in generated_set]
    files.extend(manifests)
    if include_generated:
        files.extend(generated)
    return root, sorted(set(files), key=lambda path: path.relative_to(root).as_posix())


def _zip_info(name: str, *, directory: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, _FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o40755 if directory else 0o100644) << 16
    return info


def bundle_workspace(
    *, input_path: Path, output_path: Path, include_generated: bool
) -> tuple[str, list[str]]:
    """Create a deterministic portable archive with contained source files."""
    root, files = _bundle_sources(
        input_path=input_path,
        include_generated=include_generated,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=output_path.parent,
        delete=False,
        suffix=output_path.suffix or ".zip",
    ) as handle:
        temporary = Path(handle.name)
    archived: list[str] = []
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for directory in _PORTABLE_DIRS:
                path = root / directory
                if path.is_dir():
                    name = f"{directory}/"
                    archive.writestr(_zip_info(name, directory=True), b"")
            for path in files:
                if path.resolve() == output_path.resolve():
                    continue
                contained = _contained(root=root, candidate=path)
                name = contained.relative_to(root).as_posix()
                archive.writestr(_zip_info(name), contained.read_bytes())
                archived.append(name)
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(output_path.read_bytes()).hexdigest(), archived
