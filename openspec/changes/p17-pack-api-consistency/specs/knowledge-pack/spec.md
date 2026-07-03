## MODIFIED Requirements

### Requirement: kb.search — Hybrid retrieval
`kb.search()` SHALL retrieve chunks using a hybrid FTS5 BM25 + sqlite-vec KNN pipeline fused with RRF (k=60). The `mode` parameter SHALL select `hybrid` (default), `semantic` (vector-only), or `keyword` (FTS5-only). The search text parameter SHALL be named `query` (not `q`).

#### Scenario: Hybrid mode returns fused results
- **WHEN** `kb.search(query='nudge keys', db='docs', mode='hybrid', k=5)` is called
- **THEN** up to 5 chunks are returned ranked by RRF-fused BM25 and cosine scores

#### Scenario: Metadata filters narrow results
- **WHEN** `kb.search(query='...', db='docs', source='docs.example.test', k=10)` is called
- **THEN** only chunks whose `meta.source` starts with `'docs.example.test'` are returned

#### Scenario: category filter applies
- **WHEN** `kb.search(query='...', db='docs', category='rule')` is called
- **THEN** only chunks with `category='rule'` are returned

#### Scenario: Interaction boost applied
- **WHEN** a chunk has been returned by previous searches
- **THEN** its `hit_count` is incremented and its RRF score receives a small additive boost of `0.1 * min(hit_count, 10) / 10` (max +0.1)

#### Scenario: FTS query is preprocessed
- **WHEN** a keyword or hybrid search is issued
- **THEN** the query is stripped of FTS5 operator characters (`?`, `!`, `"`, `:`, `^`, `*`, `(`, `)`, `-`) and common English stopwords before the FTS5 MATCH is executed

#### Scenario: Prefix fallback on empty FTS result
- **WHEN** a keyword search returns no results after preprocessing
- **THEN** a second pass is attempted with each query term suffixed by `*` for prefix matching

#### Scenario: FTS uses Porter stemmer
- **WHEN** the `chunks_fts` virtual table is created
- **THEN** it uses `tokenize = 'porter unicode61'` so inflected word forms match their stems

#### Scenario: query parameter accepts the query= prefix match
- **WHEN** `kb.search(q='nudge keys', db='docs')` is called (using the short `q=` keyword instead of the full `query=`)
- **THEN** it SHALL succeed identically to `kb.search(query='nudge keys', db='docs')`, because `q` is a prefix of the `query` parameter name and is resolved by the run-tool's keyword-argument prefix matching

---

### Requirement: kb.ask — Retrieval-augmented synthesis
`kb.ask()` SHALL retrieve relevant chunks via `kb.search`, optionally re-rank them, optionally expand context with 1-hop graph neighbours, then synthesise an answer via `ot_llm` with source citations. The question-text parameter SHALL be named `query` (not `q`).

#### Scenario: Answer is returned with citations
- **WHEN** `kb.ask(query='How do I nudge objects?', db='docs')` is called
- **THEN** a text answer is returned alongside a list of source citations (topic + url)

#### Scenario: Re-ranking is applied by default
- **WHEN** `kb.ask(query='...', db='docs', rerank=True)` is called
- **THEN** candidate chunks are re-ordered by relevance via a single batched LLM scoring call before synthesis

#### Scenario: Graph expansion adds neighbours
- **WHEN** `kb.ask(query='...', db='docs', expand=True)` is called
- **THEN** 1-hop outbound neighbours of top-k chunks are included as supplementary context (deduplicated)
