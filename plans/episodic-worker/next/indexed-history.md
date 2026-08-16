# Indexed History and Rich Queries

## Status

Optional and non-normative. The current bounded `history.jsonl` journal remains
the implemented design.

## Opportunity

Large numbers of Contexts or user-facing filtering may eventually require
indexed queries by episode, status, time, Console message, or changed path.

## Possible design

- Introduce a project-scoped relational store or derived index for the strict
  mechanical History schema; do not reuse semantic memory or embeddings.
- Keep the MCP as the sole writer and preserve append-oriented episode records.
- Index only bounded mechanical fields, never prompts, Console bodies, tool
  results, file contents, diffs, or agent-authored narrative.
- Keep Local Changes observation VCS-independent.
- Define pagination, retention, deletion, corruption recovery, and schema
  evolution before replacing or indexing the journal.

## Adoption criteria

- Measurements show JSONL inspection or filtering is a material usability or
  performance problem.
- Required queries and retention behavior are stable enough to justify a
  purpose-built schema without weakening channel isolation.
