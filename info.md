# Minecraft Server Stats

Monitor your Minecraft Java servers directly from Home Assistant.

## What it does

- Automatically scans for Minecraft servers on your network
- Tracks players, version, MOTD, latency, and mods for each server
- Auto-discovers new servers and shows them as "Discovered" in HA
- Includes a beautiful dashboard card with auto-rotation between servers

## Dashboard Card

After installation, just add this to your dashboard:

```yaml
type: custom:mc-server-stats-card
```

The card automatically finds all your servers – no configuration needed! Use the visual editor to customize it.

