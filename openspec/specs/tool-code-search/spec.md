# tool-code-search Specification

## Purpose

Provides semantic code search using ChunkHound indexes. Queries existing DuckDB databases for semantic code search. Requires `OT_OPENAI_API_KEY` environment variable and projects to be indexed externally with `chunkhound index <project>`.
## Requirements
### Requirement: Semantic Code Search

The `code.search()` function SHALL search for code semantically in a ChunkHound-indexed project.

#### Scenario: Basic search
- **GIVEN** an indexed project
- **WHEN** `code.search(query="authentication logic")` is called
- **THEN** it SHALL return code matches ranked by semantic similarity
- **AND** results SHALL include file paths, line numbers, and code snippets

#### Scenario: Search with project name
- **GIVEN** a project configured in onetool.yaml
- **WHEN** `code.search(query="error handling", project="onetool")` is called
- **THEN** it SHALL resolve the project path from config
- **AND** it SHALL search within that project

#### Scenario: Search with project path
- **GIVEN** an explicit project path
- **WHEN** `code.search(query="query", project="/path/to/project")` is called
- **THEN** it SHALL use the path directly

#### Scenario: Default project
- **GIVEN** no project specified
- **WHEN** `code.search(query="query")` is called
- **THEN** it SHALL use the current working directory

#### Scenario: Result limit
- **GIVEN** a limit parameter
- **WHEN** `code.search(query="query", limit=5)` is called
- **THEN** it SHALL return at most 5 results
- **AND** default limit is 10

#### Scenario: Language filter
- **GIVEN** a language parameter
- **WHEN** `code.search(query="query", language="python")` is called
- **THEN** it SHALL filter results to Python files only

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
- **WHEN** `code.search(query="query", project="unindexed")` is called
- **THEN** it SHALL return error with indexing instructions
- **AND** error SHALL include: "Run: chunkhound index {project_root}"

### Requirement: Index Status

The `code.status()` function SHALL report index statistics.

#### Scenario: Indexed project
- **GIVEN** a project with ChunkHound index
- **WHEN** `code.status(project="onetool")` is called
- **THEN** it SHALL return:
  - Database path
  - File count
  - Chunk count
  - Language distribution

#### Scenario: Unindexed project
- **GIVEN** a project without ChunkHound index
- **WHEN** `code.status(project="unindexed")` is called
- **THEN** it SHALL return indexing instructions

### Requirement: Embedding Generation

The `code.search()` function SHALL generate embeddings for queries.

#### Scenario: OpenAI embedding
- **GIVEN** `OT_OPENAI_API_KEY` environment variable is set
- **WHEN** a search query is executed
- **THEN** it SHALL use text-embedding-3-small model
- **AND** embedding dimensions SHALL be 1536

#### Scenario: Missing API key
- **GIVEN** `OT_OPENAI_API_KEY` environment variable is not set
- **WHEN** `code.search()` is called
- **THEN** it SHALL return "OT_OPENAI_API_KEY environment variable required for code search embeddings"

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

### Requirement: Project Resolution

The `code.search()` and `code.status()` functions SHALL resolve project references.

#### Scenario: Named project
- **GIVEN** project="onetool" in config: `projects: { onetool: ~/projects/onetool }`
- **WHEN** function is called
- **THEN** it SHALL resolve to ~/projects/onetool

#### Scenario: Unknown project name
- **GIVEN** project="unknown" not in config
- **WHEN** function is called
- **THEN** it SHALL return error listing available projects

### Requirement: Code Search Logging

The tool SHALL log search and index operations using LogSpan.

#### Scenario: Code search logging
- **GIVEN** a code search is requested
- **WHEN** the search completes
- **THEN** it SHALL log:
  - `span: "code.search"`
  - `query`: Search query
  - `path`: Search path
  - `resultCount`: Matches found

#### Scenario: Index build logging
- **GIVEN** a code index is built
- **WHEN** indexing completes
- **THEN** it SHALL log:
  - `span: "code.index.build"`
  - `path`: Indexed path
  - `fileCount`: Files indexed

