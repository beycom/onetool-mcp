"""Pure signature/description compaction helpers.

Core-visible (no `otdev` dependency) so both `ot.meta` (for the
``ot.tools(info='signatures')`` level) and `otdev.docsgen` (for the generated
tool index) render tool signatures identically.
"""

from __future__ import annotations

import re
from typing import Any


def signature_args(signature: str) -> str:
    """Return compact argument text from a Python function signature string."""
    start = signature.find("(")
    end = signature.rfind(")")
    if start == -1 or end == -1 or end < start:
        return ""

    args = signature[start + 1 : end]
    args = args.replace("*, ", "").replace("*", "")
    args = re.sub(r"\s+", " ", args)
    args = re.sub(r": '([^']+)'", r": \1", args)
    args = re.sub(r': "([^"]+)"', r": \1", args)
    args = re.sub(r"\s*=\s*", "=", args)
    args = re.sub(r"\s*,\s*", ", ", args)
    return args.strip()


def short_description(description: Any) -> str:
    """Return the first non-empty line of a description."""
    for raw in str(description or "").splitlines():
        line = raw.strip()
        if line:
            return line
    return ""
