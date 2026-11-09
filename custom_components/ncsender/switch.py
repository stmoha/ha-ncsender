"""Switch platform for ncSender aux outputs (M64 Pn / M65 Pn)."""

from __future__ import annotations

import re

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NcSenderConfigEntry
from .client import NcSenderError
from .const import CONF_OUTPUT_PINS, DEFAULT_OUTPUT_PINS
from .entity import NcSenderEntity


def _parse_pins(raw: str) -> list[int]:
    return sorted({int(p) for p in re.findall(r"\d+", raw or "")})


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NcSenderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    pins = _parse_pins(entry.options.get(CONF_OUTPUT_PINS, DEFAULT_OUTPUT_PINS))
    async_add_entities(NcSenderOutputSwitch(entry, pin) for pin in pins)


class NcSenderOutputSwitch(NcSenderEntity, SwitchEntity):
    """One grblHAL aux output. State mirrors ncSender's own M64/M65 tracking,
    so a press in ncSender's UI, an M64 in a job, or a toggle here all agree."""

    _attr_icon = "mdi:electric-switch"

    def __init__(self, entry: NcSenderConfigEntry, pin: int) -> None:
        super().__init__(entry, f"output_{pin}")
        self._pin = pin
        self._attr_name = f"Output P{pin}"

    @property
    def is_on(self) -> bool | None:
        pins = self.client.data.get("output_pins")
        return None if pins is None else self._pin in pins

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"on_command": f"M64 P{self._pin}", "off_command": f"M65 P{self._pin}"}

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, on: bool) -> None:
        try:
            await self.client.async_set_output(self._pin, on)
        except NcSenderError as err:
            raise HomeAssistantError(str(err)) from err
