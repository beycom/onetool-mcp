from __future__ import annotations

import pytest

from otdev.docsgen.registry_check import parse_table, validate_registry_text

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_parse_table_reads_display_name_counts() -> None:
    text = "\n".join(
        [
            "| Pack | Extra | Description | Tools | License | Functions |",
            "|---|---|---|---|---|---|",
            "| [**OT Core**](ot_core.md) | `core` | Core tools. | 2 | MIT | `tools`, `config` |",
            "| [**Brave**](brave.md) | `[util]` | Search. | 1 | MIT | `search` |",
        ]
    )

    assert parse_table(text) == {"OT Core": 2, "Brave": 1}


def test_validate_registry_text_reports_header_and_row_mismatches() -> None:
    text = "\n".join(
        [
            "**1 Packs. 99 Tools.**",
            "",
            "| Pack | Extra | Description | Tools | License | Functions |",
            "|---|---|---|---|---|---|",
            "| [**OT Core**](ot_core.md) | `core` | Core tools. | 3 | MIT | `tools`, `config` |",
            "| [**OT Secrets**](secrets.md) | `core` | Secrets. | 1 | MIT | `get` |",
        ]
    )

    failures = validate_registry_text(text, {"ot": 2, "ot_secrets": 1})

    assert "Header tool count mismatch: docs=99 runtime=3" in failures
    assert "Count mismatch for OT Core: docs=3 runtime=2" in failures
    assert "OT Secrets row must link to secrets.md" in failures
    assert "Missing table row for 'Brave'" in failures

