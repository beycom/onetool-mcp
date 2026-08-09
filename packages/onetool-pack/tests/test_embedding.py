"""Tests for otpack.embedding — serialization, fusion, and EmbeddingClient."""

from __future__ import annotations

import struct
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from otpack.embedding import (
    EmbeddingClient,
    chunk_text_by_tokens,
    cosine_similarity_blobs,
    deserialize_embedding,
    dimensions_param,
    rrf_merge,
    serialize_embedding,
)


def _make_client(**kwargs: Any) -> EmbeddingClient:
    defaults: dict[str, Any] = {
        "api_key": "sk-test",
        "model": "text-embedding-3-small",
        "log_prefix": "test",
    }
    defaults.update(kwargs)
    return EmbeddingClient(**defaults)


def _mock_response(vectors: list[list[float]]) -> MagicMock:
    resp = MagicMock()
    resp.data = [
        MagicMock(embedding=vec, index=i) for i, vec in enumerate(vectors)
    ]
    return resp


def _install_openai(client: EmbeddingClient) -> MagicMock:
    """Install a mock OpenAI client on the EmbeddingClient; return its create mock."""
    mock_openai = MagicMock()
    client._client = mock_openai
    return mock_openai.embeddings.create


@pytest.mark.unit
@pytest.mark.pkg
class TestSerialization:
    def test_round_trip(self) -> None:
        vec = [1.0, -2.5, 0.0, 3.25]
        assert deserialize_embedding(serialize_embedding(vec)) == vec

    def test_explicit_little_endian_bytes(self) -> None:
        assert serialize_embedding([1.0]) == struct.pack("<1f", 1.0)

    def test_none_passthrough(self) -> None:
        assert serialize_embedding(None) is None
        assert deserialize_embedding(None) is None

    def test_truncated_blob_raises(self) -> None:
        with pytest.raises(ValueError, match="multiple of 4"):
            deserialize_embedding(b"\x00\x00\x00")


@pytest.mark.unit
@pytest.mark.pkg
class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        blob = serialize_embedding([1.0, 2.0, 3.0])
        assert cosine_similarity_blobs(blob, blob) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        a = serialize_embedding([1.0, 0.0])
        b = serialize_embedding([0.0, 1.0])
        assert cosine_similarity_blobs(a, b) == pytest.approx(0.0)

    def test_none_passthrough(self) -> None:
        blob = serialize_embedding([1.0])
        assert cosine_similarity_blobs(None, blob) is None
        assert cosine_similarity_blobs(blob, None) is None

    def test_dimension_mismatch_raises(self) -> None:
        a = serialize_embedding([1.0, 2.0])
        b = serialize_embedding([1.0])
        with pytest.raises(ValueError, match="dimension mismatch"):
            cosine_similarity_blobs(a, b)

    def test_zero_norm_returns_zero(self) -> None:
        a = serialize_embedding([0.0, 0.0])
        b = serialize_embedding([1.0, 1.0])
        assert cosine_similarity_blobs(a, b) == 0.0


@pytest.mark.unit
@pytest.mark.pkg
class TestChunking:
    def test_short_text_returned_whole(self) -> None:
        assert chunk_text_by_tokens("hello world", 100, "text-embedding-3-small") == [
            "hello world"
        ]

    def test_over_limit_splits_losslessly(self) -> None:
        text = "word " * 50
        chunks = chunk_text_by_tokens(text, 10, "text-embedding-3-small")
        assert len(chunks) > 1
        assert "".join(chunks) == text


@pytest.mark.unit
@pytest.mark.pkg
class TestDimensionsParam:
    def test_native_dimension_returns_none(self) -> None:
        assert dimensions_param("text-embedding-3-small", 1536) is None

    def test_non_native_returns_value(self) -> None:
        assert dimensions_param("text-embedding-3-small", 256) == 256

    def test_unknown_model_returns_none(self) -> None:
        assert dimensions_param("custom-model", 1024) is None

    def test_none_configured_returns_none(self) -> None:
        assert dimensions_param("text-embedding-3-small", None) is None


@pytest.mark.unit
@pytest.mark.pkg
class TestRrfMerge:
    def test_id_in_both_lists_outranks(self) -> None:
        a = [{"id": "x"}, {"id": "y"}]
        b = [{"id": "z"}, {"id": "x"}]
        merged = rrf_merge(a, b, 3)
        assert merged[0]["id"] == "x"

    def test_boost_applied(self) -> None:
        a = [{"id": "x", "hits": 0}, {"id": "y", "hits": 10}]
        merged = rrf_merge(a, [], 2, boost=lambda r: 0.1 * r["hits"] / 10)
        assert merged[0]["id"] == "y"

    def test_limit_respected(self) -> None:
        a = [{"id": str(i)} for i in range(10)]
        assert len(rrf_merge(a, [], 3)) == 3

    def test_score_written_and_rounded(self) -> None:
        merged = rrf_merge([{"id": "x"}], [], 1)
        assert merged[0]["score"] == round(1.0 / 61, 4)


