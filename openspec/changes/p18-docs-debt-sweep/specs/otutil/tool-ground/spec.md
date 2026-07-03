## MODIFIED Requirements

### Requirement: Error Handling

The tool SHALL provide helpful error messages.

#### Scenario: Quota error
- **GIVEN** an API quota or rate limit error occurs
- **WHEN** the error is formatted
- **THEN** it SHALL return "Error: API quota exceeded. Try again later."

#### Scenario: Authentication error
- **GIVEN** an API key or authentication error occurs
- **WHEN** the error is formatted
- **THEN** it SHALL return a message mentioning GEMINI_API_KEY and secrets.yaml

#### Scenario: Timeout error
- **GIVEN** a request timeout error occurs
- **WHEN** the error is formatted
- **THEN** it SHALL return a message about the timeout and suggest increasing timeout

#### Scenario: Missing google-genai dependency
- **GIVEN** the `google-genai` package is not installed
- **WHEN** any grounding search function (`search`, `dev`, `docs`, `reddit`, `search_batch`) is called
- **THEN** the resulting `ImportError` SHALL be caught and formatted through the same error-formatting path as other `_grounded_search` failures (it SHALL NOT propagate uncaught out of the tool call)
- **AND** the returned string SHALL include the install instructions ("Install with: pip install onetool-mcp[util]")
