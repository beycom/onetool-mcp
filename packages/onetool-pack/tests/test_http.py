"""Tests for otpack.http missing-secret error guidance (p14)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from otpack.http import api_headers, check_api_key, require_api_key


@pytest.mark.unit
@pytest.mark.pkg
class TestMissingSecretGuidance:
    """The missing-key error names the secret AND a concrete setup path."""

    def _assert_guidance(self, message: str) -> None:
        assert "BRAVE_API_KEY" in message
        assert any(
            hint in message
            for hint in ("secrets.yaml", "ot_secrets.set", "onetool init")
        )

    def test_api_headers_guidance(self) -> None:
        with patch("otpack.http.get_secret", return_value=None):
            with pytest.raises(ValueError) as exc:
                api_headers("BRAVE_API_KEY")
        self._assert_guidance(str(exc.value))

    def test_require_api_key_guidance(self) -> None:
        with patch("otpack.http.get_secret", return_value=None):
            _key, err = require_api_key("BRAVE_API_KEY")
        assert err is not None
        self._assert_guidance(err)

    def test_check_api_key_guidance(self) -> None:
        with patch("otpack.http.get_secret", return_value=None):
            err = check_api_key("BRAVE_API_KEY")
        assert err is not None
        self._assert_guidance(err)
