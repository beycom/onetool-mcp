---
name: ot-research
description: Use when researching current information, comparing sources, gathering citations, investigating software documentation or package versions, extracting known URLs, or conducting web research through OneTool without a predetermined provider.
user-invocable: false
---

# OneTool Research

Select the provider by evidence need:

- `ground`: synthesized current answers with grounded citations.
- `brave`: fast web, news, image, video, freshness, or batch search.
- `tavily`: domain-filtered extraction or deliberate deep research.
- `context7`: version-specific software-library documentation.
- `package`: current package versions, releases, models, or dependency checks.
- `webfetch`: clean content after URLs are known.

## Availability

After selecting a provider, check `__ot ot.packs(pattern='<pack>', info='min')`. If `[util]`,
`[dev]`, a credential, or a service is missing, stop, name it, and offer installation or
configuration guidance; do not install, configure, or add credentials without a separate request.

Search broadly enough to find sources, fetch only useful pages, prefer primary sources, preserve
URLs, and cross-check consequential claims. Bound batches, retries, deep-research cost, and private
query disclosure. Use `ot-context` for large results and never fabricate missing citations.
