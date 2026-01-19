# Testing the Polar Bluetooth Integration

## Option 1: Quick Test (Recommended)

Test the Bluetooth connectivity without Home Assistant:

### 1. Install dependencies
```powershell
pip install bleak
```

### 2. Run the test script
```powershell
python tests/test_polar_sensor.py
```

This will:
- Scan for Polar devices
- Connect to your sensor
- Read battery level
- Display heart rate for 10 seconds

**Make sure your Polar sensor is active (wear it to turn it on)!**

---

## Option 2: Test in Home Assistant

### Prerequisites
- Home Assistant installed (Core, Container, or OS)
- Bluetooth adapter on the Home Assistant host
- Polar sensor nearby and active

### Installation Steps

1. **Copy the integration to Home Assistant:**
   ```powershell
   # Replace <ha_config_path> with your Home Assistant config directory
   Copy-Item -Path "custom_components" -Destination "<ha_config_path>/" -Recurse
   ```

2. **Restart Home Assistant**

3. **Add the integration:**
   - Go to Settings → Devices & Services
   - Click "Add Integration"
   - Search for "Polar Bluetooth Sensor"
   - Select your device

### Common Home Assistant Paths

- **Home Assistant Core:** `~/.homeassistant/` or `~/homeassistant/`
- **Home Assistant Container:** Volume mount location (check your docker-compose.yml)
- **HAOS/Supervised:** `/config/`

---

## Troubleshooting

### No devices found
- Wear the Polar sensor to activate it (LED should blink)
- Make sure it's not connected to another device (phone app, watch, etc.)
- Check Bluetooth is enabled: `Get-PnpDevice | Where-Object {$_.Class -eq "Bluetooth"}`

### Connection errors
- Restart the Polar sensor (remove it for 10 seconds, then wear it again)
- Make sure you're within 5-10 meters of the device
- On Windows, you may need to pair the device in Settings → Bluetooth first

### Permission issues (Linux)
```bash
sudo setcap cap_net_raw+ep $(eval readlink -f `which python3`)
```

---

## What to Expect

The test script will show output like:
```
🔍 Scanning for Polar devices...

✅ Found 1 Polar device(s):
   1. Polar H10 12345678 - AA:BB:CC:DD:EE:FF

📡 Connecting to Polar H10 12345678...
✅ Connected!

🔋 Battery Level: 85%

❤️  Reading heart rate for 10 seconds...
   Heart Rate: 72 BPM
   Heart Rate: 73 BPM
   Heart Rate: 71 BPM
   ...
```
