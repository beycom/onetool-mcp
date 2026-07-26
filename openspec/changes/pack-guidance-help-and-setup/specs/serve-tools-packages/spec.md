## MODIFIED Requirements

### Requirement: Tool Metadata Extraction

OneTool SHALL extract tool and pack metadata without running arbitrary top-level tool code during
discovery. Pack metadata SHALL include aliases, a valid documentation slug, normalized
requirements, and an explicit config-model hook when applicable. The composed guidance catalog
SHALL join those runtime facts with reviewed help-topic descriptors.

#### Scenario: Function signature extraction
- **GIVEN** a function with type hints
- **WHEN** the tool is discovered
- **THEN** it SHALL extract parameter names, types, and defaults

#### Scenario: Docstring extraction
- **GIVEN** a function with a Google-style docstring
- **WHEN** the tool is discovered
- **THEN** it SHALL extract the description, args, and returns sections

#### Scenario: No execution during discovery
- **GIVEN** a Python file with top-level code
- **WHEN** the registry performs static metadata discovery
- **THEN** the file SHALL NOT be executed

#### Scenario: Pack metadata extraction
- **GIVEN** a pack module declares reviewed metadata beside `pack = "..."`
- **WHEN** the tool registry scans the module
- **THEN** aliases, documentation slug, normalized requirements, and config-model hook SHALL be
  extracted as runtime metadata
- **AND** catalog composition SHALL join that metadata to reviewed help-topic descriptors for help,
  setup, and pack discovery surfaces

#### Scenario: Runtime service registration
- **GIVEN** a loaded pack module exposes `register_services(registry)`
- **WHEN** the execution tool loader imports the module
- **THEN** it SHALL call the registration function explicitly
- **AND** packs MAY register output policy, result-store, compaction, LLM, or reload hooks without core importing concrete pack modules

## ADDED Requirements

### Requirement: Normalized pack requirements

Pack-level prerequisites SHALL use one validated typed declaration supporting Python
distributions/import names, CLI executables, secret names, compatible proxy servers, required
config fields, install extras, optionality, and activation conditions.

#### Scenario: Requirements are discovered
- **GIVEN** a pack declares valid normalized requirements
- **WHEN** registry discovery or setup diagnostics inspect the pack
- **THEN** every requirement SHALL retain its kind, stable identity, purpose, install extra, optionality, and activation condition
- **AND** the same declaration SHALL drive availability checks, setup help, and generated
  dependency documentation

#### Scenario: Conditional requirement is inactive
- **GIVEN** a requirement applies only when a feature or config value is enabled
- **WHEN** that activation condition is false
- **THEN** setup diagnostics SHALL identify it as inactive or optional
- **AND** the whole pack SHALL NOT be reported unavailable because of that requirement

#### Scenario: Legacy requirement shape is rejected
- **GIVEN** a pack declares a requirement using a tuple, bare string, or old ad hoc mapping
- **WHEN** metadata validation runs
- **THEN** validation SHALL fail with the declaration path and accepted typed shape
- **AND** the old declaration SHALL NOT be interpreted through an alias, shim, or fallback

### Requirement: Introspectable pack configuration

A pack with typed configuration SHALL expose its config model through an explicit metadata hook so
help/setup surfaces can describe its supported fields without assuming the model is defined
directly in the pack module.

#### Scenario: Config schema is available
- **GIVEN** a pack declares a config-model hook
- **WHEN** setup or config help is requested
- **THEN** field names, descriptions, defaults, and validation constraints SHALL be derived from that model
- **AND** the pack's active expanded config SHALL be validated by the same model

#### Scenario: Config values are displayed safely
- **GIVEN** active pack config contains ordinary values, variable references, tokens, or credential-like fields
- **WHEN** config help renders the active state
- **THEN** ordinary non-sensitive values MAY be shown
- **AND** secrets SHALL be represented only by redacted presence state
- **AND** a variable reference MAY expose its variable name but SHALL NOT expose its expanded value

### Requirement: Composed pack catalog

Runtime discovery SHALL compose registry-derived facts with one reviewed catalog of non-derivable
pack, skill, installation-profile, documentation, and help-topic relationships.

#### Scenario: Catalog composition succeeds
- **GIVEN** all installed built-in packs have valid catalog entries
- **WHEN** the composed inventory is built
- **THEN** every pack SHALL have one display name, extra, default summary, docs slug, requirement set, config hook state, and help-topic set
- **AND** every stable pack SHALL have one skill owner
- **AND** an ownerless beta pack SHALL have an explicit skill-exclusion status and reason
- **AND** derivable runtime facts SHALL come from registry/config sources rather than duplicate catalog values

#### Scenario: Catalog drift is detected
- **GIVEN** a runtime pack, skill owner, docs page, topic resource, or install extra is missing or duplicated
- **WHEN** catalog validation runs
- **THEN** validation SHALL fail and identify the inconsistent subject
- **AND** it SHALL NOT silently synthesize a replacement mapping
