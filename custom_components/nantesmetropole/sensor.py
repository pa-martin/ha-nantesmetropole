"""Sensor platform for Nantes Métropole infrastructures."""

from __future__ import annotations

from typing import Any, ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .api import InfrastructureState
from .const import CONF_INFRASTRUCTURES, DOMAIN
from .coordinator import NantesMetropoleCoordinator


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nantes Métropole entities based on config entry."""
    coordinator: NantesMetropoleCoordinator = entry.runtime_data
    selected = entry.options.get(
        CONF_INFRASTRUCTURES,
        entry.data.get(CONF_INFRASTRUCTURES, []),
    )

    async_add_entities(
        [NantesMetropoleInfrastructureSensor(coordinator, entry, name) for name in selected],
        True,
    )


class NantesMetropoleInfrastructureSensor(
    CoordinatorEntity[NantesMetropoleCoordinator], SensorEntity
):
    """Representation of one infrastructure state sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "infrastructure_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_icon = "mdi:office-building-marker"
    _attr_options: ClassVar[tuple[str, ...]] = ("open", "closed", "unknown")

    def __init__(
        self,
        coordinator: NantesMetropoleCoordinator,
        entry: ConfigEntry,
        infrastructure_name: str,
    ) -> None:
        """Initialize sensor entity."""
        super().__init__(coordinator)
        self._name = infrastructure_name
        self._infra_type = coordinator.infrastructure_type
        self._slug = f"{slugify(self._infra_type)}:{slugify(self._name)}"
        self._attr_unique_id = f"{entry.entry_id}_{self._slug}"
        self._attr_name = self._name

    @property
    def _state_data(self) -> InfrastructureState | None:
        return self.coordinator.data.get(self._name)

    @property
    def native_value(self) -> str:
        """Return open/closed state."""
        data = self._state_data
        if data is None:
            return "unknown"
        return "open" if data.is_open else "closed"

    @property
    def available(self) -> bool:
        """Return whether entity is available."""
        return super().available and self._state_data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self._state_data
        if data is None:
            return {}

        schedules = [
            f"{opening_range.start}-{opening_range.end}"
            for opening_range in data.opening_ranges
        ]
        attrs: dict[str, Any] = {
            "is_open": data.is_open,
            "infrastructure_type": self._infra_type,
            "opening_hours_today": schedules,
            "opening_hours_today_text": " | ".join(schedules),
            "address": data.infrastructure.address,
        }

        if data.infrastructure.latitude is not None:
            attrs["latitude"] = data.infrastructure.latitude
        if data.infrastructure.longitude is not None:
            attrs["longitude"] = data.infrastructure.longitude

        return attrs

    @property
    def latitude(self) -> float | None:
        """Return infrastructure latitude for map display."""
        data = self._state_data
        return None if data is None else data.infrastructure.latitude

    @property
    def longitude(self) -> float | None:
        """Return infrastructure longitude for map display."""
        data = self._state_data
        return None if data is None else data.infrastructure.longitude

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        data = self._state_data
        manufacturer = "Nantes Métropole"
        model = self._infra_type
        if data is not None:
            model = data.infrastructure.infra_type

        return DeviceInfo(
            identifiers={(DOMAIN, self._slug)},
            name=self._name,
            manufacturer=manufacturer,
            model=model,
            entry_type=DeviceEntryType.SERVICE,
        )
