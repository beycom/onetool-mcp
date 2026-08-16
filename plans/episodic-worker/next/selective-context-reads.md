# Selective Context Reads and Deterministic Search

## Status

Optional and non-normative. Workers currently receive the complete selected
Context on the first turn.

## Opportunity

A future Context schema may grow enough that whole-state injection becomes
measurably wasteful or workers need to find one known item without reading
unrelated state.

## Possible design

- Start with exact deterministic selectors over named sections or stable IDs.
- If text search is needed, use literal or normalized substring matching with
  stable ordering and explicit limits.
- Return revision and match metadata with every response.
- Treat unknown selectors as errors, not empty successful reads.
- Keep semantic similarity, embeddings, and model-selected retrieval out unless
  evaluated as a separate memory capability.

## Adoption criteria

- Measurements show whole-state injection is a material cost or reliability
  problem at the configured size.
- Exact retrieval preserves the worker's ability to discover all state relevant
  to its task.
