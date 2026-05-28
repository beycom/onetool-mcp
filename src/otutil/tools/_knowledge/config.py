"""Configuration for the knowledge pack."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from otpack import get_tool_config
from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_CATEGORIES = {"reference", "rule", "note", "mistake"}


class ScrapeSourceConfig(BaseModel):
    """Configuration for a single named scrape source within a project."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(description="Entry-point URL to crawl")
    url_prefix: str = Field(default="", description="Restrict crawl to URLs with this path prefix")
    depth: int | None = Field(default=None, description="BFS crawl depth (None = inherit from project)")
    max_pages: int | None = Field(default=None, description="Max pages to crawl (None = inherit from project)")
    check_robots_txt: bool | None = Field(default=None, description="Respect robots.txt (None = inherit from project)")
    delay_min: float | None = Field(default=None, description="Min delay seconds (None = inherit from project)")
    delay_max: float | None = Field(default=None, description="Max delay seconds (None = inherit from project)")
    user_agent: str | None = Field(default=None, description="User-Agent string (None = inherit from project)")
    wait_for: str | None = Field(default=None, description="CSS/JS selector to wait for before extracting (None = inherit from project)")
    page_timeout: int | None = Field(default=None, description="Page load timeout in ms (None = inherit from project)")
    process_iframes: bool | None = Field(default=None, description="Extract text from embedded iframes (None = inherit from project)")
    content_filter_threshold: float | None = Field(default=None, description="PruningContentFilter threshold 0-1 (None = inherit from project)")
    min_word_threshold: int | None = Field(default=None, description="Minimum words per block for PruningContentFilter (None = inherit from project)")
    crawl_strategy: Literal["bfs", "dfs", "best_first", "seed_urls"] | None = Field(default=None, description="Crawl strategy override (None = inherit from project)")
    seed_urls: list[str] = Field(default_factory=list, description="Explicit URL list — only used when crawl_strategy=seed_urls")
    score: dict = Field(default_factory=dict, description="Scorer config for best_first strategy (e.g. {keyword_relevance: ['term:1.0']})")
    css_selector: str = Field(default="", description="CSS selector to restrict content extraction to a specific element (e.g. '#mc-main-content')")
    js_code: str = Field(default="", description="JavaScript to run on each page before extraction (crawl4ai js_code)")
    include_images: bool | None = Field(default=None, description="Append image URLs to page content (None = inherit from project)")
    flat_files: bool | None = Field(default=None, description="Write files with '::' separator instead of subdirectories (None = inherit from project)")
    category: str | None = Field(default=None, description="Default chunk category for this source (None = inherit from project). Must be one of: reference, rule, note, mistake")
    tags: list[str] | None = Field(default=None, description="Default tags to attach to all chunks from this source (None = inherit from project)")


class ScrapeProjectConfig(BaseModel):
    """Configuration for a named scrape project (collection of sources)."""

    model_config = ConfigDict(extra="forbid")

    output_base_dir: str = Field(description="Absolute base path; source output dirs are derived as output_base_dir/source_name")
    user_agent: str = Field(default="", description="Custom User-Agent string (empty = crawl4ai default)")
    delay_min: float = Field(default=0.5, description="Minimum delay between requests (seconds)")
    delay_max: float = Field(default=2.0, description="Maximum delay between requests (seconds)")
    check_robots_txt: bool = Field(default=True, description="Respect robots.txt")
    depth: int = Field(default=3, description="BFS crawl depth")
    max_pages: int = Field(default=100, description="Maximum pages to crawl")
    wait_for: str = Field(default="", description="CSS/JS selector to wait for before extracting (empty = no wait)")
    page_timeout: int = Field(default=30000, description="Page load timeout in ms")
    crawl_strategy: Literal["bfs", "dfs", "best_first", "seed_urls"] = Field(default="bfs", description="Default crawl strategy for all sources in this project")
    score: dict = Field(default_factory=dict, description="Default scorer config for best_first strategy")
    cache: bool = Field(default=False, description="Enable crawl4ai disk cache")
    process_iframes: bool = Field(default=False, description="Extract text from embedded iframes")
    content_filter_threshold: float = Field(default=0.48, description="PruningContentFilter threshold 0-1")
    min_word_threshold: int = Field(default=50, description="Minimum words per block for PruningContentFilter")
    include_images: bool = Field(default=False, description="Append image URLs to page content")
    flat_files: bool = Field(default=False, description="Write files with '::' separator instead of subdirectories")
    category: str | None = Field(default=None, description="Default chunk category for all sources in this project. Must be one of: reference, rule, note, mistake")
    tags: list[str] = Field(default_factory=list, description="Default tags to attach to all chunks in this project")
    sources: dict[str, ScrapeSourceConfig] = Field(description="Named sources in this project")

    @field_validator("output_base_dir")
    @classmethod
    def must_be_absolute(cls, v: str) -> str:
        if not Path(v).is_absolute():
            raise ValueError(f"output_base_dir must be an absolute path, got: {v!r}")
        return v


class ResolvedSourceConfig(BaseModel):
    """Fully resolved source config — no Optional fields."""

    url: str
    output_dir: Path
    url_prefix: str
    depth: int
    max_pages: int
    check_robots_txt: bool
    delay_min: float
    delay_max: float
    user_agent: str
    wait_for: str
    page_timeout: int
    cache: bool
    process_iframes: bool
    content_filter_threshold: float
    min_word_threshold: int
    crawl_strategy: str
    seed_urls: list[str]
    score: dict
    css_selector: str
    js_code: str
    include_images: bool
    flat_files: bool
    category: str | None
    tags: list[str]


