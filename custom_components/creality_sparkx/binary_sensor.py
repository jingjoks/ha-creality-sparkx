"""Binary sensor entities for the Creality SPARKX integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MANUFACTURER, DOMAIN, ERROR_CODE_MAP
from .coordinator import CrealitySparkXCoordinator


@dataclass(frozen=True, kw_only=True)
class CrealityBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None] = lambda data: None


BINARY_SENSOR_DESCRIPTIONS: tuple[CrealityBinarySensorDescription, ...] = (
    CrealityBinarySensorDescription(
        key="filament_present",
        translation_key="filament_present",
        icon="mdi:printer-3d-nozzle-outline",
        value_fn=lambda d: bool(d.get("materialStatus")),
    ),
    CrealityBinarySensorDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: bool((d.get("err") or {}).get("errcode", 0)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CrealitySparkXCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        CrealitySparkXBinarySensor(coordinator, entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
    ]
    entities.append(CrealitySparkXConnectivitySensor(coordinator, entry))
    async_add_entities(entities)


class CrealitySparkXBinarySensor(
    CoordinatorEntity[CrealitySparkXCoordinator], BinarySensorEntity
):
    entity_description: CrealityBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CrealitySparkXCoordinator,
        entry: ConfigEntry,
        description: CrealityBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer=DEVICE_MANUFACTURER,
            model=coordinator.data.get("model", "SPARKX i7"),
            name=coordinator.data.get("hostname", entry.title),
        )

    @property
    def available(self) -> bool:
        return self.coordinator.available

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        if self.entity_description.key != "problem":
            return None
        err = self.coordinator.data.get("err") or {}
        code = err.get("value") or None
        return {
            "code": code,
            "description": ERROR_CODE_MAP.get(code, "Unknown error code" if code else None),
            "errcode": err.get("errcode"),
            "key": err.get("key"),
            "retry": err.get("retry"),
        }


class CrealitySparkXConnectivitySensor(
    CoordinatorEntity[CrealitySparkXCoordinator], BinarySensorEntity
):
    """Reports whether the WebSocket link to the printer is currently up.

    Unlike other binary sensors this one is intentionally always
    'available' (its whole purpose is to report the connection state).
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "connectivity"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CrealitySparkXCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_connectivity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer=DEVICE_MANUFACTURER,
            model=coordinator.data.get("model", "SPARKX i7"),
            name=coordinator.data.get("hostname", entry.title),
        )

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.available
