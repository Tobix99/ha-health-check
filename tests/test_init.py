"""Tests for the HA Health Check integration __init__.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_health_check.const import (
    CONF_AUTH_REQUIRED,
    CONF_KEEPALIVE_INTERVAL,
    CONF_THRESHOLD,
    DEFAULT_AUTH_REQUIRED,
    DEFAULT_KEEPALIVE_INTERVAL,
    DEFAULT_THRESHOLD,
    DOMAIN,
)

# Expected entity_id: with has_entity_name=True, HA derives it from the
# device name ("HA Health Check") and entity name ("Last Seen").
ENTITY_ID = "sensor.ha_health_check_last_seen"


# ---------------------------------------------------------------------------
# Config entry setup tests
# ---------------------------------------------------------------------------


async def _setup_http(hass: HomeAssistant) -> None:
    """Ensure the HTTP component is available for view registration.

    Config entry tests that set up entries directly need the HTTP
    component initialized before the entry tries to register
    its /healthz view.
    """
    await async_setup_component(hass, "http", {})
    await hass.async_block_till_done()


async def _create_and_setup_entry(
    hass: HomeAssistant,
    threshold: int = DEFAULT_THRESHOLD,
    keepalive_interval: int = DEFAULT_KEEPALIVE_INTERVAL,
    auth_required: bool = DEFAULT_AUTH_REQUIRED,
) -> MockConfigEntry:
    """Create and set up a config entry for testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_REQUIRED: auth_required,
            CONF_THRESHOLD: threshold,
            CONF_KEEPALIVE_INTERVAL: keepalive_interval,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test config entry sets up correctly."""
    await _setup_http(hass)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_REQUIRED: False,
            CONF_THRESHOLD: 90,
            CONF_KEEPALIVE_INTERVAL: 15,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert hass.data[DOMAIN][CONF_AUTH_REQUIRED] is False
    assert hass.data[DOMAIN][CONF_THRESHOLD] == 90
    assert hass.data[DOMAIN][CONF_KEEPALIVE_INTERVAL] == 15
    assert hass.data[DOMAIN].get("cancel_timer") is not None

    state = hass.states.get(ENTITY_ID)
    assert state is not None

    # Clean up to avoid lingering timer
    await hass.config_entries.async_unload(entry.entry_id)


async def test_async_setup_entry_with_options(hass: HomeAssistant) -> None:
    """Test options override data values."""
    await _setup_http(hass)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_REQUIRED: True,
            CONF_THRESHOLD: 60,
            CONF_KEEPALIVE_INTERVAL: 10,
        },
        options={
            CONF_AUTH_REQUIRED: False,
            CONF_THRESHOLD: 120,
            CONF_KEEPALIVE_INTERVAL: 30,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    # Options should override data
    assert hass.data[DOMAIN][CONF_AUTH_REQUIRED] is False
    assert hass.data[DOMAIN][CONF_THRESHOLD] == 120
    assert hass.data[DOMAIN][CONF_KEEPALIVE_INTERVAL] == 30

    # Clean up to avoid lingering timer
    await hass.config_entries.async_unload(entry.entry_id)


# ---------------------------------------------------------------------------
# Unload tests
# ---------------------------------------------------------------------------


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test unload cancels timer, removes domain data."""
    await _setup_http(hass)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_REQUIRED: True,
            CONF_THRESHOLD: 60,
            CONF_KEEPALIVE_INTERVAL: 10,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN not in hass.data


# ---------------------------------------------------------------------------
# Update listener tests
# ---------------------------------------------------------------------------


async def test_update_listener_triggers_reload(hass: HomeAssistant) -> None:
    """Test that changing options triggers a config entry reload."""
    await _setup_http(hass)
    entry = await _create_and_setup_entry(hass)

    with patch.object(
        hass.config_entries, "async_reload", new_callable=AsyncMock
    ) as mock_reload:
        hass.config_entries.async_update_entry(entry, options={CONF_THRESHOLD: 120})
        await hass.async_block_till_done()

        mock_reload.assert_awaited_once_with(entry.entry_id)

    # Clean up
    await hass.config_entries.async_unload(entry.entry_id)


# ---------------------------------------------------------------------------
# Auth behaviour tests
# ---------------------------------------------------------------------------


async def test_healthz_auth_required(hass: HomeAssistant, hass_client) -> None:
    """Test endpoint requires authentication by default."""
    entry = await _create_and_setup_entry(hass, auth_required=True)
    client = await hass_client()

    # Set a valid timestamp so health check logic succeeds
    known_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    hass.states.async_set(ENTITY_ID, known_time.isoformat())
    await hass.async_block_till_done()

    mock_now = datetime(2025, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
    with patch(
        "custom_components.ha_health_check.dt_util.utcnow",
        return_value=mock_now,
    ):
        # hass_client includes auth token, so request should succeed
        resp = await client.get("/healthz")
        assert resp.status == 200

    # Verify the view was registered with requires_auth=True
    from custom_components.ha_health_check import HealthCheckView

    for resource in hass.http.app.router.resources():
        for route in resource:
            handler = getattr(route, "_handler", None)
            if handler is not None and hasattr(handler, "__self__"):
                view = handler.__self__
                if isinstance(view, HealthCheckView):
                    assert view.requires_auth is True
                    break

    await hass.config_entries.async_unload(entry.entry_id)


async def test_healthz_no_auth_required(hass: HomeAssistant, hass_client) -> None:
    """Test endpoint allows access when auth_required=False."""
    entry = await _create_and_setup_entry(hass, auth_required=False)
    client = await hass_client()

    # Set a valid timestamp so health check logic succeeds
    known_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    hass.states.async_set(ENTITY_ID, known_time.isoformat())
    await hass.async_block_till_done()

    mock_now = datetime(2025, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
    with patch(
        "custom_components.ha_health_check.dt_util.utcnow",
        return_value=mock_now,
    ):
        # Authenticated request should still succeed
        resp = await client.get("/healthz")
        assert resp.status == 200

    # Verify the view was registered with requires_auth=False
    from custom_components.ha_health_check import HealthCheckView

    for resource in hass.http.app.router.resources():
        for route in resource:
            handler = getattr(route, "_handler", None)
            if handler is not None and hasattr(handler, "__self__"):
                view = handler.__self__
                if isinstance(view, HealthCheckView):
                    assert view.requires_auth is False
                    break

    await hass.config_entries.async_unload(entry.entry_id)


# ---------------------------------------------------------------------------
# Health check endpoint tests
# ---------------------------------------------------------------------------


async def test_healthz_healthy(hass: HomeAssistant, hass_client) -> None:
    """Test returns {"healthy": true} (200) when last keepalive is within threshold."""
    await _create_and_setup_entry(hass, threshold=60, keepalive_interval=10)
    await hass.async_block_till_done()

    client = await hass_client()

    # Set entity state to a known timestamp
    known_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    hass.states.async_set(ENTITY_ID, known_time.isoformat())
    await hass.async_block_till_done()

    # Mock utcnow to 30s later — within the 60s threshold
    mock_now = datetime(2025, 1, 1, 0, 0, 30, tzinfo=timezone.utc)

    with patch(
        "custom_components.ha_health_check.dt_util.utcnow",
        return_value=mock_now,
    ):
        resp = await client.get("/healthz")
        assert resp.status == 200
        data = await resp.json()
        assert data["healthy"] is True


async def test_healthz_unhealthy(hass: HomeAssistant, hass_client) -> None:
    """Test returns {"healthy": false} (503) when keepalive exceeds threshold."""
    await _create_and_setup_entry(hass, threshold=60, keepalive_interval=10)
    await hass.async_block_till_done()

    client = await hass_client()

    # Set entity state to a very old timestamp (2025-01-01 00:00:00 UTC)
    old_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    hass.states.async_set(ENTITY_ID, old_time.isoformat())
    await hass.async_block_till_done()

    # Mock utcnow to be 2 minutes later — well beyond the 60s threshold
    mock_now = datetime(2025, 1, 1, 0, 2, 0, tzinfo=timezone.utc)

    with patch(
        "custom_components.ha_health_check.dt_util.utcnow",
        return_value=mock_now,
    ):
        resp = await client.get("/healthz")
        assert resp.status == 503
        data = await resp.json()
        assert data["healthy"] is False


@pytest.mark.parametrize(
    ("state", "expected_status"),
    [
        (CoreState.starting, 200),
        # CoreState.stopping triggers HA's HTTP middleware to reject with 503
        # before the view handler runs, so we verify at the HTTP level.
        (CoreState.stopping, 503),
    ],
)
async def test_healthz_non_running_state(
    hass: HomeAssistant, hass_client, state: CoreState, expected_status: int
) -> None:
    """Test behaviour when HA is not in running state."""
    await _create_and_setup_entry(hass)
    await hass.async_block_till_done()

    client = await hass_client()

    hass.set_state(state)

    resp = await client.get("/healthz")
    assert resp.status == expected_status
    if expected_status == 200:
        data = await resp.json()
        assert data["healthy"] is True


async def test_healthz_no_state(hass: HomeAssistant, hass_client) -> None:
    """Test returns unhealthy (503) when no entity state exists."""
    await _create_and_setup_entry(hass)
    await hass.async_block_till_done()

    client = await hass_client()

    # Remove the entity state so it returns None
    hass.states.async_remove(ENTITY_ID)
    await hass.async_block_till_done()

    resp = await client.get("/healthz")
    assert resp.status == 503
    data = await resp.json()
    assert data["healthy"] is False


async def test_healthz_invalid_state_value(hass: HomeAssistant, hass_client) -> None:
    """Test returns unhealthy (503) when state is not a valid datetime."""
    await _create_and_setup_entry(hass)
    await hass.async_block_till_done()

    client = await hass_client()

    # Set entity state to a value that is not a valid datetime
    hass.states.async_set(ENTITY_ID, "not_a_number")
    await hass.async_block_till_done()

    resp = await client.get("/healthz")
    assert resp.status == 503
    data = await resp.json()
    assert data["healthy"] is False


async def test_healthz_naive_datetime_state(hass: HomeAssistant, hass_client) -> None:
    """Test handles naive datetime (no timezone) by assuming UTC."""
    await _create_and_setup_entry(hass, threshold=60)
    await hass.async_block_till_done()

    client = await hass_client()

    # Set entity state to a valid ISO datetime without timezone info
    hass.states.async_set(ENTITY_ID, "2025-01-01T00:00:00")
    await hass.async_block_till_done()

    # Mock utcnow to 10s later — within the 60s threshold
    mock_now = datetime(2025, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
    with patch(
        "custom_components.ha_health_check.dt_util.utcnow",
        return_value=mock_now,
    ):
        resp = await client.get("/healthz")
        assert resp.status == 200
        data = await resp.json()
        assert data["healthy"] is True


async def test_healthz_recorder_fallback(hass: HomeAssistant, hass_client) -> None:
    """Test falls back to hass.states when recorder raises an exception.

    The production code does ``from homeassistant.components import recorder``
    inside a try/except. When the recorder raises, execution falls through to
    ``hass.states.get()``. This test forces that path by making
    ``recorder.is_entity_recorded`` raise, then verifies the endpoint still
    returns a healthy response via the state fallback.
    """
    await _create_and_setup_entry(hass)
    await hass.async_block_till_done()

    client = await hass_client()

    # Entity should exist from the sensor platform setup
    state = hass.states.get(ENTITY_ID)
    assert state is not None

    # Set a known valid timestamp so the health check considers it healthy
    known_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    hass.states.async_set(ENTITY_ID, known_time.isoformat())
    await hass.async_block_till_done()

    # Mock utcnow to 10s later — within the 60s default threshold
    mock_now = datetime(2025, 1, 1, 0, 0, 10, tzinfo=timezone.utc)

    # Force the except-Exception branch by making is_entity_recorded raise
    with (
        patch(
            "homeassistant.components.recorder.is_entity_recorded",
            side_effect=RuntimeError("recorder exploded"),
        ),
        patch(
            "custom_components.ha_health_check.dt_util.utcnow",
            return_value=mock_now,
        ),
    ):
        resp = await client.get("/healthz")
        assert resp.status == 200
        data = await resp.json()
        assert data["healthy"] is True


async def test_healthz_domain_data_missing(hass: HomeAssistant, hass_client) -> None:
    """Test returns 503 when hass.data[DOMAIN] is missing (e.g. during unload)."""
    await _create_and_setup_entry(hass)
    await hass.async_block_till_done()

    client = await hass_client()

    # Simulate domain data being removed (e.g. integration unloading)
    hass.data.pop(DOMAIN)

    resp = await client.get("/healthz")
    assert resp.status == 503
    data = await resp.json()
    assert data["healthy"] is False
