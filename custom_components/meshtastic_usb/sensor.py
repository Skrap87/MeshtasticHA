"""Sensor platform for the Meshtastic USB integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DEVICES, DOMAIN
from .coordinator import MeshtasticUsbCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Meshtastic USB sensor."""
    coordinator: MeshtasticUsbCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MeshtasticUsbSensor(coordinator)], True)


class MeshtasticUsbSensor(CoordinatorEntity[MeshtasticUsbCoordinator], SensorEntity):
    """Sensor that exposes connected USB devices."""

    _attr_icon = "mdi:usb-port"
    _attr_name = "Meshtastic USB devices"
    _attr_native_unit_of_measurement = "devices"
    _attr_unique_id = "meshtastic_usb_devices"

    @property
    def native_value(self) -> int:
        """Return the number of connected USB devices."""
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, list[dict[str, str]]]:
        """Return details about the connected USB devices."""
        devices = []
        for device in self.coordinator.data or []:
            devices.append(device.as_dict())
        return {ATTR_DEVICES: devices}
