"""Sensor platform for ncSender."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NcSenderConfigEntry
from .entity import NcSenderEntity


@dataclass(frozen=True, kw_only=True)
class NcSenderSensorDescription(SensorEntityDescription):
    """Describes an ncSender sensor; key doubles as the snapshot key."""

    attributes_key: str | None = None


SENSORS: tuple[NcSenderSensorDescription, ...] = (
    NcSenderSensorDescription(
        key="machine_state",
        translation_key="machine_state",
        icon="mdi:state-machine",
        attributes_key="machine_attributes",
    ),
    NcSenderSensorDescription(
        key="sender_status",
        translation_key="sender_status",
        icon="mdi:application-cog",
    ),
    NcSenderSensorDescription(
        key="active_output",
        translation_key="active_output",
        icon="mdi:power-plug",
    ),
    NcSenderSensorDescription(
        key="job_status",
        translation_key="job_status",
        icon="mdi:progress-wrench",
        attributes_key="job_attributes",
    ),
    NcSenderSensorDescription(
        key="job_file",
        translation_key="job_file",
        icon="mdi:file-code",
    ),
    NcSenderSensorDescription(
        key="job_progress",
        translation_key="job_progress",
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NcSenderSensorDescription(
        key="job_remaining",
        translation_key="job_remaining",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NcSenderSensorDescription(
        key="spindle_rpm",
        translation_key="spindle_rpm",
        icon="mdi:fan",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NcSenderSensorDescription(
        key="feed_rate",
        translation_key="feed_rate",
        icon="mdi:speedometer",
        native_unit_of_measurement="mm/min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NcSenderSensorDescription(
        key="laser_power",
        translation_key="laser_power",
        icon="mdi:laser-pointer",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NcSenderSensorDescription(
        key="alarm",
        translation_key="last_error",
        icon="mdi:alert",
    ),
    NcSenderSensorDescription(
        key="workspace",
        translation_key="workspace",
        icon="mdi:axis-arrow",
        attributes_key="workspace_attributes",
    ),
    NcSenderSensorDescription(
        key="tool",
        translation_key="current_tool",
        icon="mdi:tools",
        attributes_key="tool_attributes",
    ),
    NcSenderSensorDescription(
        key="tool_change",
        translation_key="tool_change",
        icon="mdi:swap-horizontal",
        device_class=SensorDeviceClass.TIMESTAMP,
        attributes_key="tool_change_attributes",
    ),
)

DEFAULT_AXES = "XYZ"


def _position_description(frame: str, letter: str) -> NcSenderSensorDescription:
    """Position sensor for one axis in machine (mpos) or work (wpos) coordinates."""
    label = "Machine" if frame == "mpos" else "Work"
    return NcSenderSensorDescription(
        key=f"{frame}_{letter.lower()}",
        name=f"{label} {letter.upper()}",
        icon="mdi:axis-arrow",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=2,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NcSenderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client = entry.runtime_data
    entities: list[NcSenderSensor] = [NcSenderSensor(entry, d) for d in SENSORS]
    added_axes: set[str] = set()

    def _axis_entities(letters: str) -> list[NcSenderSensor]:
        new: list[NcSenderSensor] = []
        for letter in letters:
            if letter in added_axes:
                continue
            added_axes.add(letter)
            new.append(NcSenderSensor(entry, _position_description("mpos", letter)))
            new.append(NcSenderSensor(entry, _position_description("wpos", letter)))
        return new

    entities.extend(_axis_entities(DEFAULT_AXES))
    async_add_entities(entities)

    # Extra axes (A/B/C rotaries) appear once ncSender reports its axis list.
    @callback
    def _check_axes() -> None:
        axes = client.data.get("axes")
        if axes:
            extra = _axis_entities(axes)
            if extra:
                async_add_entities(extra)

    entry.async_on_unload(client.add_listener(_check_axes))
    _check_axes()


class NcSenderSensor(NcSenderEntity, SensorEntity):
    entity_description: NcSenderSensorDescription

    def __init__(self, entry: NcSenderConfigEntry, description: NcSenderSensorDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        value = self.client.data.get(self._key)
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP and isinstance(value, str):
            return datetime.fromisoformat(value)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_key:
            return self.client.data.get(self.entity_description.attributes_key)
        return None