def _resolve_category(source_cat: str | None, project_cat: str | None, source_name: str) -> str | None:
    cat = source_cat if source_cat is not None else project_cat
    if cat is not None and cat not in VALID_CATEGORIES:
        raise ValueError(
            f"Source {source_name!r}: invalid category {cat!r}. Must be one of: {sorted(VALID_CATEGORIES)}"
        )
    return cat


def resolve_source(
    project: ScrapeProjectConfig,
    source_name: str,
    source: ScrapeSourceConfig,
) -> ResolvedSourceConfig:
    """Merge source-level overrides with project-level defaults."""
    crawl_strategy = source.crawl_strategy if source.crawl_strategy is not None else project.crawl_strategy
    seed_urls = source.seed_urls
    if crawl_strategy == "seed_urls" and not seed_urls:
        raise ValueError(
            f"Source {source_name!r}: crawl_strategy='seed_urls' requires at least one entry in seed_urls"
        )
    return ResolvedSourceConfig(
        url=source.url,
        output_dir=Path(project.output_base_dir) / source_name,
        url_prefix=source.url_prefix,
        depth=source.depth if source.depth is not None else project.depth,
        max_pages=source.max_pages if source.max_pages is not None else project.max_pages,
        check_robots_txt=source.check_robots_txt if source.check_robots_txt is not None else project.check_robots_txt,
        delay_min=source.delay_min if source.delay_min is not None else project.delay_min,
        delay_max=source.delay_max if source.delay_max is not None else project.delay_max,
        user_agent=source.user_agent if source.user_agent is not None else project.user_agent,
        wait_for=source.wait_for if source.wait_for is not None else project.wait_for,
        page_timeout=source.page_timeout if source.page_timeout is not None else project.page_timeout,
        cache=project.cache,
        process_iframes=source.process_iframes if source.process_iframes is not None else project.process_iframes,
        content_filter_threshold=source.content_filter_threshold if source.content_filter_threshold is not None else project.content_filter_threshold,
        min_word_threshold=source.min_word_threshold if source.min_word_threshold is not None else project.min_word_threshold,
        crawl_strategy=crawl_strategy,
        seed_urls=seed_urls,
        score=source.score if source.score else project.score,
        css_selector=source.css_selector,
        js_code=source.js_code,
        include_images=source.include_images if source.include_images is not None else project.include_images,
        flat_files=source.flat_files if source.flat_files is not None else project.flat_files,
        category=_resolve_category(source.category, project.category, source_name),
        tags=list(dict.fromkeys((project.tags or []) + (source.tags or []))),
    )


class DBConfig(BaseModel):
    """Configuration for a single named database."""

    path: str = Field(description="Path relative to .onetool/ (e.g. 'mem/docs.db')")
    description: str = Field(default="", description="Human-readable description")
    embeddings_enabled: bool = Field(default=True, description="Enable vector embeddings for this DB")


class IndexProjectConfig(BaseModel):
    """Indexing configuration for a KB project."""

    model_config = ConfigDict(extra="forbid")

    ignore_patterns: list[str] = Field(
        default_factory=list,
        description="Gitignore-style patterns to exclude from kb.index()",
    )
    topic_roots: list[str] = Field(
        default_factory=list,
        description=(
            "URL or path prefixes to strip from canonical topics during indexing. "
            "First matching root wins. Accepts full URLs or bare path prefixes."
        ),
    )


class KBProjectConfig(BaseModel):
    """Configuration for a single named KB project (db + optional scrape + index)."""

    model_config = ConfigDict(extra="forbid")

    db: DBConfig = Field(description="Database configuration")
    scrape: ScrapeProjectConfig | None = Field(default=None, description="Scrape project configuration (optional)")
    index: IndexProjectConfig = Field(default_factory=IndexProjectConfig, description="Index configuration")


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    model_config = ConfigDict(extra="forbid")

    kb: dict[str, KBProjectConfig] = Field(
        default_factory=dict,
        description="Named KB projects. Each key is a project name; each value bundles db:, scrape:, and index: config.",
    )
    model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model",
    )
    base_url: str = Field(
        default="",
        description="OpenAI-compatible API base URL for embeddings (empty = inherit from ot_llm config)",
    )
    dimensions: int = Field(
        default=1536,
        description="Embedding dimensions (must match model)",
    )
    max_embedding_tokens: int = Field(
        default=8191,
        ge=1,
        description="Max tokens for embedding input",
    )
    embedding_batch_size: int = Field(
        default=200,
        ge=1,
        le=2048,
        description="Number of texts per embeddings API call",
    )
    search_limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Default maximum search results",
    )
    search_extract: int = Field(
        default=300,
        ge=0,
        description="Character limit for content extract in search results (0 = full)",
    )
    enrich_model: str = Field(
        default="",
        description="LLM model for enrichment (falls back to ot_llm default if empty)",
    )
    min_chunk_chars: int = Field(
        default=200,
        ge=0,
        description=(
            "Minimum non-heading body characters for a chunk to be stored. "
            "Chunks below this threshold are merged into their predecessor (or skipped if no predecessor). "
            "Set to 0 to disable merging."
        ),
    )


def _get_config() -> Config:
    """Get knowledge pack configuration."""
    return get_tool_config("knowledge", Config)


def _get_kb_project(name: str) -> KBProjectConfig | None:
    """Get config for a specific named KB project, or None if not configured."""
    config = _get_config()
    return config.kb.get(name)


__all__ = [
    "VALID_CATEGORIES",
    "Config",
    "DBConfig",
    "IndexProjectConfig",
    "KBProjectConfig",
    "ResolvedSourceConfig",
    "ScrapeProjectConfig",
    "ScrapeSourceConfig",
    "_get_config",
    "_get_kb_project",
    "_resolve_category",
    "resolve_source",
]
