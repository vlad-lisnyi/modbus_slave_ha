import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import TemplateSelector
from .const import DOMAIN, CONF_SERIAL_PORT, CONF_BAUDRATE, CONF_SLAVE_ID, CONF_REGISTER_ADDR, CONF_TEMPLATE

class ModbusSlaveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
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
            vol.Optional("write_target"): str  # e.g., climate.living_room.temperature,

        })

        return self.async_show_form(step_id="user", data_schema=schema)
