"""Config flow for Polar Bluetooth integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
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
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._discovered_device: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered Polar device: %s", discovery_info)
        
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        
        self._discovered_device = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or "Polar Sensor"
        }
        
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_device.name or "Polar Sensor",
                data={
                    CONF_DEVICE_NAME: self._discovered_device.name,
                    CONF_DEVICE_ADDRESS: self._discovered_device.address,
                },
            )
        
        self._set_confirm_only()
        
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovered_device.name or "Polar Sensor"
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            discovery_info = self._discovered_devices[address]
            
            await self.async_set_unique_id(discovery_info.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=discovery_info.name or "Polar Sensor",
                data={
                    CONF_DEVICE_NAME: discovery_info.name,
                    CONF_DEVICE_ADDRESS: discovery_info.address,
                },
            )

        current_addresses = self._async_current_ids()
        
        # Discover Polar devices
        for discovery_info in async_discovered_service_info(self.hass, connectable=True):
            if (
                discovery_info.address in current_addresses
                or discovery_info.address in self._discovered_devices
            ):
                continue
            
            # Check if it matches our Bluetooth filter (Polar devices)
            if discovery_info.name and discovery_info.name.startswith("Polar"):
                self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

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
