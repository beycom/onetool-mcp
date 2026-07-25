## MODIFIED Requirements

### Requirement: Multi-question LLM Query

The `ctx.ask()` function SHALL accept one or more questions about stored content,
send them to the effective shared generation route in a single call, and return
structured question/answer pairs mirroring the image ask interface.

#### Scenario: Single question string

- **WHEN** `ctx.ask(h, q="What is the recommended entry point?")` is called
- **THEN** it SHALL return `{"handle": h, "result": [{"question": "What is the recommended entry point?", "answer": "<answer>"}]}`

#### Scenario: Batch questions list

- **WHEN** `ctx.ask(h, q=["What is the recommended entry point?", "What are common mistakes?"])` is called
- **THEN** it SHALL send both questions in a single generation call
- **AND** return `{"handle": h, "result": [{"question": "...", "answer": "..."}, {"question": "...", "answer": "..."}]}`
- **AND** the order of results SHALL match the order of questions provided

#### Scenario: Model override

- **WHEN** `ctx.ask(h, q="...", model="sol")` is called
- **THEN** it SHALL resolve `sol` from the shared model registry for that call
- **AND** fall back through `tools.ctx.llm` to top-level `llm` if `model=None`

#### Scenario: Effort override

- **WHEN** `ctx.ask(h, q="...", effort="low")` is called
- **THEN** it SHALL request low reasoning effort for that call

#### Scenario: CLIProxyAPI route

- **WHEN** the effective generation backend is `cliproxy`
- **THEN** `ctx.ask()` SHALL use the shared CLIProxyAPI service without requiring a provider API key

#### Scenario: LLM service not configured

- **WHEN** `ctx.ask(h, q="...")` is called and no valid generation route is configured
- **THEN** it SHALL return `{"handle": h, "error": "<message explaining a generation route must be configured>"}`
- **AND** it SHALL NOT raise an unhandled exception

#### Scenario: Unknown handle

- **WHEN** `ctx.ask("badhandle", q="...")` is called
- **THEN** it SHALL return `{"handle": "badhandle", "error": "Handle not found: badhandle"}`

#### Scenario: Large content truncation

- **GIVEN** a handle whose total content exceeds `ask_max_bytes`
- **WHEN** `ctx.ask(h, q="...")` is called
- **THEN** it SHALL send the first `ask_max_bytes` bytes of content to the model
- **AND** the response SHALL include a `truncated: true` field
- **AND** the response MAY include a `hint` suggesting `ctx.slice` to narrow scope before re-querying

