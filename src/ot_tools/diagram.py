# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0", "pyyaml>=6.0.0", "aiofiles>=24.1.0"]
# ///
"""Diagram generation tools using Kroki as the rendering backend.

Provides a two-stage pipeline for creating diagrams:
1. Generate source - creates diagram source code for review
2. Render diagram - renders source via Kroki to SVG/PNG/PDF

Supports 28+ diagram types through Kroki, with focus providers:
- Mermaid: flowcharts, sequences, state diagrams, Gantt, mindmaps
- PlantUML: UML diagrams, C4 architecture
- D2: modern architecture diagrams with auto-layout

Reference: https://kroki.io/
"""

from __future__ import annotations

# Pack for dot notation: diagram.generate_source(), diagram.render(), etc.
pack = "diagram"

__all__ = [
    "batch_render",
    "generate_source",
    "get_diagram_instructions",
    "get_diagram_policy",
    "get_output_config",
    "get_playground_url",
    "get_render_status",
    "get_template",
    "list_providers",
    "render_diagram",
    "render_directory",
]

import base64
import re
import uuid
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from ot_sdk import (
    get_config,
    get_config_path,
    get_project_path,
    http,
    log,
    truncate,
    worker_main,
)

# ==================== Constants ====================

# Kroki-supported diagram providers
KROKI_PROVIDERS = [
    "actdiag",
    "blockdiag",
    "bpmn",
    "bytefield",
    "c4plantuml",
    "d2",
    "dbml",
    "ditaa",
    "erd",
    "excalidraw",
    "graphviz",
    "mermaid",
    "nomnoml",
    "nwdiag",
    "packetdiag",
    "pikchr",
    "plantuml",
    "rackdiag",
    "seqdiag",
    "structurizr",
    "svgbob",
    "symbolator",
    "tikz",
    "umlet",
    "vega",
    "vegalite",
    "wavedrom",
    "wireviz",
]

# Focus providers with full guidance
FOCUS_PROVIDERS = ["mermaid", "plantuml", "d2"]

# File extensions for diagram sources
PROVIDER_EXTENSIONS = {
    "mermaid": ".mmd",
    "plantuml": ".puml",
    "d2": ".d2",
    "graphviz": ".dot",
    "ditaa": ".ditaa",
    "erd": ".erd",
    "nomnoml": ".nomnoml",
    "svgbob": ".bob",
    "vega": ".vg.json",
    "vegalite": ".vl.json",
}

# Reverse mapping: extension -> provider (for file inference)
EXTENSION_TO_PROVIDER = {v: k for k, v in PROVIDER_EXTENSIONS.items()}

# Set of all known diagram extensions (for directory scanning)
DIAGRAM_EXTENSIONS = frozenset(PROVIDER_EXTENSIONS.values())

# Output format MIME types
FORMAT_MIME_TYPES = {
    "svg": "image/svg+xml",
    "png": "image/png",
    "pdf": "application/pdf",
    "jpeg": "image/jpeg",
}

# Async task storage for batch operations
_render_tasks: dict[str, dict[str, Any]] = {}

# Cached backend URL to avoid redundant health checks
_cached_backend: dict[str, Any] = {"url": None, "is_self_hosted": None}


# ==================== Path Resolution ====================


def _resolve_output_dir(output_dir: str | None) -> Path:
    """Resolve the output directory for diagrams.

    Output is always relative to the project directory (OT_CWD), not the config
    directory. This ensures diagrams are saved where the user expects them.

    Path resolution:
        - Relative paths: resolved relative to project directory (OT_CWD)
        - Absolute paths: used as-is
        - ~ paths: expanded to home directory

    Args:
        output_dir: Output directory path, or None to use config default.

    Returns:
        Resolved absolute Path to output directory (created if needed).
    """
    if output_dir is None:
        output_dir = get_config("tools.diagram.output.dir") or "diagrams"

    path = get_project_path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


# ==================== Encoding Utilities ====================


def encode_source(source: str) -> str:
    """Encode diagram source for GET URL requests.

    Uses deflate compression + base64url encoding as required by Kroki.

    Args:
        source: The diagram source code.

    Returns:
        Encoded string suitable for Kroki GET URLs.
    """
    compressed = zlib.compress(source.encode("utf-8"), level=9)
    return base64.urlsafe_b64encode(compressed).decode("ascii")


def _decode_source(encoded: str) -> str:
    """Decode diagram source from GET URL encoding.

    Args:
        encoded: The encoded diagram source.

    Returns:
        Original diagram source code.
    """
    compressed = base64.urlsafe_b64decode(encoded)
    return zlib.decompress(compressed).decode("utf-8")


