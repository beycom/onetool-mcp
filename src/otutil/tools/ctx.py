"""Smart context store for OneTool tool outputs.

Flat-file TTL-expiring storage for large tool outputs.
Replace context-window saturation with targeted retrieval.

Tools:
    write    - Store content, get handle + format info (~1ms, synchronous)
    read     - Paginated raw content, TOC, or metadata
    grep     - Regex line search with context and truncation
    slice    - Extract by section number, heading, or line range
    toc      - Format-aware table of contents (markdown headings / json keys)
    query    - jmespath query on json or yaml handles
    ask      - Multi-question LLM query over stored content (optional)
    append   - Add content and update format/TOC
    list     - All active handles
    inspect  - Detailed metadata for one handle
    stats    - Session storage metrics
    delete   - Remove one handle
    purge    - Delete handles (expired, all, or by filter)
"""
from __future__ import annotations

# Pack for dot notation: ot_context.write() or ctx.write() (short alias)
pack = "ot_context"
pack_aliases = ("ctx",)

# No external dependencies beyond stdlib + jmespath (already a core dep)
__all__ = [
    "append", "ask", "delete", "grep", "inspect", "list", "purge", "query",
    "read", "slice", "stats", "toc", "write",
]


def register_services(registry: object) -> None:
    """Register ctx-owned runtime services."""
    from ot.ctx.result_backend import CtxResultStoreBackend
    from ot.services import OutputPolicy

    registry.register_result_store(CtxResultStoreBackend())  # type: ignore[attr-defined]
    registry.register_output_policy(  # type: ignore[attr-defined]
        lambda tool_name: OutputPolicy(allow_deflect=False)
        if tool_name.startswith(("ctx.", "ot_context."))
        else None
    )

from ot.ctx import (
    ctx_append as append,
)
from ot.ctx import (
    ctx_ask as ask,
)
from ot.ctx import (
    ctx_delete as delete,
)
from ot.ctx import (
    ctx_grep as grep,
)
from ot.ctx import (
    ctx_inspect as inspect,
)
from ot.ctx import (
    ctx_list as list,
)
from ot.ctx import (
    ctx_purge as purge,
)
from ot.ctx import (
    ctx_query as query,
)
from ot.ctx import (
    ctx_read as read,
)
from ot.ctx import (
    ctx_slice as slice,
)
from ot.ctx import (
    ctx_stats as stats,
)
from ot.ctx import (
    ctx_toc as toc,
)
from ot.ctx import (
    ctx_write as write,
)
