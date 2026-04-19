# force-context-dunder Specification

## Purpose

Defines the `__force_context__` magic variable that allows code to unconditionally store its output to the ctx backend and receive a handle summary, regardless of output size.

## Requirements

### Requirement: Force Context Storage Magic Variable

The system SHALL support a `__force_context__` magic variable that forces the current call's output to be stored in the ctx backend and returned as a handle summary, regardless of output size.

#### Scenario: Explicit enable — output stored unconditionally
- **WHEN** code sets `__force_context__ = True`
- **AND** the output is smaller than `output.max_inline_size`
- **THEN** the output SHALL be stored to the ctx backend
- **AND** a handle summary dict SHALL be returned instead of the inline output

#### Scenario: Explicit enable — large output still stored
- **WHEN** code sets `__force_context__ = True`
- **AND** the output exceeds `output.max_inline_size`
- **THEN** the output SHALL be stored to the ctx backend (same as normal large-output behaviour)

#### Scenario: Default behaviour — no force
- **WHEN** code does not set `__force_context__`
- **THEN** ctx storage SHALL only occur when output exceeds `output.max_inline_size`

#### Scenario: Explicit disable — no override
- **WHEN** code sets `__force_context__ = False`
- **THEN** ctx storage SHALL only occur when output exceeds `output.max_inline_size`

#### Scenario: ctx.* tools remain exempt
- **WHEN** code sets `__force_context__ = True`
- **AND** the tool being executed is a `ctx.*` call or `ot.result`
- **THEN** the output SHALL be returned inline
- **AND** the `__force_context__` flag SHALL be ignored for that call

#### Scenario: Compaction runs before force-context check
- **WHEN** code sets both `__compact__ = True` and `__force_context__ = True`
- **THEN** the output SHALL be compacted first
- **AND** the compacted output SHALL be stored to the ctx backend
- **AND** a handle summary SHALL be returned
