## Why

Ctx handles currently expose append and read-side metadata mutation while their
content and metadata are published as separate files. Concurrent writers or
readers can therefore lose updates or observe a mixed record; v3 can remove
these unused mutation surfaces and publish each session record atomically.

## What Changes

- **BREAKING** Remove `ctx.append` and its tool contract.
- **BREAKING** Remove read-time `access_count` state and output.
- Store every new handle as an immutable directory containing content and
  metadata, published atomically only after the complete record is written.
- Use long collision-resistant handles and reject collisions without replacing
  an existing record.
- Remove the obsolete flat two-file layout without a compatibility reader.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ctx`: Handles become immutable atomically published records; append and
  access-count behavior are removed.

## Impact

This changes the exported ctx tool set and metadata response, replaces the
session-store layout, removes append implementation/tests/docs, and adds
filesystem concurrency and failure-injection coverage.
