"""Sensor platform for Polar Bluetooth integration."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice

from homeassistant.components import bluetooth
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfFrequency,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    BATTERY_LEVEL_UUID,
    BATTERY_SERVICE_UUID,
    CONF_DEVICE_ADDRESS,
    DOMAIN,
    HEART_RATE_MEASUREMENT_UUID,
    HEART_RATE_SERVICE_UUID,
    SCAN_INTERVAL,
    STALE_DATA_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polar Bluetooth sensors from a config entry."""
    address = entry.data[CONF_DEVICE_ADDRESS]
    
    # Get the BLE device - may not be found if device is not broadcasting
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )
    
    if not ble_device:
        _LOGGER.warning(
            "Polar device with address %s not currently visible - "
            "will create sensors and wait for device to appear", 
            address
        )
        # Create a minimal BLEDevice placeholder
        # The coordinator will update it when the device appears
        from bleak.backends.device import BLEDevice as BLEDeviceType
        ble_device = BLEDeviceType(
            address=address.upper(),
            name=f"Polar Sensor {address[-8:].replace(':', '')}XX",
            details=None,
            rssi=-127  # Indicates not found
        )
    
    # Create coordinator
    coordinator = PolarDataUpdateCoordinator(hass, ble_device)
    
    # Try to do first refresh, but don't fail setup if it doesn't work
    # The coordinator will retry automatically via update_interval
    try:
        await asyncio.wait_for(
            coordinator.async_config_entry_first_refresh(),
            timeout=30.0
        )
    except (asyncio.TimeoutError, Exception) as err:
        _LOGGER.warning(
            "Initial connection to %s failed: %s - will retry automatically every %s seconds",
            address, err, SCAN_INTERVAL.total_seconds()
        )
        # Continue anyway - coordinator will retry
    
    # Create sensor entities
    entities = [
        PolarHeartRateSensor(coordinator, entry),
        PolarBatterySensor(coordinator, entry),
    ]
    
    async_add_entities(entities)


class PolarDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Polar sensor data."""

    def __init__(self, hass: HomeAssistant, ble_device: BLEDevice) -> None:
        """Initialize."""
        self.ble_device = ble_device
        self._client: BleakClient | None = None
        self._connected = False
        self._latest_heart_rate: int | None = None
        self._last_notification_time: float | None = None
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"Polar {ble_device.name}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Polar sensor."""
        # Update BLE device from scanner
        self.ble_device = (
            bluetooth.async_ble_device_from_address(
                self.hass, self.ble_device.address.upper(), connectable=True
            )
            or self.ble_device
        )
        
        # Start with last known values
        current_hr = self._latest_heart_rate
        current_battery = self.data.get("battery") if self.data else None
        
        # STEP 1: Check if heart rate data is stale (BEFORE attempting connection)
        if self._last_notification_time:
            time_since_last = time.time() - self._last_notification_time
            if time_since_last > STALE_DATA_THRESHOLD:
                # Only log warning if we're transitioning to unavailable
                # Check the previous data state, not current_hr which comes from _latest_heart_rate
                was_available = self.data.get("heart_rate") if self.data else None
                if was_available is not None:
                    _LOGGER.warning(
                        "No heart rate notifications received for %.0f seconds (threshold: %ds) - marking as unavailable",
                        time_since_last,
                        STALE_DATA_THRESHOLD
                    )
                current_hr = None  # This will make the sensor unavailable
                
        # STEP 2: Check if we need to (re)connect
        needs_connect = (
            not self._client 
            or not self._connected 
            or (hasattr(self._client, 'is_connected') and not self._client.is_connected)
        )
        
        if needs_connect:
            _LOGGER.info("Polar device not connected, attempting to connect to %s...", self.ble_device.address)
            try:
                await self._async_connect()
            except Exception as err:
                _LOGGER.warning("Failed to connect to Polar device: %s - will retry in %s seconds", err, SCAN_INTERVAL.total_seconds())
                self._connected = False
                self._client = None
                # Don't raise - return data even if connection failed
                return {
                    "heart_rate": current_hr,
                    "battery": current_battery,
                }
        
        # STEP 3: Read battery level periodically (only if connected)
        # Battery reading is lightweight, so we read it every cycle (30s)
        if self._connected and self._client:
            try:
                battery_data = await asyncio.wait_for(
                    self._client.read_gatt_char(BATTERY_LEVEL_UUID),
                    timeout=5.0
                )

                # Deal with occasional garbage values over 100
                current_battery = min(int(battery_data[0]), 100)
            except asyncio.TimeoutError:
                _LOGGER.debug("Battery read timeout - connection may be slow")
                # Don't mark as disconnected for just a slow battery read
            except Exception as err:
                _LOGGER.debug("Error reading battery: %s", err)
                # Battery read failed - connection might be dead
                self._connected = False
        
        return {
            "heart_rate": current_hr,
            "battery": current_battery,
        }

    async def _async_connect(self) -> None:
        """Connect to the device."""
        _LOGGER.info("Attempting connection to %s...", self.ble_device.address)
        
        # Clean up any existing connection first
        if self._client:
            try:
                await asyncio.wait_for(
                    self._client.stop_notify(HEART_RATE_MEASUREMENT_UUID),
                    timeout=2.0
                )
            except Exception as cleanup_err:
                _LOGGER.debug("Error stopping notifications during cleanup: %s", cleanup_err)
            try:
                await asyncio.wait_for(
                    self._client.disconnect(),
                    timeout=2.0
                )
            except Exception as cleanup_err:
                _LOGGER.debug("Error disconnecting during cleanup: %s", cleanup_err)
            self._client = None

        # Use HASS Bluetooth API (works with ESPHome proxies)
        try:
            _LOGGER.debug("Connecting via HASS Bluetooth API for %s", self.ble_device.address)
            
            # Create BleakClient using the BLE device
            self._client = BleakClient(self.ble_device)
            
            # Connect with timeout
            await asyncio.wait_for(
                self._client.connect(),
                timeout=20.0
            )
            
            self._connected = True
            _LOGGER.info("BLE client connected successfully via %s", 
                        self.ble_device.details.get('source', 'unknown') if self.ble_device.details else 'direct')
        except asyncio.TimeoutError as err:
            _LOGGER.warning("Connection timeout after 20s: %s - will retry later", err)
            self._connected = False
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None
            raise
        except Exception as err:
            _LOGGER.warning("Connection failed with error: %s (type: %s) - will retry later", err, type(err).__name__)
            self._connected = False
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None
            raise
        
        # Subscribe to heart rate notifications
        def heart_rate_notification_handler(sender, data):
            """Handle heart rate notifications."""
            self._latest_heart_rate = self._parse_heart_rate(data)
            
            # Only update timestamp for valid heart rates (> 0)
            # Polar device sends 0 when losing skin contact - don't reset the timer
            if self._latest_heart_rate > 0:
                self._last_notification_time = time.time()
                _LOGGER.debug("Received heart rate: %s BPM", self._latest_heart_rate)
                
                # Push update immediately to entities for real-time updates
                self.hass.add_job(self._handle_notification_update)
            else:
                _LOGGER.debug("Received invalid heart rate: %s BPM - ignoring", self._latest_heart_rate)
        
        try:
            await asyncio.wait_for(
                self._client.start_notify(
                    HEART_RATE_MEASUREMENT_UUID, heart_rate_notification_handler
                ),
                timeout=5.0
            )
            _LOGGER.info("Connected to Polar device %s and subscribed to notifications", self.ble_device.name)
        except Exception as err:
            _LOGGER.error("Failed to subscribe to heart rate notifications: %s", err)
            self._connected = False
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None
            raise

    @callback
    def _handle_notification_update(self) -> None:
        """Handle heart rate notification update in event loop."""
        self.async_set_updated_data({
            "heart_rate": self._latest_heart_rate,
            "battery": self.data.get("battery") if self.data else None,
        })

    @staticmethod
    def _parse_heart_rate(data: bytearray) -> int:
        """Parse heart rate from BLE characteristic data."""
        flags = data[0]
        if flags & 0x01:
            heart_rate = int.from_bytes(data[1:3], byteorder="little")
        else:
            heart_rate = data[1]
        return heart_rate

    async def async_shutdown(self) -> None:
        """Disconnect from device on shutdown."""
        if self._client and self._connected:
            try:
                await self._client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
            except Exception:
                pass
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
            self._connected = False


class PolarHeartRateSensor(CoordinatorEntity[PolarDataUpdateCoordinator], SensorEntity):
    """Representation of a Polar heart rate sensor."""

    _attr_device_class = None
    _attr_native_unit_of_measurement = "bpm"
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, coordinator: PolarDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.ble_device.name} Heart Rate"
        self._attr_unique_id = f"{coordinator.ble_device.address}_heart_rate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.ble_device.address)},
            "name": coordinator.ble_device.name or "Polar Sensor",
            "manufacturer": "Polar",
            "model": "Heart Rate Monitor",
            "connections": {("bluetooth", coordinator.ble_device.address)},
        }

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get("heart_rate")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        hr = self.coordinator.data.get("heart_rate")
        return super().available and hr is not None and hr > 0


class PolarBatterySensor(CoordinatorEntity[PolarDataUpdateCoordinator], SensorEntity):
    """Representation of a Polar battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PolarDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.ble_device.name} Battery"
        self._attr_unique_id = f"{coordinator.ble_device.address}_battery"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.ble_device.address)},
            "name": coordinator.ble_device.name or "Polar Sensor",
            "manufacturer": "Polar",
            "model": "Heart Rate Monitor",
            "connections": {("bluetooth", coordinator.ble_device.address)},
        }

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get("battery")
