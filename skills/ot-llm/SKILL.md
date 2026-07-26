---
name: ot-llm
description: Use when OneTool should offload text or structured-data transformation, extraction, summarization, translation, reformatting, JSON generation, or file-to-file conversion to its configured LLM. Prefer direct host reasoning for small tasks.
user-invocable: false
---

# OneTool LLM

Use `ot_llm` as a bounded transformation stage in a OneTool pipeline.

## Availability

Check `__ot ot.packs(pattern='ot_llm', info='min')`, then inspect status when model configuration is
uncertain. If the model or credential is missing, stop and offer configuration guidance; do not
add credentials or alter configuration without a separate request.

## Workflow

1. Define the input, transformation, and required output shape.
2. Use deterministic local processing when it is simpler and more reliable.
3. Bound file size, batch size, output length, and model cost.
4. Validate structured output before passing it downstream.
5. Verify facts independently; transformation output is not a source.

Do not send confidential material to a remote model without authorization. On failure, inspect
status and the current tool signature once, then repair or surface the missing prerequisite.
