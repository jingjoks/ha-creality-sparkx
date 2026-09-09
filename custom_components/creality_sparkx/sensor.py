"""Sensor entities for the Creality SPARKX integration."""
from __future__ import annotations

import logging

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfMass,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MANUFACTURER, DOMAIN, PRINTER_STATE_MAP
from .coordinator import CrealitySparkXCoordinator

_LOGGER = logging.getLogger(__name__)


def _to_float(raw: Any) -> float | None:
    """Printer reports several temps/speeds as numeric strings like '28.720000'."""
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class CrealitySensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any] = lambda data: None


SENSOR_DESCRIPTIONS: tuple[CrealitySensorDescription, ...] = (
    CrealitySensorDescription(
        key="nozzle_temperature",
        translation_key="nozzle_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _to_float(d.get("nozzleTemp")),
    ),
    CrealitySensorDescription(
        key="nozzle_target_temperature",
        translation_key="nozzle_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _to_float(d.get("targetNozzleTemp")),
    ),
    CrealitySensorDescription(
        key="bed_temperature",
        translation_key="bed_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _to_float(d.get("bedTemp0")),
    ),
    CrealitySensorDescription(
        key="bed_target_temperature",
        translation_key="bed_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _to_float(d.get("targetBedTemp0")),
    ),
    CrealitySensorDescription(
        key="print_progress",
        translation_key="print_progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d",
        value_fn=lambda d: d.get("printProgress"),
    ),
    CrealitySensorDescription(
        key="print_state",
        translation_key="print_state",
        icon="mdi:printer-3d-nozzle",
        device_class=SensorDeviceClass.ENUM,
        options=list(set(PRINTER_STATE_MAP.values())),
        value_fn=lambda d: PRINTER_STATE_MAP.get(d.get("state"), "unknown"),
    ),
    CrealitySensorDescription(
        key="current_file",
        translation_key="current_file",
        icon="mdi:file-outline",
        value_fn=lambda d: d.get("printFileName") or None,
    ),
    CrealitySensorDescription(
        key="current_layer",
        translation_key="current_layer",
        icon="mdi:layers-outline",
        value_fn=lambda d: d.get("layer"),
    ),
    CrealitySensorDescription(
        key="total_layers",
        translation_key="total_layers",
        icon="mdi:layers",
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("TotalLayer"),
    ),
    CrealitySensorDescription(
        key="print_time_elapsed",
        translation_key="print_time_elapsed",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("printJobTime"),
    ),
    CrealitySensorDescription(
        key="print_time_remaining",
        translation_key="print_time_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda d: d.get("printLeftTime"),
    ),
    CrealitySensorDescription(
        key="lifetime_material_used",
        translation_key="lifetime_material_used",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("allPrintMaterial"),
    ),
    CrealitySensorDescription(
        key="lifetime_print_time",
        translation_key="lifetime_print_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("allPrintTime"),
    ),
    CrealitySensorDescription(
        key="model_fan_speed",
        translation_key="model_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        icon="mdi:fan",
        value_fn=lambda d: d.get("modelFanPct"),
    ),
    CrealitySensorDescription(
        key="case_fan_speed",
        translation_key="case_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        icon="mdi:fan",
        value_fn=lambda d: d.get("caseFanPct"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CrealitySparkXCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        CrealitySparkXSensor(coordinator, entry, desc) for desc in SENSOR_DESCRIPTIONS
    ]
    entities.append(CrealitySparkXIPSensor(coordinator, entry))
    async_add_entities(entities)


class CrealitySparkXSensor(CoordinatorEntity[CrealitySparkXCoordinator], SensorEntity):
    entity_description: CrealitySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CrealitySparkXCoordinator,
        entry: ConfigEntry,
        description: CrealitySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer=DEVICE_MANUFACTURER,
            model=coordinator.data.get("model", "SPARKX i7"),
            name=coordinator.data.get("hostname", entry.title),
            sw_version=coordinator.data.get("modelVersion"),
        )

    @property
    def available(self) -> bool:
        return self.coordinator.available

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)


class CrealitySparkXIPSensor(CoordinatorEntity[CrealitySparkXCoordinator], SensorEntity):
    """Static sensor showing the printer's configured IP address."""

    _attr_has_entity_name = True
    _attr_translation_key = "ip_address"
    _attr_icon = "mdi:ip-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CrealitySparkXCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_ip_address"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer=DEVICE_MANUFACTURER,
            model=coordinator.data.get("model", "SPARKX i7"),
            name=coordinator.data.get("hostname", entry.title),
            sw_version=coordinator.data.get("modelVersion"),
        )

    @property
    def available(self) -> bool:
        # IP is static/known from config even if the printer is offline.
        return True

    @property
    def native_value(self):
        return self.coordinator.host
