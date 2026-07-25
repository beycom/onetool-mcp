## 0. Prerequisite and Protocol Verification

- [ ] 0.1 Complete and verify `add-proxied-harness-launcher` before starting this change, including its typed CLIProxyAPI configuration, model discovery, lifecycle, authentication, and redaction contracts.
- [ ] 0.2 Verify the pinned CLIProxyAPI release's bounded Chat Completions request, authentication, error, usage, model-discovery, and reasoning-effort wire behavior; add sanitized capability fixtures instead of inferred fallbacks.
- [ ] 0.3 Verify the concrete ids, aliases, generation interfaces, modalities, structured-output behavior, and supported effort values for the initial `sol`, `terra`, and `luna` entries; confirm `luma` remains invalid.

## 1. Shared Configuration and Model Registry

- [ ] 1.1 Move the prerequisite model registry from harness-only ownership to a strict top-level `models` mapping consumed by both harness and tool resolution, with no hidden registry or compatibility alias.
- [ ] 1.2 Add generation capability metadata and optional default effort to model entries, and validate unique shortcuts, ids, proxy aliases, interfaces, modalities, and supported `low`, `medium`, and `high` values.
- [ ] 1.3 Add strict discriminated top-level `llm` generation configuration for `cliproxy` and `openai_compatible` backends, including model, effort, timeout, output limit, endpoint, and named-secret requirements.
- [ ] 1.4 Add strict independent top-level `embeddings` configuration for backend, model, base URL, named secret, dimensions, timeout, batching, and token limits.
- [ ] 1.5 Remove `llm.embedding_model` and superseded pack-level embedding `model` and `base_url` fields without aliases, legacy detectors, or migration fallbacks.
- [ ] 1.6 Add reusable typed partial generation selections for pack and operation configuration, including knowledge ask, rerank, and enrichment scopes.
- [ ] 1.7 Update packaged config templates and setup materialization for `models`, `llm`, and `embeddings` while preserving the prerequisite harness and CLIProxyAPI sections.
- [ ] 1.8 Add configuration tests for valid routes, backend isolation, strict removed-key failure, named-secret validation, shortcut uniqueness, effort enums, layered partial selections, and generation/embedding independence.

## 2. Shared Generation Routing

- [ ] 2.1 Implement immutable resolved generation-selection models and precedence for per-call, operation, pack, top-level, and model-default values.
- [ ] 2.2 Implement shared model resolution for shortcuts and full ids with clear unknown, ambiguous, unavailable, and capability-incompatible errors.
- [ ] 2.3 Implement provider-neutral effort validation and verified backend translation for exactly `low`, `medium`, and `high`, omitting the wire field when no effort resolves.
- [ ] 2.4 Add an explicit bounded CLIProxyAPI generation method that accepts resolved options, uses the inference client credential, validates health and live model availability, and normalizes response and usage data.
- [ ] 2.5 Implement the explicit OpenAI-compatible generation adapter using only its base URL and named secret, with no credential or endpoint inheritance from CLIProxyAPI.
- [ ] 2.6 Integrate managed proxy readiness at server startup when configured, while ensuring individual tool calls never mutate lifecycle and proxy failures never fall back to a direct provider.
- [ ] 2.7 Add bounded route diagnostics and errors that expose only safe model, backend, effort, latency, and usage metadata and redact all credentials, identities, content, headers, and raw upstream bodies.
- [ ] 2.8 Add unit tests for complete precedence, backend switches, shortcut/full-id matching, effort translation, capability gates, proxy availability, direct-route isolation, normalized responses, no lifecycle mutation, no provider fallback, and redaction.

## 3. Generation-Backed Tool Migration

- [ ] 3.1 Migrate `ot_llm.transform` and `transform_file` to `tools.ot_llm.llm`, add optional model and effort controls, and remove the unconditional `OPENAI_API_KEY` availability check.
- [ ] 3.2 Migrate `image.ask` and `image.summary` to `tools.ot_image.llm`, add optional model and effort controls, and enforce image-input capability before network I/O.
- [ ] 3.3 Migrate `ctx.ask` to `tools.ctx.llm` with per-call model and effort resolution while preserving structured answers, batching, truncation, and error-return behavior.
- [ ] 3.4 Migrate `mem.ask` to its effective generation selection with per-call model and effort resolution while preserving its topic and answer behavior.
- [ ] 3.5 Migrate knowledge enrichment, reranking, and synthesis to their operation selections and add model and effort controls to the public generation call boundaries.
- [ ] 3.6 Add focused offline tool tests for every migrated operation covering global, pack, operation, and per-call selection; CLIProxyAPI without a provider key; direct named secrets; invalid capabilities; invalid effort; and stable result contracts.

## 4. Embedding Separation and Grounding Isolation

- [ ] 4.1 Migrate memory embedding creation, search, backfill, reindex, import, restore, and background work to the independent effective `embeddings` configuration.
- [ ] 4.2 Migrate knowledge indexing and semantic search embeddings to the independent effective `embeddings` configuration while retaining project enablement and dimension validation.
- [ ] 4.3 Ensure embedding clients never use the CLIProxyAPI generation endpoint, client credential, model registry defaults, or tool generation selections.
- [ ] 4.4 Preserve every `ground` operation on the native Google GenAI client, Gemini models, `GEMINI_API_KEY`, and Google Search grounding without registering it as a shared generation consumer.
- [ ] 4.5 Add tests proving embeddings remain usable with a different provider than generation, missing embedding config fails independently, CLIProxyAPI receives no embedding calls, and all ground operations ignore global or tool proxy routes.
- [ ] 4.6 Add tests proving `ground` rejects non-Gemini shared shortcuts and continues to require its native Gemini credential and grounding behavior.

## 5. Documentation and User Guidance

- [ ] 5.1 Document the top-level model registry, `sol`/`terra`/`luna` shortcut behavior, concrete-id resolution, capability metadata, and exact reasoning-effort values.
- [ ] 5.2 Document generation and embedding configuration as separate contracts, including backend-specific named secrets, precedence, strict removed keys, and no inheritance across backend types.
- [ ] 5.3 Update `ot_llm`, image, ctx, mem, and knowledge references with pack and operation configuration plus per-call model and effort examples.
- [ ] 5.4 Document that all ground operations are Gemini-only and never use CLIProxyAPI, while other search providers remain unchanged.
- [ ] 5.5 Extend the prerequisite subscription, billing, security, and redaction warnings to generation-backed tool routes without claiming guaranteed included subscription usage.
- [ ] 5.6 Regenerate canonical configuration, tool, and documentation indexes and run their registry and link checks.

## 6. Integration and Verification

- [ ] 6.1 Add opt-in CLIProxyAPI integration tests for subscription-backed text, structured-output, and vision generation using explicit confirmation before any request that may consume quota or incur charges.
- [ ] 6.2 Add an opt-in direct OpenAI-compatible integration fixture that verifies backend isolation without embedding or proxy credential reuse.
- [ ] 6.3 Run focused configuration, routing, tool, embedding, grounding, redaction, and documentation tests and resolve all failures.
- [ ] 6.4 Run secret scans across source, tests, fixtures, logs, errors, snapshots, generated examples, and documentation for proxy keys, named secret values, OAuth state, account identities, headers, prompts, and responses.
- [ ] 6.5 Verify no `luma`, `med`, provider-specific effort, legacy embedding alias, direct-provider fallback, arbitrary proxy request surface, or ground-to-proxy route exists.
- [ ] 6.6 Run `just check` and OpenSpec strict validation and resolve every failure before marking the change complete.

