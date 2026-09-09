"""The Creality SPARKX integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CAMERA_PORT,
    CONF_HOST,
    CONF_MOONRAKER_PORT,
    CONF_POWER_SWITCH_ENTITY_ID,
    DEFAULT_CAMERA_PORT,
    DEFAULT_MOONRAKER_PORT,
    DOMAIN,
)
from .coordinator import CrealitySparkXCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "button", "image", "camera"]

CARD_URL_PATH = "/creality_sparkx_card"
CARD_JS_FILENAME = "creality-sparkx-card.js"
_card_registered = False


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card and register it with the frontend.

    Runs once per HA process (not once per config entry) - registering the
    same static path twice raises.
    """
    global _card_registered
    if _card_registered:
        return
    www_dir = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(www_dir), cache_headers=False)]
    )
    add_extra_js_url(hass, f"{CARD_URL_PATH}/{CARD_JS_FILENAME}")
    _card_registered = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Creality SPARKX from a config entry."""
    host = entry.data[CONF_HOST]
    coordinator = CrealitySparkXCoordinator(
        hass,
        host,
        moonraker_port=entry.options.get(CONF_MOONRAKER_PORT, DEFAULT_MOONRAKER_PORT),
        camera_port=entry.options.get(CONF_CAMERA_PORT, DEFAULT_CAMERA_PORT),
        power_switch_entity_id=entry.options.get(CONF_POWER_SWITCH_ENTITY_ID),
    )
    await coordinator.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await _async_register_card(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change (e.g. power switch binding)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: CrealitySparkXCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
    return unload_ok
