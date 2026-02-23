# 🎮 Minecraft Server Stats for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration that monitors Minecraft Java servers, automatically discovers new servers, and includes a beautiful dashboard card.

---

## ✨ Features

- 🔍 **Automatic Port Scanning** – Finds all MC servers in a configurable port range
- 🔔 **Auto-Discovery** – New servers are detected automatically and shown as "Discovered" on the integrations page
- 📛 **Custom Names** – Give each server a custom name
- 📊 **Sensors** per server:
  - 👥 **Players** – Count, max players, and player list as attributes
  - 📝 **MOTD** – Message of the Day
  - 🎮 **Version** – Server version (e.g. `1.20.4`)
  - ⏱️ **Latency** – Ping in milliseconds
  - 🧩 **Mods** – Vanilla/Modded status with full mod list (Forge/NeoForge)
  - 🟢 **Status** – Online/Offline binary sensor
- 🖼️ **Dashboard Card** – Custom Lovelace card with auto-rotation between servers and a visual editor

---

## 📦 Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click **⋮ (three dots)** → **Custom repositories**
3. Add the repository URL: `https://github.com/JoshS/MCServerStats-HA`
4. Category: **Integration**
5. Click **Add** → Find **"Minecraft Server Stats"** → **Download**
6. **Restart Home Assistant**

### Manual Installation

1. Copy the `custom_components/mc_server_stats` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

---

## ⚙️ Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"Minecraft Server Stats"**
3. Enter the **IP address or hostname** of your MC server
4. Optionally adjust the **port range**, **update interval**, and **discovery interval**
5. After the scan: Give each discovered server a **custom name**

---

## 🖼️ Dashboard Card

The Lovelace resource is **automatically registered** when the integration loads. Just add the card:

1. Open your Dashboard → **Edit** (pencil icon)
2. **Add Card → Manual**
3. Enter:

```yaml
type: custom:mc-server-stats-card
```

That's it! The card **automatically finds all configured Minecraft servers** and displays them. You can also configure it via the **visual editor** (pencil icon on the card).

### Card Options

| Option | Default | Description |
|---|---|---|
| `rotate_interval` | `8` | Seconds between server rotation (0 = disabled) |
| `show_header` | `true` | Display Minecraft icon and title at the top |
| `show_offline` | `false` | Include offline servers in rotation |
| `exclude_servers` | `[]` | List of server names to hide |

All options can be configured via the **visual editor** – no YAML needed!

---

## ⚙️ Integration Options

| Option | Default | Description |
|---|---|---|
| **IP Address / Hostname** | – | Address of the MC server |
| **Status update interval** | `60s` | How often to poll the server status |
| **Discovery scan interval** | `300s` | How often to scan for new servers |
| **Port range start** | `25565` | First port to scan |
| **Port range end** | `25575` | Last port to scan |

All options can be changed after setup via the **gear icon** on the integration page.

---

## 🔍 Auto-Discovery

Once at least one server is configured, the integration continuously scans the configured port range in the background. When a new server is found:

1. It appears on the **Integrations page** as **"Discovered"**
2. Click **"Configure"**
3. Give the server a **name**
4. Done – all sensors are automatically created

---

## 🧩 Mod Detection

The **Mods sensor** automatically detects whether a server is modded:

- **Forge / NeoForge** – Full mod list with IDs and versions ✅
- **Fabric / Quilt** – Shown as `Vanilla` (no mod info in protocol) ⚠️
- **Vanilla** – Correctly shown as `Vanilla` ✅

The mod list is available as the `mod_list` attribute:
```json
[
  {"id": "forge", "version": "47.2.0"},
  {"id": "jei", "version": "15.2.0.27"}
]
```

---

## 📋 Requirements

- Home Assistant **2024.1** or newer
- **Minecraft Java Edition** server (Bedrock is not supported)
- The MC server must be **network-reachable** from the HA server

