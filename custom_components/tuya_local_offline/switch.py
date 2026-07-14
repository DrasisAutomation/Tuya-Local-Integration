"""Support for Tuya Local Offline Switch platform."""
import logging
from datetime import timedelta
import tinytuya

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    CONF_LOCAL_KEY,
    CONF_IP,
    CONF_VERSION,
    CONF_CHANNELS,
)

_LOGGER = logging.getLogger(__name__)

# Force Home Assistant to poll the switch states every 5 seconds instead of the default 30 seconds
SCAN_INTERVAL = timedelta(seconds=5)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tuya Local Switch platform."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    
    device_id = config[CONF_DEVICE_ID]
    local_key = config[CONF_LOCAL_KEY]
    ip = config[CONF_IP]
    version = config[CONF_VERSION]
    channels = config[CONF_CHANNELS]
    name = config_entry.title

    # Initialize tinytuya OutletDevice
    dev = tinytuya.OutletDevice(device_id, ip, local_key)
    try:
        float_version = float(version)
    except ValueError:
        float_version = 3.5
    dev.set_version(float_version)
    
    # Configure tinytuya to keep a persistent TCP socket open.
    # This prevents the overhead of opening/closing sockets on every single command or poll,
    # which overloads the Tuya micro-controller and causes connection refused/unavailable status drops.
    dev.set_socketPersistent(True)
    dev.set_socketTimeout(3) # Short timeout to fail-fast if device drops off network

    async def async_update_data():
        """Fetch status from Tuya device using executor thread."""
        try:
            status = await hass.async_add_executor_job(dev.status)
            if isinstance(status, dict) and "dps" in status:
                # Merge and normalize keys (both string and integer representation)
                normalized_dps = {}
                for k, v in status["dps"].items():
                    normalized_dps[k] = v
                    normalized_dps[str(k)] = v
                    try:
                        normalized_dps[int(k)] = v
                    except ValueError:
                        pass
                return normalized_dps
            raise UpdateFailed("Invalid status format returned from Tuya device")
        except Exception as err:
            raise UpdateFailed(f"Error communicating with local Tuya device: {err}")

    # Use Home Assistant's official DataUpdateCoordinator to poll once every 5 seconds
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=timedelta(seconds=5),
    )

    # Initialize with empty data so entities can load even if the device is momentarily offline during boot
    coordinator.data = {}

    # Attempt first update but catch errors gracefully so integration setup always succeeds
    try:
        await coordinator.async_refresh()
    except Exception as err:
        _LOGGER.warning("Initial update failed for local Tuya device %s (will retry): %s", device_id, err)

    entities = []
    for channel in range(1, channels + 1):
        entities.append(
            TuyaLocalOfflineSwitch(
                coordinator,
                dev,
                channel,
                name,
                device_id,
            )
        )

    async_add_entities(entities)


class TuyaLocalOfflineSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Tuya Local Offline Switch Channel."""

    def __init__(self, coordinator, device, channel, device_name, device_id):
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device = device
        self._channel = channel
        self._device_id = device_id

        self._attr_name = f"{device_name} Switch {channel}"
        self._attr_unique_id = f"tuya_local_offline_{device_id}_{channel}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "Tuya",
            "model": "Local Switch Module",
        }

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        dps = self.coordinator.data
        if dps is None:
            return False
        # Safe check for both integer and string representation of the DPS channel key
        return dps.get(self._channel, dps.get(str(self._channel), False))

    @property
    def available(self) -> bool:
        """Return true if device is connected and available."""
        # Simple and standard HA availability check based on last poll success
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        def set_on():
            try:
                # Prefer generic set_value which works directly on any DPS key type
                self._device.set_value(self._channel, True)
            except Exception:
                self._device.set_status(True, self._channel)
        
        await self.hass.async_add_executor_job(set_on)
        # Update cache data for instant state feedback in Home Assistant UI
        if self.coordinator.data is not None:
            self.coordinator.data[self._channel] = True
            self.coordinator.data[str(self._channel)] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        def set_off():
            try:
                self._device.set_value(self._channel, False)
            except Exception:
                self._device.set_status(False, self._channel)
            
        await self.hass.async_add_executor_job(set_off)
        # Update cache data for instant state feedback in Home Assistant UI
        if self.coordinator.data is not None:
            self.coordinator.data[self._channel] = False
            self.coordinator.data[str(self._channel)] = False
        self.async_write_ha_state()
