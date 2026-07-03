"""Unit tests for timer tool pack.

Tests timer.start(), timer.elapsed(), timer.list(), timer.clear().
"""

from __future__ import annotations

from time import sleep

import pytest

from ottools import ot_timer as timer


@pytest.fixture(autouse=True)
def _clean_timer_state():
    """Reset timer state between tests."""
    timer._timers.clear()
    timer._results.clear()
    yield
    timer._timers.clear()
    timer._results.clear()


# =============================================================================
# Module Structure
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_pack_name():
    assert timer.pack == "ot_timer"


@pytest.mark.unit
@pytest.mark.tools
def test_all_exports():
    assert set(timer.__all__) == {"start", "elapsed", "list", "clear"}


# =============================================================================
# Basic start + elapsed flow
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_start_elapsed_basic():
    result = timer.start()
    assert result["status"] == "started"
    assert result["name"] == "_default"
    assert "started_at" in result

    sleep(0.01)
    el = timer.elapsed()
    assert isinstance(el, dict)
    assert el["name"] == "_default"
    assert el["elapsed_seconds"] >= 0.005
    assert "elapsed_formatted" in el


# =============================================================================
# Default name behaviour
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_default_name():
    timer.start()
    el = timer.elapsed()
    assert el["name"] == "_default"


# =============================================================================
# Elapsed with unknown name returns error string
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_elapsed_unknown_name():
    result = timer.elapsed(name="nonexistent")
    assert isinstance(result, str)
    assert "nonexistent" in result


# =============================================================================
# store_as saves to list
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_store_as():
    timer.start(name="profile")
    sleep(0.01)
    timer.elapsed(name="profile", store_as="profile_result")

    stored = timer.list()
    assert "profile_result" in stored["stored"]
    assert stored["stored"]["profile_result"]["name"] == "profile"
    assert stored["stored"]["profile_result"]["elapsed_seconds"] >= 0.005


# =============================================================================
# Lap pattern: single clock, multiple snapshots
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_lap_pattern():
    timer.start(name="laps")
    sleep(0.01)
    lap1 = timer.elapsed(name="laps", store_as="lap1")
    sleep(0.01)
    lap2 = timer.elapsed(name="laps", store_as="lap2")

    assert lap2["elapsed_seconds"] > lap1["elapsed_seconds"]
    stored = timer.list()["stored"]
    assert "lap1" in stored
    assert "lap2" in stored


# =============================================================================
# Start overwrites silently
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_start_overwrites():
    timer.start(name="x")
    sleep(0.02)
    timer.start(name="x")  # restart
    sleep(0.01)
    el = timer.elapsed(name="x")
    # Should reflect time since second start, not first
    assert el["elapsed_seconds"] < 0.05


# =============================================================================
# Clear removes starts but preserves stored results
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_clear_preserves_stored():
    timer.start(name="a")
    timer.elapsed(name="a", store_as="saved")
    timer.clear()

    # Timer is gone
    result = timer.elapsed(name="a")
    assert isinstance(result, str)

    # But stored result survives
    stored = timer.list()
    assert "saved" in stored["stored"]
    assert stored["active"] == {}


@pytest.mark.unit
@pytest.mark.tools
def test_clear_with_results():
    timer.start(name="b")
    timer.elapsed(name="b", store_as="kept")
    result = timer.clear(results=True)

    assert result["timers_removed"] == 1
    assert result["results_removed"] == 1

    stored = timer.list()
    assert stored["stored"] == {}
    assert stored["active"] == {}
