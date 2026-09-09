"""Button platform for ncSender job control."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NcSenderConfigEntry
from .client import NcSenderClient, NcSenderError
from .entity import NcSenderEntity


@dataclass(frozen=True, kw_only=True)
class NcSenderButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[NcSenderClient], Awaitable[None]]


BUTTONS: tuple[NcSenderButtonDescription, ...] = (
    NcSenderButtonDescription(
        key="pause",
        translation_key="pause",
        icon="mdi:pause",
        press_fn=lambda c: c.async_pause(),
    ),
    NcSenderButtonDescription(
        key="resume",
        translation_key="resume",
        icon="mdi:play",
        press_fn=lambda c: c.async_resume(),
    ),
    NcSenderButtonDescription(
        key="stop",
        translation_key="stop",
        icon="mdi:stop",
        press_fn=lambda c: c.async_stop_job(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NcSenderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(NcSenderButton(entry, d) for d in BUTTONS)


class NcSenderButton(NcSenderEntity, ButtonEntity):
    entity_description: NcSenderButtonDescription

    def __init__(self, entry: NcSenderConfigEntry, description: NcSenderButtonDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        try:
            await self.entity_description.press_fn(self.client)
        except NcSenderError as err:
            raise HomeAssistantError(str(err)) from err
