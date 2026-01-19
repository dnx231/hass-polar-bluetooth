"""Sensor platform for Polar Bluetooth integration."""
from __future__ import annotations

import asyncio
import logging
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
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polar Bluetooth sensors from a config entry."""
    address = entry.data[CONF_DEVICE_ADDRESS]
    
    # Get the BLE device
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )
    
    if not ble_device:
        _LOGGER.error("Could not find Polar device with address %s", address)
        return
    
    # Create coordinator
    coordinator = PolarDataUpdateCoordinator(hass, ble_device)
    await coordinator.async_config_entry_first_refresh()
    
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
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"Polar {ble_device.name}",
            update_interval=asyncio.timedelta(seconds=SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Polar sensor."""
        try:
            # Update BLE device from scanner
            self.ble_device = (
                bluetooth.async_ble_device_from_address(
                    self.hass, self.ble_device.address.upper(), connectable=True
                )
                or self.ble_device
            )
            
            if not self._connected:
                await self._async_connect()
            
            data = {}
            
            # Use latest heart rate from notification
            data["heart_rate"] = self._latest_heart_rate
            
            # Read battery level periodically
            try:
                battery_data = await self._client.read_gatt_char(BATTERY_LEVEL_UUID)
                data["battery"] = int(battery_data[0])
            except Exception as err:
                _LOGGER.debug("Error reading battery: %s", err)
                data["battery"] = None
            
            return data
            
        except (BleakError, asyncio.TimeoutError) as err:
            self._connected = False
            if self._client:
                try:
                    await self._client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
                except Exception:
                    pass
                await self._client.disconnect()
                self._client = None
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    async def _async_connect(self) -> None:
        """Connect to the device."""
        _LOGGER.debug("Connecting to %s", self.ble_device.address)
        
        if self._client:
            await self._client.disconnect()
        
        selftry:
                await self._client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
            except Exception:
                pass
            await self._client.disconnect()
        
        self._client = BleakClient(self.ble_device)
        await self._client.connect()
        self._connected = True
        
        # Subscribe to heart rate notifications
        def heart_rate_notification_handler(sender, data):
            """Handle heart rate notifications."""
            self._latest_heart_rate = self._parse_heart_rate(data)
            _LOGGER.debug("Received heart rate: %s BPM", self._latest_heart_rate)
            # Trigger an update to notify entities
            self.hass.loop.call_soon_threadsafe(
                self.async_set_updated_data, {
                    "heart_rate": self._latest_heart_rate,
                    "battery": self.data.get("battery") if self.data else None,
                }
            )
        
        await self._client.start_notify(
            HEART_RATE_MEASUREMENT_UUID, heart_rate_notification_handler
        )d ttry:
                await self._client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
            except Exception:
                pass
            o Polar device %s", self.ble_device.name)

    @staticmethod
    def _parse_heart_rate(data: bytearray) -> int:
        """Parse heart rate from BLE characteristic data."""
        # First byte contains flags
        flags = data[0]
        
        # Check if heart rate is in 16-bit format (bit 0 of flags)
        if flags & 0x01:
            # 16-bit heart rate value
            heart_rate = int.from_bytes(data[1:3], byteorder="little")
        else:
            # 8-bit heart rate value
            heart_rate = data[1]
        
        return heart_rate

    async def async_shutdown(self) -> None:
        """Disconnect from device on shutdown."""
        if self._client and self._connected:
            await self._client.disconnect()
            self._client = None
            self._connected = False


class PolarHeartRateSensor(CoordinatorEntity[PolarDataUpdateCoordinator], SensorEntity):
    """Representation of a Polar heart rate sensor."""

    _attr_device_class = SensorDeviceClass.HEART_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfFrequency.BEATS_PER_MINUTE
    _attr_icon = "mdi:heart-pulse"

    def __init__(
        self,
        coordinator: PolarDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
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
        return super().available and self.coordinator.data.get("heart_rate") is not None


class PolarBatterySensor(CoordinatorEntity[PolarDataUpdateCoordinator], SensorEntity):
    """Representation of a Polar battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: PolarDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
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
