"""Offline tests for the shared-generation transform tool."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ot.generation import GenerationError
from ottools import ot_llm as llm_module
from ottools.ot_llm import Config, transform, transform_file

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def _result(content: str = "transformed") -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        latency_seconds=0.01,
        usage=SimpleNamespace(
            input_tokens=3,
            output_tokens=2,
            total_tokens=5,
        ),
    )


def test_config_accepts_typed_selection_and_rejects_removed_keys() -> None:
    config = Config.model_validate({"model": "gpt-5.6-sol", "effort": "low"})
    assert config.model == "gpt-5.6-sol"
    assert config.effort == "low"
    for key in ("base_url", "llm", "timeout", "max_tokens"):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            Config.model_validate({key: "removed"})


def test_pack_metadata_precedes_runtime_imports() -> None:
    """Tool discovery metadata remains before imports other than __future__."""
    source_file = inspect.getsourcefile(llm_module)
    assert source_file is not None
    module = ast.parse(Path(source_file).read_text(encoding="utf-8"))

    pack_index = next(
        index
        for index, node in enumerate(module.body)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "pack"
            for target in node.targets
        )
    )
    runtime_import_index = next(
        index
        for index, node in enumerate(module.body)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    )

    assert pack_index < runtime_import_index


@pytest.mark.parametrize("tool", [transform, transform_file])
def test_public_docstrings_cover_every_parameter(tool: object) -> None:
    """Registry-facing transform docs include sections and every argument."""
    assert callable(tool)
    doc = inspect.getdoc(tool) or ""
    for section in ("Args:", "Returns:", "Example:"):
        assert section in doc
    for parameter in inspect.signature(tool).parameters:
        assert f"{parameter}:" in doc


@pytest.mark.parametrize(
    ("data", "prompt", "message"),
    [
        ("data", "", "prompt is required"),
        ("", "transform", "data is required"),
        ("   ", "transform", "data is required"),
    ],
)
def test_transform_validates_inputs(
    data: str,
    prompt: str,
    message: str,
) -> None:
    assert message in transform(data=data, prompt=prompt)


def test_transform_uses_pack_call_precedence_and_untrusted_framing() -> None:
    route = SimpleNamespace(model_id="gpt-5.6-sol", effort="high")
    with (
        patch("ottools.ot_llm.resolve_generation", return_value=route) as resolve,
        patch("ottools.ot_llm.generate", return_value=_result()) as call,
    ):
        output = transform(
            data={"value": 2},
            prompt="double it",
            model="sol",
            effort="high",
        )

    assert output == "transformed"
    assert resolve.call_args.kwargs["model"] == "sol"
    assert resolve.call_args.kwargs["effort"] == "high"
    request = call.call_args.kwargs["request"]
    assert "Data:\n{'value': 2}" in request.prompt
    assert "Instructions:\ndouble it" in request.prompt
    assert "untrusted content" in request.system


def test_json_mode_sets_the_responses_wire_format() -> None:
    route = SimpleNamespace(model_id="z-ai/glm-5.2", effort=None)
    with (
        patch("ottools.ot_llm.resolve_generation", return_value=route) as resolve,
        patch(
            "ottools.ot_llm.generate",
            return_value=_result('{"ok":true}'),
        ) as call,
    ):
        output = transform(data="x", prompt="json", json_mode=True)

    assert output == '{"ok":true}'
    assert "structured_output" not in resolve.call_args.kwargs
    assert call.call_args.kwargs["request"].structured_output == "json_object"


def test_generation_error_is_returned_without_content_or_secret_logging() -> None:
    with patch(
        "ottools.ot_llm.resolve_generation",
        side_effect=GenerationError("No generation connection is configured"),
    ):
        output = transform(data="private", prompt="summarize")
    assert output == "Error: No generation connection is configured"
    assert "private" not in output


def test_transform_file_success_and_effort_forwarding(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    target = tmp_path / "output.txt"
    source.write_text("content")
    with patch(
        "ottools.ot_llm._transform_impl",
        return_value=(True, "result"),
    ) as implementation:
        output = transform_file(
            prompt="transform",
            in_file=str(source),
            out_file=str(target),
            model="sol",
            effort="medium",
        )

    assert output.startswith("OK:")
    assert target.read_text() == "result"
    implementation.assert_called_once_with(
        data="content",
        prompt="transform",
        model="sol",
        effort="medium",
        json_mode=False,
    )


@pytest.mark.parametrize(
    ("prepare", "message"),
    [
        ("missing", "Input file not found"),
        ("directory", "Input path is not a file"),
        ("empty", "Input file is empty"),
    ],
)
def test_transform_file_input_errors(
    tmp_path: Path,
    prepare: str,
    message: str,
) -> None:
    source = tmp_path / "input"
    if prepare == "directory":
        source.mkdir()
    elif prepare == "empty":
        source.write_text("")
    output = transform_file(
        prompt="transform",
        in_file=str(source),
        out_file=str(tmp_path / "output"),
    )
    assert message in output


def test_transform_file_does_not_write_on_generation_error(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    target = tmp_path / "output.txt"
    source.write_text("content")
    with patch(
        "ottools.ot_llm._transform_impl",
        return_value=(False, "Error: generation unavailable"),
    ):
        output = transform_file(
            prompt="transform",
            in_file=str(source),
            out_file=str(target),
        )
    assert output == "Error: generation unavailable"
    assert not target.exists()
