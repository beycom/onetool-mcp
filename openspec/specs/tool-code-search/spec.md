# tool-code-search Specification

## Purpose

Provides semantic code search using ChunkHound indexes. Queries existing DuckDB databases for semantic code search. Requires `OPENAI_API_KEY` in secrets.yaml and projects to be indexed externally with `chunkhound index <project>`.
## Requirements
### Requirement: Semantic Code Search

The `code.search()` function SHALL search for code semantically in a ChunkHound-indexed project.

#### Scenario: Basic search
- **GIVEN** an indexed project
- **WHEN** `code.search(query="authentication logic")` is called
- **THEN** it SHALL return code matches ranked by semantic similarity
- **AND** results SHALL include file paths, line numbers, and code snippets

#### Scenario: Search with explicit path
- **GIVEN** an explicit project path
- **WHEN** `code.search(query="error handling", path="/path/to/project")` is called
- **THEN** it SHALL use the path directly
- **AND** it SHALL search within that project

#### Scenario: Default path
- **GIVEN** no path specified
- **WHEN** `code.search(query="query")` is called
- **THEN** it SHALL use the current working directory

#### Scenario: Custom database path
- **GIVEN** a custom database location
- **WHEN** `code.search(query="query", db="custom/path/chunks.db")` is called
- **THEN** it SHALL use the specified database path relative to project root

#### Scenario: Result limit
- **GIVEN** a limit parameter
- **WHEN** `code.search(query="query", limit=5)` is called
- **THEN** it SHALL return at most 5 results
- **AND** default limit is 10

#### Scenario: Language filter
- **GIVEN** a language parameter
- **WHEN** `code.search(query="query", language="python")` is called
- **THEN** it SHALL filter results to Python files only

#### Scenario: Chunk type filter
- **GIVEN** a chunk_type parameter
- **WHEN** `code.search(query="validation", chunk_type="function")` is called
- **THEN** it SHALL filter results to functions only
- **AND** valid chunk types are: function, class, method, comment

#### Scenario: Path exclusion
- **GIVEN** an exclude parameter with pipe-separated patterns
- **WHEN** `code.search(query="error handling", exclude="test|mock|fixture")` is called
- **THEN** it SHALL exclude results where file path contains any pattern
- **AND** pattern matching SHALL be case-insensitive

#### Scenario: Context expansion
- **GIVEN** an expand parameter
- **WHEN** `code.search(query="validation", expand=20)` is called
- **THEN** it SHALL include up to 20 lines before and after each match
- **AND** expanded content SHALL be read from the source file

### Requirement: Result Format

The `code.search()` function SHALL format results for readability.

#### Scenario: Result structure
- **GIVEN** search results found
- **WHEN** results are returned
- **THEN** each result SHALL include:
  - Chunk type (function, class, etc.)
  - Name
  - Language
  - File path with line range
  - Similarity score
  - Code content (truncated to 500 chars)

#### Scenario: No results
- **GIVEN** no matching code found
- **WHEN** search completes
- **THEN** it SHALL return "No results found for: {query}"

### Requirement: Project Not Indexed

The `code.search()` function SHALL handle unindexed projects.

#### Scenario: Missing index
- **GIVEN** a project without ChunkHound index
- **WHEN** `code.search(query="query", path="/path/to/unindexed")` is called
- **THEN** it SHALL return error with indexing instructions
- **AND** error SHALL include: "Run: chunkhound index {project_root}"
- **AND** error SHALL include: "Expected database at: {db_path}"

### Requirement: Index Status

The `code.status()` function SHALL report index statistics.

#### Scenario: Indexed project
- **GIVEN** a project with ChunkHound index
- **WHEN** `code.status(path="/path/to/project")` is called
- **THEN** it SHALL return:
  - Database path
  - File count
  - Chunk count
  - Language distribution

#### Scenario: Unindexed project
- **GIVEN** a project without ChunkHound index
- **WHEN** `code.status(path="/path/to/unindexed")` is called
- **THEN** it SHALL return indexing instructions

#### Scenario: Custom database path for status
- **GIVEN** a custom database location
- **WHEN** `code.status(path="/path/to/project", db="custom/chunks.db")` is called
- **THEN** it SHALL check status at the specified database path

### Requirement: Embedding Generation

The `code.search()` function SHALL generate embeddings for queries.

#### Scenario: OpenAI embedding
- **GIVEN** `OPENAI_API_KEY` is configured in secrets.yaml
- **WHEN** a search query is executed
- **THEN** it SHALL use text-embedding-3-small model
- **AND** embedding dimensions SHALL be 1536

#### Scenario: Missing API key
- **GIVEN** `OPENAI_API_KEY` is not configured in secrets.yaml
- **WHEN** `code.search()` is called
- **THEN** it SHALL return "OPENAI_API_KEY not configured in secrets.yaml (required for code search embeddings)"

### Requirement: ChunkHound Schema Compatibility

The `code.search()` function SHALL be compatible with ChunkHound's DuckDB schema.

#### Scenario: Provider/model filtering
- **GIVEN** ChunkHound stores embeddings in `embeddings_{dims}` tables with provider and model columns
- **WHEN** search is executed
- **THEN** it SHALL filter by provider='openai' AND model='text-embedding-3-small'
- **AND** it SHALL use `embeddings_1536` table for text-embedding-3-small

