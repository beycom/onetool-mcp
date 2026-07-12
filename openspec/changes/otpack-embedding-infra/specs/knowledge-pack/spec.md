# knowledge-pack Specification (delta)

## ADDED Requirements

### Requirement: Canonical embedding vector serialization

All embedding vectors written by the knowledge pack (chunk vectors in the `vec0` table and query vectors passed to sqlite-vec) SHALL be serialized as explicit little-endian float32 (`struct` format `<{n}f`) via the shared otpack serialization helper. No knowledge module SHALL pack vectors with native byte order.

Existing databases indexed by earlier versions on little-endian platforms SHALL remain readable without reindexing, because native and little-endian float32 encodings are byte-identical there. For a database written on a big-endian host (unsupported), `kb reindex` SHALL regenerate all vectors in canonical form.

#### Scenario: Stored vectors are little-endian
- **WHEN** a chunk embedding is written during `kb index`, `kb.add`, or `kb.update`
- **THEN** the stored blob SHALL equal `struct.pack(f"<{n}f", *vector)`

#### Scenario: Pre-existing little-endian stores need no migration
- **WHEN** a database indexed before this change (on a little-endian platform) is searched after upgrading
- **THEN** semantic search SHALL return correct results without any reindex step

#### Scenario: Reindex regenerates canonical vectors
- **WHEN** `kb reindex` runs against any database
- **THEN** all regenerated vectors SHALL be stored in the canonical little-endian encoding