def _encode_plantuml(source: str) -> str:
    """Encode diagram source using PlantUML-specific encoding.

    PlantUML uses a custom alphabet for URL encoding.

    Args:
        source: The PlantUML diagram source.

    Returns:
        PlantUML-encoded string for plantuml.com URLs.
    """
    # PlantUML's custom base64 alphabet
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"

    compressed = zlib.compress(source.encode("utf-8"), level=9)[2:-4]
    result = []

    for i in range(0, len(compressed), 3):
        chunk = compressed[i : i + 3]
        if len(chunk) == 3:
            b1, b2, b3 = chunk
            result.append(alphabet[b1 >> 2])
            result.append(alphabet[((b1 & 0x3) << 4) | (b2 >> 4)])
            result.append(alphabet[((b2 & 0xF) << 2) | (b3 >> 6)])
            result.append(alphabet[b3 & 0x3F])
        elif len(chunk) == 2:
            b1, b2 = chunk
            result.append(alphabet[b1 >> 2])
            result.append(alphabet[((b1 & 0x3) << 4) | (b2 >> 4)])
            result.append(alphabet[(b2 & 0xF) << 2])
        elif len(chunk) == 1:
            b1 = chunk[0]
            result.append(alphabet[b1 >> 2])
            result.append(alphabet[(b1 & 0x3) << 4])

    return "".join(result)


# ==================== Kroki Client Utilities ====================


def _get_kroki_url() -> str:
    """Get the appropriate Kroki URL based on configuration.

    Uses cached result to avoid redundant health checks in batch operations.

    Returns:
        The Kroki base URL (remote or self-hosted).
    """
    # Return cached URL if available
    if _cached_backend["url"] is not None:
        return _cached_backend["url"]

    prefer = get_config("tools.diagram.backend.prefer") or "remote"
    remote_url = get_config("tools.diagram.backend.remote_url") or "https://kroki.io"
    self_hosted_url = (
        get_config("tools.diagram.backend.self_hosted_url") or "http://localhost:8000"
    )

    if prefer == "self_hosted":
        _cached_backend["url"] = self_hosted_url
        _cached_backend["is_self_hosted"] = True
    elif prefer == "auto":
        # Try self-hosted first, fall back to remote
        try:
            resp = http.get(f"{self_hosted_url}/health", timeout=2.0)
            if resp.status_code == 200:
                _cached_backend["url"] = self_hosted_url
                _cached_backend["is_self_hosted"] = True
            else:
                _cached_backend["url"] = remote_url
                _cached_backend["is_self_hosted"] = False
        except Exception:
            _cached_backend["url"] = remote_url
            _cached_backend["is_self_hosted"] = False
    else:
        _cached_backend["url"] = remote_url
        _cached_backend["is_self_hosted"] = False

    return _cached_backend["url"]


def _is_self_hosted() -> bool:
    """Check if using self-hosted Kroki backend.

    Uses cached result from _get_kroki_url() to avoid redundant health checks.
    """
    # Ensure cache is populated
    if _cached_backend["is_self_hosted"] is None:
        _get_kroki_url()
    return _cached_backend["is_self_hosted"] or False


def _render_via_kroki(
    source: str, provider: str, output_format: str = "svg", timeout: float = 30.0
) -> bytes:
    """Render diagram source via Kroki HTTP API.

    Uses POST for rendering to handle large diagrams without URL limits.

    Args:
        source: The diagram source code.
        provider: The diagram provider (mermaid, plantuml, d2, etc.).
        output_format: Output format (svg, png, pdf).
        timeout: Request timeout in seconds.

    Returns:
        Rendered diagram as bytes.

    Raises:
        Exception: If rendering fails.
    """
    kroki_url = _get_kroki_url()
    url = f"{kroki_url}/{provider}/{output_format}"

    with log("diagram.kroki", provider=provider, format=output_format, url=url) as span:
        resp = http.post(
            url,
            content=source.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
            timeout=timeout,
        )

        span.add(status=resp.status_code)

        if resp.status_code != 200:
            error_msg = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
            span.add(error=error_msg)
            raise Exception(f"Kroki render failed: {error_msg}")

        span.add(responseLen=len(resp.content))
        return resp.content


def _get_kroki_get_url(source: str, provider: str, output_format: str = "svg") -> str:
    """Generate a Kroki GET URL for sharing.

    Args:
        source: The diagram source code.
        provider: The diagram provider.
        output_format: Output format.

    Returns:
        Shareable Kroki GET URL.
    """
    encoded = encode_source(source)
    kroki_url = _get_kroki_url()
    return f"{kroki_url}/{provider}/{output_format}/{encoded}"


# ==================== Playground URL Generators ====================


def _get_mermaid_playground_url(source: str) -> str:
    """Generate Mermaid Live Editor URL.

    Args:
        source: Mermaid diagram source.

    Returns:
        Mermaid Live Editor URL.
    """
    # Mermaid.live uses pako (deflate + base64)
    encoded = encode_source(source)
    return f"https://mermaid.live/edit#pako:{encoded}"


