## Context

Ctx stores each handle as adjacent `<handle>` content and `<handle>.json`
metadata files. Both are updated independently through deterministic temporary
paths. Append and read-time access counters create same-handle writers, so
readers can observe a stale or mixed pair and concurrent updates can be lost.
Session data is ephemeral and has no migration requirement.

## Goals / Non-Goals

**Goals:**

- Make every published handle immutable.
- Change visibility atomically from absent to a complete content/metadata
  record.
- Make concurrent creation and forced handle collisions safe across independent
  store instances.
- Leave no visible handle or staging directory after any creation failure.
- Remove append, access counters, and all metadata update paths.

**Non-Goals:**

- Read or migrate the old flat two-file layout.
- Add locks or a mutable two-file transaction protocol.
- Preserve an append alias, compatibility error stub, or deprecated field.
- Persist session data beyond its existing lifecycle.

## Decisions

1. **Use one immutable directory per handle.** A record directory contains
   `content` and `meta.json`. Readers resolve only the final directory and never
   inspect staging directories. This makes the directory rename the single
   publication point.

2. **Build under a unique same-parent staging directory.** Each attempt uses a
   collision-resistant temporary name inside the ctx directory. Content and
   serialized metadata are written and flushed before `os.rename()` publishes
   the populated directory. Publishing a populated directory over an existing
   populated handle fails, so concurrent collisions never replace a record.

3. **Retry handle collisions at the write boundary.** `ctx.write` uses a
   128-bit random hexadecimal handle. If exclusive publication reports an
   existing target, it generates a new handle and rebuilds metadata; a
   pre-publication existence check is not treated as synchronization.

4. **Remove all same-handle updates.** Reads return immutable metadata without
   counters, and the store exposes no update operation. `ctx.append` is deleted
   rather than emulated by creating a new handle.

5. **Delete by removing the complete record directory.** A read racing deletion
   may resolve before or after removal and may return not-found, but no
   replacement or mixed-version record exists.

## Risks / Trade-offs

- **A process crash can leave a hidden staging directory.** → Normal exceptions
  always remove staging in `finally`; staging names are excluded from discovery.
- **Directory durability varies by filesystem.** → Flush both files and the
  staging directory before publication, then flush the parent directory for
  the current session durability contract.
- **Old session records become unreadable.** → This is intentional for
  ephemeral v3 session data; no fallback reader is retained.
- **Deleting a directory can race open file reads.** → Readers explicitly
  translate missing record components to not-found and never see a replacement.
