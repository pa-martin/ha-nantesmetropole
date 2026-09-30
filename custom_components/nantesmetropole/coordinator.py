"""Coordinator for Nantes Métropole integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import InfrastructureState, NantesMetropoleApi
from .const import (
    CONF_INFRASTRUCTURE_TYPE,
    CONF_INFRASTRUCTURES,
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class NantesMetropoleCoordinator(DataUpdateCoordinator[dict[str, InfrastructureState]]):
    """Handle polling and aggregation for configured infrastructures."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._api = NantesMetropoleApi(async_get_clientsession(hass))

    @property
    def infrastructure_type(self) -> str:
        """Return configured infrastructure type."""
        return str(self.config_entry.data.get(CONF_INFRASTRUCTURE_TYPE) or "")

    @property
    def selected_infrastructures(self) -> list[str]:
        """Return selected infrastructure names."""
        selected = self.config_entry.options.get(
            CONF_INFRASTRUCTURES,
            self.config_entry.data.get(CONF_INFRASTRUCTURES, []),
        )
        return [name for name in selected if isinstance(name, str)]

    async def _async_update_data(self) -> dict[str, InfrastructureState]:
        """Fetch state for all selected infrastructures."""
        try:
            if not self.infrastructure_type:
                return {}

            available = await self._api.async_fetch_infrastructures(self.infrastructure_type)
            by_name = {item.name: item for item in available}

            now_dt = dt_util.as_local(dt_util.utcnow())
            data: dict[str, InfrastructureState] = {}
            for name in self.selected_infrastructures:
                infrastructure = by_name.get(name)
                if infrastructure is None:
                    continue
                state = await self._api.async_fetch_infrastructure_state(
                    infrastructure, now_dt
                )
                data[name] = state

            if not data:
                raise UpdateFailed("No infrastructure data available")

            return data
        except UpdateFailed:
            raise
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(err) from err
