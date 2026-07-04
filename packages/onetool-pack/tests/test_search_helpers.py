"""Tests for the hoisted search-pack helpers + frontmatter parser (p22 M1/M2)."""

from __future__ import annotations

import pytest

from otpack import (
    create_json_http_client,
    extract_structured_data,
    format_sources,
    parse_frontmatter,
    validate_batch_retry_controls,
)


@pytest.mark.unit
@pytest.mark.pkg
class TestValidateBatchRetryControls:
    def test_valid_range(self):
        assert validate_batch_retry_controls(0, 0) is None
        assert validate_batch_retry_controls(3, 10_000) is None

    def test_retries_out_of_range(self):
        assert "retries must be between 0 and 3" in validate_batch_retry_controls(4, 0)
        assert "retries must be between 0 and 3" in validate_batch_retry_controls(-1, 0)

    def test_delay_out_of_range(self):
        assert "retry_delay_ms" in validate_batch_retry_controls(1, 10_001)

    def test_bool_rejected(self):
        assert validate_batch_retry_controls(True, 0) is not None


@pytest.mark.unit
@pytest.mark.pkg
class TestFormatSources:
    def test_dedup_and_numbering(self):
        out = format_sources(
            [
                {"title": "A", "url": "u1"},
                {"title": "B", "url": "u2"},
                {"title": "A dup", "url": "u1"},
            ]
        )
        assert "1. [A](u1)" in out
        assert "2. [B](u2)" in out
        assert "3." not in out

    def test_max_sources(self):
        out = format_sources(
            [{"title": "A", "url": "u1"}, {"title": "B", "url": "u2"}], max_sources=1
        )
        assert "u2" not in out

    def test_missing_url_skipped_and_title_fallback(self):
        out = format_sources([{"title": "", "url": ""}, {"url": "u1"}])
        assert "1. [u1](u1)" in out


@pytest.mark.unit
@pytest.mark.pkg
class TestCreateJsonHttpClient:
    def test_base_url_and_headers(self):
        client = create_json_http_client(
            "https://api.example.com", timeout=12.0, headers={"X-Test": "1"}
        )
        assert str(client.base_url) == "https://api.example.com"
        assert client.headers["X-Test"] == "1"
        assert client.headers["Accept"] == "application/json"
        client.close()


@pytest.mark.unit
@pytest.mark.pkg
class TestExtractStructuredData:
    def _schema(self, **f):
        return {"fields": [f]}

    def test_boolean_and_number(self):
        r = extract_structured_data(
            text="active: true count 42",
            sources=[],
            extract_schema={
                "fields": [
                    {"name": "active", "type": "boolean"},
                    {"name": "count", "type": "number"},
                ]
            },
            return_provenance=False,
        )
        assert r["data"]["active"] is True
        assert r["data"]["count"] == 42

    def test_required_missing_error(self):
        r = extract_structured_data(
            text="nothing here",
            sources=[],
            extract_schema=self._schema(name="missing", type="number", required=True),
            return_provenance=False,
        )
        assert r["errors"]
        assert r["errors"][0]["error_code"] == "required_field_missing"

    def test_provenance_with_and_without_confidence_key(self):
        sources = [{"url": "u1", "score": 0.9}]
        with_conf = extract_structured_data(
            text="x: y",
            sources=sources,
            extract_schema=self._schema(name="x", type="string"),
            return_provenance=True,
            confidence_key="score",
        )
        assert with_conf["provenance"]["x"]["confidence"] == 0.9
        assert with_conf["provenance"]["x"]["source_url"] == "u1"

        no_conf = extract_structured_data(
            text="x: y",
            sources=sources,
            extract_schema=self._schema(name="x", type="string"),
            return_provenance=True,
        )
        assert no_conf["provenance"]["x"]["confidence"] is None


@pytest.mark.unit
@pytest.mark.pkg
class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        meta, body = parse_frontmatter("---\ntitle: T\ntags: [a, b]\n---\nbody here\n")
        assert meta == {"title": "T", "tags": ["a", "b"]}
        assert body == "body here\n"

    def test_no_frontmatter(self):
        meta, body = parse_frontmatter("just content\n")
        assert meta == {}
        assert body == "just content\n"

    def test_malformed_yaml_does_not_raise(self):
        meta, body = parse_frontmatter("---\n: : broken: [\n---\nbody\n")
        assert meta == {}
        assert body == "body\n"
