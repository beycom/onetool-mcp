# tool-caveman Specification

## Purpose

Defines the ot_caveman pack — LLM-powered text compaction, expansion, and command-queue input. Accessible as `cm` (short alias) or `ot_caveman` in the executor namespace.

## Requirements

### Requirement: compact() compacts text or a file

The `compact()` tool SHALL accept either `text` (inline string) or `src` (file path or glob), not both, and compact the content using an LLM co-processor. It SHALL return a dict with keys `text`, `tokens_in`, `tokens_out`, `reduction_pct`. If `dest` is provided, the compacted text SHALL be written to that path and `file_out` SHALL be added to the result. If `cost_per_1m_tokens` is configured, `cost_saved_usd` SHALL be added. On any misconfiguration or API failure, it SHALL return an error string.

#### Scenario: Text input returns compaction dict
- **WHEN** `cm.compact(text="some prose")` is called with a configured client
- **THEN** the result is a dict with keys `text`, `tokens_in`, `tokens_out`, `reduction_pct`

#### Scenario: File input reads and compacts file
- **WHEN** `cm.compact(src="notes.md")` is called and the file exists
- **THEN** the file contents are compacted and the result dict is returned

#### Scenario: dest writes compacted result
- **WHEN** `cm.compact(text="prose", dest="slim.md")` is called
- **THEN** the compacted text is written to `slim.md` and `file_out` is present in the result

#### Scenario: In-place compaction
- **WHEN** `cm.compact(src="notes.md", dest="notes.md")` is called
- **THEN** the file is overwritten with the compacted version

#### Scenario: Glob batch mode
- **WHEN** `cm.compact(src="dev/guides/*.md", dest="scratch/compact")` is called
- **THEN** each matched file is compacted and written to the dest directory
- **AND** the result is a dict with `files`, `skipped`, `tokens_in`, `tokens_out`, `reduction_pct`

#### Scenario: Both text and src returns error
- **WHEN** both `text` and `src` are provided
- **THEN** returns `"Error: provide either text or src, not both"`

#### Scenario: Neither text nor src returns error
- **WHEN** neither `text` nor `src` is provided
- **THEN** returns `"Error: provide text or src"`

#### Scenario: Empty input returns error
- **WHEN** `text=""` or file contains only whitespace
- **THEN** returns `"Error: input is empty"`

#### Scenario: Missing file returns error
- **WHEN** `src` path does not exist
- **THEN** returns `"Error: file not found: <path>"`

#### Scenario: Unchanged result includes flag
- **WHEN** compaction produces output longer than input (fell back to original)
- **THEN** the result dict includes `"unchanged": true`

### Requirement: compact() never modifies protected content

The `compact()` tool SHALL never alter code blocks, URLs, file paths, commands, version numbers, technical identifiers, numbers, error messages, proper nouns, security warnings, or irreversible action confirmations.

#### Scenario: Code block is preserved
- **WHEN** input contains a fenced code block
- **THEN** the code block appears verbatim in the compacted output

#### Scenario: Markdown table is preserved
- **WHEN** input contains a markdown table
- **THEN** the table appears in the compacted output with columns intact

### Requirement: compact() not-configured errors are specific

The `compact()` tool SHALL return a distinct error string for each missing configuration element:
- Missing API key → error referencing `OPENAI_API_KEY in secrets.yaml`
- Missing base_url → error referencing `llm.base_url or tools.ot_caveman.base_url`
- Missing model → error referencing `llm.model or tools.ot_caveman.model`

#### Scenario: No API key
- **WHEN** `OPENAI_API_KEY` and `OT_LLM_API_KEY` are both absent
- **THEN** returns error string mentioning `OPENAI_API_KEY`

#### Scenario: No base URL configured
- **WHEN** API key is present but no base_url is set
- **THEN** returns error string mentioning `llm.base_url or tools.ot_caveman.base_url`

#### Scenario: No model configured
- **WHEN** API key and base_url are present but no model is set
- **THEN** returns error string mentioning `llm.model or tools.ot_caveman.model`

