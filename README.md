# Modbus Slave for Home Assistant

A Home Assistant custom integration that lets Home Assistant act as a Modbus RTU slave over a serial port. Each configured entry exposes one Modbus holding register backed by a Home Assistant entity (state or attribute). Optionally, incoming Modbus writes are forwarded to Home Assistant services (e.g., climate.set_temperature).

## Features

- Entity/attribute-backed registers with live updates
- Bi-directional writes using HA services (service + optional payload)
- Scaling (e.g., °C×10) and string↔number mapping
- “Use entity state” option when the entity’s state is the value you want
- Attribute dropdown with value previews to help choose scale/mappings
- Multiple independent registers, shared serial connection

## Installation

### HACS (Recommended)
1. Add this repository to HACS as a custom repository
2. Install “Modbus Slave” from HACS
3. Restart Home Assistant

### Manual
1. Copy the `modbus_slave` folder into `config/custom_components/`
2. Restart Home Assistant

## Configuration

Add via UI: Settings → Devices & Services → Add Integration → “Modbus Slave”. Each entry corresponds to one Modbus register.

The setup wizard has 3 steps:

1) Register
- Serial Port: e.g., `/dev/ttyUSB0`
- Baudrate: e.g., `9600`
- Slave ID: `1…247`
- Register Address: `0…65535`

2) Source
- Direction:
  - `write_only`: HA → register (master reads only; no HA service calls)
  - `write_read`: HA ↔ register (on master writes, call a HA service)
- Read Entity: entity that backs the register (e.g., `climate.bedroom`)

3) Details
- Read Attribute: choose from a dropdown with value previews, or select “Use entity state”.
- Scale: integer multiplier applied when storing to the register (e.g., `10` → 26.5 → 265).
- Value Map: optional JSON mapping, e.g. `{ "off": 0, "auto": 1, "heat": 2, "cool": 3 }`.
- Write Service (write_read only): choose a domain service (e.g., `climate.set_temperature`).
- Write Entity (optional): defaults to the read entity.
- Write Payload (optional): JSON body for the service; supports templating (see below).

### Service payload templating (optional)
You can template fields inside the payload. Available variables:
- `value`: raw register value (int)
- `value_scaled`: scaled float value (e.g., 265 → 26.5 when scale=10)
- `mapped_value`: reverse-mapped value (e.g., 2 → "heat")

Example:
```json
{"temperature": {{ value_scaled }}}
```

For common climate services, missing keys are injected automatically when the payload is empty or incomplete:
- `climate.set_temperature` → adds `temperature: value_scaled` if missing
- `climate.set_hvac_mode` → adds `hvac_mode: mapped_value`
- `climate.set_preset_mode` → adds `preset_mode: mapped_value`

## Example register definitions

1) Current temperature (read-only)
- Direction: `write_only`
- Entity: `climate.bedroom`
- Read: `current_temperature`
- Scale: `10` (26.5°C ↔ 265)

2) Target temperature (bi-directional)
- Direction: `write_read`
- Entity: `climate.bedroom`
- Read: `target_temperature`
- Scale: `10`
- Write Service: `climate.set_temperature`
- Write Payload: leave empty (auto-injection)

3) HVAC mode (bi-directional)
- Direction: `write_read`
- Entity: `climate.bedroom`
- Read: `Use entity state` (the entity state is the current mode)
- Value Map: `{ "off": 0, "auto": 1, "heat": 2, "cool": 3 }`
- Write Service: `climate.set_hvac_mode`
- Write Payload: leave empty (auto-injection)

4) Door sensor (read-only)
- Direction: `write_only`
- Entity: `binary_sensor.front_door`
- Read: `Use entity state`
- Value Map: `{ "off": 0, "on": 1 }`

## Value mapping

Use a JSON object to map strings ↔ numbers. Examples:
- HVAC modes: `{ "off": 0, "auto": 1, "heat": 2, "cool": 3 }`
- Booleans: `{ "off": 0, "on": 1, "false": 0, "true": 1 }`
- Actions: `{ "idle": 0, "heating": 1, "cooling": 2 }`

## Modbus protocol support

- Function 3: Read Holding Registers (quantity=1). Returns the current integer value.
- Function 6: Write Single Register. Stores the value and (in write_read mode) calls the configured HA service.
- Protocol: Modbus RTU (CRC16 validated)

Notes:
- Modbus is master-driven: the slave only replies to requests; it does not push frames.
- If you see several “Sent …” logs in quick succession, your master is polling or retrying.

## Troubleshooting

- Attribute choice for climate modes: pick “Use entity state”. The `hvac_modes` attribute is a list of supported modes (not the current one) and can’t be mapped to a single number.
- Scaling: use value previews in the dropdown to set a correct scale (e.g., `10` for one decimal place).
- Mapping: ensure your JSON is valid; the UI validates it.
- Quantity=1: This integration currently replies with a single register for FC3. Configure your master to request quantity=1 for these registers.
- Serial: check permissions and port. Example: `sudo chmod 666 /dev/ttyUSB0`.

## Dependencies

- pyserial
- Home Assistant Core

## Contributing

1. Fork this repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Open a pull request

## License

MIT

