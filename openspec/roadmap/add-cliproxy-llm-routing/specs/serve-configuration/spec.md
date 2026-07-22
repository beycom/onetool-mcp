## MODIFIED Requirements

### Requirement: Root Configuration Sections

The root config SHALL support the current top-level sections used by the runtime,
including independent model-registry, generation, embedding, and harness sections.

#### Scenario: Supported root sections
- **GIVEN** a config containing `include`, `env`, `models`, `llm`, `embeddings`, `harness`, `alias`, `snippets`, `servers`, `direct`, `tools`, `security`, `stats`, `telemetry`, `output`, `tools_dir`, `prompts`, `log_level`, `log_dir`, `compact_max_length`, `log_verbose`, or `debug_tracebacks`
- **WHEN** OneTool loads configuration
- **THEN** each recognised section SHALL be validated according to its current schema

#### Scenario: Generation configuration is independent
- **GIVEN** a top-level `llm` section
- **WHEN** OneTool loads configuration
- **THEN** the section SHALL validate generation backend, model, effort, timeout, and output-limit settings
- **AND** it SHALL NOT accept embedding model, dimensions, batching, or token-limit settings

#### Scenario: Embedding configuration is independent
- **GIVEN** a top-level `embeddings` section
- **WHEN** OneTool loads configuration
- **THEN** the section SHALL validate its own backend, model, base URL, named secret, dimensions, timeout, batching, and token-limit settings
- **AND** it SHALL NOT inherit endpoint, model, or credentials from `llm`

#### Scenario: Removed embedding key is rejected
- **GIVEN** a config containing `llm.embedding_model`
- **WHEN** OneTool loads configuration
- **THEN** strict nested validation SHALL reject the removed key
- **AND** OneTool SHALL NOT interpret it as an alias for `embeddings.model`

#### Scenario: Unknown root section
- **GIVEN** a config containing an unrecognised root key
- **WHEN** OneTool loads configuration
- **THEN** the unknown key SHALL be ignored
- **AND** OneTool SHALL emit a warning naming the ignored attribute

#### Scenario: Unknown typed nested attribute
- **GIVEN** a config containing an unrecognised key under a typed section such as `models`, `llm`, `embeddings`, `harness`, `direct.host`, `security`, `stats`, `telemetry`, or `output`
- **WHEN** OneTool loads configuration
- **THEN** the unknown nested key SHALL be rejected when that section is strict or otherwise ignored according to its current schema
- **AND** an ignored key SHALL emit a warning naming the ignored attribute path

#### Scenario: Tool-specific config sections
- **GIVEN** a config containing extra pack names under `tools`
- **WHEN** OneTool loads configuration
- **THEN** those pack-specific dictionaries SHALL be preserved for runtime tool lookup

## ADDED Requirements

### Requirement: Typed tool generation selections

Generation-capable tool configuration SHALL accept reusable typed `llm` selections
at pack or operation scope. Each selection MAY contain backend, model, effort,
timeout, and output-limit overrides and SHALL use the shared generation schema.

#### Scenario: Pack selection validates
- **WHEN** `tools.ot_image.llm` contains a valid partial generation selection
- **THEN** OneTool SHALL preserve it as a typed pack-level override

#### Scenario: Operation selection validates
- **WHEN** `tools.knowledge.ask.llm` or `tools.knowledge.enrich.llm` contains a valid partial generation selection
- **THEN** OneTool SHALL preserve it as a typed operation-level override

#### Scenario: Invalid effort is rejected
- **WHEN** any generation selection configures an effort other than `low`, `medium`, or `high`
- **THEN** configuration validation SHALL fail at that setting's path

