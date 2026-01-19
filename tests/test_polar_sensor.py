"""
Test script for Polar Bluetooth heart rate sensor connectivity.
This script can run independently without Home Assistant to verify the sensor works.
"""
import asyncio
import sys
from bleak import BleakScanner, BleakClient, BleakError

# Bluetooth UUIDs
HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"


def parse_heart_rate(data: bytearray) -> int:
    """Parse heart rate from BLE characteristic data."""
    flags = data[0]
    
    # Check if heart rate is in 16-bit format (bit 0 of flags)
    if flags & 0x01:
        heart_rate = int.from_bytes(data[1:3], byteorder="little")
    else:
        heart_rate = data[1]
    
    return heart_rate


async def scan_for_polar_devices():
    """Scan for Polar Bluetooth devices."""
    print("🔍 Scanning for Polar devices...")
    print("   Make sure your Polar sensor is active (wear it to activate)")
    print()
    
    devices = await BleakScanner.discover(timeout=10.0)
    polar_devices = [d for d in devices if d.name and "Polar" in d.name]
    
    if not polar_devices:
        print("❌ No Polar devices found!")
        print("   Troubleshooting:")
        print("   - Make sure your Polar sensor is turned on (wear it)")
        print("   - Ensure it's not connected to another device")
        print("   - Check that Bluetooth is enabled on this computer")
        return None
    
    print(f"✅ Found {len(polar_devices)} Polar device(s):")
    for i, device in enumerate(polar_devices, 1):
        print(f"   {i}. {device.name} - {device.address}")
    print()
    
    return polar_devices[0]  # Return the first device


async def test_polar_sensor(device):
    """Connect to Polar sensor and read heart rate."""
    print(f"📡 Connecting to {device.name} ({device.address})...")
    
    try:
        async with BleakClient(device.address) as client:
            print(f"✅ Connected!")
            print()
            
            # Check available services
            print("🔧 Available services:")
            for service in client.services:
                print(f"   - {service.uuid}: {service.description}")
            print()
            
            # Try to read battery level
            try:
                battery_data = await client.read_gatt_char(BATTERY_LEVEL_UUID)
                battery_level = int(battery_data[0])
                print(f"🔋 Battery Level: {battery_level}%")
            except Exception as e:
                print(f"⚠️  Could not read battery: {e}")
            
            print()
            print("❤️  Reading heart rate for 10 seconds...")
            print("   (Press Ctrl+C to stop early)")
            print()
            
            # Subscribe to heart rate notifications
            heart_rate_values = []
            
            def notification_handler(sender, data):
                """Handle heart rate notifications."""
                heart_rate = parse_heart_rate(data)
                heart_rate_values.append(heart_rate)
                print(f"   Heart Rate: {heart_rate} BPM")
            
            try:
                await client.start_notify(HEART_RATE_MEASUREMENT_UUID, notification_handler)
                await asyncio.sleep(10)
                await client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
            except KeyboardInterrupt:
                print("\n⏹️  Stopped by user")
                await client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
            except Exception as e:
                print(f"   Error reading heart rate: {e}")
            
            print()
            print("✅ Test completed successfully!")
            print()
            print("🎉 Your Polar sensor is working correctly!")
            print("   You can now install this integration in Home Assistant.")
            
    except BleakError as e:
        print(f"❌ Connection failed: {e}")
        print()
        print("Troubleshooting:")
        print("- Make sure the sensor is not connected to another device")
        print("- Try turning the sensor off and on again (remove and wear)")
        print("- Ensure you're close enough to the sensor")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    return True


async def main():
    """Main test function."""
    print("=" * 60)
    print("  Polar Bluetooth Heart Rate Sensor Test")
    print("=" * 60)
    print()
    
    # Check if bleak is installed
    try:
        import bleak
        print(f"✅ Bleak library installed")
    except ImportError:
        print("❌ Bleak library not found!")
        print("   Install it with: pip install bleak")
        return
    
    print()
    
    # Scan for devices
    device = await scan_for_polar_devices()
    if not device:
        return
    
    # Test the sensor
    await test_polar_sensor(device)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(0)
