import asyncio
import logging
import serial
import struct
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.template import Template
from homeassistant.helpers.event import async_track_template_result, TrackTemplate
from .const import DOMAIN, CONF_SERIAL_PORT, CONF_BAUDRATE, CONF_SLAVE_ID, CONF_REGISTER_ADDR, CONF_TEMPLATE, CONF_VALUE_MAP

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry):
    data = config_entry.data
    serial_port = data[CONF_SERIAL_PORT]
    baudrate = data[CONF_BAUDRATE]
    slave_id = data[CONF_SLAVE_ID]
    register_addr = data[CONF_REGISTER_ADDR]
    template_str = data[CONF_TEMPLATE]
    value_map = data.get(CONF_VALUE_MAP)

    entry_id = config_entry.entry_id

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            "entries": {},
            "serial_connection": None,
            "serial_task": None,
            "serial_port": serial_port,
            "baudrate": baudrate,
        }
    
    write_target = data.get("write_target")
    hass.data[DOMAIN]["entries"][entry_id] = {
        "slave_id": slave_id,
        "register_addr": register_addr,
        "value": 0,
        "write_target": write_target,
        "template_tracker": None,
        "value_map": value_map,
    }

    template = Template(template_str, hass)
    track_template = TrackTemplate(template, None)

    async def template_listener(event, updates):
        if entry_id not in hass.data[DOMAIN]["entries"]:
            _LOGGER.warning(f"Entry ID {entry_id} not found during template update.")
            return
        
        for result in updates:
            if result.result is not None:
                entry_value_map = hass.data[DOMAIN]["entries"][entry_id].get("value_map")
                value = parse_template_result(result.result, entry_value_map)
                hass.data[DOMAIN]["entries"][entry_id]["value"] = value
                _LOGGER.info(f"Updated Slave {slave_id} Reg {register_addr}: {value} (from '{result.result}')")
            else:
                hass.data[DOMAIN]["entries"][entry_id]["value"] = 0  # Entity unavailable fallback
                _LOGGER.warning(
                    f"Template unavailable for Slave {slave_id} Reg {register_addr}. Defaulting to 0."
                )

    template_unsubscribe = async_track_template_result(hass, [track_template], template_listener)
    hass.data[DOMAIN]["entries"][entry_id]["template_tracker"] = template_unsubscribe

    # Initialize serial connection and task
    if hass.data[DOMAIN]["serial_connection"] is None:
        try:
            serial_conn = await hass.async_add_executor_job(
                serial.Serial,
                hass.data[DOMAIN]["serial_port"],
                hass.data[DOMAIN]["baudrate"],
                'N',  # parity
                2,    # stopbits  
                8,    # bytesize
                1     # timeout
            )
            hass.data[DOMAIN]["serial_connection"] = serial_conn
            hass.data[DOMAIN]["serial_task"] = hass.async_create_task(
                modbus_slave_handler(hass, serial_conn)
            )
            _LOGGER.info(f"Started Modbus slave on {hass.data[DOMAIN]['serial_port']}")
        except Exception as e:
            _LOGGER.error(f"Failed to initialize serial connection: {e}")
            return False

    # Set up options update listener
    config_entry.async_on_unload(
        config_entry.add_update_listener(async_update_options)
    )

    return True

async def async_update_options(hass: HomeAssistant, config_entry: config_entries.ConfigEntry):
    """Handle options update."""
    entry_id = config_entry.entry_id
    
    if entry_id not in hass.data[DOMAIN]["entries"]:
        _LOGGER.warning(f"Entry {entry_id} not found for options update")
        return
    
    # Get new options
    template_str = config_entry.options.get(CONF_TEMPLATE) or config_entry.data.get(CONF_TEMPLATE)
    write_target = config_entry.options.get("write_target") or config_entry.data.get("write_target")
    value_map = config_entry.options.get(CONF_VALUE_MAP) or config_entry.data.get(CONF_VALUE_MAP)
    
    entry_data = hass.data[DOMAIN]["entries"][entry_id]
    slave_id = entry_data["slave_id"]
    register_addr = entry_data["register_addr"]
    
    # Stop old template tracker
    if entry_data["template_tracker"]:
        entry_data["template_tracker"]()
    
    # Update write target and value map
    entry_data["write_target"] = write_target
    entry_data["value_map"] = value_map
    
    # Create new template and tracker
    template = Template(template_str, hass)
    track_template = TrackTemplate(template, None)

    async def template_listener(event, updates):
        if entry_id not in hass.data[DOMAIN]["entries"]:
            _LOGGER.warning(f"Entry ID {entry_id} not found during template update.")
            return
        
        for result in updates:
            if result.result is not None:
                entry_value_map = hass.data[DOMAIN]["entries"][entry_id].get("value_map")
                value = parse_template_result(result.result, entry_value_map)
                hass.data[DOMAIN]["entries"][entry_id]["value"] = value
                _LOGGER.info(f"Updated Slave {slave_id} Reg {register_addr}: {value} (from '{result.result}')")
            else:
                hass.data[DOMAIN]["entries"][entry_id]["value"] = 0
                _LOGGER.warning(
                    f"Template unavailable for Slave {slave_id} Reg {register_addr}. Defaulting to 0."
                )

    # Start new template tracker
    template_unsubscribe = async_track_template_result(hass, [track_template], template_listener)
    entry_data["template_tracker"] = template_unsubscribe
    
    _LOGGER.info(f"Updated options for Slave {slave_id} Reg {register_addr}")

