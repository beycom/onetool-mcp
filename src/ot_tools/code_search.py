"""Semantic code search using ChunkHound indexes.

Queries existing ChunkHound DuckDB databases for semantic code search.
Requires projects to be indexed externally with `chunkhound index <project>`.
Requires OPENAI_API_KEY in secrets.yaml for embedding generation.

Reference: https://github.com/chunkhound/chunkhound
"""

from __future__ import annotations

# Pack for dot notation: code.search(), code.status()
pack = "code"

__all__ = ["autodoc", "research", "search", "search_batch", "status"]

from typing import TYPE_CHECKING, Any

# Dependency declarations for CLI validation
__ot_requires__ = {
    "lib": [
        ("duckdb", "pip install duckdb"),
        ("openai", "pip install openai"),
    ],
    "secrets": ["OPENAI_API_KEY"],
}

from pydantic import BaseModel, Field

from ot.config import get_tool_config
from ot.config.secrets import get_secret
from ot.logging import LogSpan
from ot.paths import resolve_cwd_path

if TYPE_CHECKING:
    from pathlib import Path

    from openai import OpenAI


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of search results to return",
    )
    base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenAI-compatible API base URL for embeddings",
    )
    model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model (must match ChunkHound index)",
    )
    db_path: str = Field(
        default=".chunkhound/db/chunks.db",
        description="Path to ChunkHound DuckDB database relative to project root",
    )
    provider: str = Field(
        default="openai",
        description="Embedding provider stored in ChunkHound index",
    )
    dimensions: int = Field(
        default=1536,
        description="Embedding dimensions (must match model)",
    )


def _get_config() -> Config:
    """Get code pack configuration."""
    return get_tool_config("code", Config)


def _get_db_path(path: str | None = None) -> tuple[Path, Path]:
    """Get the ChunkHound DuckDB path and project root.

    Uses SDK resolve_cwd_path() for consistent path resolution.

    Path resolution follows project conventions:
        - If path is None: uses project directory (OT_CWD)
        - If path provided: resolves with prefix/tilde expansion
        - Database is always at {project_root}/.chunkhound/db/chunks.db

    Args:
        path: Path to project root (default: OT_CWD)

    Returns:
        Tuple of (db_path, project_root)
    """
    config = _get_config()
    project_root = resolve_cwd_path(".") if path is None else resolve_cwd_path(path)
    db_path = project_root / config.db_path
    return db_path, project_root


def _get_openai_client() -> OpenAI:
    """Get OpenAI client for embedding generation."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "openai is required for code_search. Install with: pip install openai"
        ) from e

    api_key = get_secret("OPENAI_API_KEY") or ""
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not configured in secrets.yaml (required for code search embeddings)"
        )
    config = _get_config()
    return OpenAI(api_key=api_key, base_url=config.base_url or None)


def _import_duckdb():
    """Lazy import duckdb module."""
    try:
        import duckdb
    except ImportError as e:
        raise ImportError(
            "duckdb is required for code_search. Install with: pip install duckdb"
        ) from e
    return duckdb


def _generate_embedding(query: str) -> list[float]:
    """Generate embedding vector for a search query."""
    config = _get_config()
    with LogSpan(span="code.embedding", model=config.model, queryLen=len(query)) as span:
        client = _get_openai_client()
        response = client.embeddings.create(
            model=config.model,
            input=query,
        )
        span.add(dimensions=len(response.data[0].embedding))
        return response.data[0].embedding


def _generate_embeddings_batch(queries: list[str]) -> list[list[float]]:
    """Generate embedding vectors for multiple queries in a single API call."""
    config = _get_config()
    with LogSpan(
        span="code.embedding_batch", model=config.model, queryCount=len(queries)
    ) as span:
        client = _get_openai_client()
        response = client.embeddings.create(
            model=config.model,
            input=queries,
        )
        embeddings = [item.embedding for item in response.data]
        span.add(dimensions=len(embeddings[0]) if embeddings else 0)
        return embeddings


def _format_result(
    result: dict[str, Any],
    project_root: Path | None = None,
    expand: int | None = None,
) -> dict[str, Any]:
    """Format a search result for output.

    Args:
        result: Raw search result from database
        project_root: Project root for file reading (needed for expand)
        expand: Number of context lines to include around match
    """
    content = result.get("content", "")
    start_line = result.get("start_line")
    end_line = result.get("end_line")

    # Expand content if requested and we have valid line numbers
    if expand and project_root and start_line and end_line:
        file_path = project_root / result.get("file_path", "")
        if file_path.exists():
            try:
                lines = file_path.read_text().splitlines()
                # Calculate expanded range (1-indexed to 0-indexed)
                exp_start = max(0, start_line - 1 - expand)
                exp_end = min(len(lines), end_line + expand)
                content = "\n".join(lines[exp_start:exp_end])
                start_line = exp_start + 1
                end_line = exp_end
            except Exception:
                pass  # Fall back to original content

    return {
        "file": result.get("file_path", "unknown"),
        "name": result.get("symbol", ""),
        "type": result.get("chunk_type", ""),
        "language": result.get("language", ""),
        "lines": f"{start_line or '?'}-{end_line or '?'}",
        "score": round(result.get("similarity", 0.0), 4),
        "content": content[:2000] if expand else content[:500],
    }


def search(
    *,
    query: str,
    limit: int | None = None,
    language: str | None = None,
    chunk_type: str | None = None,
    expand: int | None = None,
    exclude: str | None = None,
    path: str | None = None,
) -> str:
    """Search for code semantically in a ChunkHound-indexed project.

    Finds code by meaning rather than exact keyword matches. For example,
    searching for "authentication" can find functions named `verify_jwt_token`.

    Requires the project to be indexed first with:
        chunkhound index /path/to/project

    Args:
        query: Natural language search query (e.g., "error handling", "database connection")
        limit: Maximum number of results to return (defaults to config)
        language: Filter results by language (e.g., "python", "typescript")
        chunk_type: Filter by type (e.g., "function", "class", "method", "comment")
        expand: Number of context lines to include around each match
        exclude: Pipe-separated patterns to exclude (e.g., "test|mock|fixture")
        path: Path to project root (default: cwd)

    Returns:
        Formatted search results with file paths, line numbers, code snippets,
        and relevance scores. Returns error message if project not indexed.

    Example:
        # Search in current directory
        code.search(query="authentication logic")

        # Find Python functions only
        code.search(query="database queries", language="python", chunk_type="function")

        # Get expanded context
        code.search(query="error handling", expand=10)

        # Exclude test files
        code.search(query="validation", exclude="test|mock")
    """
    if limit is None:
        limit = get_tool_config("code", Config).limit
    db_path, project_root = _get_db_path(path)

    with LogSpan(
        span="code.search",
        project=str(project_root),
        query=query,
        limit=limit,
        language=language,
        chunk_type=chunk_type,
        expand=expand,
        exclude=exclude,
    ) as s:
        # Check if project is indexed
        if not db_path.exists():
            msg = (
                f"Project not indexed. Run: chunkhound index {project_root}\n"
                f"Expected database at: {db_path}"
            )
            s.add("error", "not_indexed")
            return f"Error: {msg}"

        try:
            # Connect to DuckDB and load vss extension
            duckdb = _import_duckdb()
            conn = duckdb.connect(str(db_path), read_only=True)
            conn.execute("LOAD vss")

            # Check if required tables exist
            config = _get_config()
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
            embeddings_table = f"embeddings_{config.dimensions}"

            if "chunks" not in tables:
                s.add("error", "no_chunks_table")
                return f"Error: Database missing 'chunks' table. Re-index with: chunkhound index {project_root}"

            if embeddings_table not in tables:
                s.add("error", "no_embeddings_table")
                return f"Error: Database missing '{embeddings_table}' table. Re-index with: chunkhound index {project_root}"

            # Generate query embedding
            embedding = _generate_embedding(query)

            # Build semantic search query using array_cosine_similarity
            sql = f"""
                SELECT
                    c.id as chunk_id,
                    c.symbol,
                    c.code as content,
                    c.chunk_type,
                    c.start_line,
                    c.end_line,
                    f.path as file_path,
                    f.language,
                    array_cosine_similarity(e.embedding, ?::FLOAT[{config.dimensions}]) as similarity
                FROM {embeddings_table} e
                JOIN chunks c ON e.chunk_id = c.id
                JOIN files f ON c.file_id = f.id
                WHERE e.provider = ? AND e.model = ?
            """

            params: list[Any] = [embedding, config.provider, config.model]

            # Apply language filter if specified
            if language:
                sql += " AND LOWER(f.language) = LOWER(?)"
                params.append(language)

            # Apply chunk_type filter if specified
            if chunk_type:
                sql += " AND LOWER(c.chunk_type) = LOWER(?)"
                params.append(chunk_type)

            # Apply exclude filter if specified (pipe-separated patterns)
            if exclude:
                patterns = [p.strip() for p in exclude.split("|") if p.strip()]
                for pattern in patterns:
                    sql += " AND f.path NOT LIKE ?"
                    params.append(f"%{pattern}%")

            sql += " ORDER BY similarity DESC LIMIT ?"
            params.append(limit)

            # Execute search
            results = conn.execute(sql, params).fetchall()

            if not results:
                s.add("resultCount", 0)
                return f"No results found for: {query}"

            # Format results
            formatted = []
            for row in results:
                result = {
                    "chunk_id": row[0],
                    "symbol": row[1],
                    "content": row[2],
                    "chunk_type": row[3],
                    "start_line": row[4],
                    "end_line": row[5],
                    "file_path": row[6],
                    "language": row[7],
                    "similarity": row[8],
                }
                formatted.append(_format_result(result, project_root, expand))

            # Build output
            output_lines = [f"Found {len(formatted)} results for: {query}\n"]
            for i, r in enumerate(formatted, 1):
                output_lines.append(
                    f"{i}. [{r['type']}] {r['name']} ({r['language']})\n"
                    f"   File: {r['file']}:{r['lines']}\n"
                    f"   Score: {r['score']}\n"
                    f"   ```\n{r['content']}\n   ```\n"
                )

            output = "\n".join(output_lines)
            s.add("resultCount", len(formatted))
            s.add("outputLen", len(output))
            return output

        except Exception as e:
            s.add("error", str(e))
            return f"Error searching code: {e}"


def search_batch(
    *,
    queries: str,
    limit: int | None = None,
    language: str | None = None,
    chunk_type: str | None = None,
    expand: int | None = None,
    exclude: str | None = None,
    path: str | None = None,
) -> str:
    """Run multiple semantic searches and return merged, deduplicated results.

    Uses batch embedding API (single call) for efficiency. Results are
    deduplicated by file+lines, keeping the highest score.

    Args:
        queries: Pipe-separated search queries (e.g., "auth logic|token validation|session")
        limit: Maximum results per query (defaults to config)
        language: Filter by language (e.g., "python")
        chunk_type: Filter by type (e.g., "function", "class")
        expand: Number of context lines to include around each match
        exclude: Pipe-separated patterns to exclude (e.g., "test|mock")
        path: Path to project root (default: cwd)

    Returns:
        Merged results sorted by score, with duplicates removed.

    Example:
        # Multiple related queries
        code.search_batch(queries="authentication|login|session handling")

        # Exclude test files
        code.search_batch(queries="error handling|validation", exclude="test|mock")
    """
    if limit is None:
        limit = get_tool_config("code", Config).limit
    db_path, project_root = _get_db_path(path)

    # Parse pipe-separated queries
    query_list = [q.strip() for q in queries.split("|") if q.strip()]
    if not query_list:
        return "Error: No valid queries provided"

    with LogSpan(
        span="code.search_batch",
        project=str(project_root),
        queryCount=len(query_list),
        limit=limit,
        exclude=exclude,
    ) as s:
        if not db_path.exists():
            msg = f"Project not indexed. Run: chunkhound index {project_root}"
            s.add("error", "not_indexed")
            return f"Error: {msg}"

        try:
            duckdb = _import_duckdb()
            conn = duckdb.connect(str(db_path), read_only=True)
            conn.execute("LOAD vss")

            config = _get_config()
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
            embeddings_table = f"embeddings_{config.dimensions}"

            if "chunks" not in tables:
                s.add("error", "no_chunks_table")
                return f"Error: Database missing 'chunks' table. Re-index with: chunkhound index {project_root}"

            if embeddings_table not in tables:
                s.add("error", "no_embeddings_table")
                return f"Error: Database missing '{embeddings_table}' table. Re-index with: chunkhound index {project_root}"

            # Generate all embeddings in a single API call
            embeddings = _generate_embeddings_batch(query_list)

            # Collect all results
            all_results: dict[str, dict[str, Any]] = {}  # key: file:lines

            for query, embedding in zip(query_list, embeddings, strict=True):
                sql = f"""
                    SELECT
                        c.id as chunk_id,
                        c.symbol,
                        c.code as content,
                        c.chunk_type,
                        c.start_line,
                        c.end_line,
                        f.path as file_path,
                        f.language,
                        array_cosine_similarity(e.embedding, ?::FLOAT[{config.dimensions}]) as similarity
                    FROM {embeddings_table} e
                    JOIN chunks c ON e.chunk_id = c.id
                    JOIN files f ON c.file_id = f.id
                    WHERE e.provider = ? AND e.model = ?
                """

                params: list[Any] = [embedding, config.provider, config.model]

                if language:
                    sql += " AND LOWER(f.language) = LOWER(?)"
                    params.append(language)

                if chunk_type:
                    sql += " AND LOWER(c.chunk_type) = LOWER(?)"
                    params.append(chunk_type)

                if exclude:
                    patterns = [p.strip() for p in exclude.split("|") if p.strip()]
                    for pattern in patterns:
                        sql += " AND f.path NOT LIKE ?"
                        params.append(f"%{pattern}%")

                sql += " ORDER BY similarity DESC LIMIT ?"
                params.append(limit)

                results = conn.execute(sql, params).fetchall()

                for row in results:
                    result = {
                        "chunk_id": row[0],
                        "symbol": row[1],
                        "content": row[2],
                        "chunk_type": row[3],
                        "start_line": row[4],
                        "end_line": row[5],
                        "file_path": row[6],
                        "language": row[7],
                        "similarity": row[8],
                        "matched_query": query,
                    }
                    # Dedupe key: file path + line range
                    key = f"{row[6]}:{row[4]}-{row[5]}"
                    if key not in all_results or row[8] > all_results[key]["similarity"]:
                        all_results[key] = result

            if not all_results:
                s.add("resultCount", 0)
                return f"No results found for queries: {', '.join(query_list)}"

            # Sort by similarity and format
            sorted_results = sorted(
                all_results.values(), key=lambda x: x["similarity"], reverse=True
            )
            formatted = [
                _format_result(r, project_root, expand) for r in sorted_results
            ]

            # Build output
            output_lines = [
                f"Found {len(formatted)} results for {len(query_list)} queries\n"
            ]
            for i, r in enumerate(formatted, 1):
                output_lines.append(
                    f"{i}. [{r['type']}] {r['name']} ({r['language']})\n"
                    f"   File: {r['file']}:{r['lines']}\n"
                    f"   Score: {r['score']}\n"
                    f"   ```\n{r['content']}\n   ```\n"
                )

            output = "\n".join(output_lines)
            s.add("resultCount", len(formatted))
            s.add("outputLen", len(output))
            return output

        except Exception as e:
            s.add("error", str(e))
            return f"Error in batch search: {e}"


def research(
    *,
    query: str,
    path: str | None = None,
) -> str:
    """Deep code research with LLM synthesis using ChunkHound.

    Performs multi-hop semantic search and synthesizes findings using an LLM.
    More expensive than search() but provides comprehensive analysis.

    Args:
        query: Architectural or conceptual question (e.g., "how does auth flow work")
        path: Scope to a specific path within the project

    Returns:
        LLM-synthesized analysis of the codebase based on the query.

    Example:
        code.research(query="how does authentication flow work across services")
        code.research(query="error handling patterns", path="src/api/")
    """
    db_path, project_root = _get_db_path(path)

    with LogSpan(span="code.research", project=str(project_root), query=query) as s:
        if not db_path.exists():
            s.add("error", "not_indexed")
            return f"Error: Project not indexed. Run: chunkhound index {project_root}"

        try:
            from chunkhound.tools import code_research
        except ImportError:
            s.add("error", "chunkhound_not_installed")
            return (
                "Error: chunkhound package required for research.\n"
                "Install with: pip install chunkhound"
            )

        try:
            result = code_research(
                query=query,
                project_path=str(project_root),
                scope_path=path,
            )
            s.add("success", True)
            return result
        except Exception as e:
            s.add("error", str(e))
            return f"Error in code research: {e}"


def autodoc(
    *,
    scope: str = ".",
    out: str | None = None,
    comprehensiveness: str = "standard",
    path: str | None = None,
) -> str:
    """Generate architecture documentation using ChunkHound's Code Mapper.

    Creates flowing documentation with code citations. Expensive operation
    using multiple LLM calls.

    Args:
        scope: Directory scope for documentation (default: entire project)
        out: Output file path for generated documentation
        comprehensiveness: Level of detail - "quick", "standard", or "thorough"
        path: Path to project root (default: cwd)

    Returns:
        Generated architecture documentation or path to output file.

    Example:
        code.autodoc(scope="src/auth/", out="docs/auth-architecture.md")
        code.autodoc(scope=".", comprehensiveness="thorough")
    """
    db_path, project_root = _get_db_path(path)

    with LogSpan(
        span="code.autodoc",
        project=str(project_root),
        scope=scope,
        comprehensiveness=comprehensiveness,
    ) as s:
        if not db_path.exists():
            s.add("error", "not_indexed")
            return f"Error: Project not indexed. Run: chunkhound index {project_root}"

        try:
            from chunkhound.tools import code_mapper
        except ImportError:
            s.add("error", "chunkhound_not_installed")
            return (
                "Error: chunkhound package required for autodoc.\n"
                "Install with: pip install chunkhound"
            )

        try:
            result = code_mapper(
                project_path=str(project_root),
                scope_path=scope,
                comprehensiveness=comprehensiveness,
            )

            # Write to file if output path specified
            if out:
                out_path = project_root / out
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(result)
                s.add("output_file", str(out_path))
                return f"Documentation written to: {out_path}"

            s.add("success", True)
            return result
        except Exception as e:
            s.add("error", str(e))
            return f"Error generating documentation: {e}"


def status(*, path: str | None = None) -> str:
    """Check if a project has a ChunkHound index and show statistics.

    Args:
        path: Path to project root (default: cwd)

    Returns:
        Index statistics (file count, chunk count, languages) or
        instructions for indexing if not indexed.

    Example:
        # Current directory
        code.status()

        # Explicit path
        code.status(path="/path/to/project")
    """
    db_path, project_root = _get_db_path(path)

    with LogSpan(span="code.status", project=str(project_root)) as s:
        if not db_path.exists():
            s.add("indexed", False)
            return (
                f"Project not indexed.\n\n"
                f"To enable semantic code search, run:\n"
                f"  chunkhound index {project_root}\n\n"
                f"This creates a searchable index at:\n"
                f"  {db_path}"
            )

        try:
            duckdb = _import_duckdb()
            conn = duckdb.connect(str(db_path), read_only=True)
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]

            stats: dict[str, object] = {"tables": tables, "indexed": True}

            # Get chunk statistics
            if "chunks" in tables:
                chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                stats["chunk_count"] = chunk_count

                # Get language distribution
                try:
                    lang_results = conn.execute("""
                        SELECT f.language, COUNT(*) as cnt
                        FROM chunks c
                        JOIN files f ON c.file_id = f.id
                        GROUP BY f.language
                        ORDER BY cnt DESC
                    """).fetchall()
                    stats["languages"] = {row[0]: row[1] for row in lang_results}
                except Exception:
                    pass  # Language stats are optional

            # Get file statistics
            if "files" in tables:
                file_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
                stats["file_count"] = file_count

            # Get embedding statistics
            config = _get_config()
            embeddings_table = f"embeddings_{config.dimensions}"
            if embeddings_table in tables:
                emb_count = conn.execute(
                    f"SELECT COUNT(*) FROM {embeddings_table}"
                ).fetchone()[0]
                stats["embedding_count"] = emb_count

            # Format output
            output_lines = [
                f"Project indexed: {project_root}\n",
                f"Database: {db_path}\n",
            ]

            if "file_count" in stats:
                output_lines.append(f"Files: {stats['file_count']}")
            if "chunk_count" in stats:
                output_lines.append(f"Chunks: {stats['chunk_count']}")
            if "embedding_count" in stats:
                output_lines.append(f"Embeddings: {stats['embedding_count']}")
            if "languages" in stats:
                langs = ", ".join(f"{k}: {v}" for k, v in stats["languages"].items())
                output_lines.append(f"Languages: {langs}")

            output_lines.append(f"\nTables: {', '.join(tables)}")

            for key, value in stats.items():
                s.add(key, value)
            return "\n".join(output_lines)

        except Exception as e:
            s.add("error", str(e))
            return f"Error reading index: {e}"
