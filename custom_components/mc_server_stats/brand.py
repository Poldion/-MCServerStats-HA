"""Serve integration brand icons via custom HTTP views."""
from __future__ import annotations

from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView

ICON_DIR = Path(__file__).parent

# Map of filename patterns the HA frontend may request
ICON_FILES = {
    "icon.png": "icon.png",
    "icon@2x.png": "icon@2x.png",
    "dark_icon.png": "dark_icon.png",
    "dark_icon@2x.png": "dark_icon@2x.png",
    "logo.png": "icon.png",
    "logo@2x.png": "icon@2x.png",
    "dark_logo.png": "dark_icon.png",
    "dark_logo@2x.png": "dark_icon@2x.png",
}


class BrandIconView(HomeAssistantView):
    """Serve brand icons for the mc_server_stats integration."""

    requires_auth = False

    def __init__(self, url_prefix: str) -> None:
        self.url = url_prefix + "/{filename}"
        self.name = url_prefix.replace("/", "_").strip("_") + "_icons"

    async def get(self, request: web.Request, filename: str) -> web.Response:
        """Return the requested icon file."""
        mapped = ICON_FILES.get(filename)
        if not mapped:
            raise web.HTTPNotFound()

        icon_path = ICON_DIR / mapped
        if not icon_path.is_file():
            raise web.HTTPNotFound()

        return web.FileResponse(icon_path)


def register_icon_views(hass) -> None:
    """Register all brand icon views."""
    from .const import DOMAIN

    prefixes = [
        f"/brands/{DOMAIN}",
        f"/brands/_/{DOMAIN}",
    ]
    for prefix in prefixes:
        hass.http.register_view(BrandIconView(prefix))

