"""Tests for ot.debug() function."""

from __future__ import annotations

import re

import pytest

from ot.meta import debug


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_basic():
    """Test basic debug() call returns all required sections."""
    result = debug()

    # Verify all required sections are present
    assert "version" in result
    assert "paths" in result
    assert "config" in result
    assert "python" in result
    assert "system" in result
    assert "runtime" in result

    # Verify version section
    assert "version" in result["version"]
    assert isinstance(result["version"]["version"], str)

    # Verify paths section
    assert "install" in result["paths"]
    assert "cwd" in result["paths"]
    assert "python" in result["paths"]

    # Verify config section
    assert "version" in result["config"]
    assert "servers" in result["config"]
    assert "packs_loaded" in result["config"]
    assert "aliases" in result["config"]
    assert "snippets" in result["config"]

    # Verify python section
    assert "version" in result["python"]
    assert "implementation" in result["python"]
    assert "platform" in result["python"]
    assert "executable" in result["python"]

    # Verify system section
    assert "platform" in result["system"]
    assert "machine" in result["system"]
    assert "user" in result["system"]
    assert "pid" in result["system"]

    # Verify runtime section
    assert "packs_loaded" in result["runtime"]
    assert "tools_local" in result["runtime"]
    assert "tools_proxied" in result["runtime"]
    assert "servers_configured" in result["runtime"]
    assert "servers_connected" in result["runtime"]
    assert "servers_disconnected" in result["runtime"]
    assert "start_time" in result["runtime"]
    assert "uptime_seconds" in result["runtime"]
    assert "mcpId" in result["runtime"]
    assert "pid" in result["runtime"]


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_verbose():
    """Test verbose flag includes extra config details."""
    result = debug(verbose=True)

    # Verbose should include extra config fields
    assert "includes" in result["config"]
    assert "tools_dir" in result["config"]
    assert "stats_enabled" in result["config"]
    assert "log_verbose" in result["config"]


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_env_vars():
    """Test env_vars flag includes environment variables."""
    result = debug(env_vars=True)

    # Should include env section
    assert "env" in result
    assert "OT_CWD" in result["env"]


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_dependencies():
    """Test dependencies flag includes dependency versions."""
    result = debug(dependencies=True)

    # Should include dependencies section
    assert "dependencies" in result
    assert isinstance(result["dependencies"], dict)

    # Check for expected dependencies
    expected_deps = ["fastmcp", "pydantic", "pyyaml", "loguru", "requests", "openai"]
    for dep in expected_deps:
        assert dep in result["dependencies"]
        assert isinstance(result["dependencies"][dep], str)


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_all_flags():
    """Test debug() with all flags enabled."""
    result = debug(verbose=True, env_vars=True, dependencies=True)

    # All sections should be present
    assert "version" in result
    assert "paths" in result
    assert "config" in result
    assert "python" in result
    assert "system" in result
    assert "runtime" in result
    assert "env" in result
    assert "dependencies" in result

    # Verbose config fields
    assert "includes" in result["config"]
    assert "tools_dir" in result["config"]


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_prompts():
    """Test prompts flag includes prompt diagnostics."""
    result = debug(prompts=True)

    assert "prompts" in result
    prompts = result["prompts"]
    assert prompts["source"] in {"inline", "file"}
    assert "sha256" in prompts
    assert "instructions_excerpt" in prompts
    assert "run_description_excerpt" in prompts
    assert "checks" in prompts
    assert prompts["checks"]["has_run_contract"] is True
    assert prompts["checks"]["has_canonical_trigger"] is True
    assert prompts["checks"]["has_natural_language_mode"] is True
    assert prompts["checks"]["has_keyword_only_repair"] is True


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_runtime_timing():
    """Test runtime timing information is valid."""
    result = debug()

    runtime = result["runtime"]

    # Verify start_time is ISO format
    assert "T" in runtime["start_time"]
    assert runtime["start_time"].endswith("Z") or "+" in runtime["start_time"]

    # Verify uptime is a positive number
    assert isinstance(runtime["uptime_seconds"], (int, float))
    assert runtime["uptime_seconds"] >= 0


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_runtime_identity():
    """Runtime info exposes MCP identity."""
    result = debug()
    runtime = result["runtime"]

    assert re.fullmatch(r"\d{8}-[0-9a-f]{8}", runtime["mcpId"])
    assert isinstance(runtime["pid"], int)


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_paths_structure():
    """Test paths section has correct structure."""
    result = debug()

    paths = result["paths"]

    # All paths should be strings
    for key, value in paths.items():
        assert isinstance(value, str), f"Path {key} should be string, got {type(value)}"

    # Install path should point to src/ot directory
    assert paths["install"].endswith("src")


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_config_counts():
    """Test config section has valid counts."""
    result = debug()

    config = result["config"]

    # Counts should be non-negative integers
    assert isinstance(config["packs_loaded"], int)
    assert config["packs_loaded"] >= 0

    assert isinstance(config["aliases"], int)
    assert config["aliases"] >= 0

    assert isinstance(config["snippets"], int)
    assert config["snippets"] >= 0

    # Servers should be a list
    assert isinstance(config["servers"], list)


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_system_info():
    """Test system info has expected values."""
    result = debug()

    system = result["system"]

    # Platform should be one of the common values
    assert system["platform"] in ["Darwin", "Linux", "Windows", "Java"]

    # Machine should be a non-empty string
    assert isinstance(system["machine"], str)
    assert len(system["machine"]) > 0

    # User should be a non-empty string
    assert isinstance(system["user"], str)
    assert len(system["user"]) > 0

    # PID should be a positive integer
    assert isinstance(system["pid"], int)
    assert system["pid"] > 0


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_debug_python_version_format():
    """Test Python version is properly formatted."""
    result = debug()

    python = result["python"]

    # Version should be in format X.Y.Z
    version_parts = python["version"].split(".")
    assert len(version_parts) == 3
    for part in version_parts:
        assert part.isdigit()

    # Implementation should be a known type
    assert python["implementation"] in ["cpython", "pypy", "jython", "ironpython"]

    # Executable should be a non-empty path
    assert isinstance(python["executable"], str)
    assert len(python["executable"]) > 0
