"""LLM synthesis over memories."""

from __future__ import annotations

import re
from typing import Any

from otpack import LogSpan

from .db import _get_connection

_NUM_PAT = re.compile(r"^\s*(?:[#*]+\s*)?(\d+)[.)]\s*(?:[#*]*\s*)?")


def _parse_numbered_answers(result: str, n: int) -> list[str]:
    """Parse numbered answers from model response."""
    answers: list[str] = []
    current_lines: list[str] = []
    for line in result.strip().split("\n"):
        m = _NUM_PAT.match(line)
        if m and 1 <= int(m.group(1)) <= n:
            if current_lines:
                answers.append("\n".join(current_lines).strip())
            current_lines = [_NUM_PAT.sub("", line, count=1)]
        else:
            current_lines.append(line)
    if current_lines:
        answers.append("\n".join(current_lines).strip())

    while len(answers) < n:
        answers.append("")
    return answers[:n]


def ask(
    *,
    topic: str,
    q: str | list[str],
    id: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Ask one or more questions about a stored memory using an LLM.

    Multiple questions are batched into a single model call and answers
    are returned in the same order.

    Requires ot_llm to be configured (base_url, model, and API key).

    Args:
        topic: Exact topic path to read
        q: Question string or list of question strings
        id: Optional memory ID for direct lookup (overrides topic match)
        model: LLM model override; falls back to ot_llm configured default

    Returns:
        {"topic": str, "result": [{"question": str, "answer": str}]} on success.
        {"topic": str, "error": str} on failure.

    Example:
        mem.ask(topic="projects/onetool/rules", q="What is the main rule?")
        mem.ask(topic="specs/api", q=["What endpoints exist?", "What auth method is used?"])
    """
    questions = [q] if isinstance(q, str) else list(q)
    label = id if id else topic

    with LogSpan(span="mem.ask", topic=topic, questionCount=len(questions)) as s:
        try:
            conn = _get_connection()

            columns = "id, topic, content"
            if id:
                row = conn.execute(
                    f"SELECT {columns} FROM memories WHERE id = ?",
                    [id],
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT {columns} FROM memories WHERE topic = ?",
                    [topic],
                ).fetchone()

            if not row:
                err = f"No memory found for {'id' if id else 'topic'} '{label}'"
                s.add(error=err)
                return {"topic": label, "error": err}

            content = row[2]

        except Exception as e:
            err = f"Error reading memory: {e}"
            s.add(error=err)
            return {"topic": label, "error": err}

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
            from ottools.ot_llm import transform as llm_transform
        except ImportError:
            err = (
                "ot_llm is not installed. "
                "Install the ot_llm pack and configure base_url and model to use mem.ask."
            )
            s.add(error=err)
            return {"topic": label, "error": err}

        try:
            raw = llm_transform(data=content, prompt=prompt, model=model)
        except Exception as e:
            err_str = str(e)
            if any(
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
            return {"topic": label, "error": err}

        if raw.startswith("Error:"):
            s.add(error=raw)
            return {"topic": label, "error": raw}

        if len(questions) == 1:
            answers = [raw.strip()]
        else:
            answers = _parse_numbered_answers(raw, len(questions))

        pairs = [
            {"question": qs, "answer": a}
            for qs, a in zip(questions, answers, strict=False)
        ]
        s.add(questionCount=len(questions))
        return {"topic": row[1], "result": pairs}


__all__ = ["ask"]
