"""Constants for the Meshtastic USB integration."""

from datetime import timedelta
from homeassistant.const import Platform

DOMAIN = "meshtastic_usb"
PLATFORMS: list[Platform] = [Platform.SENSOR]
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

ATTR_DEVICES = "devices"
ATTR_NODE = "node"
ATTR_USB = "usb"
ATTR_ERROR = "error"

SENSOR_FIRMWARE = "firmware"
SENSOR_NODE_ID = "node_id"
SENSOR_CHANNEL = "channel"
SENSOR_RSSI = "rssi"
SENSOR_SNR = "snr"
SENSOR_LAST_MESSAGE = "last_message"

# Known Meshtastic-compatible USB VID/PID pairs
MESHTASTIC_VID_PID: set[tuple[int, int]] = {
    (0x10C4, 0xEA60),  # CP2102
    (0x1A86, 0x7523),  # CH340
    (0x1A86, 0x55D4),  # CH9102
    (0x239A, 0x8029),  # RAK4631 (UF2 bootloader)
    (0x239A, 0x8109),  # RAK4631 (firmware)
    (0x2886, 0x0045),  # XIAO nRF52840
    (0x2886, 0x0046),  # XIAO RP2040
}

IGNORED_PORT_PREFIXES: tuple[str, ...] = ("/dev/ttyS",)