@pytest.mark.unit
@pytest.mark.pkg
class TestEmbeddingClientCache:
    def test_cache_hit_skips_api(self) -> None:
        client = _make_client()
        create = _install_openai(client)
        create.return_value = _mock_response([[0.1, 0.2]])

        v1 = client.embed("hello", use_cache=True)
        v2 = client.embed("hello", use_cache=True)

        assert v1 == v2 == [0.1, 0.2]
        assert create.call_count == 1

    def test_no_cache_by_default(self) -> None:
        client = _make_client()
        create = _install_openai(client)
        create.return_value = _mock_response([[0.1]])

        client.embed("hello")
        client.embed("hello")
        assert create.call_count == 2

    def test_eviction_at_cap(self) -> None:
        client = _make_client(cache_max=2)
        create = _install_openai(client)
        create.return_value = _mock_response([[0.1]])

        for text in ("a", "b", "c"):
            client.embed(text, use_cache=True)
        assert len(client._cache) == 2

        # "a" was evicted — embedding it again calls the API
        calls_before = create.call_count
        client.embed("a", use_cache=True)
        assert create.call_count == calls_before + 1

    def test_distinct_key_on_model_and_dimensions(self) -> None:
        c1 = _make_client()
        c2 = _make_client(model="text-embedding-3-large")
        c3 = _make_client(dimensions=256)
        keys = {c._cache_key("same text") for c in (c1, c2, c3)}
        assert len(keys) == 3

    def test_close_releases_http_client_and_cache(self) -> None:
        client = _make_client()
        http_client = MagicMock()
        client._client = http_client
        client._cache_put(client._cache_key("query"), [0.1])

        client.close()

        http_client.close.assert_called_once_with()
        assert client._client is None
        assert not client._cache


@pytest.mark.unit
@pytest.mark.pkg
class TestEmbeddingClientRetry:
    def _http_error(self, status: int) -> Exception:
        e = RuntimeError(f"HTTP {status}")
        e.status_code = status  # type: ignore[attr-defined]
        return e

    def test_429_then_success(self) -> None:
        client = _make_client()
        create = _install_openai(client)
        create.side_effect = [self._http_error(429), _mock_response([[0.5]])]

        with patch("otpack.embedding.time.sleep"):
            result = client.embed("hello")
        assert result == [0.5]
        assert create.call_count == 2

    def test_400_not_retried(self) -> None:
        client = _make_client()
        create = _install_openai(client)
        create.side_effect = self._http_error(400)

        with pytest.raises(RuntimeError, match="HTTP 400"):
            client.embed("hello")
        assert create.call_count == 1

    def test_count_mismatch_raises_value_error(self) -> None:
        client = _make_client()
        create = _install_openai(client)
        create.return_value = _mock_response([[0.1]])  # 1 vector for 2 inputs

        with pytest.raises(ValueError, match="Expected 2 embeddings"):
            client.embed_batch(["a", "b"])


@pytest.mark.unit
@pytest.mark.pkg
class TestEmbedStrategies:
    def test_truncate_sends_single_input(self) -> None:
        client = _make_client(max_tokens=110)  # effective limit 10
        create = _install_openai(client)
        create.return_value = _mock_response([[0.1, 0.2]])

        long_text = "word " * 100
        result = client.embed(long_text, long_text="truncate")

        assert result == [0.1, 0.2]
        sent = create.call_args.kwargs["input"]
        assert len(sent) == 1

    def test_mean_sends_all_windows_and_averages(self) -> None:
        client = _make_client(max_tokens=110)  # effective limit 10
        create = _install_openai(client)

        long_text = "word " * 25  # ~25 tokens → 3 windows of 10
        def _respond(**kwargs: Any) -> MagicMock:
            n = len(kwargs["input"])
            return _mock_response([[float(i), 1.0] for i in range(n)])

        create.side_effect = _respond
        result = client.embed(long_text, long_text="mean")

        sent = create.call_args.kwargs["input"]
        assert len(sent) > 1
        n = len(sent)
        expected_first = sum(range(n)) / n
        assert result == [pytest.approx(expected_first), pytest.approx(1.0)]

    def test_batch_truncates_each_text(self) -> None:
        client = _make_client(max_tokens=110)
        create = _install_openai(client)
        create.return_value = _mock_response([[0.1], [0.2]])

        result = client.embed_batch(["word " * 100, "short"])
        assert len(result) == 2
        sent = create.call_args.kwargs["input"]
        assert len(sent) == 2

    def test_dimensions_forwarded_only_when_non_native(self) -> None:
        native = _make_client(dimensions=1536)
        create = _install_openai(native)
        create.return_value = _mock_response([[0.1]])
        native.embed("x")
        assert "dimensions" not in create.call_args.kwargs

        custom = _make_client(dimensions=256)
        create2 = _install_openai(custom)
        create2.return_value = _mock_response([[0.1]])
        custom.embed("x")
        assert create2.call_args.kwargs["dimensions"] == 256


@pytest.mark.unit
@pytest.mark.pkg
class TestMissingDependency:
    def test_missing_openai_hint(self) -> None:
        client = _make_client()
        with (
            patch.dict("sys.modules", {"openai": None}),
            pytest.raises(ImportError, match=r"onetool-pack\[embedding\]"),
        ):
            client._get_client()

    def test_missing_tiktoken_hint(self) -> None:
        from otpack.embedding import get_tiktoken_encoding

        with (
            patch.dict("sys.modules", {"tiktoken": None}),
            pytest.raises(ImportError, match=r"onetool-pack\[embedding\]"),
        ):
            get_tiktoken_encoding("text-embedding-3-small")
