# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration that implements a Modbus slave device. The integration allows Home Assistant to act as a Modbus slave, responding to Modbus RTU requests over a serial connection. It uses templates to dynamically provide register values and can optionally write received values to Home Assistant entities.

## Architecture

- **__init__.py**: Main integration module containing the Modbus slave worker thread and entry setup
- **config_flow.py**: Configuration flow for setting up integration instances via UI
- **const.py**: Constants and configuration parameter definitions
- **manifest.json**: Integration metadata and dependencies

### Core Components

1. **Configuration Flow** (`config_flow.py:6`): Handles initial user configuration with serial port, baudrate, slave ID, register address, and template setup
2. **Options Flow** (`config_flow.py:34`): Allows modification of template and write_target for existing entries without recreating them
3. **Modbus Handler** (`__init__.py:114`): Async task handling serial communication and Modbus RTU protocol using HA parallelization
4. **Template System**: Uses Home Assistant templates to dynamically calculate register values with live updates
5. **Entry Management**: Tracks multiple Modbus slave instances with different slave IDs and register addresses

### Key Architecture Patterns

- Single shared async task serves all configured Modbus slave instances using HA parallelization
- Thread-safe data structure in `hass.data[DOMAIN]["entries"]` tracks all active configurations
- Template listeners automatically update register values when Home Assistant states change
- Options flow enables runtime modification of templates and write targets without entry recreation
- Template tracker cleanup ensures proper resource management on entry updates/removal
- CRC validation ensures Modbus RTU protocol compliance
- Supports both function code 3 (read holding registers) and 6 (write single register)

## Development

### Dependencies

- **pyserial**: Required for serial communication (specified in manifest.json)
- **Home Assistant core**: Uses template system, config entries, and state management
- **voluptuous**: For configuration schema validation

### Testing Serial Communication

Since this integration requires serial hardware, testing typically involves:
- Physical Modbus master device or software simulator
- Serial port or USB-to-serial adapter
- Verify CRC calculations match Modbus RTU specification

### Template System Features

The integration supports sophisticated template handling:
- **Numeric Templates**: Standard numeric expressions like `{{ sensor.temperature | float }}`
- **State Templates**: String state values like `{{ states("climate.office") }}` 
- **Custom Value Mapping**: JSON mapping for string-to-numeric conversion
- **Built-in Mappings**: Common HVAC states (off=0, heat=1, cool=2, auto=3, etc.)

#### Value Mapping Examples
```json
{"off": 0, "heat": 1, "cool": 2}
{"idle": 0, "heating": 1, "cooling": 2}
{"false": 0, "true": 1}
```

### Common Development Tasks

When modifying register handling logic, pay attention to:
- CRC calculation in `calc_crc()` function (`__init__.py:204`)
- Buffer management and message framing (`__init__.py:220-290`)
- Template value conversion and mapping (`parse_template_result()` at `__init__.py:154`)
- String-to-numeric conversion with fallback handling
- Write target entity attribute updates (`_update_entity_attribute()` at `__init__.py:295`)