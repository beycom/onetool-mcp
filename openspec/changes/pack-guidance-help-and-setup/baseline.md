# Implementation Baseline

Captured on 2026-07-26 before implementation changes.

## Runtime inventory

The all-packs test configuration loaded 28 packs and 269 tools:

```text
arch=5, brave=5, chrome_util=5, console=5, context7=2, convert=5, db=4,
diagram=11, excel=24, file=16, ground=5, knowledge=15, localhist=15, mem=31,
ot=18, ot_context=13, ot_forge=2, ot_image=9, ot_llm=2, ot_secrets=8,
ot_servers=4, ot_timer=5, package=5, play_util=6, ripgrep=4, tavily=5,
webfetch=2, whiteboard=22
```

Command:

```bash
uv run python -c 'import json; from otdev.docsgen.registry_check import runtime_tool_counts; print(json.dumps(runtime_tool_counts(), sort_keys=True))'
```

## Read-only catalog and generated-doc checks

```text
skills check passed
docs registry check passed
```

Commands:

```bash
uv run python scripts/check_skills.py
uv run python scripts/check_docs_registry.py
```

These checks do not synchronize or rewrite generated targets.

## Focused help and proxy tests

```text
94 passed in 2.71s
```

Command:

```bash
uv run pytest tests/unit/core/test_meta_help.py tests/unit/core/test_proxy_manager.py -q
```

The baseline covers current deterministic help behavior and the existing internal proxy
resource/prompt manager operations before the new public core operations are added.
