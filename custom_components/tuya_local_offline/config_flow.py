"""Config flow for Tuya Local Offline integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    CONF_LOCAL_KEY,
    CONF_IP,
    CONF_VERSION,
    CONF_CHANNELS,
)

class TuyaLocalOfflineConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya Local Offline."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Cast channels to integer for background operations compatibility
            user_input[CONF_CHANNELS] = int(user_input[CONF_CHANNELS])

            # Check if device is already configured
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()

            # Create entry
            return self.async_create_entry(
                title=user_input.get("name", f"Tuya {user_input[CONF_DEVICE_ID]}"),
                data=user_input,
            )

        # Config flow schema definitions using string-only lists for frontend rendering safety
        data_schema = vol.Schema({
            vol.Required("name", default="Wifi Switch"): str,
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_LOCAL_KEY): str,
            vol.Required(CONF_IP): str,
            vol.Required(CONF_VERSION, default="3.5"): vol.In(["3.5", "3.3", "3.4", "3.1"]),
            vol.Required(CONF_CHANNELS, default="1"): vol.In(["1", "2", "3", "4"]),
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
