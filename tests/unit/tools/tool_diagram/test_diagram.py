"""Unit tests for diagram tool."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

import pytest
import yaml

# Diagram tool imports
from ot_tools.diagram import (
    FOCUS_PROVIDERS,
    KROKI_PROVIDERS,
    _basic_source_validation,
    _decode_source,
    _get_d2_playground_url,
    _get_mermaid_playground_url,
    _get_plantuml_playground_url,
    _get_source_extension,
    _validate_format,
    _validate_provider,
    encode_source,
)

# ==================== Encoding Tests ====================


@pytest.mark.unit
@pytest.mark.tools
def test_encode_source_basic() -> None:
    """encode_source produces valid deflate + base64url encoding."""
    source = "graph TD\n    A-->B"
    encoded = encode_source(source)

    # Verify it's base64url (no + or /)
    assert "+" not in encoded
    assert "/" not in encoded

    # Verify roundtrip
    decoded = _decode_source(encoded)
    assert decoded == source


@pytest.mark.unit
@pytest.mark.tools
def test_encode_source_unicode() -> None:
    """encode_source handles unicode characters."""
    source = 'graph TD\n    A["Start → End"]-->B["éàü"]'
    encoded = encode_source(source)

    decoded = _decode_source(encoded)
    assert decoded == source


@pytest.mark.unit
@pytest.mark.tools
def test_encode_source_empty() -> None:
    """encode_source handles empty string."""
    encoded = encode_source("")
    decoded = _decode_source(encoded)
    assert decoded == ""


@pytest.mark.unit
@pytest.mark.tools
def test_encode_source_large() -> None:
    """encode_source handles large diagrams."""
    # Generate a large source
    lines = ["graph TD"] + [f"    N{i}-->N{i + 1}" for i in range(500)]
    source = "\n".join(lines)

    encoded = encode_source(source)
    decoded = _decode_source(encoded)
    assert decoded == source


# ==================== Playground URL Tests ====================


@pytest.mark.unit
@pytest.mark.tools
def test_mermaid_playground_url() -> None:
    """Mermaid playground URL has correct format."""
    source = "graph TD\n    A-->B"
    url = _get_mermaid_playground_url(source)

    assert url.startswith("https://mermaid.live/edit#pako:")
    assert len(url) > 30  # Should have encoded content


@pytest.mark.unit
@pytest.mark.tools
def test_plantuml_playground_url() -> None:
    """PlantUML playground URL has correct format."""
    source = "@startuml\nAlice -> Bob: Hello\n@enduml"
    url = _get_plantuml_playground_url(source)

    assert url.startswith("https://www.plantuml.com/plantuml/uml/")
    assert len(url) > 40  # Should have encoded content


@pytest.mark.unit
@pytest.mark.tools
def test_d2_playground_url() -> None:
    """D2 playground URL has correct format."""
    source = "a -> b: hello"
    url = _get_d2_playground_url(source)

    assert url.startswith("https://play.d2lang.com/?script=")

    # Extract and verify base64url encoding
    encoded_part = url.split("?script=")[1]
    decoded = base64.urlsafe_b64decode(encoded_part).decode("utf-8")
    assert decoded == source


# ==================== Provider Validation Tests ====================


@pytest.mark.unit
@pytest.mark.tools
def test_validate_provider_valid() -> None:
    """Valid providers pass validation."""
    # Should not raise
    _validate_provider("mermaid")
    _validate_provider("plantuml")
    _validate_provider("d2")
    _validate_provider("graphviz")


@pytest.mark.unit
@pytest.mark.tools
def test_validate_provider_invalid() -> None:
    """Invalid providers raise ValueError."""
    with pytest.raises(ValueError, match="Unknown provider"):
        _validate_provider("invalid_provider")


@pytest.mark.unit
@pytest.mark.tools
def test_validate_format_valid() -> None:
    """Valid formats pass validation."""
    # Should not raise
    _validate_format("svg")
    _validate_format("png")
    _validate_format("pdf")


@pytest.mark.unit
@pytest.mark.tools
def test_validate_format_invalid() -> None:
    """Invalid formats raise ValueError."""
    with pytest.raises(ValueError, match="Unknown format"):
        _validate_format("gif")


# ==================== Source Validation Tests ====================


@pytest.mark.unit
@pytest.mark.tools
def test_basic_source_validation_mermaid_quotes() -> None:
    """Mermaid sequence diagram quoting warning."""
    # Wrong: quotes after 'as'
    source = 'sequenceDiagram\n    participant WS as "Web Server"'
    warnings = _basic_source_validation(source, "mermaid")
    assert len(warnings) == 1
    assert "quotes" in warnings[0].lower()


@pytest.mark.unit
@pytest.mark.tools
def test_basic_source_validation_mermaid_valid() -> None:
    """Valid Mermaid sequence diagram has no warnings."""
    source = "sequenceDiagram\n    participant WS as Web Server"
    warnings = _basic_source_validation(source, "mermaid")
    assert len(warnings) == 0


@pytest.mark.unit
@pytest.mark.tools
def test_basic_source_validation_plantuml_missing_start() -> None:
    """PlantUML without @start marker gets warning."""
    source = "Alice -> Bob: Hello"  # Missing @startuml
    warnings = _basic_source_validation(source, "plantuml")
    assert len(warnings) == 1
    assert "@start" in warnings[0]


@pytest.mark.unit
@pytest.mark.tools
def test_basic_source_validation_plantuml_valid() -> None:
    """Valid PlantUML has no warnings."""
    source = "@startuml\nAlice -> Bob: Hello\n@enduml"
    warnings = _basic_source_validation(source, "plantuml")
    assert len(warnings) == 0


@pytest.mark.unit
@pytest.mark.tools
def test_basic_source_validation_d2_with_at_marker() -> None:
    """D2 with @ markers (PlantUML syntax) gets warning."""
    source = "@startuml\na -> b"  # D2 doesn't use @
    warnings = _basic_source_validation(source, "d2")
    assert len(warnings) == 1
    assert "PlantUML" in warnings[0]


# ==================== DiagramConfig Tests ====================


@pytest.mark.unit
@pytest.mark.tools
def test_diagram_config_defaults() -> None:
    """DiagramConfig has correct defaults (now in diagram.py)."""
    from ot_tools.diagram import Config

    config = Config()

    # Backend defaults
    assert config.backend.type == "kroki"
    assert config.backend.prefer == "remote"
    assert config.backend.remote_url == "https://kroki.io"
    assert config.backend.self_hosted_url == "http://localhost:8000"
    assert config.backend.timeout == 30.0

    # Policy defaults
    assert "ASCII" in config.policy.rules
    assert config.policy.preferred_format == "svg"
    assert config.policy.preferred_providers == ["mermaid", "d2", "plantuml"]

    # Output defaults
    assert config.output.dir == "diagrams"
    assert config.output.default_format == "svg"
    assert config.output.save_source is True


@pytest.mark.unit
@pytest.mark.tools
def test_diagram_config_partial_override() -> None:
    """DiagramConfig partial override - config stored as dict at load time."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "tools": {
                        "diagram": {
                            "backend": {"prefer": "self_hosted"},
                            "output": {"dir": "./custom"},
                        }
                    },
                }
            )
        )

        config = load_config(config_path)

        # Tool configs are now stored as dicts in model_extra
        diagram_raw = config.tools.model_extra.get("diagram", {})
        assert diagram_raw.get("backend", {}).get("prefer") == "self_hosted"
        assert diagram_raw.get("output", {}).get("dir") == "./custom"


