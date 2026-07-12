"""Vision model calls for the image pack.

Uses the OpenAI-compatible messages API with base64 image content blocks.
Supports single questions, JSON-contract batched questions (with per-question
fallback), multi-image calls, and structured summary extraction.
"""

from __future__ import annotations

import base64
import json
import re
from typing import TYPE_CHECKING, Any, cast

from openai import OpenAI

from otpack import LogSpan

from .config import get_image_api_key

if TYPE_CHECKING:
    from .config import Config

# Cached client — recreated only when api_key or base_url changes
_client: OpenAI | None = None
_client_key: tuple[str, str] = ("", "")


def _get_client(config: Config) -> OpenAI:
    global _client, _client_key
    api_key = get_image_api_key() or ""
    key = (api_key, config.base_url)
    if _client is None or _client_key != key:
        _client = OpenAI(api_key=api_key, base_url=config.base_url or None)
        _client_key = key
    return _client


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


def _image_block(model_bytes: bytes) -> dict[str, Any]:
    b64 = base64.b64encode(model_bytes).decode()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{b64}"},
    }


def call_vision(images: list[bytes], prompt: str, config: Config) -> str:
    """Send one or more images and a text prompt to the configured vision model.

    Multi-image calls interleave a text label before each image block
    (``"Image 1:"``, image, ``"Image 2:"``, image, …, prompt) so questions can
    reference "image 1" / "image 2" unambiguously.

    Args:
        images: PNG byte payloads ready for upload (already resized).
        prompt: Text prompt to accompany the image(s).
        config: Image pack config (must have ``model``).

    Returns:
        Model response text, or an error string starting with ``"Error:"`` if
        the model is not configured or the API call fails.
    """
    if not config.model:
        return (
            "Error: ot_image.model not configured — "
            "set tools.ot_image.model in onetool.yaml"
        )
    if not get_image_api_key():
        return (
            "Error: image API key not configured — "
            "set OPENAI_API_KEY in secrets.yaml"
        )

    content: list[dict[str, Any]] = []
    if len(images) > 1:
        for i, model_bytes in enumerate(images, start=1):
            content.append({"type": "text", "text": f"Image {i}:"})
            content.append(_image_block(model_bytes))
    else:
        content.append(_image_block(images[0]))
    content.append({"type": "text", "text": prompt})

    try:
        client = _get_client(config)
        response = client.chat.completions.create(
            model=config.model,
            messages=cast("Any", [{"role": "user", "content": content}]),
            temperature=0.1,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "sk-" in error_msg:
            error_msg = "Authentication error — check OPENAI_API_KEY in secrets.yaml"
        return f"Error: {error_msg}"


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


def ask_questions(images: list[bytes], questions: list[str], config: Config) -> list[str]:
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
        result = call_vision(images, questions[0], config)
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
        result = call_vision(images, prompt, config)
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
            call_vision(images, question, config).strip() for question in questions
        ]


def extract_summary(model_bytes: bytes, config: Config) -> dict[str, object] | str:
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
    result = call_vision([model_bytes], _SUMMARY_PROMPT, config)
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
