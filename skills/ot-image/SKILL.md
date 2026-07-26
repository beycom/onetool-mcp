---
name: ot-image
description: Use when OneTool should inspect or compare images through its configured vision model, reuse image handles, analyze the clipboard, batch-load images, or keep image tokens out of the host conversation. Do not override a request to use native attached-image analysis.
user-invocable: false
---

# OneTool Image

Use `ot_image` for handle-based vision and repeated questions.

## Availability

Check `__ot ot.packs(pattern='ot_image', info='min')`, then inspect status if model availability is
uncertain. If the pack, vision model, or credential is missing, stop and offer configuration
guidance; do not add credentials or change configuration without a separate request.

## Workflow

1. Load only the relevant image or bounded batch and retain returned handles.
2. Ask a focused question; request structured output only when downstream work needs it.
3. Reuse handles for follow-ups and comparisons instead of reloading.
4. Verify consequential visual claims against the source image.
5. Release images when cleanup matters.

Do not send private images to a configured remote model without authorization. Inspect the handle
list and current tool signature once before retrying a failed operation.
