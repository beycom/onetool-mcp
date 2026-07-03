## MODIFIED Requirements

### Requirement: File-Based Transformation

The transform_file() function SHALL transform file contents using an LLM. It SHALL detect whether the underlying transformation succeeded via a structured internal signal shared with `transform()`, not by inspecting whether the transformed content's text happens to start with the literal string `"Error:"`.

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
- **GIVEN** the underlying transformation genuinely fails (e.g. API error, missing configuration)
- **WHEN** transform_file() is called
- **THEN** it SHALL return that error
- **AND** it SHALL NOT write the output file

#### Scenario: Legitimate output starting with "Error:" is not misclassified
- **GIVEN** the underlying transformation succeeds and the LLM's transformed content legitimately begins with the literal text "Error:" (e.g. the input asked the model to transcribe or discuss error-log text)
- **WHEN** transform_file() is called
- **THEN** it SHALL treat the transformation as successful
- **AND** it SHALL write the full transformed content to the output file
- **AND** it SHALL return "OK: Transformed {in_file} -> {out_file} ({bytes} bytes)"
