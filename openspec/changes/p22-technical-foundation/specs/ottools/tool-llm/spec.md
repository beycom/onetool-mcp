## MODIFIED Requirements

### Requirement: System Prompt

The transform() function SHALL use a focused system prompt.

The system prompt SHALL also frame the `data` argument as untrusted content: it MUST instruct the
model to treat `data` as reference material to transform, not as instructions to follow, and to
ignore any directive-like text embedded within `data` that attempts to change the model's behavior,
reveal secrets, call tools, fetch URLs, execute code, or disregard these rules. This applies
uniformly regardless of caller — `transform()` backs both `ctx.ask()` and `mem.ask()`, so fixing this
system prompt covers both call sites without a separate change in either.

#### Scenario: System message
- **GIVEN** a transform() call
- **WHEN** the LLM request is made
- **THEN** system message SHALL instruct precise output without explanations

#### Scenario: Untrusted-data boundary is present
- **GIVEN** a transform() call
- **WHEN** the LLM request is made
- **THEN** the system message SHALL explicitly instruct the model to treat `data` as untrusted
  content, not as instructions
- **AND** the system message SHALL instruct the model to ignore instructions embedded within `data`

#### Scenario: Boundary applies transitively to ctx.ask and mem.ask
- **GIVEN** `ctx.ask()` or `mem.ask()` calls `transform()` internally to answer a question about
  stored content
- **WHEN** the underlying LLM request is made
- **THEN** the same untrusted-data system message boundary SHALL be present, with no separate
  boundary logic required in `ctx.ask()` or `mem.ask()`