### Requirement: expand() reconstructs readable prose

The `expand()` tool SHALL accept either `text` or `src` and reconstruct readable prose from packed text using an LLM. It SHALL return a dict with keys `text`, `tokens_in`, `tokens_out`, `expansion_pct`. Reconstruction is lossy. If `dest` is provided, the expanded text SHALL be written to that path. Supports glob batch mode.

#### Scenario: Text input returns expansion dict
- **WHEN** `cm.expand(text=packed_text)` is called with a configured client
- **THEN** the result is a dict with keys `text`, `tokens_in`, `tokens_out`, `expansion_pct`

#### Scenario: File input with dest writes result
- **WHEN** `cm.expand(src="slim.md", dest="readable.md")` is called
- **THEN** the expanded text is written to `readable.md` and `file_out` is in the result

#### Scenario: Code block is preserved through expand
- **WHEN** packed text contains a fenced code block
- **THEN** the code block appears verbatim in the expanded output

### Requirement: input() reads next pending command from command file

The `input()` tool SHALL read a `command.md`-style file, find the first pending command block (title NOT starting with `[x]`), mark it done by prepending `[x] ` to its title line in the file, and return the command text (optionally compacted). If no pending command exists, it SHALL return `"NO MORE COMMANDS"`. Header lines (`# `) are ignored when searching.

#### Scenario: Returns first pending command
- **WHEN** the file contains a mix of done and pending commands
- **THEN** returns the text of the first pending command

#### Scenario: Marks command done in file
- **WHEN** `cm.input()` is called and a pending command exists
- **THEN** the file is updated so that command's title starts with `[x] `

#### Scenario: No more commands
- **WHEN** all commands in the file are marked `[x]`
- **THEN** returns `"NO MORE COMMANDS"`

#### Scenario: Named command lookup
- **WHEN** `cm.input(command="fix")` is called
- **THEN** finds the block with `name:fix` and returns its text without modifying the file

#### Scenario: compact=False returns raw text
- **WHEN** `cm.input(compact=False)` is called
- **THEN** the raw command text is returned without LLM compaction

### Requirement: ot_caveman pack config inherits from llm block

The `ot_caveman` pack SHALL read `tools.ot_caveman.model` and `tools.ot_caveman.base_url` from `onetool.yaml`. If those are empty, it SHALL fall back to `llm.model` and `llm.base_url` respectively. `tools.ot_caveman.timeout` (default 30s) and `tools.ot_caveman.max_tokens` (default 8192) are pack-specific with no global fallback.

#### Scenario: Empty model falls back to llm.model
- **WHEN** `tools.ot_caveman.model` is empty and `llm.model` is set
- **THEN** the pack uses the value from `llm.model`

#### Scenario: Empty base_url falls back to llm.base_url
- **WHEN** `tools.ot_caveman.base_url` is empty and `llm.base_url` is set
- **THEN** the pack uses the value from `llm.base_url`

### Requirement: ot_caveman pack declares required dependencies

The `ot_caveman` pack SHALL declare `openai` and `tiktoken` in `__ot_requires__["lib"]` and `OPENAI_API_KEY` in `__ot_requires__["secrets"]`, so the registry can surface missing deps before the first call.

#### Scenario: Dependency metadata exposed
- **WHEN** tool metadata for `ot_caveman` is discovered
- **THEN** it SHALL include library requirements for `openai` and `tiktoken`
- **AND** it SHALL include the `OPENAI_API_KEY` secret requirement

### Requirement: ot_caveman pack is registered with short alias cm

The `ot_caveman` pack SHALL declare the metadata alias `cm` so that `cm.compact(...)`, `cm.expand(...)`, and `cm.input(...)` all work.

#### Scenario: Short alias resolves to ot_caveman pack
- **WHEN** `cm.compact(text="hello")` is called in the onetool executor
- **THEN** it resolves to `ot_caveman.compact` and executes normally
