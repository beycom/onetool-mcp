"""Documentation projections derived from the runtime-safe guidance catalog."""

from __future__ import annotations

from ot.catalog import PACK_CATALOG

DOC_PATH_BY_PACK = {entry.pack: f"{entry.doc_slug}.md" for entry in PACK_CATALOG}
EXTRA_BY_PACK = {entry.pack: entry.extra.value for entry in PACK_CATALOG}
PACK_BY_DISPLAY_NAME = {entry.display_name: entry.pack for entry in PACK_CATALOG}
