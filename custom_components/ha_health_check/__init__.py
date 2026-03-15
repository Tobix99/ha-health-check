"""
HA Health Check - Health check endpoint for Home Assistant.

Exposes a /healthz HTTP endpoint for Kubernetes liveness/readiness probes.
Inspired by https://github.com/bkupidura/hass-simple-healthcheck

For more details, please refer to:
https://github.com/Tobix99/ha-health-check
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTH_REQUIRED,
    CONF_KEEPALIVE_INTERVAL,
    CONF_THRESHOLD,
    DEFAULT_AUTH_REQUIRED,
    DEFAULT_KEEPALIVE_INTERVAL,
    DEFAULT_THRESHOLD,
    DOMAIN,
    HEALTHCHECK_ENDPOINT,
    LOGGER,
    PLATFORMS,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the HA Health Check integration via config entry (UI)."""
    # Merge options over data so options flow changes take effect
    conf = {**entry.data, **entry.options}

    auth_required: bool = conf.get(CONF_AUTH_REQUIRED, DEFAULT_AUTH_REQUIRED)
    threshold: int = conf.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
    keepalive_interval: int = conf.get(
        CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL
    )

    success = await _async_setup_health_check(
        hass, auth_required, threshold, keepalive_interval
    )

    if success:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return success


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of a config entry."""
    data = hass.data.get(DOMAIN)
    if data is not None:
        cancel_timer = data.get("cancel_timer")
        if cancel_timer is not None:
            cancel_timer()

    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.pop(DOMAIN, None)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_setup_health_check(
    hass: HomeAssistant,
    auth_required: bool,
    threshold: int,
    keepalive_interval: int,
) -> bool:
    """Set up the health check components."""
    if DOMAIN in hass.data:
        LOGGER.warning("HA Health Check is already set up, skipping")
        return True

    hass.data[DOMAIN] = {
        CONF_AUTH_REQUIRED: auth_required,
        CONF_THRESHOLD: threshold,
        CONF_KEEPALIVE_INTERVAL: keepalive_interval,
    }

    # Register HTTP endpoint
    healthcheck_view = HealthCheckView(auth_required)
    hass.http.register_view(healthcheck_view)

    # Set up internal keepalive timer
    async def fire_keepalive_event(now: Any) -> None:
        """Update the sensor with the current keepalive timestamp."""
        sensor = hass.data.get(DOMAIN, {}).get("sensor")
        if sensor is not None:
            sensor.update_keepalive()

    cancel_timer = async_track_time_interval(
        hass, fire_keepalive_event, timedelta(seconds=keepalive_interval)
    )
    hass.data[DOMAIN]["cancel_timer"] = cancel_timer

    LOGGER.info(
        "HA Health Check set up: endpoint=%s, threshold=%ds, interval=%ds, auth=%s",
        HEALTHCHECK_ENDPOINT,
        threshold,
        keepalive_interval,
        auth_required,
    )

    return True


class HealthCheckView(HomeAssistantView):
    """View to handle the /healthz health check endpoint.

    Note: The requires_auth setting is fixed at registration time.
    Changing auth_required via options flow requires a full
    Home Assistant restart because HA's HTTP middleware checks
    requires_auth before the handler runs.
    """

    url = HEALTHCHECK_ENDPOINT
    name = DOMAIN

    def __init__(self, auth_required: bool) -> None:
        """Initialize the health check view."""
        self.requires_auth = auth_required

    async def get(self, request: Any) -> Any:
        """Handle GET request to /healthz."""
        hass: HomeAssistant = request.app["hass"]

        # During startup/shutdown, report as healthy
        if hass.state != CoreState.running:
            LOGGER.info(
                "Home Assistant state is not running (%s), reporting as healthy",
                hass.state,
            )
            return self.json({"healthy": True})

        domain_data = hass.data.get(DOMAIN)
        if domain_data is None:
            return self.json({"healthy": False}, status_code=503)

        sensor = domain_data.get("sensor")
        if sensor is None:
            LOGGER.error("Sensor not available, cannot determine health")
            return self.json({"healthy": False}, status_code=503)

        entity_id = sensor.entity_id
        last_seen_state = None
        threshold: int = domain_data[CONF_THRESHOLD]

        # Try to read from recorder database first (validates recorder health)
        try:
            from homeassistant.components import recorder

            if recorder.is_entity_recorded(hass, entity_id):
                LOGGER.debug("Fetching %s from recorder database", entity_id)

                entity_history = await recorder.get_instance(
                    hass
                ).async_add_executor_job(
                    recorder.history.get_last_state_changes,
                    hass,
                    1,
                    entity_id,
                )

                entity_data = entity_history.get(entity_id)
                if entity_data and len(entity_data) > 0:
                    last_seen_state = entity_data[-1]
                else:
                    LOGGER.warning(
                        "Unable to fetch %s from recorder database", entity_id
                    )
            else:
                LOGGER.debug(
                    "%s is excluded from recorder, using hass.states", entity_id
                )
                last_seen_state = hass.states.get(entity_id)
        except Exception:
            LOGGER.warning(
                "Recorder not available, falling back to hass.states",
                exc_info=True,
            )
            last_seen_state = hass.states.get(entity_id)

        now = dt_util.utcnow()

        if last_seen_state is not None:
            last_seen_dt = dt_util.parse_datetime(last_seen_state.state)
            if last_seen_dt is None:
                LOGGER.error("Invalid last_seen state value: %s", last_seen_state.state)
                return self.json({"healthy": False}, status_code=503)

            if last_seen_dt.tzinfo is None:
                last_seen_dt = last_seen_dt.replace(tzinfo=dt_util.UTC)

            last_keepalive_seconds_ago = int((now - last_seen_dt).total_seconds())

            if last_keepalive_seconds_ago < threshold:
                LOGGER.debug(
                    "Home Assistant is healthy, last keepalive %d seconds ago",
                    last_keepalive_seconds_ago,
                )
                return self.json({"healthy": True})

            LOGGER.error(
                "Home Assistant is unhealthy, last keepalive %d seconds ago "
                "(threshold: %d seconds)",
                last_keepalive_seconds_ago,
                threshold,
            )
        else:
            LOGGER.error("Home Assistant is unhealthy, no keepalive state found")

        return self.json({"healthy": False}, status_code=503)
