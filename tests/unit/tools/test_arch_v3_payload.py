from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from otdev.tools._arch.v3.payload import build_payload
from otdev.tools._arch.v3.report import PAYLOAD_TOKEN, generate_report
from otdev.tools._arch.v3.yamlio import load_architecture

pytestmark = [pytest.mark.unit, pytest.mark.tools]

FIXTURE = Path(__file__).parent / "fixtures" / "arch" / "acme.yaml"
KINDS = (
    "systems",
    "subsystems",
    "containers",
    "components",
    "code",
    "users",
    "interfaces",
    "relationships",
)


def _points(
    segment: list[int | None] | dict[str, int | str | None], end: int
) -> set[int]:
    if isinstance(segment, list):
        start, stop = segment
    else:
        start, stop = segment["start"], segment["end"]
    assert isinstance(start, int)
    assert stop is None or isinstance(stop, int)
    return set(range(start, end + 1 if stop is None else stop + 1))


def test_acme_payload_invariants() -> None:
    architecture = load_architecture(FIXTURE)
    payload = build_payload(architecture, FIXTURE.name)
    assert list(payload) == [
        "payload",
        "schema_version",
        "source",
        "milestones",
        "timelines",
        "theme",
        "layout",
        "rows",
    ]
    assert payload["theme"] == {}
    assert payload["layout"] == {}
    assert list(payload["rows"]) == list(KINDS)
    assert payload == build_payload(architecture, FIXTURE.name)
    known_ids = {row.id for kind in KINDS for row in getattr(architecture, kind)}
    clip_count = 0

    for timeline_index, timeline in enumerate(payload["timelines"]):
        domain_end = len(timeline["milestones"])
        by_group: dict[tuple[str, str], set[int]] = {}
        for kind in KINDS:
            for row in payload["rows"][kind]:
                interval = row["intervals"][timeline_index]
                occupied: set[int] = set()
                starts: list[int] = []
                for segment in interval["live"]:
                    points = _points(segment, domain_end)
                    assert points <= set(range(domain_end + 1))
                    assert occupied.isdisjoint(points)
                    occupied |= points
                    starts.append(segment[0])
                for segment in interval["clips"]:
                    points = _points(segment, domain_end)
                    assert points <= set(range(domain_end + 1))
                    assert occupied.isdisjoint(points)
                    occupied |= points
                    starts.append(segment["start"])
                    assert segment["by"] in known_ids
                    clip_count += 1
                assert starts == sorted(starts)
                group = by_group.setdefault((kind, row["id"]), set())
                assert group.isdisjoint(occupied)
                group |= occupied
    assert clip_count > 0


def test_generate_report_is_parseable_and_idempotent(tmp_path: Path) -> None:
    output = tmp_path / "report.html"
    expected = build_payload(load_architecture(FIXTURE), FIXTURE.name)
    generate_report(FIXTURE, output)
    first = output.read_bytes()
    text = first.decode()
    assert PAYLOAD_TOKEN not in text
    match = re.search(
        r'<script id="arch-payload" type="application/json">(.*?)</script>',
        text,
        re.DOTALL,
    )
    assert match is not None
    assert json.loads(match.group(1)) == expected
    generate_report(FIXTURE, output)
    assert output.read_bytes() == first
