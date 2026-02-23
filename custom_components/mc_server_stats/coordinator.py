"""Data update coordinator for Minecraft Server Stats."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from mcstatus import JavaServer

from .const import DOMAIN, SCAN_PORT_MIN, SCAN_PORT_MAX

_LOGGER = logging.getLogger(__name__)


@dataclass
class McServerData:
    """Dataclass holding the status of a single Minecraft server."""

    online: bool = False
    players_online: int = 0
    players_max: int = 0
    motd: str = ""
    version: str = ""
    latency: float = 0.0
    player_list: list[str] = field(default_factory=list)
    modded: bool = False
    mod_count: int = 0
    mod_list: list[dict[str, str]] = field(default_factory=list)


def _strip_formatting(text: str) -> str:
    """Remove Minecraft formatting codes from a string."""
    return re.sub(r"\u00a7.", "", re.sub(r"§.", "", text))


async def async_scan_ports(
    host: str,
    port_min: int = SCAN_PORT_MIN,
    port_max: int = SCAN_PORT_MAX,
    timeout: float = 3.0,
) -> list[int]:
    """Scan a range of ports on a host for running Minecraft servers."""
    found_ports: list[int] = []

    async def _check_port(port: int) -> None:
        try:
            server = JavaServer(host, port, timeout=timeout)
            await server.async_status()
            found_ports.append(port)
        except Exception:
            pass

    await asyncio.gather(*[_check_port(p) for p in range(port_min, port_max + 1)])
    found_ports.sort()
    return found_ports


class McServerStatsCoordinator(DataUpdateCoordinator[McServerData]):
    """Coordinator that polls a single Minecraft server for its status."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        update_interval_seconds: int,
    ) -> None:
        """Initialize the coordinator."""
        self.host = host
        self.port = port

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{host}_{port}",
            update_interval=timedelta(seconds=update_interval_seconds),
        )

    async def _async_update_data(self) -> McServerData:
        """Fetch status from the Minecraft server."""
        try:
            server = JavaServer(self.host, self.port, timeout=5)
            status = await server.async_status()

            motd_text = ""
            if hasattr(status, "motd") and status.motd is not None:
                if hasattr(status.motd, "to_plain"):
                    motd_text = _strip_formatting(status.motd.to_plain())
                else:
                    motd_text = _strip_formatting(str(status.motd))
            elif hasattr(status, "description"):
                motd_text = _strip_formatting(str(status.description))

            player_names: list[str] = []
            if status.players and status.players.sample:
                player_names = [p.name for p in status.players.sample]

            # Extract Forge mod data if available
            modded = False
            mod_count = 0
            mod_list: list[dict[str, str]] = []
            if hasattr(status, "forge_data") and status.forge_data is not None:
                modded = True
                mod_list = [
                    {"id": mod.name, "version": mod.marker}
                    for mod in status.forge_data.mods
                ]
                mod_count = len(mod_list)

            return McServerData(
                online=True,
                players_online=status.players.online if status.players else 0,
                players_max=status.players.max if status.players else 0,
                motd=motd_text,
                version=status.version.name if status.version else "Unknown",
                latency=round(status.latency, 2),
                player_list=player_names,
                modded=modded,
                mod_count=mod_count,
                mod_list=mod_list,
            )
        except Exception:
            return McServerData(online=False)


class McDiscoveryCoordinator(DataUpdateCoordinator[list[int]]):
    """Coordinator that periodically scans for new Minecraft servers on a host."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        update_interval_seconds: int,
        port_min: int = SCAN_PORT_MIN,
        port_max: int = SCAN_PORT_MAX,
    ) -> None:
        """Initialize the discovery coordinator."""
        self.host = host
        self.port_min = port_min
        self.port_max = port_max

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_discovery_{host}",
            update_interval=timedelta(seconds=update_interval_seconds),
        )

    async def _async_update_data(self) -> list[int]:
        """Scan for Minecraft servers and return the list of open ports."""
        try:
            return await async_scan_ports(self.host, self.port_min, self.port_max)
        except Exception:
            _LOGGER.debug("Discovery scan failed for %s", self.host)
            return self.data or []

