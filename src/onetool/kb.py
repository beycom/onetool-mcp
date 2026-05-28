"""onetool kb — CLI subcommand group for offline knowledge base operations."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

kb_app = typer.Typer(
    name="kb",
    help="Manage knowledge base databases (index, reindex, stats, info, export).",
    no_args_is_help=True,
)

console = Console(highlight=False)

_DB_ARG = typer.Argument(help="Database / project name (as configured under kb: in onetool.yaml).")


@kb_app.callback()
def kb_callback(
    _ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to onetool.yaml. Auto-detected from CWD if omitted.",
    ),
    secrets: Path | None = typer.Option(
        None,
        "--secrets",
        "-s",
        help="Path to secrets file.",
    ),
) -> None:
    """Knowledge base management — requires onetool.yaml for DB paths and API keys."""
    from loguru import logger

    from ot.config.loader import get_config

    logger.remove()

    if config is None:
        # Auto-detect: look for onetool.yaml in CWD or .onetool/
        for candidate in (Path("onetool.yaml"), Path(".onetool/onetool.yaml")):
            if candidate.exists():
                config = candidate
                break

    if config is not None:
        if secrets is None:
            # Auto-detect secrets.yaml alongside the config file
            candidate_secrets = config.parent / "secrets.yaml"
            if candidate_secrets.exists():
                secrets = candidate_secrets
        get_config(config, secrets_path=secrets)


@kb_app.command("index")
def cmd_index(
    project: Annotated[str, typer.Argument(help="Project name from onetool.yaml kb config.")],
    path: Annotated[str | None, typer.Option("--path", help="Directory to index (overrides project's output_base_dir).")] = None,
    overwrite: Annotated[str, typer.Option("--overwrite", help="'skip' (default) or 'update'.")] = "skip",
) -> None:
    """Index a project's scraped content into the knowledge database."""
    if overwrite not in ("skip", "update"):
        console.print(f"[red]Invalid --overwrite value '{overwrite}'. Must be 'skip' or 'update'.[/red]")
        raise typer.Exit(1)

    from otutil.tools._knowledge.config import _get_config
    from otutil.tools._knowledge.indexer import index_directory

    if path is None:
        cfg = _get_config()
        kb_project = cfg.kb.get(project)
        if kb_project is None:
            available = ", ".join(sorted(cfg.kb.keys())) or "(none configured)"
            console.print(f"[red]Unknown project '{project}'. Available: {available}[/red]")
            raise typer.Exit(1)
        if kb_project.scrape is None:
            console.print(f"[red]Project '{project}' has no scrape config — use --path to specify a directory.[/red]")
            raise typer.Exit(1)
        path = kb_project.scrape.output_base_dir

    db = project

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TextColumn("{task.fields[info]}"),
        console=console,
    ) as progress:
        file_task = progress.add_task("[cyan]Read[/cyan]", total=None, info="")
        embed_task = progress.add_task("[cyan]Embedding[/cyan]", total=None, visible=False, info="")
        link_task = progress.add_task("[cyan]Link graph[/cyan]", total=None, visible=False, info="")

        def on_start(total: int) -> None:
            progress.update(file_task, total=total)

        def on_file(rel: str, _chunks: int) -> None:
            progress.update(file_task, advance=1, info=rel)

        def on_embed_progress(done: int, total: int) -> None:
            progress.update(embed_task, completed=done, total=total, visible=True)

        def on_link_progress(done: int, total: int) -> None:
            progress.update(link_task, completed=done, total=total, visible=True)

        result = index_directory(
            path=path, db_name=db, overwrite=overwrite,
            on_start=on_start, on_file=on_file, on_embed_progress=on_embed_progress,
            on_link_progress=on_link_progress,
        )

    if result.errors:
        console.print(f"[yellow]Errors ({len(result.errors)}):[/yellow]")
        for err in result.errors[:5]:
            console.print(f"  [red]![/red] {err}")

    console.print(
        f"[green]✓[/green] Indexed [bold]{result.indexed}[/bold] chunks, "
        f"skipped {result.skipped}, "
        f"{result.edges_added} link edge(s) added."
    )


