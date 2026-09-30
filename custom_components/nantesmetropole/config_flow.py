"""Config flow for Nantes Métropole integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import slugify

from .api import NantesMetropoleApi
from .const import (
    CONF_INFRASTRUCTURE_TYPE,
    CONF_INFRASTRUCTURES,
    DOMAIN,
    INFRASTRUCTURE_TYPES,
)


def _type_schema(default: str | None = None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_INFRASTRUCTURE_TYPE,
                default=default or INFRASTRUCTURE_TYPES[0],
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=infra_type, label=infra_type)
                        for infra_type in INFRASTRUCTURE_TYPES
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _infrastructures_schema(
    infrastructures: list[str], current: list[str] | None = None
) -> vol.Schema:
    default = current or []
    return vol.Schema(
        {
            vol.Required(CONF_INFRASTRUCTURES, default=default): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=infrastructure, label=infrastructure)
                        for infrastructure in infrastructures
                    ],
                    mode=SelectSelectorMode.LIST,
                    multiple=True,
                )
            )
        }
    )


class NantesMetropoleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Nantes Métropole."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow state."""
        self._infra_type: str = ""
        self._available_infrastructures: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle infrastructure type selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            infra_type = str(user_input.get(CONF_INFRASTRUCTURE_TYPE) or "")
            if not infra_type:
                errors["base"] = "invalid_type"
            elif self._is_type_already_configured(infra_type):
                return self.async_abort(reason="type_already_configured")
            else:
                self._infra_type = infra_type
                api = NantesMetropoleApi(async_get_clientsession(self.hass))
                infrastructures = await api.async_fetch_infrastructures(infra_type)
                self._available_infrastructures = [
                    infrastructure.name for infrastructure in infrastructures
                ]
                if not self._available_infrastructures:
                    errors["base"] = "no_infrastructure"
                else:
                    return await self.async_step_select_infrastructures()

        return self.async_show_form(
            step_id="user",
            data_schema=_type_schema(),
            errors=errors,
        )

    async def async_step_select_infrastructures(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle infrastructures selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input.get(CONF_INFRASTRUCTURES, [])
            if selected:
                return self.async_create_entry(
                    title=f"Nantes Métropole - {self._infra_type}",
                    data={CONF_INFRASTRUCTURE_TYPE: self._infra_type},
                    options={CONF_INFRASTRUCTURES: selected},
                )
            errors["base"] = "no_infrastructure_selected"

        return self.async_show_form(
            step_id="select_infrastructures",
            data_schema=_infrastructures_schema(self._available_infrastructures),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return options flow."""
        return NantesMetropoleOptionsFlow(config_entry)

    def _is_type_already_configured(self, infra_type: str) -> bool:
        for entry in self._async_current_entries():
            if entry.data.get(CONF_INFRASTRUCTURE_TYPE) == infra_type:
                return True
        return False


class NantesMetropoleOptionsFlow(OptionsFlow):
    """Handle options flow for Nantes Métropole."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage integration options."""
        errors: dict[str, str] = {}

        infra_type = str(self.config_entry.data.get(CONF_INFRASTRUCTURE_TYPE) or "")
        current = list(self.config_entry.options.get(CONF_INFRASTRUCTURES, []))

        api = NantesMetropoleApi(async_get_clientsession(self.hass))
        infrastructures = await api.async_fetch_infrastructures(infra_type)
        names = [infrastructure.name for infrastructure in infrastructures]

        if user_input is not None:
            selected = list(user_input.get(CONF_INFRASTRUCTURES, []))
            if not selected:
                errors["base"] = "no_infrastructure_selected"
            else:
                await self._async_remove_stale_devices(infra_type, current, selected)
                return self.async_create_entry(
                    title="",
                    data={CONF_INFRASTRUCTURES: selected},
                )

        return self.async_show_form(
            step_id="init",
            data_schema=_infrastructures_schema(names, current),
            errors=errors,
        )

    async def _async_remove_stale_devices(
        self, infra_type: str, current: list[str], selected: list[str]
    ) -> None:
        """Detach stale infrastructure devices from this config entry."""
        stale = [name for name in current if name not in selected]
        if not stale:
            return

        device_registry = dr.async_get(self.hass)
        for name in stale:
            identifier = (DOMAIN, f"{slugify(infra_type)}:{slugify(name)}")
            device = device_registry.async_get_device(identifiers={identifier})
            if device:
                device_registry.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )
