"""Switch entities for the Creality SPARKX integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MANUFACTURER, DOMAIN
from .coordinator import CrealitySparkXCoordinator

LIGHT_SWITCH = SwitchEntityDescription(
    key="chamber_light",
    translation_key="chamber_light",
    icon="mdi:lightbulb",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CrealitySparkXCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CrealitySparkXLightSwitch(coordinator, entry)])


class CrealitySparkXLightSwitch(
    CoordinatorEntity[CrealitySparkXCoordinator], SwitchEntity
):
    """Chamber/case light. Confirmed working via {"lightSw": 0|1} over the WS."""

    entity_description = LIGHT_SWITCH
    _attr_has_entity_name = True

    def __init__(self, coordinator: CrealitySparkXCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_chamber_light"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer=DEVICE_MANUFACTURER,
            model=coordinator.data.get("model", "SPARKX i7"),
            name=coordinator.data.get("hostname", entry.title),
        )

    @property
    def available(self) -> bool:
        return self.coordinator.available and self.coordinator.printer_powered_on

    @property
    def is_on(self) -> bool | None:
        val = self.coordinator.data.get("lightSw")
        return None if val is None else bool(val)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command({"lightSw": 1})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command({"lightSw": 0})
