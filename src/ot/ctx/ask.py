"""Multi-question LLM query for the ctx pack."""

from __future__ import annotations

import re
from typing import Any

from ot.logging import LogSpan

from .config import _get_config
from .store import HandleStore, _get_store, _resolve_handle, is_expired


def _parse_numbered_answers(result: str, n: int) -> list[str]:
    """Parse numbered answers from model response."""
    answers: list[str] = []
    current_lines: list[str] = []
    _num_pat = re.compile(r"^\s*(?:[#*]+\s*)?(\d+)[.)]\s*(?:[#*]*\s*)?")
    for line in result.strip().split("\n"):
        m = _num_pat.match(line)
        if m and 1 <= int(m.group(1)) <= n:
            if current_lines:
                answers.append("\n".join(current_lines).strip())
            current_lines = [_num_pat.sub("", line, count=1)]
        else:
            current_lines.append(line)
    if current_lines:
        answers.append("\n".join(current_lines).strip())

    while len(answers) < n:
        answers.append("")
    return answers[:n]


def ctx_ask(
    handle: str,
    q: str | list[str],
    *,
    model: str | None = None,
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Send one or more questions about stored content to an LLM.

    Multiple questions are batched into a single model call and answers
    are returned in the same order.

    Args:
        handle: Context store handle (e.g. ``"3539ec02"``).
        q: Question string or list of question strings.
        model: LLM model override; falls back to ``ot_llm`` configured default.
        store: HandleStore instance (uses session default if not provided).

    Returns:
        ``{"handle": str, "result": [{"question": str, "answer": str}]}`` on
        success. ``{"handle": str, "error": str}`` on failure.

    Example:
        ctx.ask("3539ec02", q="What is the recommended entry point?")
        ctx.ask("3539ec02", q=["What are common mistakes?", "What is asyncio.gather?"])
    """
    questions = [q] if isinstance(q, str) else list(q)
    handle = _resolve_handle(handle)

    with LogSpan(span="ctx.ask", handle=handle, questionCount=len(questions)) as s:
        if store is None:
            store = _get_store()

        if not store.exists(handle):
            err = f"Handle not found: {handle}"
            s.add(error=err)
            return {"handle": handle, "error": err}

        try:
            meta = store.read_meta(handle)
        except (OSError, ValueError):
            err = f"Handle not found: {handle}"
            s.add(error=err)
            return {"handle": handle, "error": err}

        if is_expired(meta):
            err = f"Handle has expired: {handle}"
            s.add(error=err)
            return {"handle": handle, "error": err}

        try:
            content = store.read_content(handle)
        except OSError:
            err = f"Content not found for handle: {handle}"
            s.add(error=err)
            return {"handle": handle, "error": err}

        # Truncate large content
        config = _get_config()
        truncated = False
        ask_max = config.ask_max_bytes
        if ask_max > 0 and len(content.encode()) > ask_max:
            content = content.encode()[:ask_max].decode(errors="replace")
            truncated = True

        # Build prompt
        if len(questions) == 1:
            prompt = questions[0]
        else:
            numbered = "\n".join(f"{i + 1}. {qs}" for i, qs in enumerate(questions))
            prompt = (
                "Answer each of the following questions based on the content provided.\n"
                "Start each answer with only its question number followed by a period and space "
                f"(e.g. '1. your answer'). Do not use headings or bold formatting.\n"
                f"Questions:\n{numbered}"
            )

        try:
            from ot.services import get_services

            raw = get_services().llm_transform(data=content, prompt=prompt, model=model)
        except Exception as e:
            err_str = str(e)
            if "no llm service registered" in err_str.lower():
                err = (
                    "No LLM service is registered. "
                    "Install and load an LLM-capable pack such as ot_llm to use ctx.ask."
                )
            elif any(
                k in err_str.lower() for k in ("not configured", "api_key", "base_url")
            ):
                err = (
                    "ot_llm is not configured. "
                    "Set ot_llm.base_url, ot_llm.model, and OPENAI_API_KEY in secrets.yaml. "
                    f"Details: {e}"
                )
            else:
                err = f"ot_llm call failed: {e}"
            s.add(error=err)
            return {"handle": handle, "error": err}

        if raw.startswith("Error:"):
            s.add(error=raw)
            return {"error": raw, "handle": handle}

        if len(questions) == 1:
            answers = [raw.strip()]
        else:
            answers = _parse_numbered_answers(raw, len(questions))

        pairs = [
            {"question": qs, "answer": a}
            for qs, a in zip(questions, answers, strict=False)
        ]
        result: dict[str, Any] = {"handle": handle, "result": pairs}

        if truncated:
            result["truncated"] = True
            result["hint"] = (
                "Content was truncated to ask_max_bytes. "
                "Use ctx.slice() to narrow scope before re-querying."
            )

        s.add(questionCount=len(questions), truncated=truncated or None)
        return result


__all__ = ["ctx_ask"]
