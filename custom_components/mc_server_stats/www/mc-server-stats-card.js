const CARD_VERSION = "1.3.0";

// Register the card in the picker as early as possible
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "mc-server-stats-card")) {
  window.customCards.push({
    type: "mc-server-stats-card",
    name: "Minecraft Server Stats",
    description:
      "Automatically displays all Minecraft servers and rotates between active ones.",
    preview: true,
    documentationURL:
      "https://github.com/Poldion/-MCServerStats-HA",
  });
}

class McServerStatsCard extends HTMLElement {
  static get properties() {
    return { hass: {}, config: {} };
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._buildCard();
    }
    this._discoverServers();
    this._updateCard();
  }

  setConfig(config) {
    this._config = {
      rotate_interval: 8,
      show_header: true,
      show_offline: false,
      ...config,
    };
    this._currentIndex = 0;
    this._initialized = false;
    this._servers = [];

    if (this._rotateTimer) clearInterval(this._rotateTimer);
    if (this._config.rotate_interval > 0) {
      this._rotateTimer = setInterval(() => {
        this._rotateToNext();
      }, this._config.rotate_interval * 1000);
    }
  }

  _discoverServers() {
    if (!this._hass) return;

    if (this._config.servers && this._config.servers.length > 0) {
      this._servers = this._config.servers;
      return;
    }

    const discovered = new Map();

    const statusEntities = [];
    for (const [entityId, stateObj] of Object.entries(this._hass.states)) {
      if (!entityId.startsWith("binary_sensor.")) continue;
      const attrs = stateObj.attributes || {};
      if (attrs.device_class !== "connectivity") continue;
      const fname = attrs.friendly_name || "";
      if (!fname.endsWith(" Status")) continue;
      statusEntities.push({ entityId, fname, deviceName: fname.slice(0, -" Status".length) });
    }

    if (statusEntities.length === 0) {
      this._servers = [];
      return;
    }

    const sensorsByFriendlyName = {};
    for (const [entityId, stateObj] of Object.entries(this._hass.states)) {
      if (!entityId.startsWith("sensor.")) continue;
      const fname = (stateObj.attributes || {}).friendly_name || "";
      sensorsByFriendlyName[fname] = entityId;
    }

    for (const { entityId, deviceName } of statusEntities) {
      const playersId = sensorsByFriendlyName[`${deviceName} Players`];
      if (!playersId) continue;

      discovered.set(entityId, {
        name: deviceName,
        status_entity: entityId,
        players_entity: playersId,
        motd_entity: sensorsByFriendlyName[`${deviceName} MOTD`] || null,
        version_entity: sensorsByFriendlyName[`${deviceName} Version`] || null,
        latency_entity: sensorsByFriendlyName[`${deviceName} Latency`] || null,
        mods_entity: sensorsByFriendlyName[`${deviceName} Mods`] || null,
      });
    }

    this._servers = Array.from(discovered.values());

    const excluded = this._config.exclude_servers || [];
    if (excluded.length > 0) {
      this._servers = this._servers.filter((s) => !excluded.includes(s.name));
    }
  }

  _rotateToNext() {
    if (!this._hass) return;
    const displayServers = this._getDisplayServers();
    if (displayServers.length <= 1) return;
    this._currentIndex = (this._currentIndex + 1) % displayServers.length;
    this._updateCard(true);
  }

  _getDisplayServers() {
    if (!this._hass || !this._servers) return [];
    if (this._config.show_offline) return this._servers;
    return this._servers.filter((s) => {
      const statusEntity = this._hass.states[s.status_entity];
      return statusEntity && statusEntity.state === "on";
    });
  }

  _buildCard() {
    if (this.shadowRoot) this.shadowRoot.innerHTML = "";
    else this.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; }
      .card {
        background: var(--ha-card-background, var(--card-background-color, #1c1c1e));
        border-radius: var(--ha-card-border-radius, 12px);
        box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,.3));
        padding: 20px;
        color: var(--primary-text-color, #fff);
        font-family: var(--paper-font-body1_-_font-family, 'Segoe UI', sans-serif);
        overflow: hidden;
        position: relative;
      }
      .card-header {
        display: flex; align-items: center; gap: 10px;
        margin-bottom: 16px; font-size: 13px; font-weight: 500;
        color: var(--secondary-text-color, #aaa);
        text-transform: uppercase; letter-spacing: 0.5px;
      }
      .card-header .mc-icon { width: 20px; height: 20px; opacity: 0.7; }
      .dots { display: flex; gap: 6px; margin-left: auto; }
      .dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: var(--disabled-text-color, #555);
        transition: background 0.3s ease, transform 0.3s ease; cursor: pointer;
      }
      .dot.active { background: #4CAF50; transform: scale(1.25); }
      .server-view { opacity: 1; transition: opacity 0.4s ease-in-out; }
      .server-view.fading { opacity: 0; }
      .server-name {
        font-size: 22px; font-weight: 700; margin-bottom: 4px;
        display: flex; align-items: center; gap: 10px;
      }
      .online-badge {
        display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-size: 11px; font-weight: 600; background: #4CAF50; color: #fff;
      }
      .offline-badge {
        display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-size: 11px; font-weight: 600; background: #f44336; color: #fff;
      }
      .motd {
        font-size: 13px; color: var(--secondary-text-color, #aaa);
        margin-bottom: 16px; font-style: italic;
      }
      .stats-grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 12px; margin-bottom: 16px;
      }
      .stat-item {
        background: var(--input-fill-color, rgba(255,255,255,0.05));
        border-radius: 10px; padding: 12px; text-align: center;
      }
      .stat-value { font-size: 24px; font-weight: 700; color: var(--primary-text-color, #fff); }
      .stat-label {
        font-size: 11px; color: var(--secondary-text-color, #aaa);
        text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px;
      }
      .players-section { margin-top: 12px; }
      .players-title {
        font-size: 12px; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.5px; color: var(--secondary-text-color, #aaa); margin-bottom: 8px;
      }
      .player-list { display: flex; flex-wrap: wrap; gap: 6px; }
      .player-chip {
        display: inline-flex; align-items: center; gap: 6px;
        background: var(--input-fill-color, rgba(255,255,255,0.08));
        border-radius: 16px; padding: 4px 12px 4px 4px; font-size: 13px;
      }
      .player-avatar { width: 22px; height: 22px; border-radius: 50%; image-rendering: pixelated; }
      .no-players { font-size: 13px; color: var(--secondary-text-color, #666); font-style: italic; }
      .mods-badge {
        display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px;
        border-radius: 12px; font-size: 11px; font-weight: 600;
        background: rgba(156, 39, 176, 0.2); color: #CE93D8;
      }
      .mods-badge.vanilla { background: rgba(76, 175, 80, 0.15); color: #81C784; }
      .version-badge {
        display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px;
        border-radius: 12px; font-size: 11px; font-weight: 600;
        background: rgba(33, 150, 243, 0.15); color: #64B5F6;
      }
      .badges { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
      .all-offline { text-align: center; padding: 30px 0; color: var(--secondary-text-color, #888); }
      .all-offline .offline-icon { font-size: 48px; margin-bottom: 12px; opacity: 0.5; }
      .all-offline .offline-text { font-size: 16px; font-weight: 500; }
      .no-servers { text-align: center; padding: 30px 0; color: var(--secondary-text-color, #888); }
      .no-servers .ns-icon { font-size: 48px; margin-bottom: 12px; opacity: 0.5; }
      .no-servers .ns-text { font-size: 14px; }
    `;
    this.shadowRoot.appendChild(style);

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `<div class="content"></div>`;
    this.shadowRoot.appendChild(card);
    this._content = card.querySelector(".content");
  }

  _updateCard(animate = false) {
    if (!this._hass || !this._content) return;

    if (!this._servers || this._servers.length === 0) {
      this._content.innerHTML = this._renderNoServers();
      return;
    }

    const displayServers = this._getDisplayServers();
    if (displayServers.length === 0) {
      this._content.innerHTML = this._renderAllOffline();
      return;
    }

    if (this._currentIndex >= displayServers.length) this._currentIndex = 0;
    const server = displayServers[this._currentIndex];

    if (animate) {
      const view = this._content.querySelector(".server-view");
      if (view) {
        view.classList.add("fading");
        setTimeout(() => {
          this._content.innerHTML = this._renderServer(server, displayServers);
          this._bindDots();
        }, 400);
        return;
      }
    }

    this._content.innerHTML = this._renderServer(server, displayServers);
    this._bindDots();
  }

  _bindDots() {
    if (!this._content) return;
    this._content.querySelectorAll(".dot").forEach((dot) => {
      dot.addEventListener("click", (e) => {
        this._currentIndex = parseInt(e.target.dataset.index, 10);
        this._updateCard(true);
      });
    });
  }

  _renderHeader(dotsHtml = "") {
    if (!this._config.show_header) return "";
    return `
      <div class="card-header">
        <svg class="mc-icon" viewBox="0 0 24 24"><path fill="currentColor" d="M4,2H20A2,2 0 0,1 22,4V20A2,2 0 0,1 20,22H4A2,2 0 0,1 2,20V4A2,2 0 0,1 4,2M6,6V10H10V12H8V18H10V14H12V18H14V12H12V10H18V6H14V10H10V6H6Z"/></svg>
        Minecraft Server
        ${dotsHtml}
      </div>`;
  }

  _renderNoServers() {
    return `
      ${this._renderHeader()}
      <div class="no-servers">
        <div class="ns-icon">🔍</div>
        <div class="ns-text">No Minecraft servers found.<br>Set up the integration first.</div>
      </div>`;
  }

  _renderAllOffline() {
    return `
      ${this._renderHeader()}
      <div class="all-offline">
        <div class="offline-icon">⛏️</div>
        <div class="offline-text">All servers are offline</div>
      </div>`;
  }

  _renderServer(server, displayServers) {
    const hass = this._hass;
    const statusEntity = hass.states[server.status_entity];
    const playersEntity = server.players_entity ? hass.states[server.players_entity] : null;
    const motdEntity = server.motd_entity ? hass.states[server.motd_entity] : null;
    const versionEntity = server.version_entity ? hass.states[server.version_entity] : null;
    const latencyEntity = server.latency_entity ? hass.states[server.latency_entity] : null;
    const modsEntity = server.mods_entity ? hass.states[server.mods_entity] : null;

    const isOnline = statusEntity && statusEntity.state === "on";
    const playerCount = playersEntity ? parseInt(playersEntity.state, 10) || 0 : 0;
    const maxPlayers = playersEntity?.attributes?.max_players ?? "?";
    const playerNames = playersEntity?.attributes?.player_names ?? [];
    const motd = motdEntity?.state ?? "";
    const version = versionEntity?.state ?? "?";
    const latency = latencyEntity ? parseFloat(latencyEntity.state) || 0 : 0;
    const serverName = server.name || "Minecraft Server";
    const modded = modsEntity?.attributes?.modded ?? false;
    const modCount = modsEntity?.attributes?.mod_count ?? 0;

    let dotsHtml = "";
    if (displayServers.length > 1) {
      dotsHtml = `<div class="dots">${displayServers
        .map((s, i) => `<div class="dot ${i === this._currentIndex ? "active" : ""}" data-index="${i}"></div>`)
        .join("")}</div>`;
    }

    const statusBadge = isOnline
      ? `<span class="online-badge">ONLINE</span>`
      : `<span class="offline-badge">OFFLINE</span>`;

    const modsBadge = modsEntity
      ? modded
        ? `<span class="mods-badge">🧩 ${modCount} Mods</span>`
        : `<span class="mods-badge vanilla">🟢 Vanilla</span>`
      : "";

    const playersHtml = isOnline
      ? playerNames.length > 0
        ? playerNames
            .map((name) =>
              `<span class="player-chip">
                <img class="player-avatar" src="https://mc-heads.net/avatar/${name}/22" alt="${name}" />
                ${name}
              </span>`)
            .join("")
        : `<span class="no-players">No players online</span>`
      : `<span class="no-players">Server is offline</span>`;

    return `
      <div class="server-view">
        ${this._renderHeader(dotsHtml)}
        <div class="server-name">
          ${serverName}
          ${statusBadge}
        </div>
        ${motd && motd !== "unknown" ? `<div class="motd">${motd}</div>` : ""}
        <div class="badges">
          ${version && version !== "unknown" ? `<span class="version-badge">🎮 ${version}</span>` : ""}
          ${modsBadge}
        </div>
        ${isOnline ? `
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-value">${playerCount}<span style="font-size:14px;opacity:0.5">/${maxPlayers}</span></div>
            <div class="stat-label">Players</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">${latency}<span style="font-size:14px;opacity:0.5">ms</span></div>
            <div class="stat-label">Latency</div>
          </div>
        </div>` : ""}
        <div class="players-section">
          <div class="players-title">Online Players</div>
          <div class="player-list">${playersHtml}</div>
        </div>
      </div>`;
  }

  getCardSize() { return 4; }

  static getConfigElement() {
    return document.createElement("mc-server-stats-card-editor");
  }

  static getStubConfig() {
    return { rotate_interval: 8, show_header: true, show_offline: false };
  }
}

customElements.define("mc-server-stats-card", McServerStatsCard);


// ──────────────────────────────────────────────
//  Visual Card Editor (using native HA elements)
// ──────────────────────────────────────────────

class McServerStatsCardEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._hass = null;
    this._discoveredServers = [];
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this._discoverAvailableServers();
    this._render();
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  _discoverAvailableServers() {
    if (!this._hass) return;
    this._discoveredServers = [];

    const sensorsByFriendlyName = {};
    for (const [entityId, stateObj] of Object.entries(this._hass.states)) {
      if (!entityId.startsWith("sensor.")) continue;
      const fname = (stateObj.attributes || {}).friendly_name || "";
      sensorsByFriendlyName[fname] = entityId;
    }

    for (const [entityId, stateObj] of Object.entries(this._hass.states)) {
      if (!entityId.startsWith("binary_sensor.")) continue;
      const attrs = stateObj.attributes || {};
      if (attrs.device_class !== "connectivity") continue;
      const fname = attrs.friendly_name || "";
      if (!fname.endsWith(" Status")) continue;

      const deviceName = fname.slice(0, -" Status".length);
      if (!sensorsByFriendlyName[`${deviceName} Players`]) continue;

      this._discoveredServers.push({ name: deviceName, status_entity: entityId });
    }
  }

  _fireChanged() {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: { ...this._config } },
        bubbles: true,
        composed: true,
      })
    );
  }

  _render() {
    const config = this._config;
    const rotateInterval = config.rotate_interval ?? 8;
    const showHeader = config.show_header !== false;
    const showOffline = config.show_offline === true;
    const excludedServers = config.exclude_servers || [];

    const serversHtml = this._discoveredServers.length > 0
      ? `
        <div class="section-title">Servers (${this._discoveredServers.length} found)</div>
        ${this._discoveredServers.map((s) => `
          <div class="row">
            <div class="row-text">
              <span class="row-label">${s.name}</span>
              <span class="row-desc">${s.status_entity}</span>
            </div>
            <ha-switch
              class="server-toggle"
              data-name="${s.name}"
              ${!excludedServers.includes(s.name) ? "checked" : ""}
            ></ha-switch>
          </div>
        `).join("")}
      `
      : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .editor { padding: 0; }
        .section-title {
          font-size: 13px; font-weight: 600; text-transform: uppercase;
          letter-spacing: 0.5px; color: var(--secondary-text-color, #aaa);
          padding: 20px 0 8px 0; border-bottom: 1px solid var(--divider-color, #333);
          margin-bottom: 4px;
        }
        .section-title:first-child { padding-top: 4px; }
        .row {
          display: flex; align-items: center; justify-content: space-between;
          padding: 12px 0; border-bottom: 1px solid var(--divider-color, rgba(127,127,127,0.1));
        }
        .row:last-child { border-bottom: none; }
        .row-text { display: flex; flex-direction: column; flex: 1; min-width: 0; margin-right: 16px; }
        .row-label { font-size: 14px; color: var(--primary-text-color); }
        .row-desc { font-size: 12px; color: var(--secondary-text-color); margin-top: 2px; }
        .number-input {
          width: 72px; padding: 8px 4px; text-align: center; font-size: 14px;
          border: 1px solid var(--divider-color, #444); border-radius: 8px;
          background: var(--input-fill-color, rgba(255,255,255,0.05));
          color: var(--primary-text-color);
        }
        .number-input:focus { outline: none; border-color: var(--primary-color, #03a9f4); }
      </style>
      <div class="editor">
        <div class="section-title">Appearance</div>

        <div class="row">
          <div class="row-text">
            <span class="row-label">Show header</span>
            <span class="row-desc">Display Minecraft icon and title at the top</span>
          </div>
          <ha-switch id="show_header" ${showHeader ? "checked" : ""}></ha-switch>
        </div>

        <div class="row">
          <div class="row-text">
            <span class="row-label">Show offline servers</span>
            <span class="row-desc">Include servers that are currently offline</span>
          </div>
          <ha-switch id="show_offline" ${showOffline ? "checked" : ""}></ha-switch>
        </div>

        <div class="row">
          <div class="row-text">
            <span class="row-label">Rotation interval</span>
            <span class="row-desc">Seconds between server rotation (0 = disabled)</span>
          </div>
          <input class="number-input" type="number" id="rotate_interval" min="0" max="120" value="${rotateInterval}" />
        </div>

        ${serversHtml}
      </div>
    `;

    // Bind events after render
    this.shadowRoot.getElementById("show_header").addEventListener("change", (e) => {
      this._config.show_header = e.target.checked;
      this._fireChanged();
    });

    this.shadowRoot.getElementById("show_offline").addEventListener("change", (e) => {
      this._config.show_offline = e.target.checked;
      this._fireChanged();
    });

    this.shadowRoot.getElementById("rotate_interval").addEventListener("change", (e) => {
      this._config.rotate_interval = parseInt(e.target.value, 10) || 0;
      this._fireChanged();
    });

    this.shadowRoot.querySelectorAll(".server-toggle").forEach((toggle) => {
      toggle.addEventListener("change", () => {
        const excluded = [];
        this.shadowRoot.querySelectorAll(".server-toggle").forEach((t) => {
          if (!t.checked) excluded.push(t.dataset.name);
        });
        this._config.exclude_servers = excluded.length > 0 ? excluded : undefined;
        if (!this._config.exclude_servers) delete this._config.exclude_servers;
        this._fireChanged();
      });
    });
  }
}

customElements.define("mc-server-stats-card-editor", McServerStatsCardEditor);


console.info(
  `%c MC-SERVER-STATS-CARD %c v${CARD_VERSION} `,
  "background: #4CAF50; color: white; font-weight: bold; padding: 2px 6px; border-radius: 4px 0 0 4px;",
  "background: #333; color: #ddd; padding: 2px 6px; border-radius: 0 4px 4px 0;"
);

