"""Constants for the ncSender integration."""

DOMAIN = "ncsender"

DEFAULT_HOST = "ncsender.local"
DEFAULT_PORT = 8090
DEFAULT_NAME = "ncSender"

CONF_LASER_MAX_S = "laser_max_s"
DEFAULT_LASER_MAX_S = 1000

# Minimum interval between state pushes for high-rate telemetry
# (positions, RPM, feed, progress). State-class changes always push
# immediately; the last telemetry value of a burst is always flushed.
TELEMETRY_MIN_INTERVAL = 1.0

SERVICE_SEND_COMMAND = "send_command"
ATTR_COMMAND = "command"
ATTR_ENTRY_ID = "entry_id"

SOURCE_ID = "home-assistant"
