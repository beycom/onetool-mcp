"""Document conversion tools for OneTool.

Converts PDF, Word, PowerPoint, and Excel documents to Markdown
with LLM-optimised output including YAML frontmatter and TOC.

Supports glob patterns for batch conversion with async parallel processing.
"""

from __future__ import annotations

# Pack for dot notation: convert.pdf(), convert.word(), etc.
pack = "convert"

__all__ = ["auto", "excel", "pdf", "powerpoint", "word"]

import asyncio
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ot.logging import LogSpan
from ot.paths import get_effective_cwd
from ot_tools._convert import (
    convert_excel,
    convert_pdf,
    convert_powerpoint,
    convert_word,
)

# Type alias for converter functions
ConverterFunc = Callable[[Path, Path, str], dict[str, Any]]

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


def _resolve_glob(pattern: str) -> list[Path]:
    """Resolve glob pattern to list of files.

    Args:
        pattern: Glob pattern (can include ~, relative, or absolute paths)

    Returns:
        List of matching file paths
    """
    # Expand ~ and resolve relative to project dir
    path = Path(pattern).expanduser()
    if not path.is_absolute():
        path = get_effective_cwd() / pattern

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
                base = get_effective_cwd() / base
        else:
            base = get_effective_cwd()

        glob_pattern = str(Path(*glob_parts)) if glob_parts else "*"
        return list(base.glob(glob_pattern))

    # Simple glob in directory
    if not parent.is_absolute():
        parent = get_effective_cwd() / parent.relative_to(".") if str(parent) != "." else get_effective_cwd()

    if parent.exists():
        return list(parent.glob(glob_pattern))

    return []


def _get_source_rel(path: Path) -> str:
    """Get relative path for frontmatter source field."""
    cwd = get_effective_cwd()
    try:
        return str(path.relative_to(cwd))
    except ValueError:
        return str(path)


def _resolve_output_dir(output_dir: str) -> Path:
    """Resolve output directory path."""
    path = Path(output_dir).expanduser()
    if not path.is_absolute():
        path = get_effective_cwd() / output_dir
    return path


