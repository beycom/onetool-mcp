---
name: ot-arch
description: Use when validating an architecture Excel or YAML model, generating OneTool architecture pages and diagrams, round-tripping Excel and YAML, applying render profiles, or bundling an architecture solution.
user-invocable: false
---

# OneTool Architecture

Use `arch` for architecture-model validation and deliverable generation.

## Availability

Check `__ot ot.packs(pattern='arch', info='min')`. If `[dev]`, Git, D2, a renderer, or an input
dependency is missing, stop and offer installation or configuration guidance; do not install or
configure anything without a separate request.

## Workflow

1. Inspect the input model and validate before generating.
2. Resolve validation errors at the model source.
3. Select filters and a reviewed render profile deliberately.
4. Generate into a clean explicit output directory.
5. Inspect diagnostics and representative pages or diagrams.
6. Bundle only after the generated solution passes verification.

Preserve unknown round-trip fields and never treat a rendered diagram as proof that the source
model is valid.