@pytest.mark.unit
@pytest.mark.tools
def test_diagram_config_instructions() -> None:
    """DiagramConfig can have provider instructions (stored as dict)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "tools": {
                        "diagram": {
                            "instructions": {
                                "mermaid": {
                                    "when_to_use": "For flowcharts",
                                    "style_tips": "Use subgraphs",
                                    "syntax_guide": "https://mermaid.js.org",
                                }
                            }
                        }
                    },
                }
            )
        )

        config = load_config(config_path)

        # Tool configs are now dicts - validation happens at runtime via get_tool_config
        diagram_raw = config.tools.model_extra.get("diagram", {})
        assert "mermaid" in diagram_raw.get("instructions", {})
        mermaid = diagram_raw["instructions"]["mermaid"]
        assert mermaid["when_to_use"] == "For flowcharts"
        assert mermaid["style_tips"] == "Use subgraphs"


@pytest.mark.unit
@pytest.mark.tools
def test_diagram_config_templates() -> None:
    """DiagramConfig can have template references (stored as dict)."""
    from ot.config.loader import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test-config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "tools": {
                        "diagram": {
                            "templates": {
                                "api-flow": {
                                    "provider": "mermaid",
                                    "diagram_type": "sequence",
                                    "description": "API flow template",
                                    "file": "templates/api-flow.mmd",
                                }
                            }
                        }
                    },
                }
            )
        )

        config = load_config(config_path)

        # Tool configs are now dicts - validation happens at runtime via get_tool_config
        diagram_raw = config.tools.model_extra.get("diagram", {})
        assert "api-flow" in diagram_raw.get("templates", {})
        tmpl = diagram_raw["templates"]["api-flow"]
        assert tmpl["provider"] == "mermaid"
        assert tmpl["diagram_type"] == "sequence"
        assert tmpl["file"] == "templates/api-flow.mmd"


# ==================== File Extension Tests ====================


@pytest.mark.unit
@pytest.mark.tools
def test_get_source_extension() -> None:
    """Source extensions are correct for providers."""
    assert _get_source_extension("mermaid") == ".mmd"
    assert _get_source_extension("plantuml") == ".puml"
    assert _get_source_extension("d2") == ".d2"
    assert _get_source_extension("graphviz") == ".dot"
    # Unknown provider uses provider name
    assert _get_source_extension("unknown") == ".unknown"


# ==================== Provider List Tests ====================


@pytest.mark.unit
@pytest.mark.tools
def test_kroki_providers_constant() -> None:
    """KROKI_PROVIDERS contains expected providers."""
    # Focus providers should be in full list
    for provider in FOCUS_PROVIDERS:
        assert provider in KROKI_PROVIDERS

    # Should have 28+ providers
    assert len(KROKI_PROVIDERS) >= 28

    # Check some common ones
    assert "mermaid" in KROKI_PROVIDERS
    assert "plantuml" in KROKI_PROVIDERS
    assert "d2" in KROKI_PROVIDERS
    assert "graphviz" in KROKI_PROVIDERS
    assert "ditaa" in KROKI_PROVIDERS


@pytest.mark.unit
@pytest.mark.tools
def test_focus_providers() -> None:
    """FOCUS_PROVIDERS has the expected providers."""
    assert FOCUS_PROVIDERS == ["mermaid", "plantuml", "d2"]


# ==================== Output Config Tests ====================


@pytest.mark.unit
@pytest.mark.tools
def test_get_output_config_format() -> None:
    """get_output_config returns properly formatted output without corruption."""
    from ot_tools.diagram import get_output_config

    result = get_output_config()

    # Should have header exactly once
    assert result.count("Diagram Output Configuration") == 1

    # Should have separator line
    assert "=" * 40 in result

    # Should contain expected fields
    assert "Output directory:" in result
    assert "Naming pattern:" in result
    assert "Default format:" in result
    assert "Save source:" in result


# ==================== Cache TTL Tests ====================


@pytest.mark.unit
@pytest.mark.tools
def test_cache_ttl_constants() -> None:
    """Cache TTL constants are defined correctly."""
    from ot_tools.diagram import _CACHE_TTL_SECONDS, _cached_backend

    # TTL should be 5 minutes (300 seconds)
    assert _CACHE_TTL_SECONDS == 300

    # Cached backend should have timestamp field
    assert "timestamp" in _cached_backend


# ==================== Thread Safety Tests ====================


@pytest.mark.unit
@pytest.mark.tools
def test_render_tasks_lock_exists() -> None:
    """Thread safety lock exists for render tasks."""
    from ot_tools.diagram import _render_tasks_lock

    import threading

    assert isinstance(_render_tasks_lock, type(threading.Lock()))
