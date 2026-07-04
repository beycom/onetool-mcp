"""Shared metadata for generated tool documentation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PackDocs:
    """Documentation metadata for a OneTool pack."""

    pack: str
    display_name: str
    extra: str
    doc_path: str | None = None


PACK_DOCS: tuple[PackDocs, ...] = (
    PackDocs("ot", "OT Core", "core", "ot_core.md"),
    PackDocs("arch", "Arch", "[dev]", "arch.md"),
    PackDocs("ot_context", "OT Context", "core", "ot_context.md"),
    PackDocs("ot_forge", "OT Forge", "core", "ot_forge.md"),
    PackDocs("ot_image", "OT Image", "core", "ot_image.md"),
    PackDocs("ot_llm", "OT LLM", "core", "ot_llm.md"),
    PackDocs("ot_secrets", "OT Secrets", "core", "ot_secrets.md"),
    PackDocs("ot_servers", "OT Servers", "core", "ot_servers.md"),
    PackDocs("ot_timer", "OT Timer", "core", "ot_timer.md"),
    PackDocs("brave", "Brave", "[util]", "brave.md"),
    PackDocs("convert", "Convert", "[util]", "convert.md"),
    PackDocs("excel", "Excel", "[util]", "excel.md"),
    PackDocs("file", "File", "[util]", "file.md"),
    PackDocs("ground", "Ground", "[util]", "ground.md"),
    PackDocs("knowledge", "Knowledge", "[util]", "knowledge.md"),
    PackDocs("mem", "Mem", "[util]", "mem.md"),
    PackDocs("tavily", "Tavily", "[util]", "tavily.md"),
    PackDocs("chrome_util", "Chrome DevTools Util", "[dev]", "chrome-util.md"),
    PackDocs("console", "Console", "core", "console.md"),
    PackDocs("context7", "Context7", "[dev]", "context7.md"),
    PackDocs("db", "DB", "[dev]", "db.md"),
    PackDocs("diagram", "Diagram", "[dev]", "diagram.md"),
    PackDocs("localhist", "Localhist", "[dev]", "localhist.md"),
    PackDocs("package", "Package", "[dev]", "package.md"),
    PackDocs("play_util", "Playwright Util", "[dev]", "play-util.md"),
    PackDocs("ripgrep", "Ripgrep", "[dev]", "ripgrep.md"),
    PackDocs("whiteboard", "WB (Whiteboard)", "[util]", "whiteboard.md"),
    PackDocs("webfetch", "Webfetch", "[dev]", "webfetch.md"),
)

DOC_PATH_BY_PACK = {item.pack: item.doc_path for item in PACK_DOCS if item.doc_path}
EXTRA_BY_PACK = {item.pack: item.extra for item in PACK_DOCS}
PACK_BY_DISPLAY_NAME = {item.display_name: item.pack for item in PACK_DOCS}
