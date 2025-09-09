import json
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    EntitySelector,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_SERIAL_PORT,
    CONF_BAUDRATE,
    CONF_SLAVE_ID,
    CONF_REGISTER_ADDR,
    CONF_VALUE_MAP,
    CONF_DIRECTION,
    CONF_READ_ENTITY,
    CONF_READ_ATTRIBUTE,
    CONF_SCALE,
    CONF_WRITE_SERVICE,
    CONF_WRITE_ENTITY,
    CONF_WRITE_PAYLOAD,
)


def _shorten(val: str, max_len: int = 32) -> str:
    if len(val) <= max_len:
        return val
    return val[: max_len - 1] + "…"


def _attr_selector(hass, entity_id: str | None):
    """Return a selector (dropdown) for attributes of the given entity, with value previews.

    Always includes a top option: "Use entity state" (empty value), so users can select it explicitly.
    """
    if not entity_id:
        return str
    options = [{"label": "Use entity state", "value": ""}]
    state = hass.states.get(entity_id)
    if state and state.attributes:
        for k in sorted([str(x) for x in state.attributes.keys()]):
            try:
                v = state.attributes.get(k)
                if isinstance(v, (dict, list)):
                    v_preview = _shorten(json.dumps(v, separators=(",", ":")))
                else:
                    v_preview = _shorten(str(v))
            except Exception:
                v_preview = ""
            label = f"{k} = {v_preview}" if v_preview != "" else k
            options.append({"label": label, "value": k})
    return SelectSelector(SelectSelectorConfig(options=options))


def _normalize_direction(value: str | None) -> str:
    """Map legacy direction values to new ones for UI consistency."""
    if not value:
        return "write_only"
    if value in ("write_only",):
        return "write_only"
    if value in ("write_read", "read_write"):
        return "write_read"
    # Legacy read_only behaved like write_only for this integration
    if value in ("read_only",):
        return "write_only"
    return "write_only"


class ModbusSlaveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None):
        """Step 1: Register settings only."""
        if user_input is not None:
            # Save and go to step 2
            self._data.update({
                CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT],
                CONF_BAUDRATE: user_input[CONF_BAUDRATE],
                CONF_SLAVE_ID: user_input[CONF_SLAVE_ID],
                CONF_REGISTER_ADDR: user_input[CONF_REGISTER_ADDR],
            })
            return await self.async_step_source()

        schema = vol.Schema({
            vol.Required(CONF_SERIAL_PORT, default="/dev/ttyUSB0"): str,
            vol.Required(CONF_BAUDRATE, default=9600): int,
            vol.Required(CONF_SLAVE_ID, default=10): int,
            vol.Required(CONF_REGISTER_ADDR, default=0): int,
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_source(self, user_input=None):
        """Step 2: Select entity (input type is implicitly 'entity')."""
        if user_input is not None:
            # Save and proceed
            self._data.update({
                # New semantics: write_only (HA -> register) or write_read (bi-directional)
                CONF_DIRECTION: user_input.get(CONF_DIRECTION, "write_only"),
                CONF_READ_ENTITY: user_input.get(CONF_READ_ENTITY, ""),
            })
            return await self.async_step_details()

        schema = vol.Schema({
            vol.Optional(CONF_DIRECTION, default=_normalize_direction(self._data.get(CONF_DIRECTION))): vol.In(["write_only", "write_read"]),
            vol.Required(CONF_READ_ENTITY, default=self._data.get(CONF_READ_ENTITY, "")): EntitySelector(),
        })
        return self.async_show_form(step_id="source", data_schema=schema)

    async def async_step_details(self, user_input=None):
        """Step 3: Attributes, scaling, value map, and write service/preset."""
        selected_entity = self._data.get(CONF_READ_ENTITY)
        attr_field = _attr_selector(self.hass, selected_entity)

        # Build dynamic service options for the selected entity domain (used in write_read)
        service_options = ["none"]
        if selected_entity and "." in selected_entity:
            domain = selected_entity.split(".", 1)[0]
            all_services = self.hass.services.async_services()
            if domain in all_services:
                service_options += [f"{domain}.{name}" for name in sorted(all_services[domain].keys())]

        if user_input is not None:
            # Parse value map
            errors = {}
            value_map_raw = user_input.get(CONF_VALUE_MAP)
            if value_map_raw:
                try:
                    user_input[CONF_VALUE_MAP] = json.loads(value_map_raw)
                except json.JSONDecodeError:
                    errors[CONF_VALUE_MAP] = "invalid_json"

            # Branch by direction
            if self._data.get(CONF_DIRECTION) == "write_read":
                # Require a write service
                write_service = user_input.get(CONF_WRITE_SERVICE)
                if not write_service or write_service == "none":
                    errors[CONF_WRITE_SERVICE] = "required"

                if errors:
                    return self.async_show_form(
                        step_id="details",
                        data_schema=vol.Schema({
                            vol.Optional(CONF_READ_ATTRIBUTE, default=user_input.get(CONF_READ_ATTRIBUTE, "")): attr_field,
                            vol.Optional(CONF_SCALE, default=user_input.get(CONF_SCALE, 1)): int,
                            vol.Optional(CONF_VALUE_MAP, default=value_map_raw or ""): str,
                            vol.Required(CONF_WRITE_SERVICE, default=user_input.get(CONF_WRITE_SERVICE, "none")): SelectSelector(SelectSelectorConfig(options=service_options)),
                            vol.Optional(CONF_WRITE_ENTITY, default=user_input.get(CONF_WRITE_ENTITY, "")): EntitySelector(),
                            vol.Optional(CONF_WRITE_PAYLOAD, default=user_input.get(CONF_WRITE_PAYLOAD, "")): str,
                        }),
                        errors=errors,
                    )

                # Normalize 'none'
                if user_input.get(CONF_WRITE_SERVICE) == "none":
                    user_input[CONF_WRITE_SERVICE] = ""

                # Merge and create entry
                self._data.update({
                    CONF_READ_ATTRIBUTE: user_input.get(CONF_READ_ATTRIBUTE, ""),
                    CONF_SCALE: user_input.get(CONF_SCALE, 1),
                    CONF_VALUE_MAP: user_input.get(CONF_VALUE_MAP, {}),
                    CONF_WRITE_SERVICE: user_input.get(CONF_WRITE_SERVICE, ""),
                    CONF_WRITE_ENTITY: user_input.get(CONF_WRITE_ENTITY, ""),
                    CONF_WRITE_PAYLOAD: user_input.get(CONF_WRITE_PAYLOAD, ""),
                })
            else:
                # write_only branch: no service fields
                if errors:
                    return self.async_show_form(
                        step_id="details",
                        data_schema=vol.Schema({
                            vol.Optional(CONF_READ_ATTRIBUTE, default=user_input.get(CONF_READ_ATTRIBUTE, "")): attr_field,
                            vol.Optional(CONF_SCALE, default=user_input.get(CONF_SCALE, 1)): int,
                            vol.Optional(CONF_VALUE_MAP, default=value_map_raw or ""): str,
                        }),
                        errors=errors,
                    )

                self._data.update({
                    CONF_READ_ATTRIBUTE: user_input.get(CONF_READ_ATTRIBUTE, ""),
                    CONF_SCALE: user_input.get(CONF_SCALE, 1),
                    CONF_VALUE_MAP: user_input.get(CONF_VALUE_MAP, {}),
                    # ensure write fields are empty in write_only
                    CONF_WRITE_SERVICE: "",
                    CONF_WRITE_ENTITY: "",
                    CONF_WRITE_PAYLOAD: "",
                })

            title = f"Slave ID {self._data.get(CONF_SLAVE_ID, '')} | Register {self._data.get(CONF_REGISTER_ADDR, '')}"
            return self.async_create_entry(title=title, data=self._data)

        # Initial render for details step
        if self._data.get(CONF_DIRECTION) == "write_read":
            schema = vol.Schema({
                vol.Optional(CONF_READ_ATTRIBUTE, default=self._data.get(CONF_READ_ATTRIBUTE, "")): attr_field,
                vol.Optional(CONF_SCALE, default=self._data.get(CONF_SCALE, 1)): int,
                vol.Optional(CONF_VALUE_MAP, default=""): str,
                vol.Required(CONF_WRITE_SERVICE, default="none"): SelectSelector(SelectSelectorConfig(options=service_options)),
                vol.Optional(CONF_WRITE_ENTITY, default=self._data.get(CONF_WRITE_ENTITY, "")): EntitySelector(),
                vol.Optional(CONF_WRITE_PAYLOAD, default=self._data.get(CONF_WRITE_PAYLOAD, "")): str,
            })
        else:
            schema = vol.Schema({
                vol.Optional(CONF_READ_ATTRIBUTE, default=self._data.get(CONF_READ_ATTRIBUTE, "")): attr_field,
                vol.Optional(CONF_SCALE, default=self._data.get(CONF_SCALE, 1)): int,
                vol.Optional(CONF_VALUE_MAP, default=""): str,
            })
        return self.async_show_form(step_id="details", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry):
        return ModbusSlaveOptionsFlow()


class ModbusSlaveOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        # Determine current values
        current = self.config_entry.data

        # Determine attribute selector from provided or existing entity
        selected_entity = None
        if user_input is not None:
            selected_entity = user_input.get(CONF_READ_ENTITY) or current.get(CONF_READ_ENTITY)
        else:
            selected_entity = current.get(CONF_READ_ENTITY)
        attr_field = _attr_selector(self.hass, selected_entity)

        if user_input is not None:
            errors = {}
            value_map_raw = user_input.get(CONF_VALUE_MAP)
            if value_map_raw and isinstance(value_map_raw, str):
                try:
                    user_input[CONF_VALUE_MAP] = json.loads(value_map_raw)
                except json.JSONDecodeError:
                    errors[CONF_VALUE_MAP] = "invalid_json"

            if errors:
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema({
                        vol.Optional(CONF_DIRECTION, default=_normalize_direction(user_input.get(CONF_DIRECTION, current.get(CONF_DIRECTION, "write_only")))): vol.In(["write_only", "write_read"]),
                        vol.Optional(CONF_READ_ENTITY, default=user_input.get(CONF_READ_ENTITY, current.get(CONF_READ_ENTITY, ""))): EntitySelector(),
                        vol.Optional(CONF_READ_ATTRIBUTE, default=user_input.get(CONF_READ_ATTRIBUTE, current.get(CONF_READ_ATTRIBUTE, ""))): attr_field,
                        vol.Optional(CONF_SCALE, default=user_input.get(CONF_SCALE, current.get(CONF_SCALE, 1))): int,
                        vol.Optional("write_target", default=user_input.get("write_target", current.get("write_target", ""))): str,
                        vol.Optional(CONF_WRITE_SERVICE, default=user_input.get(CONF_WRITE_SERVICE, current.get(CONF_WRITE_SERVICE, ""))): str,
                        vol.Optional(CONF_WRITE_ENTITY, default=user_input.get(CONF_WRITE_ENTITY, current.get(CONF_WRITE_ENTITY, ""))): EntitySelector(),
                        vol.Optional(CONF_WRITE_PAYLOAD, default=user_input.get(CONF_WRITE_PAYLOAD, current.get(CONF_WRITE_PAYLOAD, ""))): str,
                        vol.Optional(CONF_VALUE_MAP, default=value_map_raw or ""): str,
                    }),
                    errors=errors,
                )

            return self.async_create_entry(title="", data=user_input)

        # Initial form with current values
        current_value_map = current.get(CONF_VALUE_MAP, "")
        if isinstance(current_value_map, dict):
            current_value_map = json.dumps(current_value_map)

        # Direction options (normalized to new values)
        schema = vol.Schema({
            vol.Optional(CONF_DIRECTION, default=_normalize_direction(current.get(CONF_DIRECTION, "write_only"))): vol.In(["write_only", "write_read"]),
            vol.Optional(CONF_READ_ENTITY, default=current.get(CONF_READ_ENTITY, "")): EntitySelector(),
            vol.Optional(CONF_READ_ATTRIBUTE, default=current.get(CONF_READ_ATTRIBUTE, "")): attr_field,
            vol.Optional(CONF_SCALE, default=current.get(CONF_SCALE, 1)): int,
            vol.Optional("write_target", default=current.get("write_target", "")): str,
            vol.Optional(CONF_WRITE_SERVICE, default=current.get(CONF_WRITE_SERVICE, "")): str,
            vol.Optional(CONF_WRITE_ENTITY, default=current.get(CONF_WRITE_ENTITY, "")): EntitySelector(),
            vol.Optional(CONF_WRITE_PAYLOAD, default=current.get(CONF_WRITE_PAYLOAD, "")): str,
            vol.Optional(CONF_VALUE_MAP, default=current_value_map): str,
        })

        return self.async_show_form(step_id="init", data_schema=schema)
