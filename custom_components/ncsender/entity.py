"""Base entity for ncSender."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import NcSenderConfigEntry
from .client import NcSenderClient
from .const import DOMAIN


class NcSenderEntity(Entity):
    """Push-updated entity bound to the ncSender client."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: NcSenderConfigEntry, key: str) -> None:
        self.client: NcSenderClient = entry.runtime_data
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, entry.title),
            manufacturer="Sienci Labs",
            model="ncSender (grblHAL)",
            configuration_url=f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.client.add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self.client.connected
