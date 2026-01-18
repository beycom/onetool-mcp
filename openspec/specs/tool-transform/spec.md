# tool-transform Specification

## Purpose

Defines the transform() tool for LLM-powered data transformation. Takes input data (typically output from another tool) and a prompt, uses an LLM to process/transform the data into a desired format. Requires `OT_OPENAI_API_KEY` environment variable.
## Requirements
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

### Requirement: API Configuration

The transform() function SHALL use OpenAI-compatible API configuration.

#### Scenario: OpenAI API key
- **GIVEN** `OT_OPENAI_API_KEY` environment variable is set
- **WHEN** transform() is called
- **THEN** it SHALL use that API key

#### Scenario: Missing API key
- **GIVEN** no API key environment variable is set
- **WHEN** transform() is called
- **THEN** it SHALL return "Error: No API key. Set OT_OPENAI_API_KEY."

### Requirement: Model Selection

The transform() function SHALL support model selection.

#### Scenario: Default model
- **GIVEN** no model parameter
- **WHEN** transform() is called
- **THEN** it SHALL use the default model from settings (openai/gpt-5-mini)

#### Scenario: Model override
- **GIVEN** model parameter specified
- **WHEN** `transform(input=data, prompt=prompt, model="openai/gpt-4o")` is called
- **THEN** it SHALL use the specified model

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

#### Scenario: Transform run logging
- **GIVEN** a transform is requested
- **WHEN** the transform completes
- **THEN** it SHALL log:
  - `span: "transform.run"`
  - `inputLength`: Input character count
  - `outputLength`: Output character count

#### Scenario: LLM call logging
- **GIVEN** the transform calls an LLM
- **WHEN** the call completes
- **THEN** it SHALL log:
  - `span: "transform.llm.call"`
  - `model`: Model used
  - `tokensIn`: Input tokens
  - `tokensOut`: Output tokens

