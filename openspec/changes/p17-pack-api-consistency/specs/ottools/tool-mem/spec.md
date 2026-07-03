## MODIFIED Requirements

### Requirement: Memory Search

The `mem.search()` function SHALL search memories in three modes: `"semantic"` (vector cosine), `"keyword"` (LIKE-based text match), or `"hybrid"` (Reciprocal Rank Fusion of the two). The non-vector mode SHALL be spelled `"keyword"` (not `"pattern"`), matching `kb.search()`'s vocabulary for the equivalent FTS/non-vector mode. `"pattern"` SHALL NOT be accepted as a `mode` value.

#### Scenario: Semantic search
- **GIVEN** a query string
- **WHEN** `mem.search(query="authentication patterns")` is called
- **THEN** it SHALL generate a query embedding
- **AND** rank results by cosine similarity

#### Scenario: keyword mode replaces pattern
- **GIVEN** a query string
- **WHEN** `mem.search(query="database", mode="keyword")` is called
- **THEN** it SHALL match using LIKE on content and topic (the same matching behavior previously reached via `mode="pattern"`)

#### Scenario: pattern mode is rejected
- **GIVEN** a query string
- **WHEN** `mem.search(query="database", mode="pattern")` is called
- **THEN** it SHALL return "Error: Invalid mode 'pattern'. Must be 'semantic', 'keyword', or 'hybrid'"

### Requirement: Embedding Token Handling

Content exceeding the embedding model's token limit SHALL be chunked and averaged rather than truncated, preserving semantic coverage of the full document.

#### Scenario: Content within token limit
- **GIVEN** content within the model's token limit (minus safety margin)
- **WHEN** an embedding is generated
- **THEN** the full content SHALL be embedded as a single string

#### Scenario: Content exceeding token limit (chunk and average)
- **GIVEN** content exceeding `max_embedding_tokens` minus safety margin (default: 8191 - 100 = 8091)
- **WHEN** an embedding is generated
- **THEN** content SHALL be split into token-limited chunks using tiktoken
- **AND** each chunk SHALL be embedded via a single batch API call
- **AND** the resulting vectors SHALL be averaged element-wise
- **AND** the chunk count SHALL be logged

#### Scenario: Safety margin
- **GIVEN** the configured `max_embedding_tokens` limit
- **WHEN** chunking is performed
- **THEN** a safety margin of 100 tokens SHALL be subtracted from the limit

#### Scenario: Configurable token limit
- **GIVEN** a custom `max_embedding_tokens` value in config
- **WHEN** an embedding is generated
- **THEN** the configured limit SHALL be used instead of the default

#### Scenario: Unknown model fallback
- **GIVEN** an embedding model not recognized by tiktoken
- **WHEN** token counting is performed
- **THEN** it SHALL fall back to the `cl100k_base` encoding

#### Scenario: Keyword search unaffected
- **GIVEN** content that was chunked for embedding
- **WHEN** `mem.search(mode="keyword")` is used
- **THEN** it SHALL search the full stored content (not the chunked version)

#### Scenario: Keyword search
- **GIVEN** a keyword query
- **WHEN** `mem.search(query="database", mode="keyword")` is called
- **THEN** it SHALL match using LIKE on content and topic

#### Scenario: Hybrid search
- **GIVEN** a query with mode="hybrid"
- **WHEN** `mem.search(query="error handling", mode="hybrid")` is called
- **THEN** it SHALL combine semantic and keyword results via Reciprocal Rank Fusion

#### Scenario: Search extract length
- **GIVEN** a search query and content longer than the extract limit
- **WHEN** `mem.search(query="test", extract=50)` is called
- **THEN** result content extracts SHALL be truncated to 50 characters with "..."
- **AND** `extract=0` SHALL return full content without truncation
- **AND** default extract length SHALL come from config `search_extract` (default: 200)

#### Scenario: Topic and category filtering
- **GIVEN** optional topic and category filters
- **WHEN** `mem.search(query="rules", topic="projects/", category="rule")` is called
- **THEN** it SHALL restrict results to matching topic prefix and category