def _get_plantuml_playground_url(source: str) -> str:
    """Generate PlantUML web server URL.

    Args:
        source: PlantUML diagram source.

    Returns:
        PlantUML playground URL.
    """
    encoded = _encode_plantuml(source)
    return f"https://www.plantuml.com/plantuml/uml/{encoded}"


def _get_d2_playground_url(source: str) -> str:
    """Generate D2 playground URL.

    Args:
        source: D2 diagram source.

    Returns:
        D2 playground URL.
    """
    # D2 playground uses base64url encoding
    encoded = base64.urlsafe_b64encode(source.encode("utf-8")).decode("ascii")
    return f"https://play.d2lang.com/?script={encoded}"


# ==================== Validation Utilities ====================


def _validate_provider(provider: str) -> None:
    """Validate that the provider is supported by Kroki.

    Args:
        provider: The diagram provider name.

    Raises:
        ValueError: If provider is not supported.
    """
    if provider not in KROKI_PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Supported: {', '.join(FOCUS_PROVIDERS)} (focus), "
            f"plus {len(KROKI_PROVIDERS) - len(FOCUS_PROVIDERS)} others."
        )


def _validate_format(output_format: str) -> None:
    """Validate that the output format is supported.

    Args:
        output_format: The output format.

    Raises:
        ValueError: If format is not supported.
    """
    if output_format not in FORMAT_MIME_TYPES:
        raise ValueError(
            f"Unknown format '{output_format}'. "
            f"Supported: {', '.join(FORMAT_MIME_TYPES.keys())}"
        )


def _basic_source_validation(source: str, provider: str) -> list[str]:
    """Perform basic validation of diagram source.

    Returns warnings/errors that don't prevent rendering but may cause issues.

    Args:
        source: The diagram source code.
        provider: The diagram provider.

    Returns:
        List of warning messages (empty if no issues).
    """
    warnings: list[str] = []

    # Check for common Mermaid issues
    if provider == "mermaid":
        # Check for quoted aliases in sequence diagrams (common mistake)
        if "sequenceDiagram" in source and re.search(
            r'participant\s+\w+\s+as\s+"[^"]+"', source
        ):
            warnings.append(
                "Mermaid sequence diagrams: quotes after 'as' appear literally. "
                "Use: participant ID as Display Name (no quotes)"
            )
        # Check for spaces in node IDs
        if re.search(r'\b\w+\s+\w+\["', source):
            warnings.append(
                "Mermaid: node IDs should not contain spaces. "
                'Use ID["Label with spaces"] format.'
            )

    # Check for PlantUML markers
    if provider == "plantuml" and not source.strip().startswith("@start"):
        warnings.append(
            "PlantUML source should start with @startuml, @startmindmap, etc."
        )

    # Check for D2 issues - D2 is pretty forgiving, just check for obvious issues
    if provider == "d2" and source.strip().startswith("@"):
        warnings.append("D2 doesn't use @ markers. This looks like PlantUML syntax.")

    return warnings


# ==================== File Utilities ====================


def _get_source_extension(provider: str) -> str:
    """Get the file extension for a diagram provider.

    Args:
        provider: The diagram provider.

    Returns:
        File extension including the dot.
    """
    return PROVIDER_EXTENSIONS.get(provider, f".{provider}")


