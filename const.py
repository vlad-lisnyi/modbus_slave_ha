DOMAIN = "modbus_slave"

CONF_SERIAL_PORT = "serial_port"
CONF_BAUDRATE = "baudrate"
CONF_SLAVE_ID = "slave_id"
CONF_REGISTER_ADDR = "register_addr"
CONF_TEMPLATE = "template"
CONF_VALUE_MAP = "value_map"

# New configuration keys for flexible mapping
CONF_DIRECTION = "direction"  # write_only (HA->register), write_read (bi-directional)
CONF_READ_MODE = "read_mode"  # deprecated; kept for backward compatibility
CONF_READ_ENTITY = "read_entity"
CONF_READ_ATTRIBUTE = "read_attribute"
CONF_SCALE = "scale"  # numeric multiplier for register representation
CONF_WRITE_SERVICE = "write_service"  # e.g., climate.set_temperature
CONF_WRITE_ENTITY = "write_entity"  # optional override entity for write
CONF_WRITE_PAYLOAD = "write_payload"  # JSON string with templated values
