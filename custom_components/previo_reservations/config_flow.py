# custom_components/previo_reservations/config_flow.py

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN

class PrevioReservationsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Previo Reservations integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            # Data are provided, create the entry
            return self.async_create_entry(title="Previo Reservations", data=user_input)

        # Define the schema for the user form
        data_schema = vol.Schema({
            vol.Required("username"): str,
            vol.Required("password"): str,
            vol.Required("hotel_id"): str,
            vol.Optional("rooms", default="14,32,21,27"): str,
        })

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )
