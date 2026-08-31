from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from otdev.tools._arch.v3.api import validate_file
from otdev.tools._arch.v3.excel import read_workbook, write_workbook
from otdev.tools._arch.v3.payload import build_payload
from otdev.tools._arch.v3.report import ReportError, generate_report, payload_file
from otdev.tools._arch.v3.sequence import compile_sequence_file, compile_sequences
from otdev.tools._arch.v3.validate import validate
from otdev.tools._arch.v3.yamlio import dump_architecture, load_architecture

pytestmark = [pytest.mark.unit, pytest.mark.tools]

FIXTURE = Path(__file__).parent / "fixtures" / "arch" / "sequence"


def _finding_triples(findings: list[object]) -> list[tuple[str, str, int]]:
    return sorted(
        (item.severity, item.code, item.line)  # type: ignore[attr-defined]
        for item in findings
    )


def _model_yaml(interfaces: str = "interfaces: []") -> str:
    return f"""schema_version: 3
milestones: []
systems:
  - id: shop
    name: Shop
subsystems: []
containers:
  - id: api
    name: API
    parent: shop
components: []
code: []
users:
  - id: customer
    name: Customer
{interfaces}
relationships: []
"""


def _flow(flow_id: str, body: str, *, name: str | None = None) -> str:
    return f"""---
id: {flow_id}
name: {name or flow_id.title()}
---

```seq
{body}
```
"""


def test_parser_vectors_and_cross_document_duplicate() -> None:
    architecture = load_architecture(FIXTURE / "model.yaml")
    expected = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
    for path in sorted((FIXTURE / "flows").glob("*.md")):
        sequence, findings = compile_sequence_file(path, architecture)
        wanted = expected["flows"][path.name]
        assert _finding_triples(findings) == sorted(
            (item["severity"], item["code"], item["line"])
            for item in wanted["findings"]
        )
        assert all(item.column >= 1 for item in findings)
        assert sequence == wanted["sequence"]

    _sequences, findings = compile_sequences(architecture, FIXTURE / "crossdoc")
    assert [
        (Path(item.file).name, item.severity, item.code, item.line) for item in findings
    ] == [("second.md", "error", "duplicate_id", 2)]


def test_large_scenario_thresholds(tmp_path: Path) -> None:
    architecture = load_architecture(FIXTURE / "model.yaml")

    def codes(name: str, body: str) -> list[str]:
        path = tmp_path / name
        path.write_text(_flow(name.removesuffix(".md"), body), encoding="utf-8")
        _sequence, findings = compile_sequence_file(path, architecture)
        return [item.code for item in findings]

    declarations_30 = "\n".join(f"participant p{i} as Person {i}" for i in range(30))
    declarations_31 = declarations_30 + "\nparticipant p30 as Person 30"
    assert "large_scenario" not in codes("participants-30.md", declarations_30)
    assert "large_scenario" in codes("participants-31.md", declarations_31)

    items_300 = "\n".join("customer ->> pay-api: Ping" for _ in range(300))
    items_301 = items_300 + "\ncustomer ->> pay-api: Ping"
    assert "large_scenario" not in codes("items-300.md", items_300)
    assert "large_scenario" in codes("items-301.md", items_301)


def test_discovery_validation_and_generate_atomicity(tmp_path: Path) -> None:
    model = tmp_path / "model.yaml"
    model.write_text(_model_yaml(), encoding="utf-8")
    sequences = tmp_path / "sequences"
    sequences.mkdir()
    (sequences / "b-good.md").write_text(
        _flow("z-flow", "customer ->> api: Works\napi ->> observer: Notice"),
        encoding="utf-8",
    )
    (sequences / "a-good.md").write_text(
        _flow("a-flow", "customer ->> api: First"), encoding="utf-8"
    )
    bad = sequences / "c-bad.md"
    bad.write_text(_flow("bad-flow", "end"), encoding="utf-8")

    result = validate_file(model)
    issue_files = {
        Path(item["file"]).name
        for severity in ("errors", "warnings")
        for item in result["issues"][severity]
    }
    assert {"b-good.md", "c-bad.md"} <= issue_files
    output = tmp_path / "report.html"
    with pytest.raises(ReportError):
        generate_report(model, output)
    assert not output.exists()

    bad.unlink()
    payload = payload_file(model)
    assert [item["id"] for item in payload["sequences"]] == ["a-flow", "z-flow"]
    shutil.rmtree(sequences)
    assert "sequences" not in payload_file(model)


