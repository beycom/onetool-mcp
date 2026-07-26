"""Image — session-scoped image loading, vision querying, and summary extraction.

Load images from files, URLs, or the clipboard once; reference them by handle
for follow-up questions. A vision model answers questions and extracts
structured summaries cached in meta.json.

**Configuration (onetool.yaml):**

    tools:
      ot_image:
        model: openai/gpt-4o-mini   # overrides llm.model for vision calls
        max_edge: 1568              # default resize limit
        session_cache_size: 10     # default LRU cap

API key, base URL, and model are inherited from the top-level ``llm:`` config if not set.
"""

from __future__ import annotations

# Pack name for dot notation: ot_image.load(), ot_image.ask(), etc.
# Must appear before other imports.
pack = "ot_image"
pack_aliases = ("img",)

__ot_requires__ = [
    {
        "kind": "lib",
        "name": "Pillow",
        "import_name": "PIL",
        "install_extra": "core",
        "purpose": "Load, inspect, resize, and encode images",
    },
    {
        "kind": "secret",
        "name": "OPENAI_API_KEY",
        "purpose": "Authenticate optional vision-model operations",
        "optional": True,
    },
]

config_model = "Config"

__all__ = ["ask", "clip_ask", "clip_view", "delete", "list", "load", "load_batch", "purge", "summary"]

from ottools._image.config import Config as _Config
from ottools._image.lifecycle import delete_image as delete
from ottools._image.lifecycle import list_images as list
from ottools._image.lifecycle import purge_images as purge
from ottools._image.tools import ask, clip_ask, clip_view, load, load_batch, summary

Config = _Config
