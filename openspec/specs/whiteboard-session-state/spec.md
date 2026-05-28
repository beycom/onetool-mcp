# whiteboard-session-state Specification

## Purpose

Defines file-backed session state for the whiteboard pack. Board state is persisted in project-local session files at `{CWD}/.onetool/state/whiteboard/{key}.json` rather than in module-level memory, enabling state to survive across process boundaries (e.g. multiple `onetool direct run` invocations).

---

## Requirements

### Requirement: Whiteboard file-backed session state

Whiteboard board state SHALL be persisted in project-local session files at `{CWD}/.onetool/state/whiteboard/{key}.json` rather than in module-level memory.

State operations (draw, erase, label, group) SHALL load state from the session file, apply changes, and write back. No Playwright browser SHALL be required for state operations.

Render operations (share, export, screenshot) SHALL load state from the session file, launch a Playwright browser, render the board, and return the result.

#### Scenario: draw is browser-free

- **WHEN** `wb.draw(input='box:A -> B')` is called in a fresh process
- **THEN** the shapes SHALL be added to the session file
- **AND** no Playwright browser SHALL be launched
- **AND** the call SHALL complete in under 100ms (no browser startup)

#### Scenario: erase is browser-free

- **WHEN** `wb.erase(ids=['A'])` is called
- **THEN** the shape SHALL be removed from the session file
- **AND** no Playwright browser SHALL be launched

#### Scenario: State persists across process boundaries

- **WHEN** `wb.draw(input='box:A')` is called in one `onetool direct run` invocation
- **AND** `wb.draw(input='box:B')` is called in a subsequent `onetool direct run` invocation
- **THEN** both shapes SHALL be present in the session file
- **AND** calling `wb.share()` SHALL render a board containing both A and B

#### Scenario: Default board keyed by CWD

- **WHEN** `wb.draw(input='...')` is called without a `board=` argument
- **THEN** state SHALL be stored in `{CWD}/.onetool/state/whiteboard/<cwd-key>.json`
- **WHERE** `<cwd-key>` is a deterministic key derived from the current working directory

#### Scenario: Named board

- **WHEN** `wb.draw(input='...', board='arch')` is called
- **THEN** state SHALL be stored in `{CWD}/.onetool/state/whiteboard/arch.json`
- **AND** subsequent calls with `board='arch'` SHALL operate on that same state

#### Scenario: share launches browser

- **WHEN** `wb.share()` is called
- **THEN** Playwright SHALL launch, load the board state, and return a shareable URL or export
- **AND** the session file SHALL not be modified by the share operation

### Requirement: Whiteboard board management tools

The whiteboard pack SHALL provide `wb.boards()` and `wb.clear()` tools for session management.

#### Scenario: List boards

- **WHEN** `wb.boards()` is called
- **THEN** it SHALL return a list of active boards with name, last-modified time, and shape count
- **AND** boards with no session file SHALL not be listed

#### Scenario: Clear default board

- **WHEN** `wb.clear()` is called
- **THEN** the session file for the CWD-keyed board SHALL be deleted
- **AND** the return value SHALL confirm the board was cleared

#### Scenario: Clear named board

- **WHEN** `wb.clear(board='arch')` is called
- **THEN** `{CWD}/.onetool/state/whiteboard/arch.json` SHALL be deleted
- **AND** the return value SHALL confirm the board was cleared

#### Scenario: Clear non-existent board

- **WHEN** `wb.clear(board='nosuchboard')` is called
- **THEN** the call SHALL return a message indicating no board was found (not raise an error)
