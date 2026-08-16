# Partial Context Updates and Rich Item Identity

## Status

Optional and non-normative. Complete Context replacement remains the implemented
and preferred model.

## Opportunity

Whole-object replacement may become inefficient if Context grows or independent
sections need mutation without resubmitting unrelated fields.

## Possible design

- Introduce stable item IDs only for sections that demonstrably need independent
  mutation.
- Support typed whole-item `upsert` and `remove`; continue rejecting arbitrary
  YAML paths and partial unvalidated objects.
- Require an expected base revision and apply a batch atomically.
- Keep runtime-managed schema and revision fields unavailable to callers.

## Adoption criteria

- Whole-Context submissions cause measured latency or repeated omission errors.
- Mutation semantics remain smaller and clearer than replacing the file.
