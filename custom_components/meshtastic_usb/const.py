"""Constants for the Meshtastic integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "meshtastic_usb"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_CONNECTION_TYPE = "connection_type"
CONNECTION_TYPE_SERIAL = "serial"
CONNECTION_TYPE_TCP = "tcp"

CONF_SERIAL_PORT = "serial_port"
AUTODETECT_SERIAL = "auto"

CONF_TCP_HOST = "tcp_host"
CONF_TCP_PORT = "tcp_port"

CONF_UPDATE_INTERVAL = "update_interval"
DEFAULT_UPDATE_INTERVAL = 30  # seconds

DEFAULT_TCP_PORT = 4403

DEFAULT_SCAN_INTERVAL = timedelta(seconds=DEFAULT_UPDATE_INTERVAL)

ATTR_DEVICES = "devices"
ATTR_NODE = "node"
ATTR_USB = "usb"
ATTR_TCP = "tcp"
ATTR_ERROR = "error"

SENSOR_FIRMWARE = "firmware"
SENSOR_NODE_ID = "node_id"
SENSOR_CHANNEL = "channel"
SENSOR_RSSI = "rssi"
SENSOR_SNR = "snr"
SENSOR_LAST_MESSAGE = "last_message"
SENSOR_BATTERY_LEVEL = "battery_level"
SENSOR_BATTERY_VOLTAGE = "battery_voltage"
SENSOR_TEMPERATURE = "temperature"
SENSOR_UPTIME = "uptime"

SERVICE_SEND_MESSAGE = "send_message"
SERVICE_REBOOT = "reboot"
SERVICE_SET_CHANNEL = "set_channel"
SERVICE_REFRESH = "refresh"

ATTR_TARGET = "target"
ATTR_MESSAGE = "message"
ATTR_CHANNEL_NAME = "channel_name"
ATTR_ENTRY_ID = "entry_id"

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
