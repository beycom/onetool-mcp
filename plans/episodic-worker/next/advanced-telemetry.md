# Advanced Episodic-Worker Telemetry

## Status

Optional and non-normative. Draft OpenSpec change
`p24-add-worker-advanced-telemetry` is available if real testing demonstrates a
specific measurement need.

## Opportunity

Detailed measurements could evaluate episodic execution cost, Context pressure,
continuation behavior, and cold/warm latency without expanding mechanical
History into another memory channel.

## Possible design

- Record provider-reported input, output, and cached tokens only when reliable.
- Separate app-server startup events, worker-output latency, per-turn duration,
  and whole-episode duration with unambiguous names and sources.
- Track terminal status, runtime mode, turn count, Context bytes and revisions,
  validation failures, and rejected sizes.
- Keep telemetry separate from Chat, Context, Console, Local Changes, Status,
  History, and Artifacts; never make it implicit agent input.
- Exclude prompts, paths, errors, bodies, file contents, diffs, tool results,
  credentials, secrets, and identifying high-cardinality labels.
- Define metric consumers, retention, privacy, and unavailable-data behavior
  before collection.

## Adoption criteria

- A concrete product or performance question cannot be answered by current
  operational logs and tests.
- Every proposed metric has a stable definition, source, consumer, retention
  policy, privacy classification, and test.
