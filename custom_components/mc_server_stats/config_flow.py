"""Config flow for Minecraft Server Stats integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_DISCOVERY_INTERVAL,
    CONF_HOST,
    CONF_PORT,
    CONF_PORT_MAX,
    CONF_PORT_MIN,
    CONF_SCAN_INTERVAL,
    CONF_SERVER_NAME,
    DEFAULT_DISCOVERY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SCAN_PORT_MAX,
    SCAN_PORT_MIN,
)
from .coordinator import async_scan_ports

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=3600)
        ),
        vol.Optional(CONF_DISCOVERY_INTERVAL, default=DEFAULT_DISCOVERY_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=30, max=86400)
        ),
        vol.Optional(CONF_PORT_MIN, default=SCAN_PORT_MIN): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_PORT_MAX, default=SCAN_PORT_MAX): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
    }
)


class McServerStatsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Server Stats."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str = ""
        self._ports: list[int] = []
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._discovery_interval: int = DEFAULT_DISCOVERY_INTERVAL
        self._port_min: int = SCAN_PORT_MIN
        self._port_max: int = SCAN_PORT_MAX
        # Used by discovery step
        self._disc_host: str = ""
        self._disc_port: int = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step – enter host and scan for servers."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            self._scan_interval = user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
            self._discovery_interval = user_input.get(
                CONF_DISCOVERY_INTERVAL, DEFAULT_DISCOVERY_INTERVAL
            )
            self._port_min = user_input.get(CONF_PORT_MIN, SCAN_PORT_MIN)
            self._port_max = user_input.get(CONF_PORT_MAX, SCAN_PORT_MAX)

            if self._port_min > self._port_max:
                errors["base"] = "invalid_port_range"
            else:
                self._ports = await async_scan_ports(
                    self._host, self._port_min, self._port_max
                )

                if not self._ports:
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_select_servers()

        return self.async_show_form(
            step_id="user",
            data_schema=USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_select_servers(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user select which servers to add and give them names."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entries_created = 0

            for port in self._ports:
                name_key = f"name_{port}"
                if name_key in user_input:
                    name = user_input[name_key].strip()
                    if name:
                        unique_id = f"{self._host}:{port}"
                        existing = await self.async_set_unique_id(unique_id)
                        if existing:
                            self.context.pop("unique_id", None)
                            continue

                        entry_data = {
                            CONF_HOST: self._host,
                            CONF_PORT: port,
                            CONF_SCAN_INTERVAL: self._scan_interval,
                            CONF_DISCOVERY_INTERVAL: self._discovery_interval,
                            CONF_PORT_MIN: self._port_min,
                            CONF_PORT_MAX: self._port_max,
                            CONF_SERVER_NAME: name,
                        }

                        if entries_created == 0:
                            entries_created += 1
                            self._first_entry = {
                                "title": name,
                                "data": entry_data,
                            }
                        else:
                            entries_created += 1
                            self.hass.async_create_task(
                                self.hass.config_entries.flow.async_init(
                                    DOMAIN,
                                    context={"source": "internal"},
                                    data=entry_data,
                                )
                            )

            if entries_created == 0:
                errors["base"] = "no_servers_selected"
            else:
                await self.async_set_unique_id(
                    f"{self._first_entry['data'][CONF_HOST]}:{self._first_entry['data'][CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._first_entry["title"],
                    data=self._first_entry["data"],
                )

        schema_dict: dict[vol.Marker, Any] = {}
        for port in self._ports:
            schema_dict[
                vol.Optional(
                    f"name_{port}",
                    default=f"Minecraft Server ({self._host}:{port})",
                )
            ] = str

        return self.async_show_form(
            step_id="select_servers",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "host": self._host,
                "count": str(len(self._ports)),
            },
            errors=errors,
        )

    async def async_step_internal(
        self, discovery_info: dict[str, Any]
    ) -> FlowResult:
        """Handle creation of additional server entries from the select_servers step."""
        unique_id = f"{discovery_info[CONF_HOST]}:{discovery_info[CONF_PORT]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=discovery_info[CONF_SERVER_NAME],
            data=discovery_info,
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any]
    ) -> FlowResult:
        """Handle a discovered Minecraft server."""
        self._disc_host = discovery_info[CONF_HOST]
        self._disc_port = discovery_info[CONF_PORT]

        unique_id = f"{self._disc_host}:{self._disc_port}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {
            "host": self._disc_host,
            "port": str(self._disc_port),
        }

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user name the discovered server and confirm setup."""
        if user_input is not None:
            name = user_input[CONF_SERVER_NAME].strip()
            # Inherit settings from an existing entry on this host
            scan_interval = DEFAULT_SCAN_INTERVAL
            discovery_interval = DEFAULT_DISCOVERY_INTERVAL
            port_min = SCAN_PORT_MIN
            port_max = SCAN_PORT_MAX
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data.get(CONF_HOST) == self._disc_host:
                    scan_interval = entry.data.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    )
                    discovery_interval = entry.data.get(
                        CONF_DISCOVERY_INTERVAL, DEFAULT_DISCOVERY_INTERVAL
                    )
                    port_min = entry.data.get(CONF_PORT_MIN, SCAN_PORT_MIN)
                    port_max = entry.data.get(CONF_PORT_MAX, SCAN_PORT_MAX)
                    break

            return self.async_create_entry(
                title=name,
                data={
                    CONF_HOST: self._disc_host,
                    CONF_PORT: self._disc_port,
                    CONF_SCAN_INTERVAL: scan_interval,
                    CONF_DISCOVERY_INTERVAL: discovery_interval,
                    CONF_PORT_MIN: port_min,
                    CONF_PORT_MAX: port_max,
                    CONF_SERVER_NAME: name,
                },
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SERVER_NAME,
                        default=f"Minecraft Server ({self._disc_host}:{self._disc_port})",
                    ): str,
                }
            ),
            description_placeholders={
                "host": self._disc_host,
                "port": str(self._disc_port),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return McServerStatsOptionsFlow()


class McServerStatsOptionsFlow(OptionsFlow):
    """Handle options flow for Minecraft Server Stats."""


    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            port_min = user_input.get(
                CONF_PORT_MIN,
                self.config_entry.data.get(CONF_PORT_MIN, SCAN_PORT_MIN),
            )
            port_max = user_input.get(
                CONF_PORT_MAX,
                self.config_entry.data.get(CONF_PORT_MAX, SCAN_PORT_MAX),
            )
            if port_min > port_max:
                errors["base"] = "invalid_port_range"
            else:
                return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        current_discovery = self.config_entry.options.get(
            CONF_DISCOVERY_INTERVAL,
            self.config_entry.data.get(CONF_DISCOVERY_INTERVAL, DEFAULT_DISCOVERY_INTERVAL),
        )
        current_port_min = self.config_entry.options.get(
            CONF_PORT_MIN,
            self.config_entry.data.get(CONF_PORT_MIN, SCAN_PORT_MIN),
        )
        current_port_max = self.config_entry.options.get(
            CONF_PORT_MAX,
            self.config_entry.data.get(CONF_PORT_MAX, SCAN_PORT_MAX),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                    vol.Optional(
                        CONF_DISCOVERY_INTERVAL, default=current_discovery
                    ): vol.All(vol.Coerce(int), vol.Range(min=30, max=86400)),
                    vol.Optional(
                        CONF_PORT_MIN, default=current_port_min
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                    vol.Optional(
                        CONF_PORT_MAX, default=current_port_max
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                }
            ),
            errors=errors,
        )

