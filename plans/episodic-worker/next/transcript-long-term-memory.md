# Transcripts and Long-Term Memory

## Status

Optional and non-normative. The current architecture deliberately carries
present Context rather than worker transcripts or cross-Context memory.

## Opportunity

Users may eventually need to recover discarded discussion, search prior episodes,
or reuse knowledge across Contexts or projects.

## Possible design

- Build transcript storage, full-text search, semantic retrieval, or durable
  cross-Context memory as a separate capability with explicit user controls.
- Treat transcripts as conversation records, never as mechanical History.
- Keep retrieved material distinct from trusted current Context and label its
  source and age.
- Define retention, deletion, privacy, prompt-injection handling, and project
  boundaries before automatic retrieval.
- Never silently expand every worker's startup with long-term memory.

## Adoption criteria

- Users demonstrably need discarded or cross-Context information that cannot be
  represented as current knowledge or a project-file reference.
- A separate proposal defines ownership, retrieval, security, and deletion.
