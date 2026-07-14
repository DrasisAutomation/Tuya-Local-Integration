# Tuya Local Offline Custom Integration for Home Assistant

This is a custom integration for Home Assistant to control Tuya switches locally and offline using the `tinytuya` Python library.

## Installation

1. Copy the `custom_components/tuya_local_offline` folder into your Home Assistant's `config/custom_components/` directory.
   The resulting path should look like:
   `config/custom_components/tuya_local_offline/`
2. Restart Home Assistant.
3. In Home Assistant, go to **Settings** -> **Devices & Services** -> click **Add Integration** -> search for **Tuya Local Offline**.
4. Enter your device's details (Name, ID, Key, IP, and select how many channels/relays it has) in the config flow form.
5. Click **Submit**. The integration will create the device and all switch entities immediately!
