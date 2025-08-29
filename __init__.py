import asyncio
import logging
import serial
import struct
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.template import Template
from homeassistant.helpers.event import async_track_template_result, TrackTemplate
from .const import DOMAIN, CONF_SERIAL_PORT, CONF_BAUDRATE, CONF_SLAVE_ID, CONF_REGISTER_ADDR, CONF_TEMPLATE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry):
    data = config_entry.data
    serial_port = data[CONF_SERIAL_PORT]
    baudrate = data[CONF_BAUDRATE]
    slave_id = data[CONF_SLAVE_ID]
    register_addr = data[CONF_REGISTER_ADDR]
    template_str = data[CONF_TEMPLATE]

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
        "write_target": write_target
    }
    
    hass.data[DOMAIN]["entries"][entry_id] = {
        "slave_id": slave_id,
        "register_addr": register_addr,
        "value": 0,
        "write_target": write_target,
    }

    template = Template(template_str, hass)
    track_template = TrackTemplate(template, None)

    async def template_listener(event, updates):
        if entry_id not in hass.data[DOMAIN]["entries"]:
            _LOGGER.warning(f"Entry ID {entry_id} not found during template update.")
            return
        
        for result in updates:
            if result.result:
                try:
                    value = int(float(result.result))
                    hass.data[DOMAIN]["entries"][entry_id]["value"] = value
                    _LOGGER.info(f"Updated Slave {slave_id} Reg {register_addr}: {value}")
                except (ValueError, TypeError) as e:
                    hass.data[DOMAIN]["entries"][entry_id]["value"] = 0  # Fallback to a safe default
                    _LOGGER.warning(
                        f"Template rendered invalid value '{result.result}' for Slave {slave_id} "
                        f"Reg {register_addr}: {e}. Defaulting to 0."
                    )
            else:
                hass.data[DOMAIN]["entries"][entry_id]["value"] = 0  # Entity unavailable fallback
                _LOGGER.warning(
                    f"Template unavailable for Slave {slave_id} Reg {register_addr}. Defaulting to 0."
                )

    async_track_template_result(hass, [track_template], template_listener)

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

    return True

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
                                await _update_entity_attribute(hass, write_target, value_received)

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
async def _update_entity_attribute(hass: HomeAssistant, write_target: str, value_received: int):
    """Update entity attribute in a thread-safe manner."""
    try:
        entity_id, attr = write_target.rsplit('.', 1)
        state_obj = hass.states.get(entity_id)
        if state_obj:
            attrs = dict(state_obj.attributes)
            attrs[attr] = value_received / 10  # adjust scaling if needed
            hass.states.async_set(entity_id, state_obj.state, attrs)
            _LOGGER.info(f"Updated {entity_id}.{attr} to {value_received / 10}")
        else:
            _LOGGER.warning(f"Entity {entity_id} not found in HA")
    except Exception as e:
        _LOGGER.error(f"Error updating entity attribute: {e}")

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.data[DOMAIN]["entries"].pop(entry.entry_id, None)
    
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
