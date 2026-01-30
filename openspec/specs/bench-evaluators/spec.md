# bench-evaluators Specification

## Purpose

Defines the evaluator system for bench, including named evaluators, deterministic matching, and LLM-as-judge evaluation.

---

## Requirements

### Requirement: Named Evaluators

The harness SHALL support reusable named evaluators.

#### Scenario: Define named evaluator
- **GIVEN** configuration with `evaluators.my_eval: {...}`
- **WHEN** tasks reference `evaluate: my_eval`
- **THEN** they SHALL use the named evaluator configuration

#### Scenario: Inline evaluator
- **GIVEN** task with inline `evaluate: { expected: "value" }`
- **WHEN** the task is evaluated
- **THEN** it SHALL use the inline configuration

### Requirement: Deterministic Evaluation

The harness SHALL support deterministic response matching.

#### Scenario: Expected string match
- **GIVEN** `evaluate.expected: "exact value"`
- **WHEN** the response is evaluated
- **THEN** it SHALL pass if the response contains the exact string

#### Scenario: Expected number match
- **GIVEN** `evaluate.expected: 42`
- **WHEN** the response is evaluated
- **THEN** it SHALL pass if the response contains the number

#### Scenario: Expected list (any match)
- **GIVEN** `evaluate.expected: ["a", "b"]`
- **WHEN** the response is evaluated
- **THEN** it SHALL pass if ALL expected values are found in the response

#### Scenario: Regex match
- **GIVEN** `evaluate.expected: [{regex: "pattern"}]`
- **WHEN** the response is evaluated
- **THEN** it SHALL pass if the regex matches somewhere in the response

#### Scenario: Expect error
- **GIVEN** `evaluate.expect_error: true`
- **WHEN** a task results in an error (e.g., timeout)
- **THEN** the error message SHALL be used as the response for evaluation
- **AND** evaluation proceeds normally against the error text
- **USE CASE** Testing timeout behavior or expected failure scenarios

### Requirement: LLM-as-Judge Evaluation

The harness SHALL support LLM-based evaluation.

#### Scenario: LLM evaluation prompt
- **GIVEN** `evaluate.prompt: "Is {response} correct? Expected: {expected}"`
- **WHEN** the response is evaluated
- **THEN** it SHALL call the LLM with the formatted prompt

#### Scenario: LLM evaluation model
- **GIVEN** `evaluate.model: openai/gpt-5-mini`
- **WHEN** LLM evaluation runs
- **THEN** it SHALL use the specified model
- **REQUIRED** No default - must be explicitly configured in evaluator
