"""The ncSender integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import NcSenderClient, NcSenderError
from .const import (
    ATTR_COMMAND,
    ATTR_ENTRY_ID,
    CONF_HA_SWITCHES,
    CONF_LASER_MAX_S,
    CONF_TELEMETRY_INTERVAL,
    DEFAULT_LASER_MAX_S,
    DEFAULT_TELEMETRY_INTERVAL,
    DOMAIN,
    EVENT_HA_COMMAND,
    SERVICE_SEND_COMMAND,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SWITCH]

type NcSenderConfigEntry = ConfigEntry[NcSenderClient]

SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_COMMAND): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: NcSenderConfigEntry) -> bool:
    """Set up ncSender from a config entry."""
    client = NcSenderClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.options.get(CONF_LASER_MAX_S, entry.data.get(CONF_LASER_MAX_S, DEFAULT_LASER_MAX_S)),
        entry.options.get(CONF_TELEMETRY_INTERVAL, DEFAULT_TELEMETRY_INTERVAL),
    )
    if not await client.async_test_connection():
        raise ConfigEntryNotReady(
            f"Cannot reach ncSender at {entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
        )

    entry.runtime_data = client
    entry.async_on_unload(client.add_ha_command_listener(_ha_command_handler(hass, entry)))
    client.start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NcSenderConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_stop()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: NcSenderConfigEntry) -> None:
    """Reload on options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _ha_command_handler(hass: HomeAssistant, entry: NcSenderConfigEntry):
    """Turn "(HA <entity_id> ON|OFF|TOGGLE)" commands into service calls,
    for allowlisted entities only. Every command fires an event either way,
    so the allowlist is easy to debug from Developer tools → Events."""
    allowed = set(entry.options.get(CONF_HA_SWITCHES) or [])

    @callback
    def _handle(entity_id: str, service: str) -> None:
        is_allowed = entity_id in allowed
        hass.bus.async_fire(
            EVENT_HA_COMMAND,
            {"entity_id": entity_id, "service": service, "allowed": is_allowed},
        )
        if not is_allowed:
            _LOGGER.warning(
                "Ignoring ncSender command for %s: not in the integration's allowed "
                "entities (Settings → ncSender → Configure)",
                entity_id,
            )
            return
        hass.async_create_task(_async_call(entity_id, service))

    async def _async_call(entity_id: str, service: str) -> None:
        try:
            await hass.services.async_call(
                "homeassistant", service, {"entity_id": entity_id}, blocking=True
            )
        except HomeAssistantError as err:
            _LOGGER.warning("ncSender command %s %s failed: %s", service, entity_id, err)

    return _handle


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        return

    async def _handle_send_command(call: ServiceCall) -> None:
        entries = [
            e for e in hass.config_entries.async_entries(DOMAIN) if hasattr(e, "runtime_data")
        ]
        entry_id = call.data.get(ATTR_ENTRY_ID)
        if entry_id:
            entries = [e for e in entries if e.entry_id == entry_id]
        if not entries:
            raise ServiceValidationError("No loaded ncSender entry matches the request")
        if len(entries) > 1:
            raise ServiceValidationError(
                "Multiple ncSender entries configured; specify entry_id"
            )
        try:
            await entries[0].runtime_data.async_send_command(call.data[ATTR_COMMAND])
        except NcSenderError as err:
            raise HomeAssistantError(f"ncSender rejected command: {err}") from err

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_COMMAND, _handle_send_command, schema=SEND_COMMAND_SCHEMA
    )
