/* Swiss Transit For HA: departure board card, five styles. */

const STYLES = ["list", "flap", "platform", "countdown", "timeline"];

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
  en: {
    now: "now", min: "min", cancelled: "Cancelled", cancelled_short: "CANC", platform: "Pl.", none: "No departures",
    unavailable: "Unavailable", time: "TIME", line: "LINE", destination: "DESTINATION", pl: "PL.", info: "INFO",
    departure: "Departure", approx: "approx.", then: "Then", leave_in: "Leave in", leave_now: "Leave now",
    style: "Style", styles: { list: "List", flap: "Split-flap board", platform: "Platform display", countdown: "Next departure, large", timeline: "Timeline" },
    entity: "Departure board sensor", title: "Title", max: "Maximum departures", show_platform: "Show platforms",
    show_alerts: "Show alerts", window: "Timeline length (min)", heading_time: "Time", heading_line: "Line", heading_dest: "Destination", heading_pl: "Platform", heading_info: "Info",
  },
  fr: {
    now: "maint.", min: "min", cancelled: "Supprimé", cancelled_short: "SUPPR", platform: "Voie", none: "Aucun départ",
    unavailable: "Indisponible", time: "HEURE", line: "LIGNE", destination: "DESTINATION", pl: "VOIE", info: "INFO",
    departure: "Départ", approx: "env.", then: "Puis", leave_in: "Pars dans", leave_now: "Pars maintenant",
    style: "Style", styles: { list: "Liste", flap: "Tableau à palettes", platform: "Affichage de quai", countdown: "Prochain départ en grand", timeline: "Frise" },
    entity: "Capteur tableau des départs", title: "Titre", max: "Nombre de départs max.", show_platform: "Afficher les voies",
    show_alerts: "Afficher les alertes", window: "Durée de la frise (min)", heading_time: "Heure", heading_line: "Ligne", heading_dest: "Destination", heading_pl: "Voie", heading_info: "Info",
  },
  de: {
    now: "jetzt", min: "Min.", cancelled: "Fällt aus", cancelled_short: "AUSF", platform: "Gl.", none: "Keine Abfahrten",
    unavailable: "Nicht verfügbar", time: "ZEIT", line: "LINIE", destination: "ZIEL", pl: "GL.", info: "INFO",
    departure: "Abfahrt", approx: "ca.", then: "Dann", leave_in: "Los in", leave_now: "Jetzt los",
    style: "Stil", styles: { list: "Liste", flap: "Fallblattanzeiger", platform: "Perronanzeiger", countdown: "Nächste Abfahrt gross", timeline: "Zeitleiste" },
    entity: "Sensor Abfahrtstafel", title: "Titel", max: "Max. Abfahrten", show_platform: "Gleise anzeigen",
    show_alerts: "Meldungen anzeigen", window: "Länge der Zeitleiste (Min.)", heading_time: "Zeit", heading_line: "Linie", heading_dest: "Ziel", heading_pl: "Gleis", heading_info: "Info",
  },
  it: {
    now: "ora", min: "min", cancelled: "Soppresso", cancelled_short: "SOPPR", platform: "Bin.", none: "Nessuna partenza",
    unavailable: "Non disponibile", time: "ORA", line: "LINEA", destination: "DESTINAZIONE", pl: "BIN.", info: "INFO",
    departure: "Partenza", approx: "ca.", then: "Poi", leave_in: "Parti tra", leave_now: "Parti ora",
    style: "Stile", styles: { list: "Elenco", flap: "Tabellone a palette", platform: "Display di binario", countdown: "Prossima partenza in grande", timeline: "Cronologia" },
    entity: "Sensore tabellone partenze", title: "Titolo", max: "Partenze max.", show_platform: "Mostra i binari",
    show_alerts: "Mostra gli avvisi", window: "Durata cronologia (min)", heading_time: "Ora", heading_line: "Linea", heading_dest: "Destinazione", heading_pl: "Binario", heading_info: "Info",
  },
};

