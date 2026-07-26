"""Document conversion tools for OneTool.

Converts PDF, Word, PowerPoint, and Excel documents to Markdown
with LLM-optimised output including YAML frontmatter and TOC.

Supports glob patterns for batch conversion with async parallel processing.
"""

from __future__ import annotations

# Pack for dot notation: convert.pdf(), convert.word(), etc.
pack = "convert"
pack_aliases = ("cv",)

__all__ = ["auto", "excel", "pdf", "powerpoint", "word"]

# Dependency declarations for CLI validation
# Use dict format for packages where import_name differs from package name
__ot_requires__ = [
    {
        "kind": "lib",
        "name": "PyMuPDF",
        "import_name": "fitz",
        "install_extra": "[util]",
        "purpose": "Extract text and images from PDF documents",
    },
    {
        "kind": "lib",
        "name": "python-docx",
        "import_name": "docx",
        "install_extra": "[util]",
        "purpose": "Extract content from Word documents",
    },
    {
        "kind": "lib",
        "name": "python-pptx",
        "import_name": "pptx",
        "install_extra": "[util]",
        "purpose": "Extract content from PowerPoint presentations",
    },
    {
        "kind": "lib",
        "name": "openpyxl",
        "import_name": "openpyxl",
        "install_extra": "[util]",
        "purpose": "Extract content and formulas from Excel workbooks",
    },
    {
        "kind": "lib",
        "name": "Pillow",
        "import_name": "PIL",
        "install_extra": "[util]",
        "purpose": "Process images embedded in converted documents",
    },
    {
        "kind": "lib",
        "name": "formulas",
        "import_name": "formulas",
        "install_extra": "[util]",
        "purpose": "Optionally evaluate Excel formulas during conversion",
        "optional": True,
    },
]

import asyncio
import atexit
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ot.utils.async_bridge import run_coro_sync
from otpack import LogSpan, resolve_cwd_path
from otutil.tools._convert import (
    convert_excel,
    convert_pdf,
    convert_powerpoint,
    convert_word,
)

# Type alias for converter functions
ConverterFunc = Callable[[Path, Path, str], dict[str, Any]]


def _format_batch_result(result: dict[str, Any], summary: str) -> str:
    lines = [summary]
    if result["outputs"]:
        lines.append("\nOutputs:")
        for output in result["outputs"]:
            lines.append(f"  {output}")
    if result["errors"]:
        lines.append("\nErrors:")
        for error in result["errors"]:
            lines.append(f"  {error}")
    return "\n".join(lines)


# Shared thread pool for file conversions (created lazily, sized for parallelism)
_conversion_executor: ThreadPoolExecutor | None = None


def _get_conversion_executor() -> ThreadPoolExecutor:
    """Get or create the shared conversion thread pool."""
    global _conversion_executor
    if _conversion_executor is None:
        # Use CPU count but cap at reasonable max for I/O-bound work
        max_workers = min(os.cpu_count() or 4, 8)
        _conversion_executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="convert",
        )
    return _conversion_executor


def _get_conversion_concurrency() -> int:
    """Get effective conversion concurrency."""
    executor = _get_conversion_executor()
    # ThreadPoolExecutor always exposes _max_workers; keep guarded for safety.
    workers = getattr(executor, "_max_workers", None)
    if isinstance(workers, int) and workers > 0:
        return workers
    return 4


def _shutdown_executor() -> None:
    """Shutdown the conversion thread pool on exit."""
    global _conversion_executor
    if _conversion_executor is not None:
        _conversion_executor.shutdown(wait=False)
        _conversion_executor = None


atexit.register(_shutdown_executor)


