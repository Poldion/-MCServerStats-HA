"""Constants for the Minecraft Server Stats integration."""

DOMAIN = "mc_server_stats"

DEFAULT_PORT = 25565
DEFAULT_SCAN_INTERVAL = 60  # seconds
DEFAULT_DISCOVERY_INTERVAL = 300  # seconds (5 min)
SCAN_PORT_MIN = 25565
SCAN_PORT_MAX = 25575

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DISCOVERY_INTERVAL = "discovery_interval"
CONF_PORT_MIN = "port_min"
CONF_PORT_MAX = "port_max"
CONF_SERVER_NAME = "server_name"

PLATFORMS = ["sensor", "binary_sensor"]

