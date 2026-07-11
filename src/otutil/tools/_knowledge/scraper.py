"""Crawl4AI-backed BFS scraping pipeline for `kb scrape`."""
from __future__ import annotations

import asyncio
import base64
import contextlib
import dataclasses
import json
import logging
import os
import random
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from ot.utils.async_bridge import run_coro_sync

# Binary file extensions to exclude from crawling
_BINARY_EXTENSIONS = re.compile(
    r"\.(pdf|zip|gz|tar|tgz|rar|7z|exe|dmg|pkg|deb|rpm"
    r"|png|jpg|jpeg|gif|bmp|svg|ico|webp|avif|heic|heif"
    r"|mp4|mp3|wav|ogg|webm|avi|mov|mkv|flv"
    r"|woff|woff2|ttf|eot|otf"
    r"|doc|docx|xls|xlsx|ppt|pptx"
    r"|bin|so|dylib|dll|class|jar|war)(?=[?#]|$)",
    re.IGNORECASE,
)


@dataclass
class PageRecord:
    """Per-page record written to the run report."""

    url: str
    slug: str
    status: str  # "ok", "empty", or "failed"
    content_len: int
    elapsed_s: float
    error: str


@dataclass
class ScrapeResult:
    """Summary counts from a completed scrape run."""

    written: int = 0
    failed: int = 0
    skipped: int = 0
    source_name: str = ""
    pages: list[PageRecord] = field(default_factory=list)
    elapsed_s: float = 0.0
    start_time: str = ""
    end_time: str = ""
    resumed: bool = False
    warnings: list[str] = field(default_factory=list)
    config_snapshot: dict = field(default_factory=dict)  # type: ignore[type-arg]


def url_to_slug(url: str, base_path: str = "") -> str:
    """Convert a URL to a filesystem-safe hierarchical slug.

    Strips .html/.htm extensions and falls back to 'index' for root paths.
    Always produces segment/segment output.

    When `base_path` is provided, that prefix is stripped from the URL path.
    `base_path` may be a full URL or a bare path prefix:
      base_path='https://docs.example.com/guide', URL '.../guide/api/ref.html' → 'api/ref'
      base_path='/guide',                          URL '.../guide/api/ref.html' → 'api/ref'
    """
    url_path = urlparse(url).path.rstrip("/")
    if not url_path:
        return "index"
    url_path = re.sub(r"\.(html?|htm)$", "", url_path, flags=re.IGNORECASE)
    if base_path:
        base_path_only = urlparse(base_path).path if "://" in base_path else base_path
        norm_base = base_path_only.rstrip("/")
        if url_path.startswith(norm_base):
            url_path = url_path[len(norm_base):]
    url_path = url_path.lstrip("/")
    segments = [re.sub(r"[^\w.\-]", "_", s) for s in url_path.split("/") if s]
    return "/".join(segments) or "index"


def _write_atomic(dest: Path, content: str) -> None:
    """Write content to dest atomically via a temp file in the same dir."""
    dir_ = dest.parent
    fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        Path(tmp).replace(dest)
    except Exception:
        with contextlib.suppress(OSError):
            Path(tmp).unlink()
        raise


def _write_atomic_bytes(dest: Path, data: bytes) -> None:
    """Write bytes to dest atomically via a temp file in the same dir."""
    dir_ = dest.parent
    fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".tmp_")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        Path(tmp).replace(dest)
    except Exception:
        with contextlib.suppress(OSError):
            Path(tmp).unlink()
        raise


def _write_page(
    output_dir: Path,
    page_url: str,
    content: str,
    source_name: str,
    page_metadata: dict[str, Any] | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    flat_files: bool = False,
) -> None:
    """Write .md and .meta.yaml for a single crawled page."""
    slug = url_to_slug(page_url)
    if flat_files:
        slug = slug.replace("/", "::")
        md_path = output_dir / f"{slug}.md"
        meta_path = output_dir / f"{slug}.meta.yaml"
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        md_path = output_dir / f"{slug}.md"
        meta_path = output_dir / f"{slug}.meta.yaml"
        md_path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(md_path, content)
    meta: dict[str, Any] = {
        "url": page_url,
        "source": source_name,
        "crawled_at": datetime.now(UTC).isoformat(),
    }
    if page_metadata:
        for key in ("title", "description", "keywords"):
            val = page_metadata.get(key)
            if val:
                meta[key] = val
    if category is not None:
        meta["category"] = category
    if tags:
        meta["tags"] = tags
    _write_atomic(meta_path, yaml.dump(meta, default_flow_style=False))


def write_run_report(result: ScrapeResult, output_dir: Path) -> Path:
    """Write ._run_report.json to output_dir atomically. Returns the path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "._run_report.json"
    data = dataclasses.asdict(result)
    _write_atomic_bytes(dest, json.dumps(data, default=str, indent=2).encode())
    return dest


def _write_debug_artifacts(page: object, slug: str, output_dir: Path) -> None:
    """Write per-page debug artifacts to ._debug/<slug>/ inside output_dir."""
    debug_dir = output_dir / "._debug" / slug.replace("/", os.sep)
    debug_dir.mkdir(parents=True, exist_ok=True)

    cleaned_html = getattr(page, "cleaned_html", None) or ""
    _write_atomic(debug_dir / "cleaned.html", cleaned_html)

    raw_html = getattr(page, "html", None) or ""
    _write_atomic(debug_dir / "raw.html", raw_html)

    screenshot = getattr(page, "screenshot", None)
    if screenshot:
        if isinstance(screenshot, str):
            try:
                screenshot_bytes = base64.b64decode(screenshot)
            except Exception:
                screenshot_bytes = b""
        else:
            screenshot_bytes = screenshot if isinstance(screenshot, bytes) else b""
        if screenshot_bytes:
            _write_atomic_bytes(debug_dir / "screenshot.png", screenshot_bytes)

    links = getattr(page, "links", {}) or {}
    meta = {
        "url": getattr(page, "url", ""),
        "status_code": getattr(page, "status_code", None),
        "redirected_url": getattr(page, "redirected_url", None),
        "links": {
            "internal": [lnk.get("href", "") for lnk in (links.get("internal") or [])],
            "external": [lnk.get("href", "") for lnk in (links.get("external") or [])],
        },
        "console_messages": getattr(page, "console_messages", None),
        "js_execution_result": getattr(page, "js_execution_result", None),
        "error_message": str(getattr(page, "error_message", "") or ""),
    }
    _write_atomic_bytes(debug_dir / "meta.json", json.dumps(meta, default=str, indent=2).encode())


def _resolve_image_urls(markdown: str, base_url: str) -> str:
    """Resolve relative image URLs in markdown to absolute URLs."""
    from urllib.parse import urljoin

    def _resolve(m: re.Match) -> str:  # type: ignore[type-arg]
        alt = m.group(1)
        src = m.group(2)
        if src and not src.startswith(("http://", "https://", "data:", "//")):
            src = urljoin(base_url, src)
        return f"![{alt}]({src})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]*)\)", _resolve, markdown)


def _extract_markdown(page: object, include_images: bool) -> str:
    """Extract fit or raw markdown from a crawl4ai page result."""
    md = getattr(page, "markdown", None)
    fit = getattr(md, "fit_markdown", None) if md else None
    raw = getattr(md, "raw_markdown", None) if md else None
    out = fit or ""
    if (not out or len(out) < 10) and raw:
        out = raw
    if include_images:
        page_url = getattr(page, "url", "") or ""
        if page_url:
            out = _resolve_image_urls(out, page_url)
    return out


def _process_page(
    page: Any,
    page_url: str,
    slug: str,
    elapsed_s: float,
    result: ScrapeResult,
    output_dir: Path,
    source_name: str,
    *,
    include_images: bool,
    category: str | None,
    tags: list[str],
    flat_files: bool,
    debug: bool,
    on_page: Callable[[int, str], None] | None,
) -> str:
    """Classify one crawled page (failed/empty/ok), write output, and record it.

    Shared by the seed-URL and deep-crawl loops. Returns the page status.
    """
    if not page.success:
        result.failed += 1
        status, content = "failed", ""
        error = str(getattr(page, "error_message", "") or "")
    else:
        content = _extract_markdown(page, include_images)
        if not content:
            result.skipped += 1
            status, error = "empty", ""
        else:
            _write_page(output_dir, page_url, content, source_name,
                        page_metadata=dict(getattr(page, "metadata", None) or {}),
                        category=category, tags=tags, flat_files=flat_files)
            result.written += 1
            status, error = "ok", ""
    result.pages.append(PageRecord(
        url=page_url, slug=slug, status=status,
        content_len=len(content) if status == "ok" else 0,
        elapsed_s=round(elapsed_s, 3), error=error,
    ))
    if debug:
        _write_debug_artifacts(page, slug, output_dir)
    if on_page:
        on_page(result.written, page_url)
    return status


def _build_deep_filter_chain(url: str, url_prefix: str) -> object:
    """Build domain + URL-prefix + binary-exclusion filter chain for deep crawl strategies."""
    from crawl4ai.deep_crawling.filters import (  # type: ignore[import-untyped]
        DomainFilter,
        FilterChain,
        URLPatternFilter,
    )
    parsed = urlparse(url)
    domain = parsed.netloc
    filters: list[object] = [DomainFilter(allowed_domains=[domain])]
    if url_prefix:
        filters.append(URLPatternFilter(patterns=[f"*{url_prefix}*"]))
    filters.append(URLPatternFilter(patterns=[_BINARY_EXTENSIONS], reverse=True))
    return FilterChain(filters)


def run_scrape(
    *,
    url: str,
    output_dir: Path,
    source_name: str,
    depth: int = 3,
    max_pages: int = 100,
    url_prefix: str = "",
    check_robots_txt: bool = True,
    delay_min: float = 0.5,
    delay_max: float = 2.0,
    user_agent: str = "",
    wait_for: str = "",
    page_timeout: int = 30000,
    cache: bool = False,
    process_iframes: bool = False,
    content_filter_threshold: float = 0.48,
    min_word_threshold: int = 50,
    crawl_strategy: str = "bfs",
    seed_urls: list[str] | None = None,
    score: dict[str, Any] | None = None,
    css_selector: str = "",
    js_code: str = "",
    include_images: bool = False,
    resume: bool = False,
    flat_files: bool = False,
    on_page: Callable[[int, str], None] | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    debug: bool = False,
) -> ScrapeResult:
    """Run a crawl from `url` and write .md + .meta.yaml pairs to `output_dir`.

    Args:
        url: Entry-point URL to crawl.
        output_dir: Directory to write output files.
        source_name: Value written to the `source` field in .meta.yaml.
        depth: Crawl depth (for bfs/dfs/best_first strategies).
        max_pages: Maximum pages to crawl.
        url_prefix: Restrict crawl to URLs with this path prefix (empty = no restriction).
        check_robots_txt: Whether to respect robots.txt.
        delay_min: Minimum delay between requests in seconds.
        delay_max: Maximum delay between requests in seconds.
        user_agent: Custom User-Agent string (empty = crawl4ai default).
        wait_for: CSS/JS selector to wait for before extracting (empty = no wait).
        page_timeout: Page load timeout in ms.
        cache: Enable crawl4ai disk cache.
        process_iframes: Extract text from embedded iframes.
        content_filter_threshold: PruningContentFilter threshold 0-1.
        min_word_threshold: Minimum words per block for PruningContentFilter.
        crawl_strategy: One of "bfs", "dfs", "best_first", "seed_urls".
        seed_urls: Explicit URL list — only used when crawl_strategy="seed_urls".
        score: Scorer config for best_first (e.g. {"keyword_relevance": ["term:1.0"]}).
        css_selector: CSS selector to restrict content extraction (e.g. "#mc-main-content").
        js_code: JavaScript to run on each page before extraction.
        resume: Resume from .state.json in output_dir. The state file is created
            when absent so a later resume can continue; applies to deep-crawl
            and seed_urls strategies alike.
        on_page: Callback(pages_written_so_far, current_url) called after each page attempt.

    Returns:
        ScrapeResult with written/failed/skipped counts and per-page records.
    """
    return run_coro_sync(_run_scrape_async(
        url=url,
        output_dir=output_dir,
        source_name=source_name,
        depth=depth,
        max_pages=max_pages,
        url_prefix=url_prefix,
        check_robots_txt=check_robots_txt,
        delay_min=delay_min,
        delay_max=delay_max,
        user_agent=user_agent,
        wait_for=wait_for,
        page_timeout=page_timeout,
        cache=cache,
        process_iframes=process_iframes,
        content_filter_threshold=content_filter_threshold,
        min_word_threshold=min_word_threshold,
        crawl_strategy=crawl_strategy,
        seed_urls=seed_urls or [],
        score=score or {},
        css_selector=css_selector,
        js_code=js_code,
        include_images=include_images,
        resume=resume,
        flat_files=flat_files,
        on_page=on_page,
        category=category,
        tags=tags or [],
        debug=debug,
    ))


async def _run_scrape_async(
    *,
    url: str,
    output_dir: Path,
    source_name: str,
    depth: int,
    max_pages: int,
    url_prefix: str,
    check_robots_txt: bool,
    delay_min: float,
    delay_max: float,
    user_agent: str,
    wait_for: str,
    page_timeout: int,
    cache: bool,
    process_iframes: bool,
    content_filter_threshold: float,
    min_word_threshold: int,
    crawl_strategy: str,
    seed_urls: list[str],
    score: dict[str, Any],
    css_selector: str,
    js_code: str,
    include_images: bool,
    resume: bool,
    flat_files: bool,
    on_page: Callable[[int, str], None] | None,
    category: str | None,
    tags: list[str],
    debug: bool,
) -> ScrapeResult:
    from crawl4ai import (  # type: ignore[import-untyped]
        AsyncWebCrawler,
        BrowserConfig,
        CacheMode,
        CrawlerRunConfig,
    )
    from crawl4ai.content_filter_strategy import (  # type: ignore[import-untyped]
        PruningContentFilter,
    )
    from crawl4ai.markdown_generation_strategy import (  # type: ignore[import-untyped]
        DefaultMarkdownGenerator,
    )
    logging.getLogger("crawl4ai").setLevel(logging.WARNING)

    output_dir.mkdir(parents=True, exist_ok=True)
    state_file = output_dir / ".state.json"

    browser_cfg = BrowserConfig(headless=True, verbose=False)
    if user_agent:
        browser_cfg = BrowserConfig(headless=True, verbose=False, user_agent=user_agent)

    content_filter = PruningContentFilter(
        threshold=content_filter_threshold,
        min_word_threshold=min_word_threshold,
    )
    md_generator = DefaultMarkdownGenerator(
        content_filter=content_filter,
        options={"ignore_images": not include_images, "body_width": 0},
    )

    cache_mode = CacheMode.ENABLED if cache else CacheMode.DISABLED

    config_snapshot = {
        "url": url,
        "url_prefix": url_prefix,
        "depth": depth,
        "max_pages": max_pages,
        "check_robots_txt": check_robots_txt,
        "delay_min": delay_min,
        "delay_max": delay_max,
        "user_agent": user_agent,
        "wait_for": wait_for,
        "page_timeout": page_timeout,
        "cache": cache,
        "process_iframes": process_iframes,
        "crawl_strategy": crawl_strategy,
    }

    result = ScrapeResult(
        source_name=source_name,
        start_time=datetime.now(UTC).isoformat(),
        resumed=resume and state_file.exists(),
        config_snapshot=config_snapshot,
    )

    t_start = asyncio.get_running_loop().time()

    if crawl_strategy == "seed_urls":
        seed_run_cfg_kwargs: dict[str, object] = {
            "verbose": False,
            "check_robots_txt": check_robots_txt,
            "wait_for": wait_for or None,
            "page_timeout": page_timeout,
            "cache_mode": cache_mode,
            "process_iframes": process_iframes,
            "css_selector": css_selector or None,
            "markdown_generator": md_generator,
            "js_code": js_code or None,
        }
        if debug:
            seed_run_cfg_kwargs["screenshot"] = True
        seed_run_cfg = CrawlerRunConfig(**seed_run_cfg_kwargs)

        # Seed-URL resume: track completed seeds in .state.json ourselves
        # (the deep-crawl strategies persist state via crawl4ai instead).
        seed_done: set[str] = set()
        if resume and state_file.exists():
            try:
                seed_done = set(json.loads(state_file.read_text(encoding="utf-8")).get("done_urls", []))
            except Exception:
                seed_done = set()

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            first_url = True
            for seed_url in seed_urls:
                if seed_url in seed_done:
                    continue
                if not first_url:
                    await asyncio.sleep(random.uniform(delay_min, delay_max))
                first_url = False
                t_page_start = asyncio.get_running_loop().time()
                page_url = seed_url
                slug = url_to_slug(page_url)
                try:
                    container = await crawler.arun(seed_url, config=seed_run_cfg)
                    page = container[0]
                    page_url = page.url
                    slug = url_to_slug(page_url)
                except Exception as exc:
                    result.failed += 1
                    result.pages.append(PageRecord(
                        url=page_url, slug=slug, status="failed",
                        content_len=0, elapsed_s=round(asyncio.get_running_loop().time() - t_page_start, 3),
                        error=str(exc),
                    ))
                    if on_page:
                        on_page(result.written, page_url)
                    continue
                status = _process_page(
                    page, page_url, slug,
                    asyncio.get_running_loop().time() - t_page_start,
                    result, output_dir, source_name,
                    include_images=include_images, category=category, tags=tags,
                    flat_files=flat_files, debug=debug, on_page=on_page,
                )
                if status != "failed":
                    seed_done.add(seed_url)
                    if resume:
                        _write_atomic(state_file, json.dumps({"done_urls": sorted(seed_done)}))
    else:
        from crawl4ai.deep_crawling import (  # type: ignore[import-untyped]
            BFSDeepCrawlStrategy,
            DFSDeepCrawlStrategy,
        )

        filter_chain = _build_deep_filter_chain(url, url_prefix)

        if crawl_strategy == "dfs":
            strategy: object = DFSDeepCrawlStrategy(
                max_depth=depth,
                max_pages=max_pages,
                filter_chain=filter_chain,
            )
        elif crawl_strategy == "best_first":
            from crawl4ai.deep_crawling import (
                BestFirstCrawlingStrategy,
            )
            from crawl4ai.deep_crawling.scorers import (  # type: ignore[import-untyped]
                KeywordRelevanceScorer,
            )
            kw_entries = score.get("keyword_relevance", [])
            scorer = KeywordRelevanceScorer(keywords=[e.split(":")[0] for e in kw_entries]) if kw_entries else None
            strategy = BestFirstCrawlingStrategy(
                max_depth=depth,
                max_pages=max_pages,
                filter_chain=filter_chain,
                url_scorer=scorer,
            )
        else:
            strategy = BFSDeepCrawlStrategy(
                max_depth=depth,
                max_pages=max_pages,
                filter_chain=filter_chain,
            )

        run_cfg_kwargs: dict[str, object] = {
            "deep_crawl_strategy": strategy,
            "verbose": False,
            "check_robots_txt": check_robots_txt,
            "wait_for": wait_for or None,
            "page_timeout": page_timeout,
            "cache_mode": cache_mode,
            "process_iframes": process_iframes,
            "css_selector": css_selector or None,
            "markdown_generator": md_generator,
            "js_code": js_code or None,
            "mean_delay": (delay_min + delay_max) / 2,
            "max_range": (delay_max - delay_min) / 2,
            "stream": True,
        }
        if debug:
            run_cfg_kwargs["screenshot"] = True
        if resume:
            # Pass the state file even when it doesn't exist yet so crawl4ai
            # creates it on the first run and consumes it on later resumes.
            run_cfg_kwargs["state_file"] = str(state_file)

        run_cfg = CrawlerRunConfig(**run_cfg_kwargs)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            t_page_start = asyncio.get_running_loop().time()
            async for page in (await crawler.arun(url, config=run_cfg)):
                page_url = page.url
                slug = url_to_slug(page_url)
                _process_page(
                    page, page_url, slug,
                    asyncio.get_running_loop().time() - t_page_start,
                    result, output_dir, source_name,
                    include_images=include_images, category=category, tags=tags,
                    flat_files=flat_files, debug=debug, on_page=on_page,
                )
                if result.written >= max_pages:
                    break
                t_page_start = asyncio.get_running_loop().time()

    result.elapsed_s = round(asyncio.get_running_loop().time() - t_start, 3)
    result.end_time = datetime.now(UTC).isoformat()

    return result


__all__ = [
    "PageRecord",
    "ScrapeResult",
    "run_scrape",
    "url_to_slug",
    "write_run_report",
]
