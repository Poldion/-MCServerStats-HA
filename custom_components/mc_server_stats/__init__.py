"""The Minecraft Server Stats integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

from homeassistant.components.frontend import async_register_extra_module_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_DISCOVERY_INTERVAL,
    CONF_HOST,
    CONF_PORT,
    CONF_PORT_MAX,
    CONF_PORT_MIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_DISCOVERY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SCAN_PORT_MAX,
    SCAN_PORT_MIN,
)
from .coordinator import McDiscoveryCoordinator, McServerStatsCoordinator

_LOGGER = logging.getLogger(__name__)

DISCOVERY_KEY = f"{DOMAIN}_discovery"

CARD_STATIC_PATH = f"/hacsfiles/{DOMAIN}"
CARD_JS = "mc-server-stats-card.js"
CARD_URL = f"{CARD_STATIC_PATH}/{CARD_JS}"
CARD_DIR = Path(__file__).parent / "www"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the custom card as a frontend module."""
    # Serve the www/ folder under /hacsfiles/mc_server_stats/
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_STATIC_PATH, str(CARD_DIR), cache_headers=False
            ),
        ]
    )

    # Inject the card JS into every Lovelace dashboard automatically.
    # This bypasses the Lovelace resources storage entirely – no manual
    # "Add resource" step is needed.
    async_register_extra_module_url(hass, CARD_URL)
    _LOGGER.debug("Registered frontend extra module: %s", CARD_URL)

    return True



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Minecraft Server Stats from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    discovery_interval = entry.options.get(
        CONF_DISCOVERY_INTERVAL,
        entry.data.get(CONF_DISCOVERY_INTERVAL, DEFAULT_DISCOVERY_INTERVAL),
    )
    port_min = entry.options.get(
        CONF_PORT_MIN,
        entry.data.get(CONF_PORT_MIN, SCAN_PORT_MIN),
    )
    port_max = entry.options.get(
        CONF_PORT_MAX,
        entry.data.get(CONF_PORT_MAX, SCAN_PORT_MAX),
    )

    coordinator = McServerStatsCoordinator(hass, host, port, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Start the background discovery scanner for this host (shared across entries)
    await _async_start_discovery(hass, host, discovery_interval, port_min, port_max)


    return True


async def _async_start_discovery(
    hass: HomeAssistant,
    host: str,
    discovery_interval: int,
    port_min: int,
    port_max: int,
) -> None:
    """Start a background discovery coordinator for a host (if not already running)."""
    hass.data.setdefault(DISCOVERY_KEY, {})

    if host in hass.data[DISCOVERY_KEY]:
        # Update the existing discovery coordinator with new settings
        existing: McDiscoveryCoordinator = hass.data[DISCOVERY_KEY][host]
        existing.port_min = port_min
        existing.port_max = port_max
        existing.update_interval = timedelta(seconds=discovery_interval)
        return

    discovery = McDiscoveryCoordinator(
        hass, host, discovery_interval, port_min, port_max
    )

    @callback
    def _on_discovery_update() -> None:
        """Check for newly discovered servers and trigger discovery flows."""
        if discovery.data is None:
            return

        # Collect all ports that already have a config entry for this host
        configured_ports: set[int] = set()
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_HOST) == host:
                configured_ports.add(entry.data.get(CONF_PORT, 0))

        # Also check pending flows to avoid duplicates
        pending_ports: set[int] = set()
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
            ctx = flow.get("context", {})
            if ctx.get("source") == "discovery":
                placeholders = ctx.get("title_placeholders", {})
                if placeholders.get("host") == host:
                    try:
                        pending_ports.add(int(placeholders.get("port", 0)))
                    except (ValueError, TypeError):
                        pass

        for port in discovery.data:
            if port not in configured_ports and port not in pending_ports:
                _LOGGER.info(
                    "Discovered new Minecraft server on %s:%s", host, port
                )
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "discovery"},
                        data={CONF_HOST: host, CONF_PORT: port},
                    )
                )

    discovery.async_add_listener(_on_discovery_update)
    await discovery.async_config_entry_first_refresh()
    hass.data[DISCOVERY_KEY][host] = discovery


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update – reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

        host = entry.data[CONF_HOST]

        # Check if there are remaining entries for this host
        remaining = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.data.get(CONF_HOST) == host and e.entry_id != entry.entry_id
        ]
        if not remaining and host in hass.data.get(DISCOVERY_KEY, {}):
            hass.data[DISCOVERY_KEY].pop(host, None)

        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)

    return unload_ok

