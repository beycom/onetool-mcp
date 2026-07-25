## MODIFIED Requirements

### Requirement: API Configuration

The transform() function SHALL use the effective shared generation route.

#### Scenario: CLIProxyAPI configuration
- **GIVEN** the effective backend is `cliproxy`
- **WHEN** transform() is called
- **THEN** it SHALL use the prerequisite CLIProxyAPI endpoint and inference client credential
- **AND** it SHALL NOT require `OPENAI_API_KEY`

#### Scenario: Direct API configuration
- **GIVEN** the effective backend is `openai_compatible`
- **WHEN** transform() is called
- **THEN** it SHALL use that route's base URL and named secret

#### Scenario: Missing generation route
- **GIVEN** no valid pack-level or top-level generation route
- **WHEN** transform() is called
- **THEN** it SHALL return an actionable tool-unavailable error

#### Scenario: Timeout configuration
- **GIVEN** an effective generation timeout with a default of 30 seconds
- **WHEN** the generation client is created
- **THEN** it SHALL use the effective timeout

#### Scenario: Max tokens configuration
- **GIVEN** an effective generation output limit
- **WHEN** transform() is called
- **THEN** it SHALL pass the limit to the selected backend
- **AND** an omitted limit SHALL NOT be sent

### Requirement: Model Selection

The transform() and transform_file() functions SHALL support model and reasoning
effort selection through the shared generation router.

#### Scenario: Default model
- **GIVEN** no model parameter
- **WHEN** transform() is called
- **THEN** it SHALL resolve the model from `tools.ot_llm.llm`, then top-level `llm`

#### Scenario: Model override
- **GIVEN** a model parameter is specified
- **WHEN** `transform(data=my_data, prompt=prompt, model="sol")` is called
- **THEN** it SHALL use the shared registry entry for `sol` for that call

#### Scenario: Effort override
- **GIVEN** a supported effort parameter is specified
- **WHEN** transform() or transform_file() is called with `effort="medium"`
- **THEN** it SHALL use medium reasoning effort for that call

#### Scenario: Missing model
- **GIVEN** no model parameter and no effective configured model
- **WHEN** transform() is called
- **THEN** it SHALL return an actionable error indicating that a generation model is required

#### Scenario: Unsupported model or effort
- **GIVEN** the resolved model lacks the required transform capability or requested effort
- **WHEN** transform() or transform_file() is called
- **THEN** it SHALL return an actionable validation error before network I/O