#### Scenario: File path resolution
- **GIVEN** ChunkHound stores file_id in chunks table (not file_path)
- **WHEN** results are formatted
- **THEN** it SHALL join with files table to resolve file paths

#### Scenario: Vector search
- **GIVEN** DuckDB vss extension is available
- **WHEN** semantic search is performed
- **THEN** it SHALL use `array_cosine_similarity()` for vector similarity

### Requirement: Path Resolution

The `code.search()` and `code.status()` functions SHALL resolve path references.

#### Scenario: Explicit path
- **GIVEN** path="/path/to/project"
- **WHEN** function is called
- **THEN** it SHALL use the path directly

#### Scenario: Tilde expansion
- **GIVEN** path="~/projects/myproject"
- **WHEN** function is called
- **THEN** it SHALL expand ~ to the home directory

#### Scenario: Default path
- **GIVEN** no path specified
- **WHEN** function is called
- **THEN** it SHALL use the current working directory (OT_CWD)

### Requirement: Code Search Logging

The tool SHALL log search and index operations using LogSpan.

#### Scenario: Code search logging
- **GIVEN** a code search is requested
- **WHEN** the search completes
- **THEN** it SHALL log:
  - `span: "code.search"`
  - `query`: Search query
  - `project`: Project root path
  - `resultCount`: Matches found

#### Scenario: Index build logging
- **GIVEN** a code index is built
- **WHEN** indexing completes
- **THEN** it SHALL log:
  - `span: "code.index.build"`
  - `path`: Indexed path
  - `fileCount`: Files indexed

### Requirement: Batch Semantic Search

The `code.search_batch()` function SHALL run multiple semantic queries efficiently.

#### Scenario: Multiple queries
- **GIVEN** pipe-separated queries
- **WHEN** `code.search_batch(queries="auth logic|token validation|session handling")` is called
- **THEN** it SHALL execute all queries
- **AND** it SHALL merge and return combined results sorted by score

#### Scenario: Batch embedding efficiency
- **GIVEN** multiple queries
- **WHEN** `code.search_batch()` is called
- **THEN** it SHALL use a single embedding API call for all queries
- **AND** it SHALL NOT make separate API calls per query

#### Scenario: Result deduplication
- **GIVEN** multiple queries returning overlapping results
- **WHEN** results are merged
- **THEN** it SHALL deduplicate by file path and line range
- **AND** it SHALL keep the result with the highest score

#### Scenario: Batch with exclusion
- **GIVEN** an exclude parameter
- **WHEN** `code.search_batch(queries="q1|q2", exclude="test|mock")` is called
- **THEN** it SHALL apply the same exclusion to all queries

### Requirement: Deep Code Research

The `code.research()` function SHALL provide deep multi-hop code analysis.

#### Scenario: Research query
- **GIVEN** an indexed project with LLM configuration
- **WHEN** `code.research(query="how does authentication flow work")` is called
- **THEN** it SHALL perform multi-hop semantic search
- **AND** it SHALL synthesise findings using LLM
- **AND** it SHALL return a comprehensive analysis

#### Scenario: Scoped research
- **GIVEN** a path parameter
- **WHEN** `code.research(query="error handling patterns", path="src/api/")` is called
- **THEN** it SHALL limit analysis to the specified directory

#### Scenario: Research cost warning
- **GIVEN** the research function is expensive (LLM calls)
- **WHEN** `code.research()` is called
- **THEN** it SHALL log the operation for cost tracking

### Requirement: Architecture Documentation

The `code.autodoc()` function SHALL generate architecture documentation.

#### Scenario: Generate documentation
- **GIVEN** an indexed project with LLM configuration
- **WHEN** `code.autodoc(scope="src/auth/")` is called
- **THEN** it SHALL identify points of interest in the scope
- **AND** it SHALL generate flowing documentation with code citations
- **AND** it SHALL return coverage summary showing referenced files

#### Scenario: Output to file
- **GIVEN** an out parameter
- **WHEN** `code.autodoc(scope=".", out="docs/architecture.md")` is called
- **THEN** it SHALL write documentation to the specified file

#### Scenario: Autodoc cost warning
- **GIVEN** the autodoc function is expensive (multiple LLM calls)
- **WHEN** `code.autodoc()` is called
- **THEN** it SHALL log the operation for cost tracking

### Requirement: Code Search Snippets

The code pack SHALL provide snippets for common search patterns.

#### Scenario: Batch search snippet
- **GIVEN** the `$c_q` snippet is invoked
- **WHEN** `$c_q q="auth|validation|session"` is called
- **THEN** it SHALL expand to `code.search_batch(queries="auth|validation|session", limit=5)`

#### Scenario: Type-filtered search snippet
- **GIVEN** the `$c_type` snippet is invoked
- **WHEN** `$c_type q="validation" type="function"` is called
- **THEN** it SHALL expand to `code.search(query="validation", chunk_type="function")`

#### Scenario: Research snippet
- **GIVEN** the `$c_research` snippet is invoked
- **WHEN** `$c_research q="how does X work"` is called
- **THEN** it SHALL expand to `code.research(query="how does X work")`