def _generate_filename(
    name: str, provider: str, output_format: str, is_source: bool = False
) -> str:
    """Generate a filename based on the configured naming pattern.

    Args:
        name: Base name for the file.
        provider: The diagram provider.
        output_format: Output format for rendered files.
        is_source: Whether this is a source file (not rendered).

    Returns:
        Generated filename.
    """
    naming_pattern = (
        get_config("tools.diagram.output.naming") or "{provider}_{name}_{timestamp}"
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = naming_pattern.format(
        provider=provider,
        name=name,
        timestamp=timestamp,
    )

    if is_source:
        return filename + _get_source_extension(provider)
    else:
        return filename + f".{output_format}"


# ==================== Core Tools ====================


def generate_source(
    *,
    source: str,
    provider: Literal[
        "mermaid", "plantuml", "d2", "graphviz", "ditaa", "erd", "nomnoml", "svgbob"
    ]
    | str,
    name: str,
    output_dir: str | None = None,
    validate: bool = True,
) -> str:
    """Save diagram source code to a file for review before rendering.

    This is the first stage of the two-stage pipeline. The source can be
    reviewed and edited before calling render_diagram().

    Args:
        source: The diagram source code.
        provider: Diagram provider (mermaid, plantuml, d2, etc.).
        name: Base name for the file (used in filename generation).
        output_dir: Output directory (defaults to config tools.diagram.output.dir).
        validate: Perform basic source validation (default: True).

    Returns:
        Result message with file path and any validation warnings.

    Example:
        result = diagram.generate_source(
            source=\"\"\"
            sequenceDiagram
                participant C as Client
                participant S as Server
                C->>S: Request
                S-->>C: Response
            \"\"\",
            provider="mermaid",
            name="api-flow"
        )
    """
    with log("diagram.generate_source", provider=provider, diagram_name=name) as s:
        try:
            _validate_provider(provider)

            # Get output directory (resolved relative to project directory)
            output_path = _resolve_output_dir(output_dir)

            # Generate filename and write source
            filename = _generate_filename(name, provider, "", is_source=True)
            file_path = output_path / filename

            file_path.write_text(source)

            # Validation warnings
            warnings: list[str] = []
            if validate:
                warnings = _basic_source_validation(source, provider)

            # Get playground URL for debugging
            playground_url = get_playground_url(source=source, provider=provider)

            result_parts = [
                f"Source saved: {file_path}",
                f"Provider: {provider}",
                f"Lines: {len(source.splitlines())}",
            ]

            if playground_url:
                result_parts.append(f"Playground: {playground_url}")

            if warnings:
                result_parts.append("\nWarnings:")
                result_parts.extend(f"  - {w}" for w in warnings)

            s.add(path=str(file_path), warnings=len(warnings))
            return "\n".join(result_parts)

        except Exception as e:
            s.add(error=str(e))
            return f"Error generating source: {e}"


def render_diagram(
    *,
    source: str | None = None,
    source_file: str | None = None,
    provider: str | None = None,
    name: str | None = None,
    output_format: Literal["svg", "png", "pdf"] = "svg",
    output_dir: str | None = None,
    save_source: bool | None = None,
    async_mode: bool = False,
) -> str:
    """Render a diagram from source code or file via Kroki.

    This is the second stage of the two-stage pipeline. Renders the diagram
    and saves the output file.

    Args:
        source: The diagram source code (mutually exclusive with source_file).
        source_file: Path to source file (mutually exclusive with source).
        provider: Diagram provider (required if source given, inferred from file).
        name: Base name for output file (defaults to source filename).
        output_format: Output format (svg, png, pdf). Default: svg.
        output_dir: Output directory (defaults to config).
        save_source: Save source alongside output (defaults to config).
        async_mode: Return immediately with task ID for status polling.

    Returns:
        If sync: Result message with output file path.
        If async: Task ID for polling with get_render_status().

    Example:
        # From source
        result = diagram.render_diagram(
            source=\"\"\"
            sequenceDiagram
                C->>S: Request
            \"\"\",
            provider="mermaid",
            name="sequence"
        )

        # From file
        result = diagram.render_diagram(
            source_file="../diagrams/mermaid_api-flow.mmd"
        )
    """
    with log(
        "diagram.render_diagram",
        provider=provider,
        diagram_name=name,
        format=output_format,
        async_mode=async_mode,
    ) as s:
        try:
            # Validate inputs
            if source is None and source_file is None:
                raise ValueError("Either source or source_file must be provided")
            if source is not None and source_file is not None:
                raise ValueError("Cannot provide both source and source_file")

            _validate_format(output_format)

            # Load source from file if needed
            if source_file is not None:
                file_path = Path(source_file)
                if not file_path.exists():
                    raise FileNotFoundError(f"Source file not found: {source_file}")

                source = file_path.read_text()

                # Infer provider from extension
                if provider is None:
                    ext = file_path.suffix.lower()
                    provider = EXTENSION_TO_PROVIDER.get(ext)
                    if provider is None:
                        raise ValueError(
                            f"Cannot infer provider from extension '{ext}'. "
                            "Please specify provider explicitly."
                        )

                # Use filename as name if not provided
                if name is None:
                    name = file_path.stem

            if provider is None:
                raise ValueError("Provider must be specified when using source")
            if name is None:
                name = "diagram"

            _validate_provider(provider)

            # Get output directory (resolved relative to project directory)
            output_path = _resolve_output_dir(output_dir)

            # Generate output filename
            output_filename = _generate_filename(name, provider, output_format)
            output_file = output_path / output_filename

            # Handle async mode
            if async_mode:
                task_id = f"render-{uuid.uuid4().hex[:8]}"
                _render_tasks[task_id] = {
                    "status": "running",
                    "source": source,
                    "provider": provider,
                    "output_format": output_format,
                    "output_file": str(output_file),
                    "started_at": datetime.now().isoformat(),
                }

                # Start async rendering (would use asyncio in real impl)
                # For now, just do it synchronously
                try:
                    timeout = get_config("tools.diagram.backend.timeout") or 30.0
                    rendered = _render_via_kroki(
                        source, provider, output_format, timeout
                    )
                    output_file.write_bytes(rendered)

                    _render_tasks[task_id]["status"] = "completed"
                    _render_tasks[task_id]["completed_at"] = datetime.now().isoformat()
                except Exception as e:
                    _render_tasks[task_id]["status"] = "failed"
                    _render_tasks[task_id]["error"] = str(e)

                s.add(task_id=task_id)
                return f"Rendering started. Task ID: {task_id}"

            # Synchronous rendering
            timeout = get_config("tools.diagram.backend.timeout") or 30.0
            rendered = _render_via_kroki(source, provider, output_format, timeout)

            # Save output
            output_file.write_bytes(rendered)

            # Optionally save source alongside
            if save_source is None:
                save_source = get_config("tools.diagram.output.save_source")
                if save_source is None:
                    save_source = True

            source_saved = ""
            if save_source and source_file is None:
                source_filename = _generate_filename(name, provider, "", is_source=True)
                source_file_path = output_path / source_filename
                source_file_path.write_text(source)
                source_saved = f"\nSource saved: {source_file_path}"

            # Get share URL
            share_url = _get_kroki_get_url(source, provider, output_format)

            s.add(output=str(output_file), size=len(rendered), format=output_format)

            return (
                f"Rendered: {output_file}\n"
                f"Size: {len(rendered):,} bytes\n"
                f"Format: {output_format.upper()}{source_saved}\n"
                f"Share URL: {truncate(share_url, 100)}"
            )

        except Exception as e:
            s.add(error=str(e))
            return f"Error rendering diagram: {e}"


def get_render_status(*, task_id: str) -> str:
    """Check the status of an async render task.

    Args:
        task_id: The task ID returned by render_diagram(async_mode=True).

    Returns:
        JSON-formatted status including progress and output file path.

    Example:
        status = diagram.get_render_status(task_id="render-abc123")
    """
    with log("diagram.get_render_status", task_id=task_id) as s:
        task = _render_tasks.get(task_id)

        if task is None:
            s.add(error="not_found")
            return f"Task not found: {task_id}"

        status = task.get("status", "unknown")
        result_parts = [
            f"Task: {task_id}",
            f"Status: {status}",
        ]

        if status == "completed":
            result_parts.append(f"Output: {task.get('output_file')}")
            if task.get("completed_at"):
                result_parts.append(f"Completed: {task.get('completed_at')}")
        elif status == "failed":
            result_parts.append(f"Error: {task.get('error')}")
        elif status == "running":
            result_parts.append(f"Started: {task.get('started_at')}")

        s.add(status=status)
        return "\n".join(result_parts)


# ==================== Batch Operations (Self-Hosted Only) ====================


def _render_single_diagram(
    item: dict[str, str],
    output_format: str,
    output_path: Path,
    timeout: float,
) -> dict[str, Any]:
    """Render a single diagram - helper for concurrent batch processing.

    Args:
        item: Dict with 'source', 'provider', 'name' keys.
        output_format: Output format (svg, png, pdf).
        output_path: Directory to save output.
        timeout: Request timeout.

    Returns:
        Result dict with name, status, file/error.
    """
    source = item.get("source", "")
    provider = item.get("provider", "mermaid")
    name = item.get("name", "diagram")

    try:
        _validate_provider(provider)
        _validate_format(output_format)

        rendered = _render_via_kroki(source, provider, output_format, timeout)

        output_filename = _generate_filename(name, provider, output_format)
        output_file = output_path / output_filename
        output_file.write_bytes(rendered)

        return {"name": name, "status": "success", "file": str(output_file)}
    except Exception as e:
        return {"name": name, "status": "failed", "error": str(e)}


def batch_render(
    *,
    sources: list[dict[str, str]],
    output_format: Literal["svg", "png", "pdf"] = "svg",
    output_dir: str | None = None,
    max_concurrent: int = 5,
) -> str:
    """Render multiple diagrams concurrently. Self-hosted Kroki only.

    This operation requires a self-hosted Kroki instance to avoid
    overloading the public kroki.io service.

    Args:
        sources: List of dicts with 'source', 'provider', 'name' keys.
        output_format: Output format for all diagrams.
        output_dir: Output directory.
        max_concurrent: Maximum concurrent render requests (default: 5).

    Returns:
        Task ID for polling status with get_render_status().

    Example:
        result = diagram.batch_render(
            sources=[
                {"source": "...", "provider": "mermaid", "name": "diagram1"},
                {"source": "...", "provider": "d2", "name": "diagram2"},
            ]
        )
    """
    with log("diagram.batch_render", count=len(sources), format=output_format) as s:
        # Check for self-hosted requirement
        if not _is_self_hosted():
            s.add(error="requires_self_hosted")
            return (
                "Error: batch_render requires self-hosted Kroki.\n"
                "The public kroki.io service has rate limits.\n"
                "Run: onetool diagram setup --self-hosted"
            )

        task_id = f"batch-{uuid.uuid4().hex[:8]}"

        _render_tasks[task_id] = {
            "status": "running",
            "type": "batch",
            "total": len(sources),
            "completed": 0,
            "failed": 0,
            "results": [],
            "started_at": datetime.now().isoformat(),
        }

        # Get output directory (resolved relative to project directory)
        output_path = _resolve_output_dir(output_dir)

        timeout = get_config("tools.diagram.backend.timeout") or 30.0

        # Process sources concurrently using thread pool
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {
                executor.submit(
                    _render_single_diagram, item, output_format, output_path, timeout
                ): item
                for item in sources
            }

            for future in as_completed(futures):
                result = future.result()
                _render_tasks[task_id]["results"].append(result)
                if result["status"] == "success":
                    _render_tasks[task_id]["completed"] += 1
                else:
                    _render_tasks[task_id]["failed"] += 1

        _render_tasks[task_id]["status"] = "completed"
        _render_tasks[task_id]["completed_at"] = datetime.now().isoformat()

        completed = _render_tasks[task_id]["completed"]
        failed = _render_tasks[task_id]["failed"]

        s.add(task_id=task_id, completed=completed, failed=failed)
        return (
            f"Batch complete. Task ID: {task_id}\n"
            f"Completed: {completed}/{len(sources)}\n"
            f"Failed: {failed}"
        )


def _render_file(
    source_file: Path,
    provider: str,
    output_format: str,
    output_path: Path,
    timeout: float,
) -> dict[str, Any]:
    """Render a diagram from file - reads file just-in-time to save memory.

    Args:
        source_file: Path to the source file.
        provider: Diagram provider.
        output_format: Output format (svg, png, pdf).
        output_path: Directory to save output.
        timeout: Request timeout.

    Returns:
        Result dict with name, status, file/error.
    """
    name = source_file.stem
    try:
        # Read file just-in-time (not pre-loaded)
        source = source_file.read_text()

        _validate_provider(provider)
        _validate_format(output_format)

        rendered = _render_via_kroki(source, provider, output_format, timeout)

        output_filename = _generate_filename(name, provider, output_format)
        output_file = output_path / output_filename
        output_file.write_bytes(rendered)

        return {"name": name, "status": "success", "file": str(output_file)}
    except Exception as e:
        return {"name": name, "status": "failed", "error": str(e)}


def render_directory(
    *,
    directory: str,
    output_format: Literal["svg", "png", "pdf"] = "svg",
    output_dir: str | None = None,
    recursive: bool = False,
    pattern: str = "*",
    max_concurrent: int = 5,
) -> str:
    """Discover and render all diagram source files in a directory.

    Self-hosted Kroki only. Files are read just-in-time to minimise memory usage.

    Args:
        directory: Directory containing diagram source files.
        output_format: Output format for all diagrams.
        output_dir: Output directory (defaults to same as source).
        recursive: Search subdirectories.
        pattern: Glob pattern to match files (e.g., "*.mmd").
        max_concurrent: Maximum concurrent render requests (default: 5).

    Returns:
        Summary of rendered files.

    Example:
        result = diagram.render_directory(
            directory="../diagrams/source",
            output_format="svg",
            recursive=True
        )
    """
    with log("diagram.render_directory", directory=directory, pattern=pattern) as s:
        if not _is_self_hosted():
            s.add(error="requires_self_hosted")
            return (
                "Error: render_directory requires self-hosted Kroki.\n"
                "Run: onetool diagram setup --self-hosted"
            )

        dir_path = Path(directory)
        if not dir_path.exists():
            s.add(error="dir_not_found")
            return f"Error: Directory not found: {directory}"

        # Find source files (just paths, don't read content yet)
        if recursive:
            files = list(dir_path.rglob(pattern))
        else:
            files = list(dir_path.glob(pattern))

        # Filter to known diagram extensions and pair with provider
        file_provider_pairs: list[tuple[Path, str]] = []
        for f in files:
            if f.suffix in DIAGRAM_EXTENSIONS:
                provider = EXTENSION_TO_PROVIDER.get(f.suffix)
                if provider:
                    file_provider_pairs.append((f, provider))

        if not file_provider_pairs:
            s.add(found=0)
            return f"No diagram source files found in {directory}"

        s.add(found=len(file_provider_pairs))

        # Get output directory (defaults to source directory if not specified)
        if output_dir is not None:
            output_path = _resolve_output_dir(output_dir)
        else:
            output_path = dir_path
            output_path.mkdir(parents=True, exist_ok=True)

        timeout = get_config("tools.diagram.backend.timeout") or 30.0

        # Process files concurrently - files are read just-in-time
        completed = 0
        failed = 0
        results: list[dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {
                executor.submit(
                    _render_file,
                    source_file,
                    provider,
                    output_format,
                    output_path,
                    timeout,
                ): source_file
                for source_file, provider in file_provider_pairs
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                if result["status"] == "success":
                    completed += 1
                else:
                    failed += 1

        s.add(completed=completed, failed=failed)
        return (
            f"Directory render complete.\n"
            f"Completed: {completed}/{len(file_provider_pairs)}\n"
            f"Failed: {failed}"
        )


# ==================== Configuration Tools ====================


def get_diagram_policy() -> str:
    """Get the diagram policy rules from configuration.

    Returns policy rules that guide LLM diagram generation behaviour.

    Returns:
        Policy rules as formatted text.

    Example:
        policy = diagram.get_diagram_policy()
    """
    with log("diagram.get_diagram_policy") as s:
        policy = get_config("tools.diagram.policy")

        if policy is None:
            s.add(source="default")
            return (
                "NEVER use ASCII art or text-based diagrams in markdown.\n"
                "Use the diagram tools for all visual representations.\n"
                "Save output as SVG and reference in markdown.\n"
                "Always generate source first, then render."
            )

        result_parts = [
            "Diagram Policy",
            "=" * 40,
            "",
            "Rules:",
            policy.get("rules", "No rules configured"),
            "",
            f"Preferred format: {policy.get('preferred_format', 'svg')}",
            f"Preferred providers: {', '.join(policy.get('preferred_providers', ['mermaid', 'd2', 'plantuml']))}",
        ]

        s.add(source="config")
        return "\n".join(result_parts)


def get_diagram_instructions(
    *, provider: Literal["mermaid", "plantuml", "d2"] | str | None = None
) -> str:
    """Get provider-specific diagram instructions.

    Returns guidance on when to use the provider, style tips,
    syntax guides, and examples.

    Args:
        provider: Specific provider to get instructions for.
                  If None, returns instructions for all focus providers.

    Returns:
        Formatted instructions text.

    Example:
        # All providers
        instructions = diagram.get_diagram_instructions()

        # Specific provider
        mermaid_guide = diagram.get_diagram_instructions(provider="mermaid")
    """
    with log("diagram.get_diagram_instructions", provider=provider) as s:
        instructions = get_config("tools.diagram.instructions") or {}

        # If no config, use defaults
        if not instructions:
            instructions = _get_default_instructions()

        if provider is not None:
            if provider not in instructions:
                s.add(found=False)
                return f"No instructions found for provider: {provider}"

            instr = instructions[provider]
            result = _format_provider_instructions(provider, instr)
            s.add(found=True)
            return result

        # Return all focus provider instructions
        result_parts = ["Diagram Provider Instructions", "=" * 40]

        for p in FOCUS_PROVIDERS:
            if p in instructions:
                result_parts.append("")
                result_parts.append(_format_provider_instructions(p, instructions[p]))

        s.add(providers=len([p for p in FOCUS_PROVIDERS if p in instructions]))
        return "\n".join(result_parts)


def _get_default_instructions() -> dict[str, Any]:
    """Get default instructions when not configured."""
    return {
        "mermaid": {
            "when_to_use": (
                "Flowcharts and decision trees\n"
                "Sequence diagrams for API flows\n"
                "Class diagrams for data models\n"
                "State diagrams for workflows"
            ),
            "style_tips": (
                "Use subgraphs to group related nodes\n"
                "Keep flowcharts top-to-bottom (TD) for readability\n"
                "QUOTING: NO quotes after 'as' in sequence diagrams"
            ),
            "syntax_guide": "https://mermaid.js.org/syntax/",
            "example": (
                "sequenceDiagram\n"
                "    participant C as Client\n"
                "    participant S as Server\n"
                "    C->>S: Request\n"
                "    S-->>C: Response"
            ),
        },
        "plantuml": {
            "when_to_use": (
                "Complex UML diagrams\n"
                "C4 architecture diagrams\n"
                "Detailed sequence diagrams with notes"
            ),
            "style_tips": (
                "Use skinparam for consistent theming\n"
                "QUOTING: Quote display names BEFORE 'as'"
            ),
            "syntax_guide": "https://plantuml.com/",
        },
        "d2": {
            "when_to_use": (
                "Clean architecture diagrams\n"
                "System context diagrams\n"
                "Hand-drawn style (sketch mode)"
            ),
            "style_tips": (
                "Use containers for logical grouping\n"
                "D2 auto-layouts well\n"
                "QUOTING: Always quote labels after colon"
            ),
            "syntax_guide": "https://d2lang.com/tour/intro",
        },
    }


def _format_provider_instructions(provider: str, instr: dict[str, Any]) -> str:
    """Format instructions for a single provider."""
    parts = [f"## {provider.upper()}"]

    if instr.get("when_to_use"):
        parts.append("\nWhen to use:")
        parts.append(instr["when_to_use"])

    if instr.get("style_tips"):
        parts.append("\nStyle tips:")
        parts.append(instr["style_tips"])

    if instr.get("syntax_guide"):
        parts.append(f"\nSyntax guide: {instr['syntax_guide']}")

    if instr.get("example"):
        parts.append("\nExample:")
        parts.append("```")
        parts.append(instr["example"])
        parts.append("```")

    return "\n".join(parts)


def get_output_config() -> str:
    """Get diagram output configuration settings.

    Returns:
        Formatted output configuration.

    Example:
        config = diagram.get_output_config()
    """
    with log("diagram.get_output_config") as s:
        output_dir = get_config("tools.diagram.output.dir") or "diagrams"
        naming = (
            get_config("tools.diagram.output.naming") or "{provider}_{name}_{timestamp}"
        )
        default_format = get_config("tools.diagram.output.default_format") or "svg"
        save_source = get_config("tools.diagram.output.save_source")
        if save_source is None:
            save_source = True

        result = (
            "Diagram Output Configuration\n"
            "=" * 40 + "\n\n"
            f"Output directory: {output_dir}\n"
            f"Naming pattern: {naming}\n"
            f"Default format: {default_format}\n"
            f"Save source: {save_source}"
        )

        s.add(dir=output_dir, format=default_format)
        return result


def get_template(*, name: str) -> str:
    """Load a diagram template by name.

    Templates are defined in the diagram config and provide
    starting points for common diagram types.

    Args:
        name: Template name (e.g., "api-flow", "c4-context").

    Returns:
        Template source code with metadata.

    Example:
        template = diagram.get_template(name="api-flow")
    """
    with log("diagram.get_template", template_name=name) as s:
        templates = get_config("tools.diagram.templates") or {}

        if name not in templates:
            s.add(found=False)
            available = ", ".join(templates.keys()) if templates else "none configured"
            return f"Template not found: {name}\nAvailable: {available}"

        template = templates[name]
        file_path = template.get("file", "")

        # Try to load the template file
        if file_path:
            # Resolve relative to config directory (.onetool/)
            path = get_config_path(file_path)

            if path.exists():
                source = path.read_text()
                s.add(found=True, lines=len(source.splitlines()))
                return (
                    f"Template: {name}\n"
                    f"Provider: {template.get('provider', 'unknown')}\n"
                    f"Type: {template.get('diagram_type', 'unknown')}\n"
                    f"Description: {template.get('description', '')}\n"
                    f"\n--- Source ---\n{source}"
                )

        s.add(found=False, reason="file_not_found")
        return f"Template '{name}' configured but file not found: {file_path}"


def list_providers(*, focus_only: bool = False) -> str:
    """List all available diagram providers.

    Args:
        focus_only: Only list focus providers with full guidance
                   (mermaid, plantuml, d2).

    Returns:
        Formatted list of providers.

    Example:
        # All providers
        providers = diagram.list_providers()

        # Focus providers only
        focus = diagram.list_providers(focus_only=True)
    """
    with log("diagram.list_providers", focus_only=focus_only) as s:
        if focus_only:
            result = (
                "Focus Providers (with full guidance)\n"
                "=" * 40 + "\n\n"
                "- mermaid: Flowcharts, sequences, state, Gantt, mindmaps\n"
                "- plantuml: UML diagrams, C4 architecture\n"
                "- d2: Modern architecture diagrams with auto-layout\n"
                "\nUse diagram.get_diagram_instructions(provider='...') for details."
            )
            s.add(count=len(FOCUS_PROVIDERS))
            return result

        result_parts = [
            "All Kroki Providers",
            "=" * 40,
            "",
            "Focus providers (with guidance):",
        ]
        result_parts.extend(f"  - {p}" for p in FOCUS_PROVIDERS)

        result_parts.append("\nOther providers:")
        other = [p for p in KROKI_PROVIDERS if p not in FOCUS_PROVIDERS]
        result_parts.extend(f"  - {p}" for p in sorted(other))

        result_parts.append(f"\nTotal: {len(KROKI_PROVIDERS)} providers")

        s.add(count=len(KROKI_PROVIDERS))
        return "\n".join(result_parts)


# ==================== Utility Tools ====================


def get_playground_url(
    *,
    source: str,
    provider: Literal["mermaid", "plantuml", "d2"] | str,
) -> str:
    """Generate a playground URL for interactive editing.

    Playground URLs allow editing diagrams in the browser before
    saving the final source.

    Args:
        source: The diagram source code.
        provider: The diagram provider.

    Returns:
        Playground URL or message if not supported.

    Example:
        url = diagram.get_playground_url(
            source="sequenceDiagram\\n    A->>B: Hello",
            provider="mermaid"
        )
    """
    with log("diagram.get_playground_url", provider=provider) as s:
        if provider == "mermaid":
            url = _get_mermaid_playground_url(source)
        elif provider == "plantuml":
            url = _get_plantuml_playground_url(source)
        elif provider == "d2":
            url = _get_d2_playground_url(source)
        else:
            s.add(supported=False)
            # Fall back to Kroki GET URL
            url = _get_kroki_get_url(source, provider, "svg")

        s.add(supported=True, url_length=len(url))
        return url


if __name__ == "__main__":
    worker_main()
