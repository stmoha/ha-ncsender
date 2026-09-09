"""Binary sensor platform for ncSender."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NcSenderConfigEntry
from .entity import NcSenderEntity

BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="connected",
        translation_key="controller_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="spindle",
        translation_key="spindle",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="laser",
        translation_key="laser",
        icon="mdi:laser-pointer",
    ),
    BinarySensorEntityDescription(
        key="flood_coolant",
        translation_key="flood_coolant",
        icon="mdi:water-pump",
    ),
    BinarySensorEntityDescription(
        key="mist_coolant",
        translation_key="mist_coolant",
        icon="mdi:spray",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NcSenderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(NcSenderBinarySensor(entry, d) for d in BINARY_SENSORS)


class NcSenderBinarySensor(NcSenderEntity, BinarySensorEntity):
    def __init__(self, entry: NcSenderConfigEntry, description: BinarySensorEntityDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        value = self.client.data.get(self._key)
        return None if value is None else bool(value)
