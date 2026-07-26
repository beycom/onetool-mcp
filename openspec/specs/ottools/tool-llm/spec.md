# tool-llm Specification

## Purpose

Defines the provider-neutral LLM transformation tools: `transform()` for
in-memory data and `transform_file()` for file-based transformations. Both use
the effective shared generation route.

## Requirements

### Requirement: Input Validation

The transform() function SHALL validate inputs before processing.

#### Scenario: Empty prompt
- **GIVEN** an empty or whitespace-only prompt
- **WHEN** transform() is called
- **THEN** it SHALL return "Error: prompt is required and cannot be empty"
- **AND** it SHALL NOT call the LLM API

#### Scenario: Empty data
- **GIVEN** an empty or whitespace-only data parameter
- **WHEN** transform() is called
- **THEN** it SHALL return "Error: data is required and cannot be empty"
- **AND** it SHALL NOT call the LLM API

### Requirement: Data Transformation

The transform() function SHALL transform data according to prompt instructions.

#### Scenario: Extract structured data
- **GIVEN** search results and extraction prompt
- **WHEN** `transform(data=search_results, prompt="Extract the price as a number")` is called
- **THEN** it SHALL return the extracted data

#### Scenario: Format conversion
- **GIVEN** data and format prompt
- **WHEN** `transform(data=my_data, prompt="Return as YAML with fields: name, value")` is called
- **THEN** it SHALL return the data in the requested format

#### Scenario: Summarization
- **GIVEN** long text and summarization prompt
- **WHEN** `transform(data=text, prompt="Summarize in 3 bullet points")` is called
- **THEN** it SHALL return a summary

#### Scenario: Non-string data
- **GIVEN** non-string data (dict, list, etc.)
- **WHEN** transform() is called
- **THEN** it SHALL convert data to string before processing

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
- **THEN** it SHALL return a safe generation error without upstream response bodies or credentials
- **AND** it SHALL NOT expose the actual API key

### Requirement: Composability

The transform() function SHALL compose with other tools.

#### Scenario: Chain with search
- **GIVEN** `llm.transform(data=brave.search(query="gold price"), prompt="Extract price")`
- **WHEN** executed
- **THEN** it SHALL transform the search results according to the prompt

#### Scenario: Keyword-only arguments
- **GIVEN** a transform() call
- **WHEN** called with positional arguments
- **THEN** it SHALL raise TypeError
- **EXAMPLE** Use `transform(data=my_data, prompt="...")` not `transform(my_data, "...")`

### Requirement: Transform Logging

The tool SHALL emit structured runtime logs for LLM operations.

#### Scenario: Transform logging
- **GIVEN** a transform is requested
- **WHEN** the transform completes
- **THEN** it SHALL log:
  - `span: "llm.transform"`
  - `dataLen`: Data character count
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

### Requirement: File-Based Transformation

The transform_file() function SHALL transform file contents using an LLM.

#### Scenario: Basic file transformation
- **GIVEN** an input file path, output file path, and transformation prompt
- **WHEN** `transform_file(prompt="Convert to uppercase", in_file="in.txt", out_file="out.txt")` is called
- **THEN** it SHALL read the input file
- **AND** it SHALL transform the content using the LLM
- **AND** it SHALL write the result to the output file
- **AND** it SHALL return "OK: Transformed {in_file} -> {out_file} ({bytes} bytes)"

#### Scenario: Input file not found
- **GIVEN** an in_file path that does not exist
- **WHEN** transform_file() is called
- **THEN** it SHALL return "Error: Input file not found: {path}"
- **AND** it SHALL NOT call the LLM API

#### Scenario: Input path is directory
- **GIVEN** an in_file path that is a directory
- **WHEN** transform_file() is called
- **THEN** it SHALL return "Error: Input path is not a file: {path}"

#### Scenario: Empty input file
- **GIVEN** an in_file with empty or whitespace-only content
- **WHEN** transform_file() is called
- **THEN** it SHALL return "Error: Input file is empty"
- **AND** it SHALL NOT call the LLM API

#### Scenario: Empty prompt
- **GIVEN** an empty or whitespace-only prompt
- **WHEN** transform_file() is called
- **THEN** it SHALL return "Error: prompt is required and cannot be empty"

#### Scenario: Model override
- **GIVEN** model parameter specified
- **WHEN** `transform_file(prompt=..., in_file=..., out_file=..., model="gpt-4")` is called
- **THEN** it SHALL use the specified model for transformation

#### Scenario: JSON mode
- **GIVEN** json_mode=True parameter
- **WHEN** transform_file() is called
- **THEN** it SHALL pass json_mode=True to the underlying transform() call

#### Scenario: Parent directory creation
- **GIVEN** an out_file path with non-existent parent directories
- **WHEN** transform_file() is called
- **THEN** it SHALL create the parent directories
- **AND** it SHALL write the output file

#### Scenario: Transform error propagation
- **GIVEN** the underlying transform() returns an error
- **WHEN** transform_file() is called
- **THEN** it SHALL return that error
- **AND** it SHALL NOT write the output file

### Requirement: File Transform Logging

The `transform_file()` function SHALL emit structured runtime logs for file operations.

#### Scenario: File transform logging
- **GIVEN** a file transform is requested
- **WHEN** the transform completes
- **THEN** it SHALL log:
  - `span: "llm.transform_file"`
  - `inFile`: Input file path
  - `outFile`: Output file path
  - `promptLen`: Prompt character count
  - `inLen`: Input file character count
  - `outLen`: Output bytes written