def _resolve_glob(pattern: str) -> list[Path]:
    """Resolve glob pattern to list of files.

    Uses SDK resolve_cwd_path() for consistent path resolution.

    Args:
        pattern: Glob pattern (can include ~, relative, or absolute paths)

    Returns:
        List of matching file paths
    """
    cwd = resolve_cwd_path(".")
    # Expand ~ and resolve relative to project dir
    path = Path(pattern).expanduser()
    if not path.is_absolute():
        path = cwd / pattern

    # If pattern has no glob chars and exists, return it directly
    if path.exists() and path.is_file():
        return [path]

    # Otherwise glob from parent
    parent = path.parent
    glob_pattern = path.name

    # Handle recursive globs in parent
    if "**" in str(path):
        # Find the base directory before **
        parts = Path(pattern).expanduser().parts
        base_parts: list[str] = []
        glob_parts: list[str] = []
        found_glob = False
        for part in parts:
            if "**" in part or "*" in part or "?" in part:
                found_glob = True
            if found_glob:
                glob_parts.append(part)
            else:
                base_parts.append(part)

        if base_parts:
            base = Path(*base_parts)
            if not base.is_absolute():
                base = cwd / base
        else:
            base = cwd

        glob_pattern = str(Path(*glob_parts)) if glob_parts else "*"
        return sorted(base.glob(glob_pattern))

    # Simple glob in directory
    if not parent.is_absolute():
        parent = cwd / parent.relative_to(".") if str(parent) != "." else cwd

    if parent.exists():
        return sorted(parent.glob(glob_pattern))

    return []


def _get_source_rel(path: Path) -> str:
    """Get relative path for frontmatter source field."""
    cwd = resolve_cwd_path(".")
    try:
        return str(path.relative_to(cwd))
    except ValueError:
        return str(path)


def _resolve_output_dir(output_dir: str) -> Path:
    """Resolve output directory path.

    Uses SDK resolve_cwd_path() for consistent path resolution.
    """
    return resolve_cwd_path(output_dir)


