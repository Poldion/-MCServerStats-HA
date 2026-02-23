const CARD_VERSION = "1.1.0";

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

  /**
   * Auto-discover all mc_server_stats servers by scanning hass entities.
   * Uses friendly_name matching to group entities belonging to the same server device.
   */
  _discoverServers() {
    if (!this._hass) return;

    // If the user manually specified servers, use those
    if (this._config.servers && this._config.servers.length > 0) {
      this._servers = this._config.servers;
      return;
    }

    const discovered = new Map();

    // Step 1: Find all candidate status entities (binary_sensor with device_class connectivity)
    // whose friendly_name ends with " Status"
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

    // Step 2: Build a lookup of all sensor entities by friendly_name
    const sensorsByFriendlyName = {};
    for (const [entityId, stateObj] of Object.entries(this._hass.states)) {
      if (!entityId.startsWith("sensor.")) continue;
      const fname = (stateObj.attributes || {}).friendly_name || "";
      sensorsByFriendlyName[fname] = entityId;
    }

    // Step 3: For each status entity, find matching sensors by device name prefix
    for (const { entityId, deviceName } of statusEntities) {
      const playersId = sensorsByFriendlyName[`${deviceName} Spieler`];

      // Must have a players sensor to confirm this is our integration
      if (!playersId) continue;

      const motdId = sensorsByFriendlyName[`${deviceName} MOTD`] || null;
      const versionId = sensorsByFriendlyName[`${deviceName} Version`] || null;
      const latencyId = sensorsByFriendlyName[`${deviceName} Latenz`] || null;
      const modsId = sensorsByFriendlyName[`${deviceName} Mods`] || null;

      discovered.set(entityId, {
        name: deviceName,
        status_entity: entityId,
        players_entity: playersId,
        motd_entity: motdId,
        version_entity: versionId,
        latency_entity: latencyId,
        mods_entity: modsId,
      });
    }

    this._servers = Array.from(discovered.values());
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
      :host {
        display: block;
      }
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
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
        font-size: 13px;
        font-weight: 500;
        color: var(--secondary-text-color, #aaa);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .card-header .mc-icon {
        width: 20px;
        height: 20px;
        opacity: 0.7;
      }
      .dots {
        display: flex;
        gap: 6px;
        margin-left: auto;
      }
      .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--disabled-text-color, #555);
        transition: background 0.3s ease, transform 0.3s ease;
        cursor: pointer;
      }
      .dot.active {
        background: #4CAF50;
        transform: scale(1.25);
      }
      .server-view {
        opacity: 1;
        transition: opacity 0.4s ease-in-out;
      }
      .server-view.fading {
        opacity: 0;
      }
      .server-name {
        font-size: 22px;
        font-weight: 700;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .online-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        background: #4CAF50;
        color: #fff;
      }
      .offline-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        background: #f44336;
        color: #fff;
      }
      .motd {
        font-size: 13px;
        color: var(--secondary-text-color, #aaa);
        margin-bottom: 16px;
        font-style: italic;
      }
      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 12px;
        margin-bottom: 16px;
      }
      .stat-item {
        background: var(--input-fill-color, rgba(255,255,255,0.05));
        border-radius: 10px;
        padding: 12px;
        text-align: center;
      }
      .stat-value {
        font-size: 24px;
        font-weight: 700;
        color: var(--primary-text-color, #fff);
      }
      .stat-label {
        font-size: 11px;
        color: var(--secondary-text-color, #aaa);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
      }
      .players-section {
        margin-top: 12px;
      }
      .players-title {
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: var(--secondary-text-color, #aaa);
        margin-bottom: 8px;
      }
      .player-list {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .player-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: var(--input-fill-color, rgba(255,255,255,0.08));
        border-radius: 16px;
        padding: 4px 12px 4px 4px;
        font-size: 13px;
      }
      .player-avatar {
        width: 22px;
        height: 22px;
        border-radius: 50%;
        image-rendering: pixelated;
      }
      .no-players {
        font-size: 13px;
        color: var(--secondary-text-color, #666);
        font-style: italic;
      }
      .mods-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        background: rgba(156, 39, 176, 0.2);
        color: #CE93D8;
      }
      .mods-badge.vanilla {
        background: rgba(76, 175, 80, 0.15);
        color: #81C784;
      }
      .version-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        background: rgba(33, 150, 243, 0.15);
        color: #64B5F6;
      }
      .badges {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 14px;
      }
      .all-offline {
        text-align: center;
        padding: 30px 0;
        color: var(--secondary-text-color, #888);
      }
      .all-offline .offline-icon {
        font-size: 48px;
        margin-bottom: 12px;
        opacity: 0.5;
      }
      .all-offline .offline-text {
        font-size: 16px;
        font-weight: 500;
      }
      .no-servers {
        text-align: center;
        padding: 30px 0;
        color: var(--secondary-text-color, #888);
      }
      .no-servers .ns-icon {
        font-size: 48px;
        margin-bottom: 12px;
        opacity: 0.5;
      }
      .no-servers .ns-text {
        font-size: 14px;
      }
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

    if (this._currentIndex >= displayServers.length) {
      this._currentIndex = 0;
    }

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
        const idx = parseInt(e.target.dataset.index, 10);
        this._currentIndex = idx;
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
        <div class="ns-text">Keine Minecraft Server gefunden.<br>Richte zuerst die Integration ein.</div>
      </div>`;
  }

  _renderAllOffline() {
    return `
      ${this._renderHeader()}
      <div class="all-offline">
        <div class="offline-icon">⛏️</div>
        <div class="offline-text">Alle Server sind offline</div>
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
      const dots = displayServers
        .map(
          (s, i) =>
            `<div class="dot ${i === this._currentIndex ? "active" : ""}" data-index="${i}"></div>`
        )
        .join("");
      dotsHtml = `<div class="dots">${dots}</div>`;
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
            .map(
              (name) =>
                `<span class="player-chip">
                  <img class="player-avatar" src="https://mc-heads.net/avatar/${name}/22" alt="${name}" />
                  ${name}
                </span>`
            )
            .join("")
        : `<span class="no-players">Keine Spieler online</span>`
      : `<span class="no-players">Server ist offline</span>`;

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
            <div class="stat-label">Spieler</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">${latency}<span style="font-size:14px;opacity:0.5">ms</span></div>
            <div class="stat-label">Latenz</div>
          </div>
        </div>` : ""}
        <div class="players-section">
          <div class="players-title">Online Spieler</div>
          <div class="player-list">${playersHtml}</div>
        </div>
      </div>`;
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return {
      rotate_interval: 8,
      show_header: true,
      show_offline: false,
    };
  }
}

customElements.define("mc-server-stats-card", McServerStatsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "mc-server-stats-card",
  name: "Minecraft Server Stats",
  description: "Zeigt automatisch alle Minecraft Server an und rotiert zwischen aktiven Servern.",
  preview: true,
});

console.info(
  `%c MC-SERVER-STATS-CARD %c v${CARD_VERSION} `,
  "background: #4CAF50; color: white; font-weight: bold; padding: 2px 6px; border-radius: 4px 0 0 4px;",
  "background: #333; color: #ddd; padding: 2px 6px; border-radius: 0 4px 4px 0;"
);

