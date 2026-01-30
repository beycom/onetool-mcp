# tool-msg Specification

## Purpose

The MSG tool provides a simple message publishing interface for LLM-to-IDE communication. It routes messages to YAML files based on topic patterns, enabling real-time status updates and documentation streaming. No external message queue required—uses file-based YAML streams that IDEs can watch with `tail -f` or `yq`.
## Requirements
### Requirement: MSG Push Function

The `ot.push()` function SHALL accept topic and message parameters to publish messages to YAML files.

#### Scenario: Basic message
- **WHEN** calling `ot.push(topic="status:scan", message="Scanning src/")`
- **THEN** the function returns "OK: status:scan -> <file>" immediately
- **AND** the message is appended to the matching topic file in background

#### Scenario: No matching topic
- **WHEN** calling `ot.push(topic="unknown:topic", message="test")`
- **AND** no topic pattern matches "unknown:topic"
- **THEN** the function returns "OK: no matching topic"

#### Scenario: Multiline message
- **WHEN** calling `ot.push(topic="doc:api", message="Line 1\nLine 2\nLine 3")`
- **THEN** the message is stored using YAML literal block style (`|-`)

### Requirement: Topic Pattern Matching

Messages SHALL be routed to files based on glob-style topic patterns.

#### Scenario: First match wins
- **GIVEN** configuration:
  ```yaml
  tools:
    msg:
      topics:
        - pattern: "status:*"
          file: .msg/status.yaml
        - pattern: "*"
          file: .msg/default.yaml
  ```
- **WHEN** calling `ot.push(topic="status:scan", message="test")`
- **THEN** the message is written to `.msg/status.yaml`

#### Scenario: Glob wildcards
- **GIVEN** pattern "doc:*" matches files `.msg/docs.yaml`
- **WHEN** calling `ot.push(topic="doc:api", message="API docs")`
- **THEN** the message is written to `.msg/docs.yaml`
- **WHEN** calling `ot.push(topic="doc:user:guide", message="User guide")`
- **THEN** the message is NOT matched (glob * doesn't match :)

### Requirement: Message Format

Messages SHALL be stored in YAML stream format.

#### Scenario: YAML document format
- **WHEN** a message is written to file
- **THEN** it is formatted as:
  ```yaml
  ---
  ts: 2024-01-09T10:23:45Z
  topic: status:scan
  message: |-
    Scanning src/ directory
  ```

#### Scenario: Multiple messages
- **WHEN** multiple messages are pushed to the same file
- **THEN** each message is a separate YAML document separated by `---`

### Requirement: Configuration

MSG SHALL be configured via the `tools.msg` section of onetool.yaml.

#### Scenario: Topic mapping configuration
- **GIVEN** configuration:
  ```yaml
  tools:
    msg:
      topics:
        - pattern: "status:*"
          file: .msg/status.yaml
        - pattern: "doc:*"
          file: .msg/docs.yaml
  ```
- **WHEN** the server starts
- **THEN** topic patterns are loaded for routing

#### Scenario: Path expansion
- **GIVEN** file path `~/.onetool/messages.yaml`
- **WHEN** a message is pushed
- **THEN** the path is expanded to the user's home directory

