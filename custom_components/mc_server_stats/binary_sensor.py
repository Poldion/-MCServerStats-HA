"""Binary sensor platform for Minecraft Server Stats."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, CONF_PORT, CONF_SERVER_NAME, DOMAIN
from .coordinator import McServerData, McServerStatsCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Minecraft Server Stats binary sensor entities."""
    coordinator: McServerStatsCoordinator = hass.data[DOMAIN][entry.entry_id]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    custom_name = entry.data.get(CONF_SERVER_NAME)

    async_add_entities(
        [McServerOnlineBinarySensor(coordinator, host, port, custom_name)],
        update_before_add=True,
    )


class McServerOnlineBinarySensor(
    CoordinatorEntity[McServerStatsCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether a Minecraft server is online."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, host, port, custom_name=None):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._host = host
        self._port = port

        display_name = custom_name or f"{host}:{port}"

        self._attr_unique_id = f"{host}_{port}_online"
        self._attr_name = f"{display_name} Status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
            name=custom_name or f"Minecraft Server {host}:{port}",
            manufacturer="Mojang",
            model="Minecraft Java Server",
        )

    @property
    def _server_data(self) -> McServerData:
        """Return data for this server."""
        if self.coordinator.data:
            return self.coordinator.data
        return McServerData()

    @property
    def is_on(self) -> bool:
        """Return True if the server is online."""
        return self._server_data.online

