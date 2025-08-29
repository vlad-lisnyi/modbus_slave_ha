# Modbus Slave for Home Assistant

A Home Assistant custom integration that implements a Modbus slave device, allowing Home Assistant to respond to Modbus RTU requests over a serial connection.

## Features

- **Template-based Register Values**: Use Home Assistant templates to dynamically calculate register values
- **Multi-instance Support**: Configure multiple Modbus slave instances with different slave IDs and register addresses
- **Bidirectional Communication**: Read register values and optionally write back to Home Assistant entities
- **Value Mapping**: Convert string states to numeric values using custom or built-in mappings
- **Real-time Updates**: Register values update automatically when Home Assistant states change

## Installation

### HACS (Recommended)
1. Add this repository to HACS as a custom repository
2. Install "Modbus Slave" from HACS
3. Restart Home Assistant

### Manual Installation
1. Copy the `modbus_slave` folder to your `custom_components` directory
2. Restart Home Assistant

## Configuration

Add the integration through the Home Assistant UI:

**Settings** → **Devices & Services** → **Add Integration** → **Modbus Slave**

### Configuration Parameters

- **Serial Port**: Path to serial device (e.g., `/dev/ttyUSB0`)
- **Baudrate**: Serial communication speed (default: 9600)
- **Slave ID**: Modbus slave identifier (1-247)
- **Register Address**: Starting register address (0-65535)
- **Template**: Home Assistant template for register value calculation
- **Write Target** (optional): Entity or attribute to update when master writes to register
- **Value Mapping** (optional): JSON mapping for string-to-numeric conversion

## Template Examples

### Numeric Templates
```yaml
# Temperature sensor (multiplied by 10 for precision)
{{ (state_attr("climate.office", "current_temperature") * 10) | int }}

# Humidity sensor
{{ states("sensor.humidity") | float | int }}

# Power consumption
{{ states("sensor.power_meter") | float * 100 | int }}
```

### State-based Templates
```yaml
# Climate mode as numeric value
{{ 0 if states("climate.office") == 'off' else 1 }}

# Multi-state mapping
{% set mode = states("climate.office") %}
{% if mode == "off" %}0
{% elif mode == "heat" %}1  
{% elif mode == "cool" %}2
{% elif mode == "auto" %}3
{% else %}0{% endif %}
```

### Advanced Templates with Calculations
```yaml
# Average of multiple sensors
{{ ((states("sensor.temp1") | float + states("sensor.temp2") | float) / 2 * 10) | int }}

# Complex logic
{% set state = states("climate.office") %}
{% set temp = state_attr("climate.office", "current_temperature") | float %}
{{ (temp * 10) | int if state != "off" else 0 }}
```

## Value Mapping

Use JSON format to map string states to numeric values:

### HVAC States
```json
{"off": 0, "heat": 1, "cool": 2, "auto": 3, "dry": 4, "fan_only": 5}
```

### Boolean States
```json
{"false": 0, "true": 1, "off": 0, "on": 1}
```

### Custom States
```json
{"idle": 0, "heating": 1, "cooling": 2, "defrost": 3}
```

## Write Target Configuration

Configure bidirectional communication by specifying where master writes should be stored:

### Entity State Updates
- **Target**: `climate.office` - Updates entity state directly
- **Use case**: Master writing HVAC mode changes

### Entity Attribute Updates  
- **Target**: `climate.office.target_temperature` - Updates specific attribute
- **Use case**: Master writing setpoint changes

### Examples
```yaml
# Update climate mode when master writes
Write Target: climate.office
Value Mapping: {"0": "off", "1": "heat", "2": "cool", "3": "auto"}

# Update target temperature attribute
Write Target: climate.office.target_temperature  
Template: {{ state_attr("climate.office", "target_temperature") * 10 | int }}
```

## Built-in Value Mappings

The integration includes common HVAC state mappings:

| State | Value | State | Value |
|-------|-------|-------|-------|
| off | 0 | idle | 0 |
| heat | 1 | heating | 1 |
| cool | 2 | cooling | 2 |
| auto | 3 | false | 0 |
| dry | 4 | true | 1 |
| fan_only | 5 | on | 1 |

## Modbus Protocol Support

- **Function Code 3**: Read Holding Registers - Returns template-calculated values
- **Function Code 6**: Write Single Register - Updates Home Assistant entities
- **Protocol**: Modbus RTU over serial
- **CRC**: Full CRC16 validation for data integrity

## Example Use Cases

### 1. Temperature Monitoring
```yaml
Template: {{ (states("sensor.room_temperature") | float * 10) | int }}
Register: 100
Slave ID: 10
```
Master reads register 100 to get room temperature × 10

### 2. HVAC Control
```yaml
Template: {{ 0 if states("climate.office") == 'off' else 1 }}
Write Target: climate.office
Value Mapping: {"0": "off", "1": "heat", "2": "cool"}
Register: 200
Slave ID: 15
```
Master can read current HVAC state and write new modes

### 3. Multi-sensor Dashboard
```yaml
# Configure multiple registers for different sensors
Register 0: {{ states("sensor.temperature") | float * 10 | int }}
Register 1: {{ states("sensor.humidity") | int }}
Register 2: {{ 1 if states("binary_sensor.motion") == 'on' else 0 }}
```

## Troubleshooting

### Serial Connection Issues
- Verify serial device permissions: `sudo chmod 666 /dev/ttyUSB0`
- Check device availability: `ls -la /dev/tty*`
- Ensure no other applications are using the serial port

### Template Errors
- Test templates in Home Assistant Developer Tools → Template
- Check entity names and attribute availability
- Verify numeric conversion with `| float | int`

### Modbus Communication
- Verify CRC calculations with Modbus testing tools
- Check baudrate, parity, and stop bits match master configuration
- Monitor Home Assistant logs for detailed error messages

## Dependencies

- **pyserial**: Serial communication library
- **Home Assistant Core**: Template system and entity management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Join the Home Assistant community forums
- **Documentation**: Refer to Home Assistant template documentation for advanced usage