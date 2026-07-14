"""Support for Tuya Local Offline Switch platform."""
import logging
import time
import threading
import tinytuya

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    CONF_LOCAL_KEY,
    CONF_IP,
    CONF_VERSION,
    CONF_CHANNELS,
)

_LOGGER = logging.getLogger(__name__)

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
    dev.set_version(float(version))

    # Thread lock to prevent concurrent socket connection collisions on the same device
    device_lock = threading.Lock()

    # Shared state cache between channels to avoid redundant network polling
    state_cache = {"dps": {}, "connected": False, "last_updated": 0}

    # Poll device status safely in executor thread with rate limiting and socket lock
    def poll_device():
        now = time.time()
        # Rate limit polls to once every 5 seconds
        if now - state_cache["last_updated"] < 5:
            return True
            
        with device_lock:
            try:
                status = dev.status()
                if status and "dps" in status:
                    state_cache["dps"] = status["dps"]
                    state_cache["connected"] = True
                    state_cache["last_updated"] = now
                    return True
            except Exception as err:
                _LOGGER.debug("Error polling Tuya device %s: %s", device_id, err)
        
        # Mark offline only if connection has been failing for a while (15s)
        if now - state_cache["last_updated"] > 15:
            state_cache["connected"] = False
        return False

    entities = []
    for channel in range(1, channels + 1):
        entities.append(
            TuyaLocalOfflineSwitch(
                dev,
                device_id,
                local_key,
                ip,
                name,
                channel,
                state_cache,
                poll_device,
                device_lock,
                hass,
            )
        )

    async_add_entities(entities, update_before_add=True)


class TuyaLocalOfflineSwitch(SwitchEntity):
    """Representation of a Tuya Local Offline Switch Channel."""

    def __init__(
        self,
        device,
        device_id,
        local_key,
        ip,
        device_name,
        channel,
        state_cache,
        poll_fn,
        device_lock,
        hass,
    ):
        """Initialize the switch."""
        self._device = device
        self._device_id = device_id
        self._local_key = local_key
        self._ip = ip
        self._device_name = device_name
        self._channel = channel
        self._state_cache = state_cache
        self._poll_fn = poll_fn
        self._device_lock = device_lock
        self._hass = hass

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
        dps = self._state_cache["dps"]
        # Safe check for both integer and string representation of the DPS channel key
        return dps.get(self._channel, dps.get(str(self._channel), False))

    @property
    def available(self) -> bool:
        """Return true if device is connected and available."""
        return self._state_cache["connected"]

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        def set_on():
            with self._device_lock:
                try:
                    # Prefer generic set_value which works directly on any DPS key type
                    self._device.set_value(self._channel, True)
                except Exception:
                    self._device.set_status(True, self._channel)
        
        await self._hass.async_add_executor_job(set_on)
        # Update both integer and string keys in cache for instant UI state feedback
        self._state_cache["dps"][self._channel] = True
        self._state_cache["dps"][str(self._channel)] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        def set_off():
            with self._device_lock:
                try:
                    self._device.set_value(self._channel, False)
                except Exception:
                    self._device.set_status(False, self._channel)
            
        await self._hass.async_add_executor_job(set_off)
        # Update both integer and string keys in cache for instant UI state feedback
        self._state_cache["dps"][self._channel] = False
        self._state_cache["dps"][str(self._channel)] = False
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity state."""
        await self._hass.async_add_executor_job(self._poll_fn)
