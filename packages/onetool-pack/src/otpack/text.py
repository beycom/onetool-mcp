"""Text truncation and error formatting utilities."""

from __future__ import annotations

import re
import subprocess
from typing import Any

import yaml

__all__ = [
    "extract_structured_data",
    "format_error",
    "format_sources",
    "parse_frontmatter",
    "run_command",
    "truncate",
]

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def format_sources(
    results: list[dict[str, Any]], *, max_sources: int | None = None
) -> str:
    """Format source URLs as a numbered, deduplicated markdown link list."""
    seen_urls: set[str] = set()
    lines: list[str] = []
    num = 0
    for result in results:
        url = result.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        num += 1
        if max_sources is not None and num > max_sources:
            break
        title = result.get("title", "") or url
        lines.append(f"{num}. [{title}]({url})")
    return "\n".join(lines)


def extract_structured_data(
    *,
    text: str,
    sources: list[dict[str, Any]],
    extract_schema: dict[str, Any],
    return_provenance: bool,
    confidence_key: str | None = None,
) -> dict[str, Any]:
    """Extract structured fields from free text using a constrained schema.

    Shared by search packs. ``confidence_key`` (e.g. ``"score"``) reads a per-source
    confidence value into provenance when provided; ``None`` omits it.
    """
    data: dict[str, Any] = {}
    errors: list[dict[str, str]] = []
    provenance: dict[str, dict[str, Any]] = {}
    source_url = sources[0].get("url") if sources else None
    confidence = (
        sources[0].get(confidence_key) if (sources and confidence_key) else None
    )

    for field in extract_schema.get("fields", []):
        name = str(field.get("name", "")).strip()
        field_type = str(field.get("type", "string"))
        required = bool(field.get("required", False))
        lowered_name = name.lower()
        value: Any = None
        snippet: str = ""

        if field_type == "boolean":
            for token in ("true", "false"):
                idx = text.lower().find(token)
                if idx >= 0:
                    value = token == "true"
                    snippet = text[max(0, idx - 20):idx + len(token) + 20].strip()
                    break
        elif field_type == "number":
            match = _NUMBER_RE.search(text)
            if match:
                snippet = match.group(0)
                value = float(snippet) if "." in snippet else int(snippet)
        else:
            if "email" in lowered_name:
                match = _EMAIL_RE.search(text)
                if match:
                    value = match.group(0)
                    snippet = value
            if value is None:
                key_match = re.search(
                    rf"{re.escape(name)}\s*[:=-]\s*(.+)",
                    text,
                    flags=re.IGNORECASE,
                )
                if key_match:
                    value = key_match.group(1).strip().splitlines()[0]
                    snippet = value

        data[name] = value
        if required and value in (None, ""):
            errors.append(
                {
                    "field": name,
                    "error_code": "required_field_missing",
                    "error_message": f"Required field '{name}' could not be extracted",
                }
            )

        if return_provenance:
            provenance[name] = {
                "source_url": source_url,
                "snippet": snippet,
                "confidence": confidence,
            }

    result: dict[str, Any] = {
        "mode": "structured_extraction",
        "data": data,
        "errors": errors,
    }
    if return_provenance:
        result["provenance"] = provenance
    return result


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split leading YAML frontmatter from body. Returns ``(metadata, body)``.

    Content with no frontmatter returns ``({}, content)`` unchanged; malformed YAML
    in the frontmatter block does not raise — it falls back to ``({}, body)``.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    body = content[match.end():]
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body


def truncate(text: str, max_length: int = 4000, indicator: str = "...") -> str:
    """Truncate text to a maximum length with an indicator.

    Args:
        text: Text to truncate
        max_length: Maximum length including indicator
        indicator: String to append when truncated (default: "...")

    Returns:
        Truncated text with indicator, or original if within limit
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(indicator)] + indicator


def format_error(message: str, details: dict[str, Any] | None = None) -> str:
    """Format an error message consistently.

    Args:
        message: Main error message
        details: Optional additional details

    Returns:
        Formatted error string
    """
    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        return f"Error: {message} ({detail_str})"
    return f"Error: {message}"


def run_command(
    args: list[str],
    *,
    timeout: float = 30.0,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """Run a subprocess command with timeout.

    Args:
        args: Command and arguments
        timeout: Timeout in seconds (default: 30)
        cwd: Working directory

    Returns:
        Tuple of (return_code, stdout, stderr)

    Raises:
        subprocess.TimeoutExpired: If command times out
    """
    result = subprocess.run(
        args,
        timeout=timeout,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr
