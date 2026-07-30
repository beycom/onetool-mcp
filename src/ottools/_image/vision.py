"""Provider-neutral shared generation calls for the image pack.

Supports single questions, JSON-contract batched questions (with per-question
recovery), multi-image calls, and structured summary extraction.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from ot.config import get_config
from ot.generation import (
    GenerationError,
    GenerationRequest,
    generate,
    resolve_generation,
)
from otpack import LogSpan, get_secret

if TYPE_CHECKING:
    from ot.config.routing import ReasoningEffort, StructuredOutputMode

    from .config import Config

_SUMMARY_PROMPT = """\
You are an OCR and image analysis engine. Return ONLY valid JSON with exactly these keys:
{
  "type": "<one of: screenshot, diagram, photo, chart, code, ui, other>",
  "mode": "<one of: dark, light, unknown>",
  "colours": ["<2-5 dominant colour names>"],
  "description": "<one sentence describing the overall purpose or subject>",
  "content": "<full structured markdown OCR — see rules below>"
}

Rules for the 'content' field:
- Extract ALL visible text verbatim. Do not paraphrase or summarise.
- Use ## for top-level visual sections, ### for subsections, matching visual hierarchy.
- Wrap code in triple-backtick blocks with language hint.
- Render tables as markdown tables.
- Render lists as markdown lists, preserving numbering or bullets.
- Mark buttons and badges as **[Label]**, input fields as _[placeholder]_.
- Include a ## Interactive Controls section at the end: a markdown table with columns Label | Type | Location.
- Skip purely decorative elements (icons without labels, background imagery)."""


def call_vision(
    images: list[bytes],
    prompt: str,
    config: Config,
    *,
    model: str | None = None,
    effort: ReasoningEffort | None = None,
    structured_output: StructuredOutputMode | None = None,
) -> str:
    """Send one or more images and a text prompt to the configured vision model.

    Multi-image calls interleave a text label before each image block
    (``"Image 1:"``, image, ``"Image 2:"``, image, …, prompt) so questions can
    reference "image 1" / "image 2" unambiguously.

    Args:
        images: PNG byte payloads ready for upload (already resized).
        prompt: Text prompt to accompany the image(s).
        config: Image pack config containing any pack-level route override.

    Returns:
        Model response text, or an error string starting with ``"Error:"`` if
        the model is not configured or the API call fails.
    """
    root = get_config()
    try:
        route = resolve_generation(
            config=root,
            pack=config.llm,
            model=model,
            effort=effort,
            required_modalities=frozenset({"text", "image"}),
            structured_output=structured_output,
        )
        labelled_prompt = prompt
        if len(images) > 1:
            labelled_prompt = (
                "Images are attached in numeric order as image 1, image 2, and so on.\n\n"
                f"{prompt}"
            )
        result = generate(
            route=route,
            request=GenerationRequest(
                prompt=labelled_prompt,
                images=tuple(images),
                structured_output=structured_output,
            ),
            secret_resolver=get_secret,
        )
        return result.content
    except GenerationError as exc:
        return f"Error: {exc}"


def parse_json_payload(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from model output.

    Strips markdown code fences, tries ``json.loads``, then falls back to the
    first embedded ``{...}`` object. Returns ``None`` when no object parses.
    """
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group())
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def ask_questions(
    images: list[bytes],
    questions: list[str],
    config: Config,
    *,
    model: str | None = None,
    effort: ReasoningEffort | None = None,
) -> list[str]:
    """Send one or more questions to the vision model in a single call.

    Multi-question batches use a JSON answer contract (return only
    ``{"answers": [...]}`` with exactly N strings in question order). When the
    batched response fails to parse or the answer count mismatches, falls back
    to one ``call_vision()`` per question so a question never gets another
    question's answer or a silent empty string.

    Args:
        images: PNG byte payloads ready for upload.
        questions: One or more question strings.
        config: Image pack config.

    Returns:
        List of answer strings in the same order as ``questions``.
        Returns a single-element list with an error string if the call fails.
    """
    if len(questions) == 1:
        # Single question stays plain text — no JSON round-trip
        result = call_vision(
            images,
            questions[0],
            config,
            model=model,
            effort=effort,
        )
        if result.startswith("Error:"):
            return [result]
        return [result.strip()]

    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    prompt = (
        "Answer each of the following questions about the image(s).\n"
        'Return ONLY a JSON object of the form {"answers": ["<answer 1>", ...]} '
        f"with exactly {len(questions)} answer strings, in question order. "
        "No markdown, no other keys, no commentary.\n"
        f"Questions:\n{numbered}"
    )

    with LogSpan(span="ot_image.ask_questions", questionCount=len(questions)) as s:
        result = call_vision(
            images,
            prompt,
            config,
            model=model,
            effort=effort,
            structured_output="json_object",
        )
        if result.startswith("Error:"):
            # Fallback would fail identically — short-circuit
            s.add(error=result)
            return [result]

        payload = parse_json_payload(result)
        answers = payload.get("answers") if payload else None
        if isinstance(answers, list) and len(answers) == len(questions):
            return [str(a) for a in answers]

        # Batched contract violated — recover losslessly, one call per question
        s.add(fallback="per_question")
        return [
            call_vision(
                images,
                question,
                config,
                model=model,
                effort=effort,
            ).strip()
            for question in questions
        ]


def extract_summary(
    model_bytes: bytes,
    config: Config,
    *,
    model: str | None = None,
    effort: ReasoningEffort | None = None,
) -> dict[str, object] | str:
    """Extract a structured summary of the image via the vision model.

    Calls the vision model with a structured extraction prompt and parses the
    JSON response. The result is suitable for caching in ``meta.json``.

    Args:
        model_bytes: PNG bytes ready for upload.
        config: Image pack config.

    Returns:
        Summary dict with keys ``type``, ``mode``, ``colours``, ``description``,
        ``content`` (full structured markdown OCR of all visible text).
        Returns an error string if the model is not configured or the response
        cannot be parsed.
    """
    result = call_vision(
        [model_bytes],
        _SUMMARY_PROMPT,
        config,
        model=model,
        effort=effort,
        structured_output="json_object",
    )
    if result.startswith("Error:"):
        return result

    parsed = parse_json_payload(result)
    if parsed is None:
        return "Error: Could not parse vision model response as JSON"
    data: dict[str, object] = dict(parsed)

    # Fill missing required keys with safe defaults
    if "colours" not in data:
        data["colours"] = []
    for key in ("mode", "type", "description", "content"):
        if key not in data:
            data[key] = ""

    # Normalise mode to allowed values
    if data.get("mode") not in ("dark", "light", "unknown"):
        data["mode"] = "unknown"

    return {k: data[k] for k in ("type", "mode", "colours", "description", "content")}