def parse_template_result(result_value, value_map=None):
    """Parse template result into numeric value, supporting string-to-numeric mapping."""
    if result_value is None:
        return 0
        
    result_str = str(result_value).strip()
    
    # First try direct numeric conversion
    try:
        return int(float(result_str))
    except (ValueError, TypeError):
        pass
    
    # If value_map is provided, try to map string values
    if value_map and isinstance(value_map, dict):
        # Try case-insensitive lookup
        for key, value in value_map.items():
            if str(key).lower() == result_str.lower():
                try:
                    return int(float(value))
                except (ValueError, TypeError):
                    _LOGGER.warning(f"Value map contains non-numeric value: {key} -> {value}")
                    continue
    
    # If no mapping found, try some common HVAC state mappings
    common_mappings = {
        'off': 0,
        'heat': 1,
        'cool': 2,
        'auto': 3,
        'dry': 4,
        'fan_only': 5,
        'idle': 0,
        'heating': 1,
        'cooling': 2,
        'false': 0,
        'true': 1,
        'on': 1,
        'unknown': 0,
        'unavailable': 0
    }
    
    mapped_value = common_mappings.get(result_str.lower())
    if mapped_value is not None:
        return mapped_value
    
    # Last resort: return 0
    _LOGGER.warning(f"Could not convert template result '{result_value}' to numeric value, using 0")
    return 0

def reverse_value_mapping(numeric_value, value_map=None):
    """Convert numeric value back to string using reverse mapping."""
    # If value_map is provided, try reverse lookup
    if value_map and isinstance(value_map, dict):
        for key, value in value_map.items():
            try:
                if int(float(value)) == numeric_value:
                    return str(key)
            except (ValueError, TypeError):
                continue
    
    # Use common HVAC state mappings for reverse lookup
    common_reverse_mappings = {
        0: 'off',
        1: 'heat', 
        2: 'cool',
        3: 'auto',
        4: 'dry',
        5: 'fan_only'
    }
    
    return common_reverse_mappings.get(numeric_value, str(numeric_value))

