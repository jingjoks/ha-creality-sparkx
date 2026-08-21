"""Config flow for the Creality SPARKX integration."""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_HOST, DOMAIN, INFO_PATH

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def _async_validate_host(hass, host: str) -> dict[str, Any]:
    """Hit the printer's /info endpoint to confirm it's reachable and get its serial."""
    session = async_get_clientsession(hass)
    url = f"http://{host}{INFO_PATH}"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
        resp.raise_for_status()
        text = await resp.text()
        return json.loads(text)


class CrealitySparkXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Creality SPARKX."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                info = await _async_validate_host(self.hass, host)
            except (aiohttp.ClientError, TimeoutError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                serial = info.get("sn") or host
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Creality {info.get('model', 'SPARKX')} ({host})",
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
