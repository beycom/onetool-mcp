# tool-transform Specification

## Purpose

Defines the transform() tool for LLM-powered data transformation. Takes input data (typically output from another tool) and a prompt, uses an LLM to process/transform the data into a desired format. Requires `OPENAI_API_KEY` in secrets.yaml and configuration in onetool.yaml.

## Requirements

### Requirement: Input Validation

The transform() function SHALL validate inputs before processing.

#### Scenario: Empty prompt
- **GIVEN** an empty or whitespace-only prompt
- **WHEN** transform() is called
- **THEN** it SHALL return "Error: prompt is required and cannot be empty"
- **AND** it SHALL NOT call the LLM API

#### Scenario: Empty input
- **GIVEN** an empty or whitespace-only input
- **WHEN** transform() is called
- **THEN** it SHALL return "Error: input is required and cannot be empty"
- **AND** it SHALL NOT call the LLM API

### Requirement: Data Transformation

The transform() function SHALL transform input data according to prompt instructions.

#### Scenario: Extract structured data
- **GIVEN** search results and extraction prompt
- **WHEN** `transform(input=search_results, prompt="Extract the price as a number")` is called
- **THEN** it SHALL return the extracted data

#### Scenario: Format conversion
- **GIVEN** input data and format prompt
- **WHEN** `transform(input=data, prompt="Return as YAML with fields: name, value")` is called
- **THEN** it SHALL return the data in the requested format

#### Scenario: Summarization
- **GIVEN** long text and summarization prompt
- **WHEN** `transform(input=text, prompt="Summarize in 3 bullet points")` is called
- **THEN** it SHALL return a summary

#### Scenario: Non-string input
- **GIVEN** non-string input (dict, list, etc.)
- **WHEN** transform() is called
- **THEN** it SHALL convert input to string before processing

### Requirement: JSON Mode

The transform() function SHALL support structured JSON output.

#### Scenario: JSON mode enabled
- **GIVEN** json_mode=True parameter
- **WHEN** transform() is called
- **THEN** it SHALL set response_format to json_object
- **AND** the response SHALL be valid JSON

#### Scenario: JSON mode disabled
- **GIVEN** json_mode=False or not specified
- **WHEN** transform() is called
- **THEN** it SHALL NOT set response_format

### Requirement: API Configuration

The transform() function SHALL use OpenAI-compatible API configuration.

#### Scenario: Secrets configuration
- **GIVEN** `OPENAI_API_KEY` in secrets.yaml
- **WHEN** transform() is called
- **THEN** it SHALL use that API key

#### Scenario: Missing API key
- **GIVEN** no API key in secrets.yaml
- **WHEN** transform() is called
- **THEN** it SHALL return "Error: Transform tool not available. Set OPENAI_API_KEY in secrets.yaml."

#### Scenario: Missing base URL
- **GIVEN** no transform.base_url in config
- **WHEN** transform() is called
- **THEN** it SHALL return "Error: Transform tool not available. Set transform.base_url in config."

#### Scenario: Timeout configuration
- **GIVEN** transform.timeout in config (default: 30 seconds)
- **WHEN** OpenAI client is created
- **THEN** it SHALL use the configured timeout

#### Scenario: Max tokens configuration
- **GIVEN** transform.max_tokens in config
- **WHEN** transform() is called
- **THEN** it SHALL pass max_tokens to the API call
- **NOTE** If None (default), max_tokens is not sent

### Requirement: Model Selection

The transform() function SHALL support model selection.

#### Scenario: Default model
- **GIVEN** no model parameter
- **WHEN** transform() is called
- **THEN** it SHALL use the default model from transform.model config

#### Scenario: Model override
- **GIVEN** model parameter specified
- **WHEN** `transform(input=data, prompt=prompt, model="openai/gpt-4o")` is called
- **THEN** it SHALL use the specified model

#### Scenario: Missing model
- **GIVEN** no model parameter and no transform.model config
- **WHEN** transform() is called
- **THEN** it SHALL return "Error: Transform tool not available. Set transform.model in config."

### Requirement: System Prompt

The transform() function SHALL use a focused system prompt.

#### Scenario: System message
- **GIVEN** a transform() call
- **WHEN** the LLM request is made
- **THEN** system message SHALL instruct precise output without explanations

### Requirement: Error Handling

The transform() function SHALL handle errors gracefully.

#### Scenario: API error
- **GIVEN** an API error occurs
- **WHEN** transform() is called
- **THEN** it SHALL return "Error: {error_message}"
- **AND** it SHALL NOT raise an exception

#### Scenario: Sensitive error sanitization
- **GIVEN** an error message containing API keys or "sk-" prefix
- **WHEN** the error is returned
- **THEN** it SHALL replace the message with "Authentication error - check OPENAI_API_KEY in secrets.yaml"
- **AND** it SHALL NOT expose the actual API key

### Requirement: Composability

The transform() function SHALL compose with other tools.

#### Scenario: Chain with search
- **GIVEN** `llm.transform(input=brave.search(query="gold price"), prompt="Extract price")`
- **WHEN** executed
- **THEN** it SHALL transform the search results according to the prompt

#### Scenario: Keyword-only arguments
- **GIVEN** a transform() call
- **WHEN** called with positional arguments
- **THEN** it SHALL raise TypeError
- **EXAMPLE** Use `transform(input=data, prompt="...")` not `transform(data, "...")`

### Requirement: Transform Logging

The tool SHALL log LLM operations using LogSpan.

#### Scenario: Transform logging
- **GIVEN** a transform is requested
- **WHEN** the transform completes
- **THEN** it SHALL log:
  - `span: "llm.transform"`
  - `inputLen`: Input character count
  - `outputLen`: Output character count
  - `promptLen`: Prompt character count
  - `model`: Model used
  - `jsonMode`: Whether JSON mode was enabled

#### Scenario: Token usage logging
- **GIVEN** the LLM response includes usage data
- **WHEN** the call completes
- **THEN** it SHALL log:
  - `inputTokens`: Prompt tokens
  - `outputTokens`: Completion tokens
  - `totalTokens`: Total tokens

#### Scenario: Error logging
- **GIVEN** an error occurs
- **WHEN** the error is handled
- **THEN** it SHALL log:
  - `error`: The (sanitized) error message
