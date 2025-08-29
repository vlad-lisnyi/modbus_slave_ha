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

1. **Configuration Flow** (`config_flow.py:6`): Handles user configuration with serial port, baudrate, slave ID, register address, and template setup
2. **Modbus Worker Thread** (`__init__.py:81`): Dedicated thread handling serial communication and Modbus RTU protocol
3. **Template System**: Uses Home Assistant templates to dynamically calculate register values
4. **Entry Management**: Tracks multiple Modbus slave instances with different slave IDs and register addresses

### Key Architecture Patterns

- Single shared serial thread serves all configured Modbus slave instances
- Thread-safe data structure in `hass.data[DOMAIN]["entries"]` tracks all active configurations
- Template listeners automatically update register values when Home Assistant states change
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

### Common Development Tasks

When modifying register handling logic, pay attention to:
- CRC calculation in `calc_crc()` function (`__init__.py:92`)
- Buffer management and message framing (`__init__.py:100-152`)
- Template value conversion and error handling (`__init__.py:54-68`)
- Write target entity attribute updates (`__init__.py:139-151`)