def test_interface_attachments_round_trip_and_locations(tmp_path: Path) -> None:
    files = tmp_path / "files"
    files.mkdir()
    (files / "request.json").write_text("{}", encoding="utf-8")
    (files / "response.json").write_text("{}", encoding="utf-8")
    interfaces = """interfaces:
  - id: request
    name: Request
    provider: api
    consumer: customer
    attachments:
      - files/request.json
      - files/response.json
  - id: blank
    name: Blank
    provider: api
    consumer: customer"""
    source = tmp_path / "model.yaml"
    source.write_text(_model_yaml(interfaces), encoding="utf-8")
    architecture = load_architecture(source)
    dumped = tmp_path / "dumped.yaml"
    dump_architecture(architecture, dumped)
    assert load_architecture(dumped) == architecture
    workbook = tmp_path / "model.xlsx"
    write_workbook(architecture, workbook)
    assert read_workbook(workbook) == architecture

    invalid = """interfaces:
  - id: missing
    name: Missing
    provider: api
    consumer: customer
    attachments: [files/missing.json]
  - id: escape
    name: Escape
    provider: api
    consumer: customer
    attachments: [../escape.json]
  - id: characters
    name: Characters
    provider: api
    consumer: customer
    attachments: [files/bad name.json]"""
    invalid_path = tmp_path / "invalid.yaml"
    invalid_path.write_text(_model_yaml(invalid), encoding="utf-8")
    findings = [
        item
        for item in validate(load_architecture(invalid_path))
        if item.code in {"invalid_path", "unresolved_file"}
    ]
    assert [item.code for item in findings] == [
        "unresolved_file",
        "invalid_path",
        "invalid_path",
    ]
    lines = invalid_path.read_text(encoding="utf-8").splitlines()
    assert [lines[item.line - 1].strip() for item in findings] == [
        "attachments: [files/missing.json]",
        "attachments: [../escape.json]",
        "attachments: [files/bad name.json]",
    ]


def test_attachment_embedding_languages_dedup_and_size(tmp_path: Path) -> None:
    files = tmp_path / "files"
    files.mkdir()
    contents = {
        "sample.json": "{}",
        "sample.xml": "<root />",
        "sample.csv": "a,b\n1,2\n",
        "sample.yaml": "key: value\n",
        "sample.txt": "plain\n",
        "exact.txt": "x" * (256 * 1024),
        "large.txt": "x" * (256 * 1024 + 1),
    }
    for name, text in contents.items():
        (files / name).write_text(text, encoding="utf-8")
    paths = [f"files/{name}" for name in contents]
    rendered_paths = ", ".join(paths)
    interfaces = f"""interfaces:
  - id: samples
    name: Samples
    provider: api
    consumer: customer
    attachments: [{rendered_paths}]"""
    model = tmp_path / "model.yaml"
    model.write_text(_model_yaml(interfaces), encoding="utf-8")
    sequences = tmp_path / "sequences"
    sequences.mkdir()
    (sequences / "sample.md").write_text(
        _flow("sample", "customer ->> api: Sample\nattach files/sample.json"),
        encoding="utf-8",
    )
    architecture = load_architecture(model)
    findings = validate(architecture)
    assert [item.code for item in findings].count("large_attachment") == 1
    payload = build_payload(architecture, model.name)
    assert list(payload["files"]) == sorted(paths)
    assert len(payload["files"]) == len(paths)
    assert {path: item["lang"] for path, item in payload["files"].items()} == {
        "files/exact.txt": "text",
        "files/large.txt": "text",
        "files/sample.csv": "csv",
        "files/sample.json": "json",
        "files/sample.txt": "text",
        "files/sample.xml": "xml",
        "files/sample.yaml": "yaml",
    }
    assert payload["files"]["files/sample.json"]["text"] == "{}"

    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()
    plain = plain_dir / "plain.yaml"
    plain.write_text(_model_yaml(), encoding="utf-8")
    assert "files" not in build_payload(load_architecture(plain), plain.name)
