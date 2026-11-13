/* Swiss Transit For HA: departure board card. */

const MODE_ICONS = {
  train: "mdi:train",
  bus: "mdi:bus",
  tram: "mdi:tram",
  metro: "mdi:subway-variant",
  ship: "mdi:ferry",
  cableway: "mdi:gondola",
  other: "mdi:transit-connection-variant",
};

const TEXTS = {
  en: { now: "now", min: "min", cancelled: "Cancelled", platform: "Pl.", none: "No departures", unavailable: "Unavailable" },
  fr: { now: "maint.", min: "min", cancelled: "Supprimé", platform: "Voie", none: "Aucun départ", unavailable: "Indisponible" },
  de: { now: "jetzt", min: "Min.", cancelled: "Fällt aus", platform: "Gl.", none: "Keine Abfahrten", unavailable: "Nicht verfügbar" },
  it: { now: "ora", min: "min", cancelled: "Soppresso", platform: "Bin.", none: "Nessuna partenza", unavailable: "Non disponibile" },
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

class SwissTransitCard extends HTMLElement {
  static getConfigForm() {
    return {
      schema: [
        {
          name: "entity",
          required: true,
          selector: { entity: { domain: "sensor", integration: "swisstransit4ha" } },
        },
        { name: "title", selector: { text: {} } },
        { name: "max", selector: { number: { min: 1, max: 30, mode: "box" } } },
        { name: "show_platform", selector: { boolean: {} } },
        { name: "show_alerts", selector: { boolean: {} } },
      ],
    };
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(
      (id) => id.startsWith("sensor.") && hass.states[id].attributes.swisstransit_board,
    );
    return { entity: entity || "", show_platform: true, show_alerts: true };
  }

  setConfig(config) {
    if (!config.entity) throw new Error("entity is required");
    this._config = { show_platform: true, show_alerts: true, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    const state = hass.states[this._config?.entity];
    const changed = !this._hass || state !== this._state || hass.language !== this._hass.language;
    this._hass = hass;
    this._state = state;
    if (changed) this._render();
  }

  connectedCallback() {
    // Minutes count down between two updates of the sensor.
    this._timer = setInterval(() => this._render(), 30000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  getCardSize() {
    return 2 + Math.min(this._config?.max || 6, 10);
  }

  _t(key) {
    const lang = (this._hass?.language || "en").slice(0, 2);
    return (TEXTS[lang] || TEXTS.en)[key];
  }

  _clock(iso) {
    return new Date(iso).toLocaleTimeString(this._hass?.locale?.language || this._hass?.language || "en", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  _row(dep) {
    const time = dep.expected || dep.planned;
    const minutes = Math.round((new Date(time) - Date.now()) / 60000);
    const late = dep.delay > 0;
    const countdown = dep.cancelled
      ? `<span class="cancelled-label">${this._t("cancelled")}</span>`
      : minutes <= 0
        ? `<span class="soon">${this._t("now")}</span>`
        : minutes < 60
          ? `${minutes}&nbsp;${this._t("min")}`
          : "";
    const platform =
      this._config.show_platform && dep.platform
        ? `<span class="platform ${dep.platform_changed ? "changed" : ""}">${this._t("platform")} ${esc(dep.platform)}</span>`
        : '<span class="platform"></span>';
    return `
      <div class="row ${dep.cancelled ? "is-cancelled" : ""}">
        <ha-icon class="mode" icon="${MODE_ICONS[dep.mode] || MODE_ICONS.other}"></ha-icon>
        <span class="line mode-${esc(dep.mode)}">${esc(dep.line)}</span>
        <span class="dest">${esc(dep.destination)}${dep.situations?.length ? ' <ha-icon class="warn" icon="mdi:alert"></ha-icon>' : ""}</span>
        ${platform}
        <span class="time">
          <span class="${late ? "planned" : ""}">${this._clock(dep.planned)}</span>
          ${late ? `<span class="delay">+${dep.delay}'</span>` : ""}
        </span>
        <span class="countdown">${countdown}</span>
      </div>`;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const state = this._state;
    const attrs = state?.attributes || {};
    const title = this._config.title ?? attrs.stop_name ?? "";
    let body;
    if (!state || state.state === "unavailable") {
      body = `<div class="empty">${this._t("unavailable")}</div>`;
    } else {
      const deps = (attrs.departures || []).slice(0, this._config.max || 30);
      body = deps.length ? deps.map((d) => this._row(d)).join("") : `<div class="empty">${this._t("none")}</div>`;
    }
    const alerts =
      this._config.show_alerts && attrs.alerts?.length
        ? `<div class="alerts">${attrs.alerts
            .map(
              (a) =>
                `<details><summary><ha-icon icon="mdi:alert"></ha-icon>${esc(a.summary)}</summary>${
                  a.description ? `<p>${esc(a.description)}</p>` : ""
                }</details>`,
            )
            .join("")}</div>`
        : "";
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 12px 16px 8px; }
        .header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 8px; }
        .title { font-size: 1.2em; font-weight: 500; }
        .alerts { margin-bottom: 8px; }
        details { background: rgba(var(--rgb-warning-color, 255,166,0), 0.15); border-left: 3px solid var(--warning-color, #ffa600);
                  border-radius: 4px; padding: 6px 8px; margin-bottom: 4px; font-size: 0.9em; }
        summary { cursor: pointer; display: flex; gap: 6px; align-items: center; }
        summary ha-icon { --mdc-icon-size: 18px; color: var(--warning-color, #ffa600); flex: none; }
        details p { margin: 6px 0 0; white-space: pre-line; color: var(--secondary-text-color); }
        .row { display: grid; grid-template-columns: 24px auto 1fr auto auto 56px; gap: 8px; align-items: center;
               padding: 6px 0; border-top: 1px solid var(--divider-color); }
        .row:first-child { border-top: none; }
        .mode { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
        .line { min-width: 2.2em; text-align: center; font-weight: 600; font-size: 0.85em; padding: 2px 6px; border-radius: 4px;
                background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
        .line.mode-train { background: #eb0000; }
        .line.mode-ship { background: #0079c7; }
        .dest { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .warn { --mdc-icon-size: 16px; color: var(--warning-color, #ffa600); }
        .platform { font-size: 0.8em; color: var(--secondary-text-color); white-space: nowrap; }
        .platform.changed { color: var(--error-color, #db4437); font-weight: 600; }
        .time { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
        .planned { text-decoration: line-through; color: var(--secondary-text-color); }
        .delay { color: var(--error-color, #db4437); font-weight: 600; margin-left: 4px; }
        .countdown { text-align: right; font-weight: 500; white-space: nowrap; font-variant-numeric: tabular-nums; }
        .soon { color: var(--success-color, #43a047); }
        .is-cancelled .dest, .is-cancelled .time { text-decoration: line-through; color: var(--secondary-text-color); }
        .cancelled-label { color: var(--error-color, #db4437); font-size: 0.85em; }
        .empty { padding: 12px 0; color: var(--secondary-text-color); text-align: center; }
        .source { font-size: 0.7em; color: var(--secondary-text-color); }
      </style>
      <ha-card>
        <div class="header"><span class="title">${esc(title)}</span><span class="source">${esc(attrs.source || "")}</span></div>
        ${alerts}
        <div class="rows">${body}</div>
      </ha-card>`;
  }
}

if (!customElements.get("swisstransit-departures-card")) {
  customElements.define("swisstransit-departures-card", SwissTransitCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "swisstransit-departures-card",
    name: "Swiss Transit departures",
    description: "Next departures, delays and disruptions of a Swiss stop or station.",
    preview: true,
    documentationURL: "https://github.com/SashConnection/swisstransit4HA",
  });
}
