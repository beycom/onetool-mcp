"""Semantic code search using ChunkHound indexes.

Queries existing ChunkHound DuckDB databases for semantic code search.
Requires projects to be indexed externally with `chunkhound index <project>`.
Requires OPENAI_API_KEY in secrets.yaml for embedding generation.

Reference: https://github.com/chunkhound/chunkhound
"""

from __future__ import annotations

# Pack for dot notation: code.search(), code.status()
pack = "code"

__all__ = ["search", "status"]

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ot.config import get_tool_config
from ot.config.secrets import get_secret
from ot.paths import get_effective_cwd
from ot_sdk import log


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of search results to return",
    )

try:
    import duckdb
except ImportError as e:
    raise ImportError(
        "duckdb is required for code_search. Install with: pip install duckdb"
    ) from e

try:
    from openai import OpenAI
except ImportError as e:
    raise ImportError(
        "openai is required for code_search. Install with: pip install openai"
    ) from e

# ChunkHound database paths (DuckDB default)
CHUNKHOUND_DB_PATH = ".chunkhound/db/chunks.db"

# Embedding configuration (must match ChunkHound's configuration)
EMBEDDING_PROVIDER = "openai"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def _get_db_path(path: str | None = None) -> tuple[Path, Path]:
    """Get the ChunkHound DuckDB path and project root.

    Path resolution follows project conventions:
        - If path is None: uses project directory (OT_CWD)
        - If path provided: resolves as absolute or ~ path
        - Database is always at {project_root}/.chunkhound/db/chunks.db

    Note: ${VAR} patterns are NOT expanded. Use ~/path instead of ${HOME}/path.

    Args:
        path: Path to project root (default: OT_CWD)

    Returns:
        Tuple of (db_path, project_root)
    """
    if path is None:
        project_root = get_effective_cwd()
    else:
        project_root = Path(path).expanduser().resolve()
    db_path = project_root / CHUNKHOUND_DB_PATH
    return db_path, project_root


def _get_openai_client() -> OpenAI:
    """Get OpenAI client for embedding generation."""
    api_key = get_secret("OPENAI_API_KEY") or ""
    base_url = get_secret("OPENAI_BASE_URL") or ""
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not configured in secrets.yaml (required for code search embeddings)"
        )
    return OpenAI(api_key=api_key, base_url=base_url or None)


def _generate_embedding(query: str) -> list[float]:
    """Generate embedding vector for a search query."""
    with log("code.embedding", model=EMBEDDING_MODEL, queryLen=len(query)) as span:
        client = _get_openai_client()
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=query,
        )
        span.add(dimensions=len(response.data[0].embedding))
        return response.data[0].embedding


def _format_result(result: dict[str, Any]) -> dict[str, Any]:
    """Format a search result for output."""
    return {
        "file": result.get("file_path", "unknown"),
        "name": result.get("symbol", ""),
        "type": result.get("chunk_type", ""),
        "language": result.get("language", ""),
        "lines": f"{result.get('start_line', '?')}-{result.get('end_line', '?')}",
        "score": round(result.get("similarity", 0.0), 4),
        "content": result.get("content", "")[:500],  # Truncate long content
    }


def search(
    *,
    query: str,
    limit: int | None = None,
    language: str | None = None,
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
        path: Path to project root (default: cwd)

    Returns:
        Formatted search results with file paths, line numbers, code snippets,
        and relevance scores. Returns error message if project not indexed.

    Example:
        # Search in current directory
        code.search("authentication logic")

        # Find Python-only results
        code.search("database queries", language="python")

        # Explicit path
        code.search("error handling", path="/path/to/other-project")
    """
    if limit is None:
        limit = get_tool_config("code", Config).limit
    db_path, project_root = _get_db_path(path)

    with log(
        "code.search",
        project=str(project_root),
        query=query,
        limit=limit,
        language=language,
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
            conn = duckdb.connect(str(db_path), read_only=True)
            conn.execute("LOAD vss")

            # Check if required tables exist
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
            embeddings_table = f"embeddings_{EMBEDDING_DIMENSIONS}"

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
                    array_cosine_similarity(e.embedding, ?::FLOAT[{EMBEDDING_DIMENSIONS}]) as similarity
                FROM {embeddings_table} e
                JOIN chunks c ON e.chunk_id = c.id
                JOIN files f ON c.file_id = f.id
                WHERE e.provider = ? AND e.model = ?
            """

            params: list[Any] = [embedding, EMBEDDING_PROVIDER, EMBEDDING_MODEL]

            # Apply language filter if specified
            if language:
                sql += " AND LOWER(f.language) = LOWER(?)"
                params.append(language)

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
                formatted.append(_format_result(result))

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

    with log("code.status", project=str(project_root)) as s:
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
            embeddings_table = f"embeddings_{EMBEDDING_DIMENSIONS}"
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
