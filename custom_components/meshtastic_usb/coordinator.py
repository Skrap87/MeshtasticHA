"""Data update coordinator for the Meshtastic USB integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class UsbDevice:
    """Representation of a USB serial device."""

    device: str
    description: str | None
    hwid: str | None
    manufacturer: str | None
    product: str | None
    serial_number: str | None
    vid: int | None
    pid: int | None
    location: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dictionary with serializable values."""
        data = asdict(self)
        if self.vid is not None:
            data["vid"] = f"0x{self.vid:04x}"
        if self.pid is not None:
            data["pid"] = f"0x{self.pid:04x}"
        return {key: value for key, value in data.items() if value is not None}


class MeshtasticUsbCoordinator(DataUpdateCoordinator[list[UsbDevice]]):
    """Coordinator that queries connected USB serial devices."""

    def __init__(self, hass: HomeAssistant, update_interval: timedelta) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} device scanner",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> list[UsbDevice]:
        """Fetch the latest list of connected USB devices."""
        return await self.hass.async_add_executor_job(_scan_usb_devices)


def _scan_usb_devices() -> list[UsbDevice]:
    """Return the connected USB serial devices."""
    from serial.tools.list_ports import comports

    devices: list[UsbDevice] = []
    for port in comports():
        devices.append(
            UsbDevice(
                device=port.device,
                description=port.description,
                hwid=port.hwid,
                manufacturer=getattr(port, "manufacturer", None),
                product=getattr(port, "product", None),
                serial_number=getattr(port, "serial_number", None),
                vid=getattr(port, "vid", None),
                pid=getattr(port, "pid", None),
                location=getattr(port, "location", None),
            )
        )
    return devices
