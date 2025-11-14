# Meshtastic Home Assistant Integration

This repository provides a custom Home Assistant integration that discovers USB devices connected to a Home Assistant OS installation and exposes them as a sensor entity. The sensor reports how many compatible USB devices are available and adds their details as sensor attributes.

## Installation

1. Copy the `custom_components/meshtastic_usb` folder into the `custom_components` directory of your Home Assistant configuration. If the directory does not exist, create it.
2. Restart Home Assistant.
3. In Home Assistant, navigate to **Settings → Devices & Services → Integrations** and click **Add Integration**.
4. Search for **Meshtastic USB** and complete the setup wizard.

After setup, the integration will create a sensor named **Meshtastic USB devices**. The sensor value is the number of connected USB serial devices, and its attributes include detailed information for each device (port, description, vendor/product IDs, etc.).
