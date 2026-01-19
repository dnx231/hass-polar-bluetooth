"""Constants for the Polar Bluetooth integration."""

DOMAIN = "polar_bluetooth"

# Bluetooth UUIDs for Polar sensors
HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# Configuration
CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_ADDRESS = "device_address"

# Default values
DEFAULT_NAME = "Polar Heart Rate"
SCAN_INTERVAL = 1  # seconds
