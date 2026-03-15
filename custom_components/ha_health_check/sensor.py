"""Sensor platform for HA Health Check."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HA Health Check sensor from a config entry."""
    sensor = HAHealthCheckSensor(entry)
    hass.data[DOMAIN]["sensor"] = sensor
    async_add_entities([sensor], update_before_add=True)


class HAHealthCheckSensor(SensorEntity):
    """Sensor that tracks the last keepalive timestamp."""

    _attr_has_entity_name = True
    _attr_name = "Last Seen"
    _attr_icon = "mdi:heart-pulse"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = f"{entry.entry_id}_last_seen"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="HA Health Check",
            entry_type=DeviceEntryType.SERVICE,
        )

    def update_keepalive(self) -> None:
        """Update the sensor with the current timestamp.

        Called from the keepalive timer callback on the event loop.
        Guards against being called before the entity is added to HA.
        """
        if self.hass is None:
            return
        self._attr_native_value = int(dt_util.utcnow().timestamp())
        self.async_write_ha_state()
