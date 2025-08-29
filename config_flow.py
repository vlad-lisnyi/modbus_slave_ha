import json
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import TemplateSelector
from .const import DOMAIN, CONF_SERIAL_PORT, CONF_BAUDRATE, CONF_SLAVE_ID, CONF_REGISTER_ADDR, CONF_TEMPLATE, CONF_VALUE_MAP

class ModbusSlaveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Process value_map JSON string if provided
            if user_input.get(CONF_VALUE_MAP):
                try:
                    user_input[CONF_VALUE_MAP] = json.loads(user_input[CONF_VALUE_MAP])
                except json.JSONDecodeError:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=vol.Schema({
                            vol.Required(CONF_SERIAL_PORT, default=user_input.get(CONF_SERIAL_PORT, '/dev/ttyUSB0')): str,
                            vol.Required(CONF_BAUDRATE, default=user_input.get(CONF_BAUDRATE, 9600)): int,
                            vol.Required(CONF_SLAVE_ID, default=user_input.get(CONF_SLAVE_ID, 10)): int,
                            vol.Required(CONF_REGISTER_ADDR, default=user_input.get(CONF_REGISTER_ADDR, 0)): int,
                            vol.Required(CONF_TEMPLATE, default=user_input.get(CONF_TEMPLATE, "{{ 0 }}")): TemplateSelector(),
                            vol.Optional("write_target", default=user_input.get("write_target", "")): str,
                            vol.Optional(CONF_VALUE_MAP, default=user_input.get(CONF_VALUE_MAP, "")): str,
                        }),
                        errors={"value_map": "invalid_json"}
                    )
            
            slave_id = user_input[CONF_SLAVE_ID]
            register_addr = user_input[CONF_REGISTER_ADDR]
            title = f"Slave ID {slave_id} | Register {register_addr}"
            return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_SERIAL_PORT, default='/dev/ttyUSB0'): str,
            vol.Required(CONF_BAUDRATE, default=9600): int,
            vol.Required(CONF_SLAVE_ID, default=10): int,
            vol.Required(CONF_REGISTER_ADDR, default=0): int,
            vol.Required(CONF_TEMPLATE, default="{{ 0 }}"): TemplateSelector(),
            vol.Optional("write_target"): str,  # e.g., climate.living_room.temperature
            vol.Optional(CONF_VALUE_MAP): str,  # JSON string mapping, e.g. {"off":0, "heat":1, "cool":2}

        })

        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return ModbusSlaveOptionsFlow(config_entry)


class ModbusSlaveOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Modbus Slave."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Process value_map JSON string if provided
            if user_input.get(CONF_VALUE_MAP):
                try:
                    user_input[CONF_VALUE_MAP] = json.loads(user_input[CONF_VALUE_MAP])
                except json.JSONDecodeError:
                    current_template = user_input.get(CONF_TEMPLATE, self.config_entry.data.get(CONF_TEMPLATE, "{{ 0 }}"))
                    current_write_target = user_input.get("write_target", self.config_entry.data.get("write_target", ""))
                    return self.async_show_form(
                        step_id="init",
                        data_schema=vol.Schema({
                            vol.Required(CONF_TEMPLATE, default=current_template): TemplateSelector(),
                            vol.Optional("write_target", default=current_write_target): str,
                            vol.Optional(CONF_VALUE_MAP, default=user_input.get(CONF_VALUE_MAP, "")): str,
                        }),
                        errors={"value_map": "invalid_json"}
                    )
            
            # Update the entry with new options
            return self.async_create_entry(title="", data=user_input)

        # Get current values from the config entry
        current_template = self.config_entry.data.get(CONF_TEMPLATE, "{{ 0 }}")
        current_write_target = self.config_entry.data.get("write_target", "")
        current_value_map = self.config_entry.data.get(CONF_VALUE_MAP, "")
        
        # Convert dict value_map back to JSON string for display
        if isinstance(current_value_map, dict):
            current_value_map = json.dumps(current_value_map)

        schema = vol.Schema({
            vol.Required(CONF_TEMPLATE, default=current_template): TemplateSelector(),
            vol.Optional("write_target", default=current_write_target): str,
            vol.Optional(CONF_VALUE_MAP, default=current_value_map): str,
        })

        return self.async_show_form(step_id="init", data_schema=schema)
