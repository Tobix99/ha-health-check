"""Tests for HA Health Check config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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


# ---------------------------------------------------------------------------
# Config flow – user step
# ---------------------------------------------------------------------------


async def test_user_flow_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows a form when no input is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Verify schema contains the expected keys
    schema = result["data_schema"].schema
    schema_keys = {str(k) for k in schema}
    assert CONF_AUTH_REQUIRED in schema_keys
    assert CONF_THRESHOLD in schema_keys
    assert CONF_KEEPALIVE_INTERVAL in schema_keys


async def test_user_flow_with_defaults(hass: HomeAssistant) -> None:
    """Test creating an entry with default values."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_AUTH_REQUIRED: DEFAULT_AUTH_REQUIRED,
            CONF_THRESHOLD: DEFAULT_THRESHOLD,
            CONF_KEEPALIVE_INTERVAL: DEFAULT_KEEPALIVE_INTERVAL,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "HA Health Check"
    assert result["data"] == {
        CONF_AUTH_REQUIRED: False,
        CONF_THRESHOLD: 60,
        CONF_KEEPALIVE_INTERVAL: 10,
    }


async def test_user_flow_with_custom_values(hass: HomeAssistant) -> None:
    """Test creating an entry with custom values."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_AUTH_REQUIRED: False,
            CONF_THRESHOLD: 120,
            CONF_KEEPALIVE_INTERVAL: 30,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "HA Health Check"
    assert result["data"] == {
        CONF_AUTH_REQUIRED: False,
        CONF_THRESHOLD: 120,
        CONF_KEEPALIVE_INTERVAL: 30,
    }


async def test_user_flow_single_instance_guard(hass: HomeAssistant) -> None:
    """Test that a second config entry is aborted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_REQUIRED: True,
            CONF_THRESHOLD: 60,
            CONF_KEEPALIVE_INTERVAL: 10,
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


async def test_options_flow_init(hass: HomeAssistant) -> None:
    """Test that the options flow shows current values as defaults."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_REQUIRED: True,
            CONF_THRESHOLD: 60,
            CONF_KEEPALIVE_INTERVAL: 10,
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ha_health_check.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Verify the schema defaults match current entry data
    schema = result["data_schema"].schema
    for key in schema:
        if str(key) == CONF_AUTH_REQUIRED:
            assert key.default() is True
        elif str(key) == CONF_THRESHOLD:
            assert key.default() == 60
        elif str(key) == CONF_KEEPALIVE_INTERVAL:
            assert key.default() == 10


async def test_user_flow_threshold_too_low(hass: HomeAssistant) -> None:
    """Test that threshold <= keepalive_interval is rejected with an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_AUTH_REQUIRED: DEFAULT_AUTH_REQUIRED,
            CONF_THRESHOLD: 10,
            CONF_KEEPALIVE_INTERVAL: 10,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "threshold_too_low"}


async def test_options_flow_threshold_too_low(hass: HomeAssistant) -> None:
    """Test that options flow rejects threshold <= keepalive_interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_REQUIRED: True,
            CONF_THRESHOLD: 60,
            CONF_KEEPALIVE_INTERVAL: 10,
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ha_health_check.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_AUTH_REQUIRED: True,
            CONF_THRESHOLD: 10,
            CONF_KEEPALIVE_INTERVAL: 10,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "threshold_too_low"}


async def test_options_flow_update(hass: HomeAssistant) -> None:
    """Test that submitting options updates the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_REQUIRED: True,
            CONF_THRESHOLD: 60,
            CONF_KEEPALIVE_INTERVAL: 10,
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ha_health_check.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_AUTH_REQUIRED: False,
            CONF_THRESHOLD: 120,
            CONF_KEEPALIVE_INTERVAL: 30,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_AUTH_REQUIRED: False,
        CONF_THRESHOLD: 120,
        CONF_KEEPALIVE_INTERVAL: 30,
    }
