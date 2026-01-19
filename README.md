# Polar Bluetooth Heart Rate Sensor for Home Assistant

This custom integration allows you to connect Polar heart rate sensors to Home Assistant via Bluetooth and monitor your heart rate in real-time.

## Features

- 📡 Automatic discovery of Polar Bluetooth sensors
- ❤️ Real-time heart rate monitoring
- 🔋 Battery level tracking
- 🔄 Automatic reconnection on connection loss
- ⚙️ Easy UI-based configuration through Home Assistant

## Supported Devices

This integration should work with any Polar heart rate sensor that supports Bluetooth Low Energy (BLE) and the standard Heart Rate Service, including:

- Polar H10
- Polar H9
- Polar OH1
- Polar Verity Sense
- And other Polar heart rate monitors

## Installation

### HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed
2. Add this repository as a custom repository in HACS:
   - Go to HACS → Integrations
   - Click the three dots in the top right
   - Select "Custom repositories"
   - Add `https://github.com/dehuesde/hass-polar-bluetooth` as an Integration
3. Click "Install" on the Polar Bluetooth Sensor card
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/polar_bluetooth` directory to your Home Assistant's `custom_components` directory
2. If the `custom_components` directory doesn't exist, create it in the same directory as your `configuration.yaml`
3. Restart Home Assistant

## Configuration

### Prerequisites

- Home Assistant with Bluetooth support enabled
- A Polar heart rate sensor
- The sensor should be worn and active (blinking light indicates it's broadcasting)

### Setup Steps

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Polar Bluetooth Sensor**
4. Your Polar device should appear in the list if it's nearby and broadcasting
5. Select your device and click **Submit**
6. The integration will create two sensors:
   - Heart Rate sensor (in beats per minute)
   - Battery Level sensor (in percentage)

### Automatic Discovery

If your Polar sensor is turned on and broadcasting, Home Assistant will automatically discover it and show a notification. Simply click on the notification to add the device.

## Usage

Once configured, you'll have the following entities:

- `sensor.polar_<device_name>_heart_rate` - Your current heart rate in BPM
- `sensor.polar_<device_name>_battery` - Battery level percentage

### Example Automations

**Alert on High Heart Rate:**

```yaml
automation:
  - alias: "High Heart Rate Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.polar_h10_12345678_heart_rate
        above: 160
    action:
      - service: notify.mobile_app
        data:
          title: "High Heart Rate"
          message: "Your heart rate is {{ states('sensor.polar_h10_12345678_heart_rate') }} BPM!"
```

**Track Heart Rate in Lovelace:**

```yaml
type: gauge
entity: sensor.polar_h10_12345678_heart_rate
min: 40
max: 200
severity:
  green: 60
  yellow: 120
  red: 160
needle: true
name: Heart Rate
```

**Low Battery Notification:**

```yaml
automation:
  - alias: "Polar Sensor Low Battery"
    trigger:
      - platform: numeric_state
        entity_id: sensor.polar_h10_12345678_battery
        below: 20
    action:
      - service: notify.mobile_app
        data:
          title: "Low Battery"
          message: "Polar sensor battery is at {{ states('sensor.polar_h10_12345678_battery') }}%"
```

## Testing

Before installing in Home Assistant, you can test the Bluetooth connectivity locally:

```powershell
pip install bleak
python tests/test_polar_sensor.py
```

See [tests/README.md](tests/README.md) for detailed testing instructions.

## Troubleshooting

### Device Not Discovered

1. Make sure your Polar sensor is turned on and broadcasting (wearing it activates most sensors)
2. Ensure Bluetooth is enabled on your Home Assistant host
3. Check that your Bluetooth adapter supports BLE (Bluetooth Low Energy)
4. Try moving closer to the Home Assistant device

### Connection Issues

1. Remove the integration and re-add it
2. Restart the Polar sensor
3. Make sure the sensor is not connected to another device (like a phone app)
4. Check Home Assistant logs for specific error messages

### Viewing Logs

Enable debug logging to see detailed information:

```yaml
logger:
  default: info
  logs:
    custom_components.polar_bluetooth: debug
```

## Development

This integration uses:
- The [bleak](https://github.com/hbldh/bleak) library for Bluetooth communication
- Home Assistant's Bluetooth integration for device discovery
- Standard Bluetooth GATT services for heart rate (0x180D) and battery (0x180F)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Acknowledgments

- Thanks to the Home Assistant community
- Thanks to Polar for their excellent heart rate sensors
