"""OT Caveman — LLM-powered text compaction and expansion.

Compacts verbose prose to terse caveman-speak, expands packed text back to
readable prose, and reads commands from a task queue.

NOTE: The compaction tool is named ``compact`` (not ``pack``) to avoid
shadowing the module-level ``pack = "ot_caveman"`` variable required for pack
name discovery. Use ``cm.compact(...)`` in the executor namespace.

**Requires configuration:**
- OPENAI_API_KEY in secrets.yaml
- llm.base_url or tools.ot_caveman.base_url in onetool.yaml
- llm.model or tools.ot_caveman.model in onetool.yaml
"""

from __future__ import annotations

# Pack name for dot notation: cm.compact(), cm.expand(), cm.input()
# Must appear before other imports.
pack = "ot_caveman"

__all__ = ["compact", "expand", "input"]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "lib": [
        ("openai", "pip install openai"),
        ("tiktoken", "pip install tiktoken"),
    ],
    "secrets": ["OPENAI_API_KEY"],
}

import re
from pathlib import Path
from typing import Any

from loguru import logger
from openai import OpenAI
from otpack import LogSpan, get_secret, get_tool_config, resolve_cwd_path
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Client cache — avoids new connection pool per call
# ---------------------------------------------------------------------------
_client_cache: dict[tuple[str, str, int], OpenAI] = {}

# ---------------------------------------------------------------------------
# Protected-content extraction — placeholder-based preservation
# ---------------------------------------------------------------------------

# Fenced code blocks: opening ``` (+ optional language) through closing ```
_FENCE_RE = re.compile(r"```[^\n]*\n[\s\S]*?```")
_PLACEHOLDER_FMT = "[!PLACEHOLDER:{n}!]"   # code-block placeholders

# Markdown tables: header row, separator row (─ : |), then data rows
_TABLE_FMT = "[!TABLE:{n}!]"               # table placeholders

# Injected into the system prompt whenever any placeholders are present
_PLACEHOLDER_INSTRUCTION = (
    "\n\nIMPORTANT: This text contains protected-content markers."
    "\n  [!PLACEHOLDER:N!] — protected code block (e.g. [!PLACEHOLDER:0!])"
    "\n  [!TABLE:N!]       — protected table     (e.g. [!TABLE:0!])"
    "\nCopy every marker EXACTLY as written — never remove, modify, or paraphrase them."
    "\nThey are restored verbatim after compaction."
)

# ---------------------------------------------------------------------------
# Preamble stripping helpers
# ---------------------------------------------------------------------------