async def _convert_file_async(
    converter: Any,
    input_path: Path,
    output_dir: Path,
    source_rel: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run conversion in shared thread pool for async execution."""
    loop = asyncio.get_event_loop()
    executor = _get_conversion_executor()
    return await loop.run_in_executor(
        executor,
        lambda: converter(input_path, output_dir, source_rel, **kwargs),
    )


async def _convert_batch_async(
    files: list[Path],
    output_dir: Path,
    converter: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convert multiple files in parallel."""
    tasks = []
    for path in files:
        source_rel = _get_source_rel(path)
        tasks.append(_convert_file_async(converter, path, output_dir, source_rel, **kwargs))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    converted = 0
    failed = 0
    outputs: list[str] = []
    errors: list[str] = []

    for path, res in zip(files, results, strict=True):
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


async def _convert_auto_batch_async(
    files: list[Path],
    output_dir: Path,
    converters: dict[str, ConverterFunc],
) -> dict[str, Any]:
    """Convert multiple files in parallel with auto-detection."""
    tasks = []
    task_paths: list[Path] = []
    skipped = 0

    for path in files:
        ext = path.suffix.lower()
        if ext not in converters:
            skipped += 1
            continue

        source_rel = _get_source_rel(path)
        converter = converters[ext]
        tasks.append(_convert_file_async(converter, path, output_dir, source_rel))
        task_paths.append(path)

    if not tasks:
        return {
            "converted": 0,
            "failed": 0,
            "skipped": skipped,
            "outputs": [],
            "errors": [],
        }

    results = await asyncio.gather(*tasks, return_exceptions=True)

    converted = 0
    failed = 0
    outputs: list[str] = []
    errors: list[str] = []

    for path, res in zip(task_paths, results, strict=True):
        if isinstance(res, BaseException):
            failed += 1
            errors.append(f"{path.name}: {res}")
        else:
            converted += 1
            outputs.append(res["output"])

    return {
        "converted": converted,
        "failed": failed,
        "skipped": skipped,
        "outputs": outputs,
        "errors": errors,
    }


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
    with LogSpan(span="convert.pdf", pattern=pattern, output_dir=output_dir) as s:
        files = _resolve_glob(pattern)
        if not files:
            s.add(error="no_match")
            return f"No files matched pattern: {pattern}"

        out_path = _resolve_output_dir(output_dir)

        if len(files) == 1:
            # Single file conversion
            try:
                source_rel = _get_source_rel(files[0])
                result = convert_pdf(files[0], out_path, source_rel)
                s.add(converted=1, pages=result["pages"], images=result["images"])
                return f"Converted {files[0].name}: {result['pages']} pages, {result['images']} images\nOutput: {result['output']}"
            except Exception as e:
                s.add(error=str(e))
                return f"Error converting {files[0].name}: {e}"

        # Batch conversion
        try:
            result = asyncio.run(_convert_batch_async(files, out_path, convert_pdf))
            s.add(converted=result["converted"], failed=result["failed"])

            lines = [f"Converted {result['converted']} files, {result['failed']} failed"]
            if result["outputs"]:
                lines.append("\nOutputs:")
                for output in result["outputs"]:
                    lines.append(f"  {output}")
            if result["errors"]:
                lines.append("\nErrors:")
                for error in result["errors"]:
                    lines.append(f"  {error}")

            return "\n".join(lines)
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


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
    with LogSpan(span="convert.word", pattern=pattern, output_dir=output_dir) as s:
        files = _resolve_glob(pattern)
        if not files:
            s.add(error="no_match")
            return f"No files matched pattern: {pattern}"

        out_path = _resolve_output_dir(output_dir)

        if len(files) == 1:
            try:
                source_rel = _get_source_rel(files[0])
                result = convert_word(files[0], out_path, source_rel)
                s.add(
                    converted=1,
                    paragraphs=result["paragraphs"],
                    tables=result["tables"],
                    images=result["images"],
                )
                return f"Converted {files[0].name}: {result['paragraphs']} paragraphs, {result['tables']} tables, {result['images']} images\nOutput: {result['output']}"
            except Exception as e:
                s.add(error=str(e))
                return f"Error converting {files[0].name}: {e}"

        try:
            result = asyncio.run(_convert_batch_async(files, out_path, convert_word))
            s.add(converted=result["converted"], failed=result["failed"])

            lines = [f"Converted {result['converted']} files, {result['failed']} failed"]
            if result["outputs"]:
                lines.append("\nOutputs:")
                for output in result["outputs"]:
                    lines.append(f"  {output}")
            if result["errors"]:
                lines.append("\nErrors:")
                for error in result["errors"]:
                    lines.append(f"  {error}")

            return "\n".join(lines)
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


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
    with LogSpan(
        span="convert.powerpoint",
        pattern=pattern,
        output_dir=output_dir,
        include_notes=include_notes,
    ) as s:
        files = _resolve_glob(pattern)
        if not files:
            s.add(error="no_match")
            return f"No files matched pattern: {pattern}"

        out_path = _resolve_output_dir(output_dir)

        if len(files) == 1:
            try:
                source_rel = _get_source_rel(files[0])
                result = convert_powerpoint(
                    files[0], out_path, source_rel, include_notes=include_notes
                )
                s.add(converted=1, slides=result["slides"], images=result["images"])
                return f"Converted {files[0].name}: {result['slides']} slides, {result['images']} images\nOutput: {result['output']}"
            except Exception as e:
                s.add(error=str(e))
                return f"Error converting {files[0].name}: {e}"

        try:
            result = asyncio.run(
                _convert_batch_async(
                    files, out_path, convert_powerpoint, include_notes=include_notes
                )
            )
            s.add(converted=result["converted"], failed=result["failed"])

            lines = [f"Converted {result['converted']} files, {result['failed']} failed"]
            if result["outputs"]:
                lines.append("\nOutputs:")
                for output in result["outputs"]:
                    lines.append(f"  {output}")
            if result["errors"]:
                lines.append("\nErrors:")
                for error in result["errors"]:
                    lines.append(f"  {error}")

            return "\n".join(lines)
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


def excel(
    *,
    pattern: str,
    output_dir: str,
    include_formulas: bool = False,
) -> str:
    """Convert Excel spreadsheets to Markdown.

    Converts XLSX files to Markdown tables with sheet-based sections.
    Uses streaming for memory-efficient processing of large files.

    Args:
        pattern: Glob pattern for input files (e.g., "data/*.xlsx")
        output_dir: Directory for output files
        include_formulas: Include cell formulas as comments

    Returns:
        Conversion summary with output paths, or error message

    Example:
        convert.excel(pattern="data/report.xlsx", output_dir="data/md")
        convert.excel(pattern="spreadsheets/*.xlsx", output_dir="output", include_formulas=True)
    """
    with LogSpan(
        span="convert.excel",
        pattern=pattern,
        output_dir=output_dir,
        include_formulas=include_formulas,
    ) as s:
        files = _resolve_glob(pattern)
        if not files:
            s.add(error="no_match")
            return f"No files matched pattern: {pattern}"

        out_path = _resolve_output_dir(output_dir)

        if len(files) == 1:
            try:
                source_rel = _get_source_rel(files[0])
                result = convert_excel(
                    files[0], out_path, source_rel, include_formulas=include_formulas
                )
                s.add(converted=1, sheets=result["sheets"], rows=result["rows"])
                return f"Converted {files[0].name}: {result['sheets']} sheets, {result['rows']} rows\nOutput: {result['output']}"
            except Exception as e:
                s.add(error=str(e))
                return f"Error converting {files[0].name}: {e}"

        try:
            result = asyncio.run(
                _convert_batch_async(
                    files, out_path, convert_excel, include_formulas=include_formulas
                )
            )
            s.add(converted=result["converted"], failed=result["failed"])

            lines = [f"Converted {result['converted']} files, {result['failed']} failed"]
            if result["outputs"]:
                lines.append("\nOutputs:")
                for output in result["outputs"]:
                    lines.append(f"  {output}")
            if result["errors"]:
                lines.append("\nErrors:")
                for error in result["errors"]:
                    lines.append(f"  {error}")

            return "\n".join(lines)
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


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
    with LogSpan(span="convert.auto", pattern=pattern, output_dir=output_dir) as s:
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
            result = asyncio.run(_convert_auto_batch_async(files, out_path, converters))
            s.add(converted=result["converted"], failed=result["failed"], skipped=result["skipped"])

            lines = [f"Converted {result['converted']} files, {result['failed']} failed, {result['skipped']} skipped (unsupported format)"]
            if result["outputs"]:
                lines.append("\nOutputs:")
                for output in result["outputs"]:
                    lines.append(f"  {output}")
            if result["errors"]:
                lines.append("\nErrors:")
                for error in result["errors"]:
                    lines.append(f"  {error}")

            return "\n".join(lines)
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"
