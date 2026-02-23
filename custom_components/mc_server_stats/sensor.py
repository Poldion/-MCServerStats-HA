"""Sensor platform for Minecraft Server Stats."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
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
    """Set up Minecraft Server Stats sensor entities."""
    coordinator: McServerStatsCoordinator = hass.data[DOMAIN][entry.entry_id]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    custom_name = entry.data.get(CONF_SERVER_NAME)

    async_add_entities(
        [
            McServerPlayerCountSensor(coordinator, host, port, custom_name),
            McServerMaxPlayersSensor(coordinator, host, port, custom_name),
            McServerMotdSensor(coordinator, host, port, custom_name),
            McServerVersionSensor(coordinator, host, port, custom_name),
            McServerLatencySensor(coordinator, host, port, custom_name),
            McServerPlayerListSensor(coordinator, host, port, custom_name),
        ],
        update_before_add=True,
    )


class McServerSensorBase(CoordinatorEntity[McServerStatsCoordinator], SensorEntity):
    """Base class for Minecraft server sensor entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: McServerStatsCoordinator,
        host: str,
        port: int,
        sensor_type: str,
        name_suffix: str,
        custom_name: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._host = host
        self._port = port
        self._sensor_type = sensor_type

        display_name = custom_name or f"{host}:{port}"

        self._attr_unique_id = f"{host}_{port}_{sensor_type}"
        self._attr_name = f"{display_name} {name_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
            name=custom_name or f"Minecraft Server {host}:{port}",
            manufacturer="Mojang",
            model="Minecraft Java Server",
        )

    @property
    def _server_data(self) -> McServerData:
        """Return data for this server, or a default if unavailable."""
        if self.coordinator.data:
            return self.coordinator.data
        return McServerData()


class McServerPlayerCountSensor(McServerSensorBase):
    """Sensor for the current player count."""

    _attr_icon = "mdi:account-group"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, host, port, custom_name=None):
        super().__init__(coordinator, host, port, "players_online", "Spieler Online", custom_name)

    @property
    def native_value(self):
        return self._server_data.players_online

    @property
    def extra_state_attributes(self):
        return {"max_players": self._server_data.players_max}


class McServerMaxPlayersSensor(McServerSensorBase):
    """Sensor for the max player count."""

    _attr_icon = "mdi:account-group-outline"

    def __init__(self, coordinator, host, port, custom_name=None):
        super().__init__(coordinator, host, port, "players_max", "Max Spieler", custom_name)

    @property
    def native_value(self):
        return self._server_data.players_max


class McServerMotdSensor(McServerSensorBase):
    """Sensor for the server MOTD."""

    _attr_icon = "mdi:message-text"

    def __init__(self, coordinator, host, port, custom_name=None):
        super().__init__(coordinator, host, port, "motd", "MOTD", custom_name)

    @property
    def native_value(self):
        return self._server_data.motd or None


class McServerVersionSensor(McServerSensorBase):
    """Sensor for the server version."""

    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator, host, port, custom_name=None):
        super().__init__(coordinator, host, port, "version", "Version", custom_name)

    @property
    def native_value(self):
        return self._server_data.version or None


class McServerLatencySensor(McServerSensorBase):
    """Sensor for the server latency (ping)."""

    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, host, port, custom_name=None):
        super().__init__(coordinator, host, port, "latency", "Latenz", custom_name)

    @property
    def native_value(self):
        return self._server_data.latency


class McServerPlayerListSensor(McServerSensorBase):
    """Sensor that exposes the list of online players."""

    _attr_icon = "mdi:format-list-bulleted"

    def __init__(self, coordinator, host, port, custom_name=None):
        super().__init__(coordinator, host, port, "player_list", "Spielerliste", custom_name)

    @property
    def native_value(self):
        return len(self._server_data.player_list)

    @property
    def extra_state_attributes(self):
        return {"player_names": self._server_data.player_list}

