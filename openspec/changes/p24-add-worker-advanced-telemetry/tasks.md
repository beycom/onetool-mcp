## 1. Confirm Foundation and Freeze the Metric Catalog

- [ ] 1.1 Confirm verified named-Context `p11` specs are synced and identify which optional
  `p21` turn and `p23` runtime measurements are available without depending on them.
- [ ] 1.2 Define every v1 metric's name, unit, source, scope, availability,
  aggregation, consumer, retention, and privacy classification in typed models.
- [ ] 1.3 Add strict disabled-by-default telemetry configuration with retention
  and record-limit defaults/ranges plus unknown-field tests.

## 2. Implement Privacy-Bounded Collection

- [ ] 2.1 Capture per-turn duration and provider-reported token values with
  measured, estimated, or unavailable provenance and no fabricated zeros.
- [ ] 2.2 Capture whole-episode latency, first event, status, turn count, runtime
  mode, and Context byte/revision/validation measurements with correct units.
- [ ] 2.3 Enforce a strict schema excluding Context names, descriptions, tags,
  prompts, messages, paths, error text, Context/Console/file/tool bodies,
  credentials, secrets, and unapproved high-cardinality labels.
- [ ] 2.4 Keep telemetry collection after known episode outcomes and isolate its
  failures from worker, Console, Context, Local Changes, Status, and History.

## 3. Add Bounded Storage and Explicit Access

- [ ] 3.1 Implement the dedicated project-scoped append store, age/count pruning,
  crash-safe valid-prefix handling, and disabled-collection behavior.
- [ ] 3.2 Add bounded `telemetry_query` intervals and approved filters returning
  only counts, availability, min/max/mean, and fixed histograms.
- [ ] 3.3 Add explicit interval-based `telemetry_clear` with deletion counts and
  prove disabling collection does not silently delete stored observations.

## 4. Verify Semantics and Privacy

- [ ] 4.1 Test one-turn and continued episodes, cold/warm or unavailable runtime
  mode, provider token availability, Context size labeling, and aggregation math.
- [ ] 4.2 Test retention boundaries, record limits, malformed stores, query bounds,
  approved filters, explicit clear, and collection failure behavior.
- [ ] 4.3 Use sensitive canary values to prove prohibited content never enters
  telemetry and telemetry never becomes automatic agent input or another channel.

## 5. Promote and Validate

- [ ] 5.1 Verify metric semantics, privacy, retention, unavailable-data behavior,
  and `p31` evidence sufficiency against all artifacts.
- [ ] 5.2 Update `plans/episodic-worker/arch.md` with verified telemetry behavior,
  then remove only `Advanced Telemetry` and supporting-only text from
  `plans/episodic-worker/next.md`.
- [ ] 5.3 Update worker/reference documentation and the delivery plan status if an
  execution record or status field has been added.
- [ ] 5.4 Run focused telemetry/privacy tests, strict OpenSpec validation, and
  `just check`; resolve every failure before syncing or archiving the change.
