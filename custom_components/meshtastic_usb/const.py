"""Constants for the Meshtastic USB integration."""

from datetime import timedelta
from homeassistant.const import Platform

DOMAIN = "meshtastic_usb"
PLATFORMS: list[Platform] = [Platform.SENSOR]
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

ATTR_DEVICES = "devices"