@kb_app.command("reindex")
def cmd_reindex(
    db: Annotated[str, _DB_ARG],
) -> None:
    """Backfill missing embeddings for all chunks in the database."""
    from otutil.tools._knowledge.indexing import reindex

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        embed_task = progress.add_task("[cyan]Embedding[/cyan]", total=None)

        def on_progress(done: int, total: int) -> None:
            progress.update(embed_task, completed=done, total=total)

        result = reindex(db=db, on_progress=on_progress)

    console.print(f"[green]✓[/green] {result}")


@kb_app.command("stats")
def cmd_stats(
    db: Annotated[str, _DB_ARG],
) -> None:
    """Print chunk counts, embedding coverage, and file size."""
    from otutil.tools._knowledge.listing import stats

    console.print(stats(db=db))
    console.print(f"[green]✓[/green] Stats for '{db}'.")


@kb_app.command("info")
def cmd_info(
    db: Annotated[str, _DB_ARG],
) -> None:
    """Print database metadata, path, and version info."""
    from otutil.tools._knowledge.listing import info

    console.print(info(db=db))
    console.print(f"[green]✓[/green] Info for '{db}'.")


@kb_app.command("scrape")
def cmd_scrape(
    project: Annotated[str, typer.Argument(help="Project name from onetool.yaml scrape config.")],
    only: Annotated[str | None, typer.Option("--only", help="Comma-separated source names to run.")] = None,
    resume: Annotated[bool, typer.Option("--resume", help="Resume each source from .state.json if present.")] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Write per-page debug artifacts (cleaned.html, raw.html, screenshot.png, meta.json) to ._debug/<slug>/ inside each source output dir.")] = False,
    max_pages: Annotated[int | None, typer.Option("--max-pages", help="Hard limit on pages written per source (overrides per-source and project config).")] = None,
    flat_files: Annotated[bool | None, typer.Option("--flat-files/--no-flat-files", help="Write flat '::'-separated files instead of subdirectories (overrides per-source config).")] = None,
) -> None:
    """Crawl all sources in a scrape project."""
    import time

    # Suppress RequestsDependencyWarning from requests/__init__.py (crawl4ai transitive dep).
    # Must be applied before `import crawl4ai` below, which triggers the warning at import time.
    import warnings
    warnings.filterwarnings("ignore", module="requests")

    # Lazy import crawl4ai — not installed unless [scrape] extra is present
    try:
        import crawl4ai  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as exc:
        console.print(
            "[red]crawl4ai is required. Install with:[/red] pip install 'onetool\\[scrape]'"
        )
        raise typer.Exit(1) from exc

    # Detect missing Playwright browser (crawl4ai uses Playwright internally)
    try:
        from playwright.sync_api import (
            sync_playwright,  # type: ignore[import-not-found]
        )
        with sync_playwright() as pw:
            browser = None
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:
                if "executable doesn't exist" in str(exc) or "not found" in str(exc).lower():
                    console.print(
                        "[red]Playwright browser not found. Run:[/red] playwright install chromium"
                    )
                    raise typer.Exit(1) from exc
                raise
            finally:
                if browser is not None:
                    browser.close()
    except ImportError as exc:
        console.print(
            "[red]Playwright is required. Install with:[/red] pip install 'onetool\\[scrape]'"
        )
        raise typer.Exit(1) from exc

    from otutil.tools._knowledge.config import _get_config, resolve_source
    from otutil.tools._knowledge.scraper import run_scrape, write_run_report

    cfg = _get_config()
    kb_project = cfg.kb.get(project)
    if kb_project is None or kb_project.scrape is None:
        available = ", ".join(sorted(k for k, v in cfg.kb.items() if v.scrape is not None)) or "(none configured)"
        console.print(f"[red]Unknown scrape project '{project}'. Available: {available}[/red]")
        raise typer.Exit(1)
    project_cfg = kb_project.scrape

    sources_to_run = dict(project_cfg.sources)
    if only:
        only_names = {s.strip() for s in only.split(",")}
        unknown = only_names - sources_to_run.keys()
        if unknown:
            available_srcs = ", ".join(sorted(sources_to_run.keys()))
            console.print(
                f"[red]Unknown source(s): {', '.join(sorted(unknown))}. "
                f"Available: {available_srcs}[/red]"
            )
            raise typer.Exit(1)
        sources_to_run = {k: v for k, v in sources_to_run.items() if k in only_names}

    for source_name, source in sources_to_run.items():
        resolved = resolve_source(project_cfg, source_name, source)
        resume_this = resume and (resolved.output_dir / ".state.json").exists()

        # Emit config threshold warnings at run start
        if resolved.crawl_strategy != "seed_urls":
            if resolved.max_pages > 500:
                console.print(f"[yellow]⚠  {source_name}: max_pages={resolved.max_pages} — large crawl[/yellow]")
            if resolved.depth > 4:
                console.print(f"[yellow]⚠  {source_name}: depth={resolved.depth} — deep crawl, may be slow[/yellow]")
        if resolved.url_prefix == "":
            console.print(f"[yellow]⚠  {source_name}: no url_prefix — entire domain will be crawled[/yellow]")
        if resolved.delay_min < 0.5:
            console.print(f"[yellow]⚠  {source_name}: delay_min={resolved.delay_min} — aggressive rate; may trigger blocks[/yellow]")
        if resolved.crawl_strategy in ("bfs", "dfs", "best_first") and resolved.seed_urls:
            console.print(f"[yellow]⚠  {source_name}: seed_urls is set but crawl_strategy={resolved.crawl_strategy!r} — seed_urls will be ignored[/yellow]")

        start = time.monotonic()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            _effective_max_pages = max_pages if max_pages is not None else resolved.max_pages
            _scrape_total = len(resolved.seed_urls) if resolved.crawl_strategy == "seed_urls" else _effective_max_pages
            crawl_task = progress.add_task(
                f"[cyan]Scraping {source_name}[/cyan] — 0 / {_scrape_total} pages",
                total=None,
            )

            def on_page(written: int, current_url: str, _name: str = source_name, _max: int = _scrape_total, _task: object = crawl_task) -> None:
                short_url = current_url[:80] + "…" if len(current_url) > 80 else current_url
                progress.update(
                    _task,
                    description=(
                        f"[cyan]Scraping {_name}[/cyan] — "
                        f"{written} / {_max} pages  [dim]{short_url}[/dim]"
                    ),
                )

            _effective_flat_files = flat_files if flat_files is not None else resolved.flat_files
            result = run_scrape(
                url=resolved.url,
                output_dir=resolved.output_dir,
                source_name=source_name,
                depth=resolved.depth,
                max_pages=_effective_max_pages,
                url_prefix=resolved.url_prefix,
                check_robots_txt=resolved.check_robots_txt,
                delay_min=resolved.delay_min,
                delay_max=resolved.delay_max,
                user_agent=resolved.user_agent,
                wait_for=resolved.wait_for,
                page_timeout=resolved.page_timeout,
                cache=resolved.cache,
                process_iframes=resolved.process_iframes,
                content_filter_threshold=resolved.content_filter_threshold,
                min_word_threshold=resolved.min_word_threshold,
                crawl_strategy=resolved.crawl_strategy,
                seed_urls=resolved.seed_urls,
                score=resolved.score,
                css_selector=resolved.css_selector,
                js_code=resolved.js_code,
                include_images=resolved.include_images,
                resume=resume_this,
                flat_files=_effective_flat_files,
                on_page=on_page,
                category=resolved.category,
                tags=resolved.tags,
                debug=debug,
            )

        # Clean up state file after successful completion
        state_file = resolved.output_dir / ".state.json"
        if state_file.exists():
            state_file.unlink()

        elapsed = time.monotonic() - start
        resumed_tag = " [resumed]" if resume_this else ""
        console.print(
            f"[green]✓[/green] {source_name}{resumed_tag} — "
            f"[bold]{result.written}[/bold] written, "
            f"{result.failed} failed, "
            f"{result.skipped} skipped "
            f"({elapsed:.1f}s)  [dim]{resolved.output_dir}[/dim]"
        )

        report_path = write_run_report(result, resolved.output_dir)
        console.print(f"  Report: {report_path}")


@kb_app.command("export")
def cmd_export(
    db: Annotated[str, _DB_ARG],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output JSON file path.")],
    category: Annotated[str | None, typer.Option("--category", help="Filter by category.")] = None,
    topic: Annotated[str | None, typer.Option("--topic", help="Filter by topic prefix.")] = None,
) -> None:
    """Export all chunks (or a filtered subset) to a JSON file."""
    from otutil.tools._knowledge.listing import export_db

    with console.status(f"[cyan]Exporting '{db}' to {output}…[/cyan]"):
        result = export_db(db=db, path=str(output), category=category, topic=topic)

    console.print(f"[green]✓[/green] {result}")
