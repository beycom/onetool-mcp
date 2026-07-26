---
name: ot-image
description: Use when OneTool should inspect or compare images through its configured vision model, reuse image handles, analyze the clipboard, batch-load images, or keep image tokens out of the host conversation. Do not override a request to use native attached-image analysis.
user-invocable: false
---

# OneTool Image

Use `ot_image` for handle-based vision and repeated questions.

## Capability boundary

Check `__ot ot.packs(pattern='ot_image', info='min')`, then inspect status if model availability is
uncertain. If the pack, vision model, or credential is missing, stop and offer configuration
guidance; do not add credentials or change configuration without a separate request.

Use `load`/`load_batch` to create reusable handles, `ask` for focused questions across at most
eight images, `summary` for cached structured extraction, and `clip_ask`/`clip_view` only where the
host clipboard is supported. `list`, `delete`, and `purge` own the session image lifecycle.

## Workflow

1. Inspect the source type (path, URL, data, or clipboard), privacy, size, and intended comparison.
2. Load only relevant images; keep the returned handle rather than the containing result object.
3. Ask a focused question or compare a bounded group. Use `summary` when stable structured metadata
   will be reused.
4. Reuse handles for follow-ups and verify consequential observations against source pixels.
5. Inspect `list` and clean up with targeted `delete`; use `purge` only with explicit scope.

## Safety and side effects

Loading persists image/session artifacts and vision calls may send resized images to a configured
remote model, incurring cost and privacy exposure. Clipboard access is platform-dependent. Do not
claim OCR-grade certainty or invisible detail, and do not bypass model/secret readiness.

## Verification and recovery

Confirm handles with `ot_image.list()`, compare the model answer to the displayed/source image,
and report uncertainty. If a load or model call fails, inspect setup/config help and the exact
signature once, then retry once. A cached summary must be invalidated by reloading when the source
changes.

<!-- BEGIN GENERATED:CATALOG_COVERAGE -->
## Catalog coverage

**Role:** `capability-owner`

| Pack | Extra | Help topics | Docs |
|---|---|---|---|
| `ot_image` | `core` | `overview`, `workflow`, `setup`, `config` | [reference](https://onetool.beycom.online/reference/tools/ot_image/) |

For a missing pack, dependency, secret, or config field, inspect `ot.help(query='<pack>', topic='setup')` and hand off to `ot-setup`. For outbound MCP server setup or lifecycle, hand off to `ot-mcp-proxy`.
<!-- END GENERATED:CATALOG_COVERAGE -->