# Common LLM opener phrases to strip when they appear as the entire first line
_PREAMBLE_MARKERS = (
    "sure",
    "of course",
    "certainly",
    "here's",
    "here is",
    "absolutely",
    "happy to",
    "i'll",
    "i will",
    "no problem",
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class Config(BaseModel):
    """Pack configuration — discovered by registry."""

    base_url: str = Field(
        default="",
        description="OpenAI-compatible API base URL (empty = inherit from llm.base_url)",
    )
    model: str = Field(
        default="",
        description="Model to use (empty = inherit from llm.model)",
    )
    timeout: int = Field(default=30, description="API timeout in seconds")
    max_tokens: int = Field(default=8192, description="Maximum tokens in response")
    cost_per_1m_tokens: float = Field(
        default=0.0,
        description="Cost rate (USD per 1M tokens). When non-zero, cost_saved_usd "
        "is included in compact/expand results.",
    )


def _get_config() -> Config:
    """Get ot_caveman config with llm.* fallback."""
    config = get_tool_config("ot_caveman", Config)
    try:
        from ot.config import get_llm_config

        llm = get_llm_config()
        updates: dict[str, str] = {}
        if not config.base_url and llm.base_url:
            updates["base_url"] = llm.base_url
        if not config.model and llm.model:
            updates["model"] = llm.model
        if updates:
            config = config.model_copy(update=updates)
    except Exception as e:
        logger.warning("Failed to load top-level llm config for ot_caveman fallbacks: {}", e)
    return config


def _get_client(config: Config) -> tuple[OpenAI, str] | tuple[None, str]:
    """Return (client, model) or (None, error_string).

    Returns a distinct error string for each missing configuration element.
    """
    api_key = get_secret("OPENAI_API_KEY") or get_secret("OT_LLM_API_KEY")
    if not api_key:
        return None, (
            "Error: ot_caveman not configured. "
            "Set OPENAI_API_KEY in secrets.yaml."
        )
    if not config.base_url:
        return None, (
            "Error: ot_caveman not configured. "
            "Set llm.base_url or tools.ot_caveman.base_url in onetool.yaml."
        )
    if not config.model:
        return None, (
            "Error: ot_caveman not configured. "
            "Set llm.model or tools.ot_caveman.model in onetool.yaml."
        )

    cache_key = (api_key, config.base_url, config.timeout)
    if cache_key not in _client_cache:
        _client_cache[cache_key] = OpenAI(
            api_key=api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )
    return _client_cache[cache_key], config.model


def _count_tokens(text: str) -> int:
    """Count tokens using tiktoken (gpt-4 encoding with cl100k_base fallback)."""
    import tiktoken

    try:
        enc = tiktoken.encoding_for_model("gpt-4")
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _call_llm(
    client: OpenAI,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> tuple[str, str | None]:
    """Call the LLM API. Returns (content, error) where error is None on success."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or "", None
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "sk-" in error_msg:
            error_msg = "Authentication error - check OPENAI_API_KEY in secrets.yaml"
        return "", error_msg


def _strip_preamble(text: str) -> str:
    """Strip common LLM preambles from the start of a response.

    Removes common opener phrases ("Sure, ...", "Here's ...") on the first line only.
    """
    first = text.split("\n", 1)[0].strip().lower().rstrip(",!.")
    if not any(
        first == marker or first.startswith((marker + " ", marker + ","))
        for marker in _PREAMBLE_MARKERS
    ):
        return text.strip()

    lines = text.split("\n")[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    return "\n".join(lines).strip()


def _extract_fences(text: str) -> tuple[str, dict[str, str]]:
    """Replace fenced code blocks with [!PLACEHOLDER:N!] placeholders.

    Returns (prose_with_placeholders, {placeholder: original_block}).
    Returns (text, {}) when no fenced blocks are present.
    """
    blocks: dict[str, str] = {}
    counter = 0

    def _replace(m: re.Match[str]) -> str:
        nonlocal counter
        key = _PLACEHOLDER_FMT.format(n=counter)
        blocks[key] = m.group(0)
        counter += 1
        return key

    result = _FENCE_RE.sub(_replace, text)
    return result, blocks


def _is_table_row(line: str) -> bool:
    """Return True if line looks like a markdown table row (starts and ends with |)."""
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and len(s) > 2


def _is_separator_row(line: str) -> bool:
    """Return True if line is a markdown table separator (only | - : space/tab, has -)."""
    s = line.strip()
    return (
        s.startswith("|")
        and s.endswith("|")
        and "-" in s
        and all(c in "|-: \t" for c in s)
    )


def _normalize_table(table: str) -> str:
    """Strip column-alignment padding from a markdown table.

    - Data cells: strip surrounding whitespace inside each cell.
    - Separator row: normalize to |---|---| (preserve : alignment markers).
    """
    out: list[str] = []
    for line in table.split("\n"):
        if not _is_table_row(line):
            out.append(line)
            continue
        cells = line.strip().split("|")[1:-1]  # drop leading/trailing empty strings
        if _is_separator_row(line):
            norm: list[str] = []
            for cell in cells:
                c = cell.strip()
                left, right = c.startswith(":"), c.endswith(":")
                if left and right:
                    norm.append(":---:")
                elif left:
                    norm.append(":---")
                elif right:
                    norm.append("---:")
                else:
                    norm.append("---")
            out.append("|" + "|".join(norm) + "|")
        else:
            out.append("| " + " | ".join(c.strip() for c in cells) + " |")
    return "\n".join(out)


def _extract_tables(text: str) -> tuple[str, dict[str, str]]:
    """Replace markdown tables with [!TABLE:N!] placeholders (normalized first).

    Scans line-by-line: a table is a header row immediately followed by a
    separator row, then zero or more data rows. Returns
    (text_with_placeholders, {placeholder: normalized_table}).
    """
    lines = text.split("\n")
    blocks: dict[str, str] = {}
    counter = 0
    result: list[str] = []
    i = 0
    while i < len(lines):
        # A table starts when the NEXT line is a separator row
        if (
            _is_table_row(lines[i])
            and i + 1 < len(lines)
            and _is_separator_row(lines[i + 1])
        ):
            table_lines = [lines[i], lines[i + 1]]
            j = i + 2
            while j < len(lines) and _is_table_row(lines[j]):
                table_lines.append(lines[j])
                j += 1
            normalized = _normalize_table("\n".join(table_lines))
            key = _TABLE_FMT.format(n=counter)
            blocks[key] = normalized
            counter += 1
            result.append(key)
            i = j
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result), blocks


def _restore_protected(text: str, blocks: dict[str, str]) -> tuple[str, list[str]]:
    """Restore all protected blocks (fences and tables) from their placeholders.

    Returns (restored_text, missing_keys).
    missing_keys is non-empty if the LLM dropped or altered any marker.
    """
    missing: list[str] = []
    for key, block in blocks.items():
        if key in text:
            text = text.replace(key, block)
        else:
            missing.append(key)
    return text, missing


def _verify_compact(original: str, compacted: str) -> tuple[str, bool]:
    """Verify compact output is valid. Returns (text, fell_back).

    Falls back to the original (unchanged) when:
    - Output is empty — model returned nothing useful.
    - Output has fewer ``` fences than input — protected code blocks were dropped.
    - Output is longer than input — model expanded instead of compacting.

    The second element is True when the original was returned unchanged.
    """
    if not compacted.strip():
        return original, True
    if compacted.count("```") < original.count("```"):
        return original, True
    if len(compacted) > len(original):
        return original, True
    return compacted, False


def _get_template(name: str) -> str:
    """Load a named prompt template from the global prompts config."""
    from ot.prompts import get_prompts

    return get_prompts().templates.get(name, "")


def _is_glob(s: str) -> bool:
    """Return True if string contains glob wildcard characters."""
    return any(c in s for c in ("*", "?", "["))


def _glob_expand(pattern: str) -> tuple[list[Path], Path]:
    """Expand a glob pattern relative to cwd. Returns (sorted paths, anchor)."""
    p = Path(pattern)
    parts = p.parts

    # Separate the non-wildcard anchor from the glob pattern
    anchor_parts: list[str] = []
    for part in parts:
        if any(c in part for c in ("*", "?", "[")):
            break
        anchor_parts.append(part)

    if anchor_parts:
        anchor = resolve_cwd_path(str(Path(*anchor_parts)))
        glob_pattern = str(Path(*parts[len(anchor_parts) :]))
    else:
        anchor = resolve_cwd_path(".")
        glob_pattern = pattern

    return sorted(anchor.glob(glob_pattern)), anchor


def _output_path(
    fpath: Path,
    glob_anchor: Path,
    dest_dir: Path | None,
    overwrite: bool,
    suffix: str,
) -> Path:
    """Compute output path for a batch-processed file."""
    if overwrite:
        return fpath
    if dest_dir is not None:
        rel = fpath.relative_to(glob_anchor)
        return dest_dir / rel.parent / f"{rel.stem}{suffix}{rel.suffix}"
    return fpath.parent / f"{fpath.stem}{suffix}{fpath.suffix}"


def _compact_text(text: str) -> str:
    """Compact text to terse caveman-speak. Raises RuntimeError on failure.

    Returns the compacted text, or the original text if compaction fell back
    (e.g., output was longer, empty, or dropped code blocks).
    Never returns an error string — callers should catch RuntimeError.
    """
    system_prompt = _get_template("ot_caveman_compact")
    user_msg_tpl = _get_template("ot_caveman_compact_input")
    if not system_prompt:
        raise RuntimeError("missing 'ot_caveman_compact' template in prompts.yaml")
    if not user_msg_tpl:
        raise RuntimeError("missing 'ot_caveman_compact_input' template in prompts.yaml")

    config = _get_config()
    client, model_or_err = _get_client(config)
    if client is None:
        raise RuntimeError(str(model_or_err).removeprefix("Error: "))
    model = model_or_err  # type: ignore[assignment]

    prose, fence_blocks = _extract_fences(text)
    prose, table_blocks = _extract_tables(prose)
    all_blocks = {**fence_blocks, **table_blocks}
    effective_system = system_prompt + _PLACEHOLDER_INSTRUCTION if all_blocks else system_prompt
    user_msg = user_msg_tpl.format(content=prose)

    raw, err = _call_llm(
        client,
        model,
        [
            {"role": "system", "content": effective_system},
            {"role": "user", "content": user_msg},
        ],
        0.1,
        config.max_tokens,
    )
    if err:
        raise RuntimeError(err)

    stripped = _strip_preamble(raw)
    if all_blocks:
        restored, missing = _restore_protected(stripped, all_blocks)
        compacted, _ = (text, True) if missing else _verify_compact(text, restored)
    else:
        compacted, _ = _verify_compact(text, stripped)
    return compacted


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def compact(
    *,
    text: str | None = None,
    src: str | None = None,
    dest: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any] | str:
    """Compact text or a file to terse caveman-speak.

    Accepts either inline text or a file path (not both). Compaction is lossy
    — meaning is preserved but original wording is not recoverable. Code blocks,
    URLs, paths, error messages, security warnings, and other protected content
    are never modified.

    Args:
        text: Inline text to compact.
        src: Path to input file (relative to cwd or absolute). Supports glob
            patterns (*, ?, [) for batch processing.
        dest: Path to write compacted result (may equal src for in-place). For
            glob src, dest is a directory; each result is written as
            <dest>/<stem>-min.<ext>.
        overwrite: For glob src only — write each result in-place (ignores -min naming).

    Returns:
        Dict with keys: text, tokens_in, tokens_out, reduction_pct.
        Adds file_out key when dest is given.
        For glob src: returns {files, skipped, tokens_in, tokens_out, reduction_pct}.
        Adds cost_saved_usd to any result when tools.ot_caveman.cost_per_1m_tokens is set.
        Returns error string on misconfiguration, invalid input, or API failure.

    Example:
        cm.compact(text="The quick brown fox jumped over the lazy dog.")
        cm.compact(src="notes.md", dest="notes-slim.md")
        cm.compact(src="notes.md", dest="notes.md")
        cm.compact(src="dev/guides/*.md", dest="scratch/compact")
    """
    with LogSpan(span="ot_caveman.compact") as s:
        # --- Input validation ---
        if text is not None and src is not None:
            return "Error: provide either text or src, not both"
        if text is None and src is None:
            return "Error: provide text or src"

        # --- Pre-validate single-file / inline content before any LLM setup ---
        single_content: str | None = None
        if src is None or not _is_glob(src):
            if src is not None:
                path = resolve_cwd_path(src)
                if not path.exists():
                    return f"Error: file not found: {src}"
                single_content = path.read_text(encoding="utf-8")
            else:
                single_content = text
            if not single_content or not single_content.strip():
                return "Error: input is empty"
            s.add(inputLen=len(single_content))

        # --- Glob batch mode ---
        if src is not None and _is_glob(src):
            matched, glob_anchor = _glob_expand(src)
            if not matched:
                return f"Error: no files matched pattern: {src}"

            # Pre-validate config/client before touching any files
            config = _get_config()
            _client, _err = _get_client(config)
            if _client is None:
                return _err  # type: ignore[return-value]

            dest_dir: Path | None = None
            if dest is not None:
                dest_dir = resolve_cwd_path(dest)
                dest_dir.mkdir(parents=True, exist_ok=True)

            total_in = total_out = processed = skipped = unchanged = 0

            for fpath in matched:
                try:
                    content = fpath.read_text(encoding="utf-8")
                except OSError as e:
                    logger.warning("ot_caveman.compact: skipping {} — read error: {}", fpath, e)
                    skipped += 1
                    continue
                if not content or not content.strip():
                    skipped += 1
                    continue

                tokens_in = _count_tokens(content)
                try:
                    compacted = _compact_text(content)
                except RuntimeError as e:
                    logger.warning("ot_caveman.compact: skipping {} — {}", fpath, e)
                    skipped += 1
                    continue
                fell_back = compacted == content
                if fell_back:
                    logger.debug("ot_caveman.compact: fell back for {} (output longer, empty, or dropped blocks)", fpath)
                    unchanged += 1
                tokens_out_file = tokens_in if fell_back else _count_tokens(compacted)

                out_path = _output_path(fpath, glob_anchor, dest_dir, overwrite, "-min")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(compacted, encoding="utf-8")

                total_in += tokens_in
                total_out += tokens_out_file
                processed += 1

            reduction = round((1 - total_out / max(total_in, 1)) * 100)
            batch_result: dict[str, Any] = {
                "files": processed,
                "skipped": skipped,
                "tokens_in": total_in,
                "tokens_out": total_out,
                "reduction_pct": reduction,
            }
            if unchanged:
                batch_result["unchanged"] = unchanged
            if config.cost_per_1m_tokens:
                batch_result["cost_saved_usd"] = round(
                    (total_in - total_out) / 1_000_000 * config.cost_per_1m_tokens, 6
                )
            return batch_result

        # --- Single-file / inline mode ---
        content = single_content  # type: ignore[assignment]
        config = _get_config()
        tokens_in = _count_tokens(content)

        try:
            compacted = _compact_text(content)
        except RuntimeError as e:
            s.add(error=str(e))
            return f"Error: {e}"

        fell_back = compacted == content
        tokens_out = _count_tokens(compacted)
        reduction_pct = round((1 - tokens_out / max(tokens_in, 1)) * 100)

        s.add(tokensIn=tokens_in, tokensOut=tokens_out, reductionPct=reduction_pct)

        result: dict[str, Any] = {
            "text": compacted,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "reduction_pct": reduction_pct,
        }
        if fell_back:
            result["unchanged"] = True

        if config.cost_per_1m_tokens:
            result["cost_saved_usd"] = round(
                (tokens_in - tokens_out) / 1_000_000 * config.cost_per_1m_tokens, 6
            )

        if dest is not None:
            out_path = resolve_cwd_path(dest)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(compacted, encoding="utf-8")
            result["file_out"] = dest

        return result


def expand(
    *,
    text: str | None = None,
    src: str | None = None,
    dest: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any] | str:
    """Expand packed (compressed) text back to readable prose.

    Reconstruction is lossy — does not attempt to restore original wording.
    Code blocks and other protected content are preserved verbatim.

    Args:
        text: Inline packed text to expand.
        src: Path to file containing packed text. Supports glob patterns for batch.
        dest: Path to write expanded result. For glob src, dest is a directory.
        overwrite: For glob src only — write each result in-place.

    Returns:
        Dict with keys: text, tokens_in, tokens_out, expansion_pct.
        Adds file_out key when dest is given.
        For glob src: returns {files, skipped, tokens_in, tokens_out, expansion_pct}.
        Adds cost_saved_usd when tools.ot_caveman.cost_per_1m_tokens is set.
        Returns error string on misconfiguration, invalid input, or API failure.

    Example:
        cm.expand(text="fox jump lazy dog")
        cm.expand(src="notes-slim.md", dest="notes-readable.md")
        cm.expand(src="scratch/compact/*.md", dest="scratch/expanded")
    """
    with LogSpan(span="ot_caveman.expand") as s:
        if text is not None and src is not None:
            return "Error: provide either text or src, not both"
        if text is None and src is None:
            return "Error: provide text or src"

        # --- Pre-validate single-file / inline content before any LLM setup ---
        single_content: str | None = None
        if src is None or not _is_glob(src):
            if src is not None:
                path = resolve_cwd_path(src)
                if not path.exists():
                    return f"Error: file not found: {src}"
                single_content = path.read_text(encoding="utf-8")
            else:
                single_content = text
            if not single_content or not single_content.strip():
                return "Error: input is empty"
            s.add(inputLen=len(single_content))

        # --- Load prompts ---
        system_prompt = _get_template("ot_caveman_expand")
        if not system_prompt:
            return "Error: missing 'ot_caveman_expand' template in prompts.yaml"

        # --- Get LLM client ---
        config = _get_config()
        client, model_or_err = _get_client(config)
        if client is None:
            return model_or_err  # type: ignore[return-value]
        model = model_or_err  # type: ignore[assignment]

        # --- Glob batch mode ---
        if src is not None and _is_glob(src):
            matched, glob_anchor = _glob_expand(src)
            if not matched:
                return f"Error: no files matched pattern: {src}"

            dest_dir: Path | None = None
            if dest is not None:
                dest_dir = resolve_cwd_path(dest)
                dest_dir.mkdir(parents=True, exist_ok=True)

            total_in = total_out = processed = skipped = 0

            for fpath in matched:
                try:
                    content = fpath.read_text(encoding="utf-8")
                except OSError as e:
                    logger.warning("ot_caveman.expand: skipping {} — read error: {}", fpath, e)
                    skipped += 1
                    continue
                if not content or not content.strip():
                    skipped += 1
                    continue

                tokens_in = _count_tokens(content)
                raw, err = _call_llm(
                    client,
                    model,
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content},
                    ],
                    0.2,
                    config.max_tokens,
                )
                if err:
                    logger.warning("ot_caveman.expand: skipping {} — LLM error: {}", fpath, err)
                    skipped += 1
                    continue

                expanded = _strip_preamble(raw)
                tokens_out_file = _count_tokens(expanded)

                out_path = _output_path(fpath, glob_anchor, dest_dir, overwrite, "-exp")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(expanded, encoding="utf-8")

                total_in += tokens_in
                total_out += tokens_out_file
                processed += 1

            expansion_pct = round((total_out / max(total_in, 1) - 1) * 100)
            batch_result: dict[str, Any] = {
                "files": processed,
                "skipped": skipped,
                "tokens_in": total_in,
                "tokens_out": total_out,
                "expansion_pct": expansion_pct,
            }
            if config.cost_per_1m_tokens:
                batch_result["cost_saved_usd"] = round(
                    (total_in - total_out) / 1_000_000 * config.cost_per_1m_tokens, 6
                )
            return batch_result

        # --- Single-file / inline mode ---
        content = single_content  # type: ignore[assignment]
        tokens_in = _count_tokens(content)

        raw, err = _call_llm(
            client,
            model,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            0.2,
            config.max_tokens,
        )
        if err:
            s.add(error=err)
            return f"Error: {err}"

        expanded = _strip_preamble(raw)
        tokens_out = _count_tokens(expanded)
        expansion_pct = round((tokens_out / max(tokens_in, 1) - 1) * 100)

        s.add(tokensIn=tokens_in, tokensOut=tokens_out, expansionPct=expansion_pct)

        result: dict[str, Any] = {
            "text": expanded,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "expansion_pct": expansion_pct,
        }

        if config.cost_per_1m_tokens:
            result["cost_saved_usd"] = round(
                (tokens_in - tokens_out) / 1_000_000 * config.cost_per_1m_tokens, 6
            )

        if dest is not None:
            out_path = resolve_cwd_path(dest)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(expanded, encoding="utf-8")
            result["file_out"] = dest

        return result


def _find_named_command(blocks: list[str], command: str) -> str | None:
    """Find a block whose first non-header line is name:<command>.

    Ignores [x] done status. Returns the block body (lines after the name: line),
    or None if not found.
    """
    name_tag = f"name:{command}".lower()
    for block in blocks:
        if not block:
            continue
        lines = block.splitlines()
        for j, line in enumerate(lines):
            if line.startswith("# "):
                continue
            # First non-header line — check for name:<command> (ignoring [x] prefix)
            check = line.strip().removeprefix("[x] ").strip()
            if check.lower() == name_tag:
                return "\n".join(lines[j + 1:]).strip()
            break  # First non-header line is not the name tag — skip this block
    return None


def _compact_command_text(command_text: str) -> str:
    """Compact command text using the ot_caveman_input_compact prompt.

    Returns the compacted text, or an error string on failure.
    """
    system_prompt = _get_template("ot_caveman_input_compact")
    if not system_prompt:
        return "Error: missing 'ot_caveman_input_compact' template in prompts.yaml"

    config = _get_config()
    client, model_or_err = _get_client(config)
    if client is None:
        return model_or_err  # type: ignore[return-value]
    model = model_or_err  # type: ignore[assignment]

    raw, err = _call_llm(
        client,
        model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": command_text},
        ],
        0.1,
        config.max_tokens,
    )
    if err:
        return f"Error: {err}"
    return _strip_preamble(raw) or command_text


def input(
    *,
    file: str = "command.md",
    command: str | None = None,
    compact: bool = True,
) -> str:
    """Read the next pending command from a command.md task file.

    Parses the file for command blocks separated by ``---`` dividers. Finds
    the first block whose title line does NOT start with ``[x]``, marks it
    done by prepending ``[x] `` to the title in the file, and returns the
    full command text (title + body).

    Header lines starting with ``# `` are skipped when searching for the
    pending title.

    Args:
        file: Path to command file (default: "command.md", relative to cwd).
        command: If given, find the block with a matching ``name:<command>``
            first line and return its text without modifying the file. Ignores
            ``[x]`` status — named commands can be re-invoked on demand.
        compact: If True (default), compact the returned command text using the
            ``ot_caveman_input_compact`` prompt before returning. Pass
            ``compact=False`` to get raw text.

    Returns:
        The command text (optionally compacted), or "NO MORE COMMANDS" if all
        are done, or an error string if the file is not found or the named
        command is not found.

    Example:
        cm.input(compact=False)
        cm.input(file="tasks/sprint.md", compact=False)
        cm.input(command="fix")
    """
    with LogSpan(span="ot_caveman.input", file=file) as s:
        path = resolve_cwd_path(file)
        if not path.exists():
            return f"Error: file not found: {file}"

        raw = path.read_text(encoding="utf-8")
        raw_blocks = re.split(r"\n\s*---\s*\n", raw)
        blocks = [b.strip() for b in raw_blocks]

        # --- Named command lookup (read-only, ignores done status) ---
        if command is not None:
            cmd_text = _find_named_command(blocks, command)
            if cmd_text is None:
                return f"Error: command not found: {command}"
            s.add(result="named_command_returned", command=command)
            if compact:
                return _compact_command_text(cmd_text)
            return cmd_text

        # --- Sequential queue ---
        pending_idx: int | None = None
        pending_title_line_idx: int | None = None

        for i, block in enumerate(blocks):
            if not block:
                continue
            lines = block.splitlines()
            for j, line in enumerate(lines):
                if line.startswith("# ") or not line.strip():
                    continue
                # First non-header, non-blank line is the title
                if not line.startswith("[x]"):
                    pending_idx = i
                    pending_title_line_idx = j
                break

            if pending_idx is not None:
                break

        if pending_idx is None:
            s.add(result="no_more_commands")
            return "NO MORE COMMANDS"

        block_lines = blocks[pending_idx].splitlines()
        title_idx = pending_title_line_idx  # type: ignore[assignment]

        # Collect command text before modifying block_lines — skip leading # headers
        cmd_lines: list[str] = []
        header_done = False
        for line in block_lines:
            if not header_done and line.startswith("# "):
                continue
            header_done = True
            cmd_lines.append(line)

        command_text = "\n".join(cmd_lines).strip()

        # Mark title as done in the file
        block_lines[title_idx] = f"[x] {block_lines[title_idx]}"

        # Write updated content back — preserve blank lines around --- dividers
        blocks[pending_idx] = "\n".join(block_lines)
        updated = "\n\n---\n\n".join(blocks)
        path.write_text(updated, encoding="utf-8")

        s.add(result="command_returned")
        if compact:
            return _compact_command_text(command_text)
        return command_text