const FLAP_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:+'-.,/()";

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const flapText = (value) =>
  String(value ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toUpperCase()
    .replace(/[^ A-Z0-9:+'\-.,/()]/g, " ");

const pageLang = () => (document.documentElement.lang || navigator.language || "en").slice(0, 2);
const textsFor = (lang) => TEXTS[lang] || TEXTS.en;

const BASE_CSS = `
  :host { display: block; min-width: 0; }
  ha-card { overflow: hidden; min-width: 0; container-type: inline-size; }
  .empty { padding: 12px 0; color: var(--secondary-text-color); text-align: center; }
  .line { display: inline-block; min-width: 2.2em; text-align: center; font-weight: 600; font-size: 0.85em; padding: 2px 6px;
          border-radius: 4px; background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); box-sizing: border-box; }
  .line.mode-train { background: #eb0000; }
  .line.mode-ship { background: #0079c7; }
  .line.mode-metro { background: #1d9e75; }
  .line.mode-tram { background: #7f77dd; }
  .line.mode-cableway { background: #ba7517; }
`;

const STYLE_CSS = {
  list: `
    .wrap { padding: 12px 16px 8px; }
    .header { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
    .title { font-size: 1.2em; font-weight: 500; }
    .source { font-size: 0.7em; color: var(--secondary-text-color); }
    .alerts { margin-bottom: 8px; }
    details { background: rgba(var(--rgb-warning-color, 255,166,0), 0.15); border-left: 3px solid var(--warning-color, #ffa600);
              padding: 6px 8px; margin-bottom: 4px; font-size: 0.9em; }
    summary { cursor: pointer; display: flex; gap: 6px; align-items: center; }
    summary ha-icon { --mdc-icon-size: 18px; color: var(--warning-color, #ffa600); flex: none; }
    details p { margin: 6px 0 0; white-space: pre-line; color: var(--secondary-text-color); }
    .row { display: grid; grid-template-columns: 24px auto minmax(0,1fr) auto auto 56px; gap: 8px; align-items: center;
           padding: 6px 0; border-top: 1px solid var(--divider-color); }
    .row:first-child { border-top: none; }
    .mode { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
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
    @container (max-width: 380px) {
      .row { grid-template-columns: auto minmax(0,1fr) auto 50px; gap: 6px; }
      .mode, .platform, .source { display: none; }
    }
  `,
  flap: `
    .board { overflow: hidden; background: #141414; padding: 12px 12px 10px; font-family: "Roboto Mono", "DejaVu Sans Mono", Menlo, Consolas, monospace; }
    .ftitle { color: #bdbdbd; font-size: 13px; letter-spacing: 1px; margin-bottom: 8px; display: flex; justify-content: space-between; }
    .fhead, .frow { display: flex; gap: 2px; align-items: center; }
    .fhead { color: #8a8a8a; font-size: 10px; letter-spacing: 1px; margin-bottom: 4px; }
    .fhead span { overflow: hidden; white-space: nowrap; }
    .frow { margin: 3px 0; }
    .fgap { flex: none; width: var(--gap, 6px); }
    .c { flex: none; width: var(--cw, 16px); height: calc(var(--cw, 16px) * 1.55); background: #252525; color: #f2f2f2;
         font-size: calc(var(--cw, 16px) * 1.02); display: flex; align-items: center; justify-content: center; border-radius: 2px;
         position: relative; line-height: 1; }
    .c::after { content: ""; position: absolute; left: 0; right: 0; top: 50%; height: 1px; background: #0a0a0a; }
    .c.f-line { color: #ffd23f; }
    .c.f-info { color: #ff7a5c; }
    .c.flip { animation: flip 70ms ease-in; }
    @keyframes flip { 0% { transform: scaleY(1); } 50% { transform: scaleY(0.15); } 100% { transform: scaleY(1); } }
    .falert { margin-top: 8px; color: #ffd23f; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  `,
  platform: `
    .quai { background: #0d2a5c; color: #fff; padding: 12px 16px 10px; }
    .qtop { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
    .qtitle { font-size: 1.25em; font-weight: 500; }
    .qstop { font-size: 0.8em; color: #9fb4d8; }
    .clock { font-variant-numeric: tabular-nums; font-size: 1.25em; }
    .qgrid { display: grid; grid-template-columns: auto auto minmax(0,1fr) auto auto; column-gap: 10px; align-items: center;
             font-variant-numeric: tabular-nums; }
    .qgrid.no-pl { grid-template-columns: auto auto minmax(0,1fr) auto; }
    .qrow { display: contents; }
    .qrow > span { padding: 7px 0; border-top: 1px solid #23427a; }
    .qrow.h > span { border: none; color: #9fb4d8; font-size: 0.75em; padding: 0 0 2px; }
    .short { display: none; }
    @container (max-width: 380px) { .long { display: none; } .short { display: inline; } .qgrid { column-gap: 6px; } }
    .qdest { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .qline { display: inline-block; background: #fff; color: #0d2a5c; border-radius: 3px; padding: 1px 5px; font-weight: 600;
             font-size: 0.85em; min-width: 2em; text-align: center; box-sizing: border-box; }
    .qpl.changed { color: #ffd23f; font-weight: 600; }
    .qinfo { color: #ffd23f; font-size: 0.85em; white-space: nowrap; }
    .qinfo.cancel { color: #ff8a80; }
    .blink { animation: blink 1.2s steps(2) infinite; }
    @keyframes blink { 50% { opacity: 0.3; } }
    .qcancel .qdest { text-decoration: line-through; color: #9fb4d8; }
    .ticker { margin-top: 8px; background: #ffd23f; color: #3a2a00; border-radius: 4px; padding: 5px 0; font-size: 0.85em;
              overflow: hidden; white-space: nowrap; }
    .ticker span { display: inline-block; padding-left: 100%; animation: scroll var(--dur, 20s) linear infinite; }
    @keyframes scroll { from { transform: translateX(0); } to { transform: translateX(-100%); } }
  `,
  countdown: `
    .cd { padding: 16px 18px; }
    .cdtop { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
    .cdstop { font-size: 0.85em; color: var(--secondary-text-color); }
    .cdline { display: flex; align-items: center; gap: 10px; margin-top: 6px; min-width: 0; }
    .cdline .line { font-size: 1.1em; padding: 3px 10px; }
    .cddest { font-size: 1.05em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .cdbig { text-align: right; flex: none; }
    .cdnum { font-size: 3.2em; font-weight: 500; line-height: 1; font-variant-numeric: tabular-nums; }
    .cdnum.late { color: var(--error-color, #db4437); }
    .cdsub { font-size: 0.85em; color: var(--secondary-text-color); white-space: nowrap; }
    .bar { height: 6px; background: var(--secondary-background-color, rgba(127,127,127,0.15)); border-radius: 3px; margin: 14px 0 10px; overflow: hidden; }
    .bar div { height: 100%; background: var(--success-color, #43a047); border-radius: 3px; transition: width 1s linear; }
    .bar div.hurry { background: var(--warning-color, #ffa600); }
    .chips { display: flex; gap: 8px; flex-wrap: wrap; font-size: 0.85em; }
    .chip { background: var(--secondary-background-color, rgba(127,127,127,0.12)); border-radius: 8px; padding: 4px 10px;
            display: inline-flex; align-items: center; gap: 4px; }
    .chip ha-icon { --mdc-icon-size: 16px; }
    .chip.warn { background: rgba(var(--rgb-warning-color, 255,166,0), 0.18); color: var(--warning-color, #b06d00); }
    .chip.go { background: rgba(var(--rgb-success-color, 67,160,71), 0.15); color: var(--success-color, #2e7d32); }
    .chip.bad { background: rgba(var(--rgb-error-color, 219,68,55), 0.15); color: var(--error-color, #db4437); }
  `,
  timeline: `
    .tl { padding: 12px 16px 10px; }
    .tlhead { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
    .tltitle { font-size: 1.1em; font-weight: 500; }
    .tlrow { display: grid; grid-template-columns: 3.6em minmax(0,1fr); gap: 8px; align-items: center; height: 30px; }
    .tllabel { text-align: right; }
    .track { position: relative; height: 100%; border-left: 2px dashed var(--error-color, #db4437); }
    .track::before { content: ""; position: absolute; left: 0; right: 0; top: 50%; border-top: 1px solid var(--divider-color); }
    .dot { position: absolute; top: 50%; transform: translate(-50%, -50%); font-size: 0.72em; padding: 2px 5px; border-radius: 4px;
           white-space: nowrap; background: var(--card-background-color, #fff); border: 1px solid var(--divider-color);
           font-variant-numeric: tabular-nums; }
    .dot.late { border-color: var(--error-color, #db4437); color: var(--error-color, #db4437); }
    .dot.cancel { text-decoration: line-through; color: var(--secondary-text-color); }
    .axis { display: grid; grid-template-columns: 3.6em minmax(0,1fr); gap: 8px; margin-top: 4px; }
    .ticks { position: relative; height: 14px; font-size: 0.7em; color: var(--secondary-text-color); border-top: 1px solid var(--divider-color); }
    .ticks span { position: absolute; top: 2px; transform: translateX(-50%); }
    .ticks span:first-child { transform: none; }
    .ticks span:last-child { transform: translateX(-100%); }
  `,
};

class SwissTransitCard extends HTMLElement {
  static getConfigForm() {
    const t = textsFor(pageLang());
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "swisstransit4ha" } } },
        {
          name: "style",
          selector: { select: { mode: "dropdown", options: STYLES.map((value) => ({ value, label: t.styles[value] })) } },
        },
        { name: "title", selector: { text: {} } },
        {
          type: "grid",
          name: "",
          schema: [
            { name: "max", selector: { number: { min: 1, max: 30, mode: "box" } } },
            { name: "window", selector: { number: { min: 10, max: 120, step: 5, mode: "box" } } },
            { name: "show_platform", selector: { boolean: {} } },
            { name: "show_alerts", selector: { boolean: {} } },
          ],
        },
      ],
      computeLabel: (schema) => t[schema.name] ?? undefined,
    };
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(
      (id) => id.startsWith("sensor.") && hass.states[id].attributes.swisstransit_board,
    );
    return { entity: entity || "", style: "list", show_platform: true, show_alerts: true };
  }

  setConfig(config) {
    if (!config.entity) throw new Error("entity is required");
    const style = STYLES.includes(config.style) ? config.style : "list";
    this._config = { show_platform: true, show_alerts: true, window: 30, ...config, style };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._built = null;
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
    this._timer = setInterval(() => this._render(), 20000);
    this._clockTimer = setInterval(() => this._tickClock(), 1000);
    if (this._board && this._resize) this._resize.observe(this._board);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    clearInterval(this._clockTimer);
    this._resize?.disconnect();
  }

  getCardSize() {
    const rows = Math.min(this._config?.max || 6, 10);
    return this._config?.style === "countdown" ? 3 : 2 + rows;
  }

  getGridOptions() {
    return this._config?.style === "countdown" ? { columns: 6, min_columns: 3 } : { columns: 12, min_columns: 6 };
  }

  // --- helpers ------------------------------------------------------------

  get _t() {
    return textsFor((this._hass?.language || pageLang()).slice(0, 2));
  }

  _clock(iso) {
    return new Date(iso).toLocaleTimeString(this._hass?.locale?.language || this._hass?.language || "en", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  _minutes(dep) {
    return Math.round((new Date(dep.expected || dep.planned) - Date.now()) / 60000);
  }

  _departures() {
    const attrs = this._state?.attributes || {};
    return (attrs.departures || []).filter((d) => this._minutes(d) > -1).slice(0, this._config.max || 30);
  }

  _alerts() {
    return this._config.show_alerts ? this._state?.attributes?.alerts || [] : [];
  }

  _title() {
    return this._config.title ?? this._state?.attributes?.stop_name ?? "";
  }

  _countdown(dep) {
    if (dep.cancelled) return `<span class="cancelled-label">${this._t.cancelled}</span>`;
    const m = this._minutes(dep);
    if (m <= 0) return `<span class="soon">${this._t.now}</span>`;
    return m < 60 ? `${m}&nbsp;${this._t.min}` : "";
  }

  // --- rendering ----------------------------------------------------------

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const style = this._config.style;
    if (this._built !== style) {
      this.shadowRoot.innerHTML = `<style>${BASE_CSS}${STYLE_CSS[style]}</style><ha-card><div id="root"></div></ha-card>`;
      this._root = this.shadowRoot.getElementById("root");
      this._built = style;
      this._flapKey = null;
      this._resize?.disconnect();
    }
    if (!this._state || this._state.state === "unavailable") {
      this._flapKey = null;
      this._root.innerHTML = `<div class="empty" style="padding:16px">${this._t.unavailable}</div>`;
      return;
    }
    this[`_render_${style}`]();
  }

  _render_list() {
    const deps = this._departures();
    const rows = deps.length
      ? deps.map((d) => this._listRow(d)).join("")
      : `<div class="empty">${this._t.none}</div>`;
    const alerts = this._alerts().length
      ? `<div class="alerts">${this._alerts()
          .map(
            (a) =>
              `<details><summary><ha-icon icon="mdi:alert"></ha-icon>${esc(a.summary)}</summary>${
                a.description ? `<p>${esc(a.description)}</p>` : ""
              }</details>`,
          )
          .join("")}</div>`
      : "";
    this._root.innerHTML = `
      <div class="wrap">
        <div class="header"><span class="title">${esc(this._title())}</span><span class="source">${esc(this._state.attributes.source || "")}</span></div>
        ${alerts}<div>${rows}</div>
      </div>`;
  }

  _listRow(dep) {
    const late = dep.delay > 0;
    const platform =
      this._config.show_platform && dep.platform
        ? `<span class="platform ${dep.platform_changed ? "changed" : ""}">${this._t.platform} ${esc(dep.platform)}</span>`
        : '<span class="platform"></span>';
    return `
      <div class="row ${dep.cancelled ? "is-cancelled" : ""}">
        <ha-icon class="mode" icon="${MODE_ICONS[dep.mode] || MODE_ICONS.other}"></ha-icon>
        <span class="line mode-${esc(dep.mode)}">${esc(dep.line)}</span>
        <span class="dest">${esc(dep.destination)}${dep.situations?.length ? ' <ha-icon class="warn" icon="mdi:alert"></ha-icon>' : ""}</span>
        ${platform}
        <span class="time"><span class="${late ? "planned" : ""}">${this._clock(dep.planned)}</span>${late ? `<span class="delay">+${dep.delay}'</span>` : ""}</span>
        <span class="countdown">${this._countdown(dep)}</span>
      </div>`;
  }

  // Split-flap board: cells are kept between updates and only the ones whose
  // character changes spin to their new letter.
  _render_flap() {
    const t = this._t;
    const rows = Math.min(this._config.max || 6, 12);
    const showPl = this._config.show_platform;
    const fields = [
      { key: "time", w: 5, head: t.time },
      { key: "line", w: 4, head: t.line },
      { key: "dest", w: this._flapDest || 16, head: t.destination },
      ...(showPl ? [{ key: "pl", w: 3, head: t.pl }] : []),
      { key: "info", w: 5, head: t.info },
    ];
    const key = `${rows}|${fields.map((f) => f.key + f.w).join()}|${t.time}`;
    if (this._flapKey !== key) this._buildFlap(rows, fields, key);

    const deps = this._departures();
    for (let r = 0; r < rows; r++) {
      const d = deps[r];
      const values = d
        ? {
            time: this._clock(d.planned),
            line: d.line,
            dest: d.destination,
            pl: d.platform || "",
            info: d.cancelled ? t.cancelled_short : d.delay > 0 ? `+${d.delay}'` : "",
          }
        : {};
      fields.forEach((f, i) => {
        const text = flapText(values[f.key]).padEnd(f.w).slice(0, f.w);
        this._cells[r][i].forEach((cell, k) => this._flip(cell, text[k]));
      });
    }
    this._flapTitle.textContent = flapText(this._title());
    const alerts = this._alerts();
    this._flapAlert.textContent = alerts.length ? `⚠ ${alerts.map((a) => a.summary).join(" · ")}` : "";
    this._flapAlert.style.display = alerts.length ? "" : "none";
  }

  _buildFlap(rows, fields, key) {
    const total = fields.reduce((s, f) => s + f.w, 0);
    const head = fields
      .map((f, i) => `${i ? '<span class="fgap"></span>' : ""}<span style="width:calc(var(--cw) * ${f.w} + 2px * ${f.w - 1})">${esc(f.head)}</span>`)
      .join("");
    let body = "";
    for (let r = 0; r < rows; r++) {
      body += '<div class="frow">';
      fields.forEach((f, i) => {
        if (i) body += '<span class="fgap"></span>';
        for (let k = 0; k < f.w; k++) body += `<span class="c f-${f.key}" data-r="${r}" data-i="${i}"> </span>`;
      });
      body += "</div>";
    }
    this._root.innerHTML = `<div class="board"><div class="ftitle"><span class="ft"></span></div>
      <div class="fhead">${head}</div>${body}<div class="falert"></div></div>`;
    this._board = this._root.querySelector(".board");
    this._flapTitle = this._root.querySelector(".ft");
    this._flapAlert = this._root.querySelector(".falert");
    this._cells = Array.from({ length: rows }, () => fields.map(() => []));
    this._root.querySelectorAll(".c").forEach((c) => {
      c._char = " ";
      this._cells[+c.dataset.r][+c.dataset.i].push(c);
    });
    this._flapKey = key;
    // Size the cells to the card width; the destination gets the room left.
    const gaps = fields.length - 1;
    const others = total - fields.find((f) => f.key === "dest").w;
    const fit = () => {
      const width = this._board.clientWidth - 24;
      if (width <= 0) return;
      const gap = Math.max(4, Math.round(width / 90));
      const cw = Math.max(9, Math.min(22, Math.floor(width / 30)));
      const dest = Math.max(6, Math.min(28, Math.floor((width - gaps * gap + 2 * fields.length) / (cw + 2)) - others));
      this._board.style.setProperty("--cw", `${cw}px`);
      this._board.style.setProperty("--gap", `${gap}px`);
      if (dest !== (this._flapDest || 16)) {
        this._flapDest = dest;
        requestAnimationFrame(() => this._render());
      }
    };
    this._resize = new ResizeObserver(fit);
    this._resize.observe(this._board);
    fit();
  }

  _flip(cell, target) {
    target = FLAP_CHARS.includes(target) ? target : " ";
    if (cell._target === target) return;
    cell._target = target;
    clearTimeout(cell._timeout);
    let index = Math.max(0, FLAP_CHARS.indexOf(cell._char));
    const goal = FLAP_CHARS.indexOf(target);
    const step = () => {
      index = (index + 1) % FLAP_CHARS.length;
      cell._char = FLAP_CHARS[index];
      cell.textContent = cell._char;
      cell.classList.remove("flip");
      void cell.offsetWidth;
      cell.classList.add("flip");
      if (index !== goal) cell._timeout = setTimeout(step, 28 + Math.random() * 20);
    };
    if (cell._char !== target) cell._timeout = setTimeout(step, Math.random() * 300);
  }

  _render_platform() {
    const t = this._t;
    const showPl = this._config.show_platform;
    const cls = "qrow";
    const deps = this._departures();
    const rows = deps
      .map((d) => {
        const info = d.cancelled
          ? `<span class="qinfo cancel"><span class="long">${t.cancelled}</span><span class="short">${t.cancelled_short}</span></span>`
          : d.delay > 0
            ? `<span class="qinfo blink"><span class="long">${t.approx} +${d.delay} ${t.min}</span><span class="short">+${d.delay}'</span></span>`
            : "";
        const pl = showPl ? `<span class="qpl ${d.platform_changed ? "changed" : ""}">${esc(d.platform || "")}</span>` : "";
        return `<div class="${cls} ${d.cancelled ? "qcancel" : ""}"><span>${this._clock(d.planned)}</span>
          <span><span class="qline">${esc(d.line)}</span></span><span class="qdest">${esc(d.destination)}</span>${pl}<span>${info}</span></div>`;
      })
      .join("");
    const alerts = this._alerts();
    const text = alerts.map((a) => a.summary + (a.description ? ` — ${a.description}` : "")).join("   ·   ");
    const ticker = alerts.length
      ? `<div class="ticker"><span style="--dur:${Math.max(12, text.length / 6).toFixed(0)}s">${esc(text)}</span></div>`
      : "";
    this._root.innerHTML = `
      <div class="quai">
        <div class="qtop"><div><div class="qtitle">${t.departure}</div><div class="qstop">${esc(this._title())}</div></div><span class="clock"></span></div>
        <div class="qgrid${showPl ? "" : " no-pl"}">
        <div class="${cls} h"><span>${t.heading_time}</span><span>${t.heading_line}</span><span>${t.heading_dest}</span>${
          showPl ? `<span>${t.heading_pl}</span>` : ""
        }<span>${t.heading_info}</span></div>
        ${rows}</div>
        ${rows ? "" : `<div class="empty" style="color:#9fb4d8">${t.none}</div>`}
        ${ticker}
      </div>`;
    this._tickClock();
  }

  _tickClock() {
    const clock = this._config?.style === "platform" && this._root?.querySelector(".clock");
    if (clock) {
      clock.textContent = new Date().toLocaleTimeString(this._hass?.language || "en", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    }
  }

  _render_countdown() {
    const t = this._t;
    const deps = this._departures();
    const next = deps.find((d) => !d.cancelled) || deps[0];
    if (!next) {
      this._root.innerHTML = `<div class="cd"><div class="cdstop">${esc(this._title())}</div><div class="empty">${t.none}</div></div>`;
      return;
    }
    const minutes = Math.max(0, this._minutes(next));
    const walk = Number(this._state.attributes.walk_time || 0);
    const leave = minutes - walk;
    const fill = Math.max(4, Math.min(100, 100 - (minutes / 15) * 100));
    const chips = [];
    deps
      .filter((d) => d !== next)
      .slice(0, 3)
      .forEach((d, i) => {
        const m = Math.max(0, this._minutes(d));
        chips.push(
          `<span class="chip ${d.cancelled ? "bad" : ""}">${i === 0 ? `${t.then} ` : ""}${esc(d.line)} · ${this._clock(d.expected || d.planned)}${
            d.cancelled ? ` · ${t.cancelled}` : ` · ${m} ${t.min}`
          }</span>`,
        );
      });
    this._alerts()
      .slice(0, 2)
      .forEach((a) => chips.push(`<span class="chip warn"><ha-icon icon="mdi:alert"></ha-icon>${esc(a.summary)}</span>`));
    if (walk > 0) {
      chips.push(
        `<span class="chip go"><ha-icon icon="mdi:walk"></ha-icon>${
          leave <= 0 ? t.leave_now : `${t.leave_in} ${leave} ${t.min}`
        }</span>`,
      );
    }
    const late = next.delay > 0;
    this._root.innerHTML = `
      <div class="cd">
        <div class="cdtop">
          <div style="min-width:0">
            <div class="cdstop">${esc(this._title())}</div>
            <div class="cdline"><span class="line mode-${esc(next.mode)}">${esc(next.line)}</span><span class="cddest">${esc(next.destination)}</span></div>
          </div>
          <div class="cdbig">
            <div class="cdnum ${late ? "late" : ""}">${minutes <= 0 ? t.now : minutes}</div>
            <div class="cdsub">${minutes <= 0 ? "" : `${t.min} · `}${this._clock(next.expected || next.planned)}${late ? ` (+${next.delay}')` : ""}${
              this._config.show_platform && next.platform ? ` · ${t.platform} ${esc(next.platform)}` : ""
            }</div>
          </div>
        </div>
        <div class="bar"><div class="${walk > 0 && leave <= 1 ? "hurry" : ""}" style="width:${fill.toFixed(0)}%"></div></div>
        <div class="chips">${chips.join("")}</div>
      </div>`;
  }

  _render_timeline() {
    const t = this._t;
    const span = Number(this._config.window) || 30;
    const deps = (this._state.attributes.departures || []).filter((d) => {
      const m = this._minutes(d);
      return m > -1 && m <= span;
    });
    const lines = [];
    deps.forEach((d) => {
      let row = lines.find((l) => l.line === d.line);
      if (!row) lines.push((row = { line: d.line, mode: d.mode, deps: [] }));
      row.deps.push(d);
    });
    const rows = lines
      .slice(0, 8)
      .map((row) => {
        const trackPx = Math.max(120, (this.clientWidth || 400) - 90);
        let prevRight = -Infinity;
        const dots = row.deps
          .map((d) => {
            const m = Math.max(0, this._minutes(d));
            const label = this._clock(d.expected || d.planned).length + (d.delay > 0 ? 4 : 0);
            const half = ((label * 6.2 + 12) / 2 / trackPx) * 100;
            let left = Math.min(100 - half, Math.max(half, (m / span) * 100));
            left = Math.max(left, prevRight + half + 0.8);
            prevRight = left + half;
            const cls = d.cancelled ? "cancel" : d.delay > 0 ? "late" : "";
            return `<span class="dot ${cls}" style="left:${left.toFixed(1)}%" title="${esc(d.destination)}">${this._clock(
              d.expected || d.planned,
            )}${d.delay > 0 ? ` +${d.delay}'` : ""}</span>`;
          })
          .join("");
        return `<div class="tlrow"><span class="tllabel"><span class="line mode-${esc(row.mode)}">${esc(row.line)}</span></span><div class="track">${dots}</div></div>`;
      })
      .join("");
    const ticks = [0, span / 3, (2 * span) / 3, span]
      .map((m, i) => `<span style="left:${((m / span) * 100).toFixed(1)}%">${i === 0 ? t.now : `+${Math.round(m)}`}</span>`)
      .join("");
    const alerts = this._alerts();
    this._root.innerHTML = `
      <div class="tl">
        <div class="tlhead"><span class="tltitle">${esc(this._title())}</span><span style="font-size:0.75em;color:var(--secondary-text-color)">${span} ${t.min}</span></div>
        ${rows || `<div class="empty">${t.none}</div>`}
        <div class="axis"><span></span><div class="ticks">${ticks}</div></div>
        ${
          alerts.length
            ? `<div style="margin-top:8px;font-size:0.85em;color:var(--warning-color,#b06d00)">⚠ ${esc(alerts.map((a) => a.summary).join(" · "))}</div>`
            : ""
        }
      </div>`;
  }
}

if (!customElements.get("swisstransit-departures-card")) {
  customElements.define("swisstransit-departures-card", SwissTransitCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "swisstransit-departures-card",
    name: "Swiss Transit departures",
    description: "Next departures, delays and disruptions of a Swiss stop: list, split-flap board, platform display, large countdown or timeline.",
    preview: true,
    documentationURL: "https://github.com/SashConnection/swisstransit4HA",
  });
}
