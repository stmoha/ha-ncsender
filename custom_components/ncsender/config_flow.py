"""Config flow for ncSender."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import NcSenderClient
from .const import (
    CONF_LASER_MAX_S,
    CONF_OUTPUT_PINS,
    CONF_TELEMETRY_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_LASER_MAX_S,
    DEFAULT_NAME,
    DEFAULT_OUTPUT_PINS,
    DEFAULT_PORT,
    DEFAULT_TELEMETRY_INTERVAL,
    DOMAIN,
    MAX_TELEMETRY_INTERVAL,
    MIN_TELEMETRY_INTERVAL,
)

INTERVAL_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=MIN_TELEMETRY_INTERVAL, max=MAX_TELEMETRY_INTERVAL))

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_LASER_MAX_S, default=DEFAULT_LASER_MAX_S): int,
    }
)


class NcSenderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            client = NcSenderClient(
                async_get_clientsession(self.hass), host, port, user_input[CONF_LASER_MAX_S]
            )
            if await client.async_test_connection():
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_NAME: user_input[CONF_NAME],
                    },
                    options={
                        CONF_LASER_MAX_S: user_input[CONF_LASER_MAX_S],
                        CONF_TELEMETRY_INTERVAL: DEFAULT_TELEMETRY_INTERVAL,
                    },
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NcSenderOptionsFlow()


class NcSenderOptionsFlow(OptionsFlow):
    """Options: laser S-value ceiling."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LASER_MAX_S, default=opts.get(CONF_LASER_MAX_S, DEFAULT_LASER_MAX_S)
                    ): int,
                    vol.Required(
                        CONF_TELEMETRY_INTERVAL,
                        default=opts.get(CONF_TELEMETRY_INTERVAL, DEFAULT_TELEMETRY_INTERVAL),
                    ): INTERVAL_SCHEMA,
                    vol.Optional(
                        CONF_OUTPUT_PINS,
                        default=opts.get(CONF_OUTPUT_PINS, DEFAULT_OUTPUT_PINS),
                    ): str,
                }
            ),
        )
