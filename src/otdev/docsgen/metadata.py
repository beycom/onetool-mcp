"""Shared metadata for generated tool documentation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PackDocs:
    """Documentation metadata for a OneTool pack."""

    pack: str
    display_name: str
    extra: str
    skill_owner: str
    doc_path: str | None = None


PACK_DOCS: tuple[PackDocs, ...] = (
    PackDocs("ot", "OT Core", "core", "ot-ref", "ot_core.md"),
    PackDocs("arch", "Arch", "[dev]", "ot-arch", "arch.md"),
    PackDocs("ot_context", "OT Context", "core", "ot-context", "ot_context.md"),
    PackDocs("ot_forge", "OT Forge", "core", "ot-forge", "ot_forge.md"),
    PackDocs("ot_image", "OT Image", "core", "ot-image", "ot_image.md"),
    PackDocs("ot_llm", "OT LLM", "core", "ot-llm", "ot_llm.md"),
    PackDocs("ot_secrets", "OT Secrets", "core", "ot-secrets", "ot_secrets.md"),
    PackDocs("ot_servers", "OT Servers", "core", "ot-servers", "ot_servers.md"),
    PackDocs("ot_timer", "OT Timer", "core", "ot-ref", "ot_timer.md"),
    PackDocs("brave", "Brave", "[util]", "ot-research", "brave.md"),
    PackDocs("convert", "Convert", "[util]", "ot-convert", "convert.md"),
    PackDocs("excel", "Excel", "[util]", "ot-excel", "excel.md"),
    PackDocs("file", "File", "[util]", "ot-file", "file.md"),
    PackDocs("ground", "Ground", "[util]", "ot-research", "ground.md"),
    PackDocs("knowledge", "Knowledge", "[util]", "ot-knowledge", "knowledge.md"),
    PackDocs("mem", "Mem", "[util]", "ot-mem", "mem.md"),
    PackDocs("tavily", "Tavily", "[util]", "ot-research", "tavily.md"),
    PackDocs(
        "chrome_util",
        "Chrome DevTools Util",
        "[dev]",
        "ot-browser-guidance",
        "chrome-util.md",
    ),
    PackDocs("console", "Console", "core", "ot-ref", "console.md"),
    PackDocs("context7", "Context7", "[dev]", "ot-research", "context7.md"),
    PackDocs("db", "DB", "[dev]", "ot-db", "db.md"),
    PackDocs("diagram", "Diagram", "[dev]", "ot-diagram", "diagram.md"),
    PackDocs("localhist", "Localhist", "[dev]", "ot-localhist", "localhist.md"),
    PackDocs("package", "Package", "[dev]", "ot-research", "package.md"),
    PackDocs(
        "play_util",
        "Playwright Util",
        "[dev]",
        "ot-browser-guidance",
        "play-util.md",
    ),
    PackDocs("ripgrep", "Ripgrep", "[dev]", "ot-ref", "ripgrep.md"),
    PackDocs(
        "whiteboard", "WB (Whiteboard)", "[util]", "ot-whiteboard", "whiteboard.md"
    ),
    PackDocs("webfetch", "Webfetch", "[dev]", "ot-research", "webfetch.md"),
)

CURATED_SKILLS: tuple[str, ...] = (
    "ot-ref",
    "ot-ask",
    "ot-context",
    "ot-forge",
    "ot-image",
    "ot-llm",
    "ot-secrets",
    "ot-servers",
    "ot-convert",
    "ot-excel",
    "ot-file",
    "ot-knowledge",
    "ot-mem",
    "ot-whiteboard",
    "ot-arch",
    "ot-db",
    "ot-diagram",
    "ot-localhist",
    "ot-research",
    "ot-browser-guidance",
)

PROFILE_SKILLS: dict[str, frozenset[str]] = {
    "Foundation": frozenset({"ot-ref", "ot-ask"}),
    "Core": frozenset(
        {
            "ot-ref",
            "ot-ask",
            "ot-context",
            "ot-forge",
            "ot-image",
            "ot-llm",
            "ot-secrets",
            "ot-servers",
        }
    ),
    "Core + [util]": frozenset(
        {
            "ot-ref",
            "ot-ask",
            "ot-context",
            "ot-forge",
            "ot-image",
            "ot-llm",
            "ot-secrets",
            "ot-servers",
            "ot-convert",
            "ot-excel",
            "ot-file",
            "ot-knowledge",
            "ot-mem",
            "ot-whiteboard",
            "ot-research",
        }
    ),
    "Core + [dev]": frozenset(
        {
            "ot-ref",
            "ot-ask",
            "ot-context",
            "ot-forge",
            "ot-image",
            "ot-llm",
            "ot-secrets",
            "ot-servers",
            "ot-arch",
            "ot-db",
            "ot-diagram",
            "ot-localhist",
            "ot-research",
            "ot-browser-guidance",
        }
    ),
    "[all]": frozenset(CURATED_SKILLS),
}

DOC_PATH_BY_PACK = {item.pack: item.doc_path for item in PACK_DOCS if item.doc_path}
EXTRA_BY_PACK = {item.pack: item.extra for item in PACK_DOCS}
PACK_BY_DISPLAY_NAME = {item.display_name: item.pack for item in PACK_DOCS}
