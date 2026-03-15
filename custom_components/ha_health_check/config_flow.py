"""Config flow for HA Health Check integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_AUTH_REQUIRED,
    CONF_KEEPALIVE_INTERVAL,
    CONF_THRESHOLD,
    DEFAULT_AUTH_REQUIRED,
    DEFAULT_KEEPALIVE_INTERVAL,
    DEFAULT_THRESHOLD,
    DOMAIN,
)


def _build_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the config/options form schema with the given defaults."""
    if defaults is None:
        defaults = {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_AUTH_REQUIRED,
                default=defaults.get(CONF_AUTH_REQUIRED, DEFAULT_AUTH_REQUIRED),
            ): bool,
            vol.Optional(
                CONF_THRESHOLD,
                default=defaults.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Optional(
                CONF_KEEPALIVE_INTERVAL,
                default=defaults.get(
                    CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=5)),
        }
    )


class HAHealthCheckConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Health Check."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Only allow a single instance
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            threshold = user_input.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
            keepalive = user_input.get(
                CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL
            )
            if threshold <= keepalive:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_build_schema(user_input),
                    errors={"base": "threshold_too_low"},
                )
            return self.async_create_entry(
                title="HA Health Check",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HAHealthCheckOptionsFlow:
        """Get the options flow for this handler."""
        return HAHealthCheckOptionsFlow()


class HAHealthCheckOptionsFlow(OptionsFlow):
    """Handle options flow for HA Health Check."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            threshold = user_input.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
            keepalive = user_input.get(
                CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL
            )
            if threshold <= keepalive:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_build_schema(user_input),
                    errors={"base": "threshold_too_low"},
                )
            return self.async_create_entry(title="", data=user_input)

        # Merge options over data so current values are shown as defaults
        current = {**self.config_entry.data, **self.config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(current),
        )