def calc_crc(data):
    """Calculate Modbus RTU CRC16."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc.to_bytes(2, 'little')

def read_serial_data(serial_conn):
    """Read data from serial port (blocking operation for executor)."""
    return serial_conn.read(1)

def write_serial_data(serial_conn, data):
    """Write data to serial port (blocking operation for executor)."""
    return serial_conn.write(data)

async def modbus_slave_handler(hass: HomeAssistant, serial_conn):
    """Handle Modbus slave communication using HA async patterns."""
    buffer = b''
    
    try:
        while True:
            try:
                # Read byte using executor to avoid blocking event loop
                byte = await hass.async_add_executor_job(read_serial_data, serial_conn)
                if not byte:
                    continue
                
                buffer += byte

                if len(buffer) >= 8:
                    req_slave, func, addr_hi, addr_lo, val_hi, val_lo, crc_lo, crc_hi = buffer[:8]
                    addr = (addr_hi << 8) | addr_lo
                    value_received = (val_hi << 8) | val_lo
                    crc_received = buffer[6:8]
                    crc_calculated = calc_crc(buffer[:6])

                    if crc_received != crc_calculated:
                        buffer = buffer[1:]
                        continue

                    matched_entry = None
                    for entry in hass.data[DOMAIN]["entries"].values():
                        if entry["slave_id"] == req_slave and entry["register_addr"] == addr:
                            matched_entry = entry
                            break

                    if matched_entry:
                        if func == 3:  # Read Holding Register
                            value = matched_entry["value"]
                            payload = struct.pack('>h', value)
                            response = bytes([req_slave, 3, 2]) + payload
                            crc_resp = calc_crc(response)
                            await hass.async_add_executor_job(write_serial_data, serial_conn, response + crc_resp)
                            _LOGGER.info(f"Sent {value} to Slave {req_slave} Reg {addr}")

                        elif func == 6:  # Write Single Register
                            matched_entry["value"] = value_received
                            response = buffer[:6] + crc_calculated
                            await hass.async_add_executor_job(write_serial_data, serial_conn, response)
                            _LOGGER.info(f"Received {value_received} from Master (Slave {req_slave} Reg {addr})")

                            # Update entity/property using thread-safe method
                            write_target = matched_entry.get("write_target")
                            if write_target:
                                value_map = matched_entry.get("value_map")
                                await _update_entity_attribute(hass, write_target, value_received, value_map)

                    buffer = b''  # reset buffer after processing
                    
            except asyncio.CancelledError:
                _LOGGER.info("Modbus slave handler cancelled")
                break
            except Exception as e:
                _LOGGER.error(f"Error in Modbus slave handler: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying
                
    finally:
        # Clean up serial connection
        if serial_conn.is_open:
            await hass.async_add_executor_job(serial_conn.close)
        _LOGGER.info("Modbus slave handler stopped")

@callback
async def _update_entity_attribute(hass: HomeAssistant, write_target: str, value_received: int, value_map=None):
    """Update entity state or attribute using reverse value mapping."""
    try:
        if '.' in write_target:
            # Format: entity.attribute - update attribute  
            entity_id, attr = write_target.rsplit('.', 1)
            state_obj = hass.states.get(entity_id)
            if state_obj:
                # Convert numeric value back to string if value mapping exists
                mapped_value = reverse_value_mapping(value_received, value_map)
                
                attrs = dict(state_obj.attributes)
                attrs[attr] = mapped_value
                hass.states.async_set(entity_id, state_obj.state, attrs)
                _LOGGER.info(f"Updated {entity_id}.{attr} to '{mapped_value}' (from {value_received})")
            else:
                _LOGGER.warning(f"Entity {entity_id} not found in HA")
        else:
            # Format: entity_id - update state directly
            entity_id = write_target
            state_obj = hass.states.get(entity_id)
            if state_obj:
                # Convert numeric value back to string if value mapping exists
                mapped_value = reverse_value_mapping(value_received, value_map)
                
                # For climate entities, use service calls for proper state changes
                if entity_id.startswith('climate.'):
                    await _update_climate_state(hass, entity_id, mapped_value)
                else:
                    # For other entities, set state directly
                    hass.states.async_set(entity_id, mapped_value, state_obj.attributes)
                    _LOGGER.info(f"Updated {entity_id} state to '{mapped_value}' (from {value_received})")
            else:
                _LOGGER.warning(f"Entity {entity_id} not found in HA")
    except Exception as e:
        _LOGGER.error(f"Error updating entity: {e}")

async def _update_climate_state(hass: HomeAssistant, entity_id: str, hvac_mode: str):
    """Update climate entity state using service calls."""
    try:
        # Map common values to climate service calls
        if hvac_mode.lower() == 'off':
            await hass.services.async_call('climate', 'turn_off', {'entity_id': entity_id})
        elif hvac_mode.lower() in ['heat', 'cool', 'auto', 'dry', 'fan_only']:
            await hass.services.async_call('climate', 'set_hvac_mode', {
                'entity_id': entity_id,
                'hvac_mode': hvac_mode.lower()
            })
        else:
            _LOGGER.warning(f"Unknown HVAC mode '{hvac_mode}' for {entity_id}")
            
        _LOGGER.info(f"Updated {entity_id} HVAC mode to '{hvac_mode}'")
    except Exception as e:
        _LOGGER.error(f"Error updating climate entity {entity_id}: {e}")

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    entry_id = entry.entry_id
    entry_data = hass.data[DOMAIN]["entries"].get(entry_id)
    
    # Clean up template tracker
    if entry_data and entry_data.get("template_tracker"):
        entry_data["template_tracker"]()
    
    hass.data[DOMAIN]["entries"].pop(entry_id, None)
    
    # If this was the last entry, clean up the serial connection and task
    if not hass.data[DOMAIN]["entries"]:
        if hass.data[DOMAIN]["serial_task"]:
            hass.data[DOMAIN]["serial_task"].cancel()
            try:
                await hass.data[DOMAIN]["serial_task"]
            except asyncio.CancelledError:
                pass
            hass.data[DOMAIN]["serial_task"] = None
            
        if hass.data[DOMAIN]["serial_connection"]:
            await hass.async_add_executor_job(hass.data[DOMAIN]["serial_connection"].close)
            hass.data[DOMAIN]["serial_connection"] = None
            
        _LOGGER.info("Stopped Modbus slave - all entries removed")
    
    return True