async def _convert_file_async(
    converter: Any,
    input_path: Path,
    output_dir: Path,
    source_rel: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run conversion in shared thread pool for async execution."""
    loop = asyncio.get_running_loop()
    executor = _get_conversion_executor()
    return await loop.run_in_executor(
        executor,
        lambda: converter(input_path, output_dir, source_rel, **kwargs),
    )


async def _gather_conversions(
    work: list[tuple[Path, ConverterFunc]],
    output_dir: Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run (path, converter) pairs in bounded concurrent chunks."""
    converted = 0
    failed = 0
    outputs: list[str] = []
    errors: list[str] = []
    concurrency = _get_conversion_concurrency()

    # Process in bounded chunks to avoid creating unbounded task/result lists.
    for i in range(0, len(work), concurrency):
        chunk = work[i:i + concurrency]
        tasks = [
            _convert_file_async(converter, path, output_dir, _get_source_rel(path), **kwargs)
            for path, converter in chunk
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for (path, _converter), res in zip(chunk, results, strict=True):
            if isinstance(res, BaseException):
                failed += 1
                errors.append(f"{path.name}: {res}")
            else:
                converted += 1
                outputs.append(res["output"])

    return {
        "converted": converted,
        "failed": failed,
        "outputs": outputs,
        "errors": errors,
    }


async def _convert_batch_async(
    files: list[Path],
    output_dir: Path,
    converter: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convert multiple files in parallel."""
    return await _gather_conversions([(f, converter) for f in files], output_dir, **kwargs)


async def _convert_auto_batch_async(
    files: list[Path],
    output_dir: Path,
    converters: dict[str, ConverterFunc],
) -> dict[str, Any]:
    """Convert multiple files in parallel with auto-detection."""
    work: list[tuple[Path, ConverterFunc]] = []
    skipped = 0

    for path in files:
        ext = path.suffix.lower()
        if ext not in converters:
            skipped += 1
            continue

        work.append((path, converters[ext]))

    if not work:
        return {
            "converted": 0,
            "failed": 0,
            "skipped": skipped,
            "outputs": [],
            "errors": [],
        }

    result = await _gather_conversions(work, output_dir)
    return {**result, "skipped": skipped}


def _run_conversion(
    *,
    span: str,
    pattern: str,
    output_dir: str,
    converter: ConverterFunc,
    single_summary: Any,
    span_extras: dict[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    """Shared glob -> convert -> summarise scaffold for the per-format tools.

    ``single_summary(result)`` returns ``(stats_for_span, summary_text)`` for
    the single-file path; batch runs report converted/failed counts.
    """
    with LogSpan(span=span, pattern=pattern, outputDir=output_dir, **(span_extras or {})) as s:
        files = _resolve_glob(pattern)
        if not files:
            s.add(error="no_match")
            return f"No files matched pattern: {pattern}"

        out_path = _resolve_output_dir(output_dir)

        if len(files) == 1:
            try:
                source_rel = _get_source_rel(files[0])
                result = converter(files[0], out_path, source_rel, **kwargs)
                stats, text = single_summary(result)
                s.add(converted=1, **stats)
                return f"Converted {files[0].name}: {text}\nOutput: {result['output']}"
            except Exception as e:
                s.add(error=str(e))
                return f"Error converting {files[0].name}: {e}"

        try:
            result = run_coro_sync(_convert_batch_async(files, out_path, converter, **kwargs))
            s.add(converted=result["converted"], failed=result["failed"])
            return _format_batch_result(
                result, f"Converted {result['converted']} files, {result['failed']} failed"
            )
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


def pdf(
    *,
    pattern: str,
    output_dir: str,
) -> str:
    """Convert PDF documents to Markdown.

    Converts PDF files to Markdown with page-by-page text extraction,
    embedded image export, and outline-based heading structure.

    Args:
        pattern: Glob pattern for input files (e.g., "docs/*.pdf", "report.pdf")
        output_dir: Directory for output files

    Returns:
        Conversion summary with output paths, or error message

    Example:
        convert.pdf(pattern="docs/report.pdf", output_dir="docs/md")
        convert.pdf(pattern="input/*.pdf", output_dir="output")
    """
    return _run_conversion(
        span="convert.pdf",
        pattern=pattern,
        output_dir=output_dir,
        converter=convert_pdf,
        single_summary=lambda r: (
            {"pages": r["pages"], "images": r["images"]},
            f"{r['pages']} pages, {r['images']} images",
        ),
    )


def word(
    *,
    pattern: str,
    output_dir: str,
) -> str:
    """Convert Word documents to Markdown.

    Converts DOCX files to Markdown with heading style detection,
    table conversion, and embedded image export.

    Args:
        pattern: Glob pattern for input files (e.g., "docs/*.docx", "spec.docx")
        output_dir: Directory for output files

    Returns:
        Conversion summary with output paths, or error message

    Example:
        convert.word(pattern="specs/design.docx", output_dir="specs/md")
        convert.word(pattern="docs/**/*.docx", output_dir="output")
    """
    return _run_conversion(
        span="convert.word",
        pattern=pattern,
        output_dir=output_dir,
        converter=convert_word,
        single_summary=lambda r: (
            {"paragraphs": r["paragraphs"], "tables": r["tables"], "images": r["images"]},
            f"{r['paragraphs']} paragraphs, {r['tables']} tables, {r['images']} images",
        ),
    )


def powerpoint(
    *,
    pattern: str,
    output_dir: str,
    include_notes: bool = False,
) -> str:
    """Convert PowerPoint presentations to Markdown.

    Converts PPTX files to Markdown with slide structure,
    table conversion, and embedded image export.

    Args:
        pattern: Glob pattern for input files (e.g., "slides/*.pptx")
        output_dir: Directory for output files
        include_notes: Include speaker notes after slide content

    Returns:
        Conversion summary with output paths, or error message

    Example:
        convert.powerpoint(pattern="slides/deck.pptx", output_dir="slides/md")
        convert.powerpoint(pattern="presentations/*.pptx", output_dir="output", include_notes=True)
    """
    return _run_conversion(
        span="convert.powerpoint",
        pattern=pattern,
        output_dir=output_dir,
        converter=convert_powerpoint,
        span_extras={"include_notes": include_notes},
        include_notes=include_notes,
        single_summary=lambda r: (
            {"slides": r["slides"], "images": r["images"]},
            f"{r['slides']} slides, {r['images']} images",
        ),
    )


def excel(
    *,
    pattern: str,
    output_dir: str,
    include_formulas: bool = False,
    compute_formulas: bool = False,
) -> str:
    """Convert Excel spreadsheets to Markdown.

    Converts XLSX files to Markdown tables with sheet-based sections.
    Uses streaming for memory-efficient processing of large files.

    Args:
        pattern: Glob pattern for input files (e.g., "data/*.xlsx")
        output_dir: Directory for output files
        include_formulas: Include cell formulas as comments
        compute_formulas: Evaluate formulas when cached values are missing
            (requires 'formulas' library: pip install formulas)

    Returns:
        Conversion summary with output paths, or error message

    Example:
        convert.excel(pattern="data/report.xlsx", output_dir="data/md")
        convert.excel(pattern="spreadsheets/*.xlsx", output_dir="output", include_formulas=True)
        convert.excel(pattern="data/*.xlsx", output_dir="out", compute_formulas=True)
    """
    return _run_conversion(
        span="convert.excel",
        pattern=pattern,
        output_dir=output_dir,
        converter=convert_excel,
        span_extras={
            "include_formulas": include_formulas,
            "compute_formulas": compute_formulas,
        },
        include_formulas=include_formulas,
        compute_formulas=compute_formulas,
        single_summary=lambda r: (
            {"sheets": r["sheets"], "rows": r["rows"]},
            f"{r['sheets']} sheets, {r['rows']} rows",
        ),
    )


def auto(
    *,
    pattern: str,
    output_dir: str,
) -> str:
    """Auto-detect format and convert documents to Markdown.

    Detects file format from extension and uses the appropriate converter.
    Supports PDF, DOCX, PPTX, and XLSX formats.

    Args:
        pattern: Glob pattern for input files (e.g., "docs/*", "input/**/*")
        output_dir: Directory for output files

    Returns:
        Conversion summary with output paths, or error message

    Example:
        convert.auto(pattern="docs/*", output_dir="output")
        convert.auto(pattern="input/**/*.{pdf,docx}", output_dir="converted")
    """
    with LogSpan(span="convert.auto", pattern=pattern, outputDir=output_dir) as s:
        files = _resolve_glob(pattern)
        if not files:
            s.add(error="no_match")
            return f"No files matched pattern: {pattern}"

        out_path = _resolve_output_dir(output_dir)

        # Converters by extension
        converters: dict[str, ConverterFunc] = {
            ".pdf": convert_pdf,
            ".docx": convert_word,
            ".pptx": convert_powerpoint,
            ".xlsx": convert_excel,
        }

        # Single supported file - convert directly
        supported_files = [f for f in files if f.suffix.lower() in converters]
        skipped = len(files) - len(supported_files)

        if len(supported_files) == 1:
            path = supported_files[0]
            try:
                source_rel = _get_source_rel(path)
                result = converters[path.suffix.lower()](path, out_path, source_rel)
                s.add(converted=1, failed=0, skipped=skipped)
                msg = f"Converted {path.name}\nOutput: {result['output']}"
                if skipped:
                    msg += f"\n{skipped} skipped (unsupported format)"
                return msg
            except Exception as e:
                s.add(converted=0, failed=1, skipped=skipped, error=str(e))
                return f"Error converting {path.name}: {e}"

        if not supported_files:
            s.add(converted=0, failed=0, skipped=skipped)
            return f"No supported files found. {skipped} skipped (unsupported format)"

        # Batch conversion with async parallel processing
        try:
            result = run_coro_sync(_convert_auto_batch_async(files, out_path, converters))
            s.add(converted=result["converted"], failed=result["failed"], skipped=result["skipped"])

            return _format_batch_result(
                result,
                f"Converted {result['converted']} files, {result['failed']} failed, {result['skipped']} skipped (unsupported format)",
            )
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"
