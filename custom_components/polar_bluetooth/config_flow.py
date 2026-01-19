"""Config flow for Polar Bluetooth integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DEVICE_ADDRESS, CONF_DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PolarBluetoothConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Polar Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.info("✓ async_step_bluetooth called - Device: %s (%s)", 
                    discovery_info.name, discovery_info.address)
        _LOGGER.debug("  RSSI: %s, TX Power: %s", discovery_info.rssi, discovery_info.tx_power)
        _LOGGER.debug("  Service data keys: %s", list(discovery_info.service_data.keys()) if discovery_info.service_data else "None")
        
        try:
            await self.async_set_unique_id(discovery_info.address)
            _LOGGER.debug("  ✓ Unique ID set for %s", discovery_info.address)
        except Exception as err:
            _LOGGER.error("  ✗ Failed to set unique ID: %s", err)
            raise
        
        self._abort_if_unique_id_configured()
        _LOGGER.debug("  ✓ Not yet configured")
        
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or f"Polar Sensor ({discovery_info.address})"
        }
        
        _LOGGER.info("  → Moving to bluetooth_confirm")
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        
        if user_input is not None:
            _LOGGER.info("✓ User confirmed device: %s (%s)", 
                        discovery_info.name or discovery_info.address, 
                        discovery_info.address)
            try:
                device_name = discovery_info.name or f"Polar Sensor ({discovery_info.address})"
                return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_DEVICE_NAME: discovery_info.name,
                        CONF_DEVICE_ADDRESS: discovery_info.address,
                    },
                )
            except Exception as err:
                _LOGGER.error("  ✗ Failed to create config entry: %s", err)
                raise
        
        device_name = discovery_info.name or f"Polar Sensor ({discovery_info.address})"
        _LOGGER.debug("Showing confirmation form for: %s", device_name)
        self._set_confirm_only()
        
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": device_name
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        _LOGGER.info("async_step_user called - Manual setup initiated")
        
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            _LOGGER.info("User selected device: %s", address)
            
            if address not in self._discovered_devices:
                _LOGGER.error("  ✗ Selected address not in discovered devices")
                return self.async_abort(reason="invalid_device")
            
            discovery_info = self._discovered_devices[address]
            _LOGGER.debug("  Creating entry for: %s (%s)", discovery_info.name, address)
            
            try:
                await self.async_set_unique_id(discovery_info.address, raise_on_progress=False)
            except Exception as err:
                _LOGGER.error("  ✗ Failed to set unique ID: %s", err)
                raise
            
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=discovery_info.name or "Polar Sensor",
                data={
                    CONF_DEVICE_NAME: discovery_info.name,
                    CONF_DEVICE_ADDRESS: discovery_info.address,
                },
            )

        current_addresses = self._async_current_ids()
        _LOGGER.debug("Already configured addresses: %s", current_addresses)
        
        # Discover devices using async_discovered_service_info (gets all devices from scanner)
        _LOGGER.info("Scanning for devices...")
        all_devices = list(async_discovered_service_info(self.hass, connectable=True))
        _LOGGER.info("Found %d total BLE devices in scanner", len(all_devices))
        
        for discovery_info in all_devices:
            address = discovery_info.address
            name = discovery_info.name or "Unknown"
            
            _LOGGER.debug("  Checking device: %s (%s)", name, address)
            
            if address in current_addresses:
                _LOGGER.debug("    → Already configured")
                continue
            
            if address in self._discovered_devices:
                _LOGGER.debug("    → Already in discovered list")
                continue
            
            # Check if it's a Polar device by name
            if discovery_info.name and discovery_info.name.startswith("Polar"):
                _LOGGER.info("  ✓ Added Polar device: %s (%s)", name, address)
                self._discovered_devices[address] = discovery_info
            else:
                _LOGGER.debug("    → Not a Polar device (name: %s)", name)
        
        _LOGGER.info("Polar devices found: %d", len(self._discovered_devices))

        if not self._discovered_devices:
            _LOGGER.warning("✗ No Polar devices found in manual discovery!")
            return self.async_abort(reason="no_devices_found")

        _LOGGER.info("Showing device selection with %d devices", len(self._discovered_devices))
        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        service_info.address: (
                            f"{service_info.name} ({service_info.address})"
                        )
                        for service_info in self._discovered_devices.values()
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )
