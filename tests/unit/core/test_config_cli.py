"""Unit tests for direct config schema (DirectConfig)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.unit
@pytest.mark.core
class TestDirectConfig:
    def test_defaults_without_direct_section(self) -> None:
        from ot.config.models import OneToolConfig

        cfg = OneToolConfig()
        assert cfg.direct.host.enabled is False
        assert cfg.direct.host.port == 8765

    def test_defaults_load_from_yaml_without_direct(self, write_config: Callable) -> None:
        from ot.config.loader import load_config

        p = write_config({"version": 2})
        cfg = load_config(p)

        assert cfg.direct.host.enabled is False
        assert cfg.direct.host.port == 8765

    def test_direct_section_overrides_host_port(self, write_config: Callable) -> None:
        from ot.config.loader import load_config

        p = write_config({"version": 2, "direct": {"host": {"port": 9000}}})
        cfg = load_config(p)

        assert cfg.direct.host.port == 9000
        assert cfg.direct.host.enabled is False

    def test_direct_section_host_enabled(self, write_config: Callable) -> None:
        from ot.config.loader import load_config

        p = write_config({"version": 2, "direct": {"host": {"enabled": True}}})
        cfg = load_config(p)

        assert cfg.direct.host.enabled is True
        assert cfg.direct.host.port == 8765

    def test_direct_api_port_must_be_valid(self) -> None:
        from pydantic import ValidationError

        from ot.config.models import DirectConfig

        with pytest.raises(ValidationError):
            DirectConfig(host={"port": 70000})

    def test_direct_api_enabled_must_be_bool(self) -> None:
        from pydantic import ValidationError

        from ot.config.models import DirectConfig

        with pytest.raises(ValidationError):
            DirectConfig(host={"enabled": "yes"})

    def test_direct_accepts_expected_shape(self) -> None:
        from ot.config.models import DirectConfig

        cfg = DirectConfig(host={"enabled": True, "port": 9001})
        assert cfg.host.enabled is True
        assert cfg.host.port == 9001

    def test_load_config_ignores_direct_host_timeout_with_warning(
        self, write_config: Callable
    ) -> None:
        from ot.config.loader import load_config

        p = write_config(
            {
                "version": 2,
                "direct": {"host": {"enabled": True, "port": 9001, "timeout": 240}},
            }
        )

        with pytest.warns(UserWarning, match="direct.host.timeout"):
            cfg = load_config(p)

        assert cfg.direct.host.enabled is True
        assert cfg.direct.host.port == 9001
        assert not hasattr(cfg.direct.host, "timeout")

    def test_direct_api_rejects_unknown_fields(self) -> None:
        from pydantic import ValidationError

        from ot.config.models import DirectConfig

        with pytest.raises(ValidationError):
            DirectConfig(host={"mode": "api"})
