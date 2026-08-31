"""Generate self-contained architecture reports from the prebuilt bundle."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .api import _load_document
from .payload import build_payload

PAYLOAD_TOKEN = "__ARCH_PAYLOAD_JSON__"
TEMPLATE_PATH = Path(__file__).parent / "_bundle" / "report-template.html"


class ReportError(ValueError):
    """Raised when an architecture report cannot be generated."""


def payload_file(yaml_path: Path) -> dict[str, Any]:
    """Load, validate, and compile one architecture payload."""
    architecture, sequences, findings = _load_document(yaml_path)
    errors = [item for item in findings if item.severity == "error"]
    if errors:
        codes = ", ".join(dict.fromkeys(item.code for item in errors))
        raise ReportError(f"architecture has validation errors: {codes}")
    return build_payload(architecture, yaml_path.name, sequences=sequences)


def generate_report(yaml_path: Path, html_path: Path) -> dict[str, Any]:
    """Build and atomically write a self-contained HTML report."""
    payload = payload_file(yaml_path)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if template.count(PAYLOAD_TOKEN) != 1:
        raise ReportError("report template must contain exactly one payload token")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    content = template.replace(PAYLOAD_TOKEN, encoded.replace("</", "<\\/"))
    html_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=html_path.parent,
        delete=False,
        prefix=f".{html_path.name}.",
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        temporary.replace(html_path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"ok": True, "input_path": str(yaml_path), "path": str(html_path)}
