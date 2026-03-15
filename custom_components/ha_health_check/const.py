"""Constants for the HA Health Check integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "ha_health_check"

LOGGER: Final = logging.getLogger(f"custom_components.{DOMAIN}")

PLATFORMS: Final = [Platform.SENSOR]

HEALTHCHECK_ENDPOINT: Final = "/healthz"

CONF_AUTH_REQUIRED: Final = "auth_required"
CONF_THRESHOLD: Final = "threshold"
CONF_KEEPALIVE_INTERVAL: Final = "keepalive_interval"

DEFAULT_AUTH_REQUIRED: Final = True
DEFAULT_THRESHOLD: Final = 60
DEFAULT_KEEPALIVE_INTERVAL: Final = 10
