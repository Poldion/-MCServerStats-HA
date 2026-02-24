"""The Minecraft Server Stats integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

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
CARD_REGISTERED_KEY = f"{DOMAIN}_card_registered"

CARD_STATIC_PATH = f"/hacsfiles/{DOMAIN}"
CARD_JS = "mc-server-stats-card.js"
CARD_URL = f"{CARD_STATIC_PATH}/{CARD_JS}"
CARD_DIR = Path(__file__).parent / "www"

RESOURCE_STARTUP_DELAY = 5
RESOURCE_RETRY_DELAY = 30
RESOURCE_MAX_RETRIES = 3
RESOURCE_RETRY_KEY = f"{DOMAIN}_card_register_retries"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Serve the custom card JS file via HTTP."""
    # Serve the www/ folder under /hacsfiles/mc_server_stats/
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_STATIC_PATH, str(CARD_DIR), cache_headers=False
            ),
        ]
    )
    hass.async_create_task(_async_register_lovelace_resource(hass))
    return True


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Add the card JS as a Lovelace dashboard resource so it appears in the card picker."""
    if hass.data.get(CARD_REGISTERED_KEY):
        return

    def _schedule_retry(delay: int, *, increment: bool = True) -> None:
        if hass.data.get(CARD_REGISTERED_KEY):
            return
        retries = hass.data.get(RESOURCE_RETRY_KEY, 0)
        if increment:
            if retries >= RESOURCE_MAX_RETRIES:
                _LOGGER.warning(
                    "Could not auto-register Lovelace resource. "
                    "Please add '%s' manually under Settings → Dashboards → Resources (type: JavaScript Module).",
                    CARD_URL,
                )
                return
            hass.data[RESOURCE_RETRY_KEY] = retries + 1

        @callback
        def _retry(_now: datetime) -> None:
            hass.async_create_task(_async_register_lovelace_resource(hass))

        async_call_later(hass, delay, HassJob(_retry))

    try:
        lovelace = hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None) if lovelace else None
        if resources is None:
            _LOGGER.debug("Lovelace resources not available yet")
            _schedule_retry(RESOURCE_RETRY_DELAY)
            return

        # Ensure the collection is loaded
        if hasattr(resources, "loaded") and not resources.loaded:
            await resources.async_load()
        elif hasattr(resources, "async_get_info"):
            await resources.async_get_info()

        # Check if already registered (and clean up stale entries)
        items = []
        if hasattr(resources, "async_items"):
            items = list(resources.async_items())
        elif hasattr(resources, "data"):
            items = list(resources.data.values()) if isinstance(resources.data, dict) else list(resources.data)

        for item in items:
            url = item.get("url", "") if isinstance(item, dict) else getattr(item, "url", "")
            item_id = item.get("id", "") if isinstance(item, dict) else getattr(item, "id", "")
            if url == CARD_URL:
                hass.data[CARD_REGISTERED_KEY] = True
                hass.data.pop(RESOURCE_RETRY_KEY, None)
                _LOGGER.debug("Lovelace resource already registered: %s", url)
                return
            if CARD_JS in url and url != CARD_URL:
                try:
                    await resources.async_delete_item(item_id)
                    _LOGGER.info("Removed stale card resource: %s", url)
                except Exception:  # noqa: BLE001
                    pass

        # Create the resource
        await resources.async_create_item({"res_type": "module", "url": CARD_URL})
        hass.data[CARD_REGISTERED_KEY] = True
        hass.data.pop(RESOURCE_RETRY_KEY, None)
        _LOGGER.info("Auto-registered Lovelace resource: %s", CARD_URL)

    except Exception as exc:  # noqa: BLE001
        _LOGGER.debug("Lovelace resource registration attempt failed: %s", exc)
        _schedule_retry(RESOURCE_RETRY_DELAY)


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

