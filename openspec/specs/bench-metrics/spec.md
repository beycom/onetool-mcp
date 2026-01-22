# bench-metrics Specification

## Purpose

Defines per-LLM-call metrics tracking and context growth analysis for ot-bench.

---

## Requirements

### Requirement: Per-LLM-Call Metrics

The harness SHALL track metrics for each individual LLM API call within a task execution.

#### Scenario: Track per-call input tokens
- **GIVEN** a task that makes multiple LLM calls (agentic loop)
- **WHEN** the task completes
- **THEN** `TaskResult.llm_call_metrics` SHALL contain one entry per LLM call
- **AND** each entry SHALL include `input_tokens` from that call's `response.usage.prompt_tokens`

#### Scenario: Track per-call output tokens
- **GIVEN** a task with multiple LLM calls
- **WHEN** the task completes
- **THEN** each `LLMCallMetrics` entry SHALL include `output_tokens` from `response.usage.completion_tokens`

#### Scenario: Track per-call latency
- **GIVEN** a task with multiple LLM calls
- **WHEN** each LLM API call is made
- **THEN** the harness SHALL measure wall-clock time for that call
- **AND** store it as `latency_ms` in the metrics entry

#### Scenario: Track cumulative input
- **GIVEN** a task with N LLM calls
- **WHEN** the task completes
- **THEN** each `LLMCallMetrics` entry SHALL include `cumulative_input`
- **AND** `cumulative_input` for call N equals sum of `input_tokens` for calls 1 through N
- **NOTE** This is a running total computed during execution, not stored redundantly

#### Scenario: Track tool calls per LLM response
- **GIVEN** an LLM response with tool calls
- **WHEN** metrics are recorded
- **THEN** `tool_calls_made` SHALL equal the number of tool calls in that response

### Requirement: Context Growth Analysis

The harness SHALL provide analysis of context growth patterns.

#### Scenario: Estimate base context
- **GIVEN** a completed task with per-call metrics
- **WHEN** `TaskResult.base_context` is accessed
- **THEN** it SHALL return the `input_tokens` from the first LLM call
- **REASON** First call represents system prompt + tool definitions before conversation history

#### Scenario: Calculate average context growth
- **GIVEN** a completed task with N > 1 LLM calls
- **WHEN** `TaskResult.context_growth_avg` is accessed
- **THEN** it SHALL return the average increase in `input_tokens` between consecutive calls
- **FORMULA** `sum(call[i+1].input_tokens - call[i].input_tokens) / (N - 1)`

#### Scenario: Handle single LLM call growth
- **GIVEN** a completed task with exactly 1 LLM call
- **WHEN** `TaskResult.context_growth_avg` is accessed
- **THEN** it SHALL return 0
