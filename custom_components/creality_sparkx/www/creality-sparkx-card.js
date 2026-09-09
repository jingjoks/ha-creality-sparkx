/**
 * Creality SPARKX status card.
 *
 * Dependency-free custom Lovelace card (no external libraries, no
 * card-tools) bundled with the ha-creality-sparkx integration and
 * auto-registered on Home Assistant startup - nothing to install
 * separately.
 *
 * Example card config:
 *
 *   type: custom:creality-sparkx-card
 *   title: SparkX i7
 *   state_entity: sensor.sparkx_i7_print_state
 *   progress_entity: sensor.sparkx_i7_print_progress
 *   file_entity: sensor.sparkx_i7_current_file
 *   time_remaining_entity: sensor.sparkx_i7_print_time_remaining
 *   nozzle_temp_entity: sensor.sparkx_i7_nozzle_temperature
 *   bed_temp_entity: sensor.sparkx_i7_bed_temperature
 *   problem_entity: binary_sensor.sparkx_i7_problem
 *   light_entity: switch.sparkx_i7_chamber_light
 *   pause_entity: button.sparkx_i7_pause_print
 *   resume_entity: button.sparkx_i7_resume_print
 *   cancel_entity: button.sparkx_i7_cancel_print
 *   camera_entity: camera.sparkx_i7_printer_camera
 *   image_entity: image.sparkx_i7_print_preview
 *   accent_color: "#3fa9f5"   # optional, defaults shown below
 *
 * Every *_entity key is optional except state_entity - rows/buttons for
 * anything not configured (or not present in this HA install) are simply
 * not shown, so the same card works whether or not you set up the
 * optional power-switch binding, camera, etc.
 *
 * Media row: if camera_entity is set, the card embeds HA's own
 * <ha-camera-stream> element (the same element the built-in camera card
 * uses) for a genuine live view (WebRTC/HLS, whichever HA negotiates for
 * that entity) - not a polled snapshot. image_entity (the slicer-embedded
 * print-preview thumbnail) is shown alongside it, smaller, when configured.
 */

class CrealitySparkXCard extends HTMLElement {
  setConfig(config) {
    if (!config.state_entity) {
      throw new Error("creality-sparkx-card: 'state_entity' is required");
    }
    this._config = config;
    this._built = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) {
      this._build();
      this._built = true;
    }
    this._update();
  }

  getCardSize() {
    return this._config.camera_entity ? 8 : 4;
  }

  _fmtDuration(seconds) {
    const s = Number(seconds);
    if (!Number.isFinite(s) || s <= 0) return "-";
    const total = Math.floor(s);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const sec = total % 60;
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(h)}:${pad(m)}:${pad(sec)}`;
  }

  _fmtFinishTime(seconds) {
    const s = Number(seconds);
    if (!Number.isFinite(s) || s <= 0) return null;
    const finish = new Date(Date.now() + s * 1000);
    return finish.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  }

  _stateLabel(entityId) {
    const st = this._hass.states[entityId];
    if (!st) return null;
    return this._hass.formatEntityState
      ? this._hass.formatEntityState(st)
      : st.state;
  }

  _callButton(entityId) {
    if (!entityId) return;
    this._hass.callService("button", "press", { entity_id: entityId });
  }

  _toggleLight(entityId) {
    if (!entityId) return;
    const st = this._hass.states[entityId];
    this._hass.callService("switch", st && st.state === "on" ? "turn_off" : "turn_on", {
      entity_id: entityId,
    });
  }

  _build() {
    const c = this._config;
    const accent = c.accent_color || "var(--primary-color, #03a9f4)";
    const root = this.attachShadow ? this.attachShadow({ mode: "open" }) : this;

    root.innerHTML = `
      <style>
        ha-card { padding: 16px; }
        .header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
        .title { font-size: 1.1em; font-weight: 500; }
        .state { font-size: 0.95em; padding: 2px 10px; border-radius: 12px; background: var(--secondary-background-color); }
        .state.problem { background: var(--error-color, #db4437); color: white; }
        .media-row { display: flex; gap: 10px; margin-bottom: 10px; align-items: flex-start; }
        .media-row img { border-radius: 8px; max-width: 100%; display: block; }
        .media-row ha-camera-stream { border-radius: 8px; overflow: hidden; display: block; background: #000; }
        .media-row .preview-wrap { flex: 0 0 auto; max-width: 35%; }
        .media-row .preview-wrap img { width: 100%; }
        .progress-wrap { background: var(--divider-color); border-radius: 6px; height: 10px; overflow: hidden; margin: 10px 0 4px; }
        .progress-bar { height: 100%; background: ${accent}; transition: width 0.5s ease; }
        .meta-row { display: flex; justify-content: space-between; font-size: 0.85em; color: var(--secondary-text-color); margin-bottom: 10px; }
        .pills { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
        .pill { background: var(--secondary-background-color); border-radius: 14px; padding: 4px 10px; font-size: 0.85em; display: flex; align-items: center; gap: 4px; }
        .buttons { display: flex; gap: 8px; flex-wrap: wrap; }
        .buttons button { flex: 1; min-width: 80px; border: none; border-radius: 8px; padding: 8px; font-size: 0.85em; cursor: pointer; background: var(--secondary-background-color); color: var(--primary-text-color); }
        .buttons button.accent { background: ${accent}; color: white; }
        .filename { font-size: 0.85em; color: var(--secondary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-bottom: 6px; }
      </style>
      <ha-card>
        <div class="header">
          <div class="title">${c.title || "Creality SPARKX"}</div>
          <div class="state" id="state-pill">-</div>
        </div>
        <div class="media-row" id="media-row"></div>
        <div class="filename" id="filename" hidden></div>
        <div class="progress-wrap"><div class="progress-bar" id="progress-bar" style="width:0%"></div></div>
        <div class="meta-row"><span id="progress-pct">-</span><span id="time-remaining"></span><span id="finish-time"></span></div>
        <div class="pills" id="pills"></div>
        <div class="buttons" id="buttons"></div>
      </ha-card>
    `;
    this._root = root;
  }

  _update() {
    const c = this._config;
    const hass = this._hass;
    const root = this._root;

    const stateEnt = hass.states[c.state_entity];
    const problemOn = c.problem_entity && hass.states[c.problem_entity]?.state === "on";
    const statePill = root.getElementById("state-pill");
    statePill.textContent = stateEnt
      ? this._stateLabel(c.state_entity) || stateEnt.state
      : "unavailable";
    statePill.className = "state" + (problemOn ? " problem" : "");

    // Media row: a genuine live <ha-camera-stream> (WebRTC/HLS, whatever HA
    // negotiates) when camera_entity is configured, plus the smaller
    // slicer-thumbnail preview image alongside it when image_entity is set.
    // Built once; the stream element then just gets fresh .hass/.stateObj
    // on every update, same as HA's own picture-entity/camera cards do.
    const mediaRow = root.getElementById("media-row");
    if (!mediaRow.dataset.built) {
      mediaRow.innerHTML = "";
      const haveCamera = c.camera_entity && hass.states[c.camera_entity];
      const havePreview = c.image_entity && hass.states[c.image_entity];
      if (haveCamera) {
        const streamEl = document.createElement("ha-camera-stream");
        streamEl.id = "camera-stream";
        streamEl.style.flex = "1 1 auto";
        streamEl.style.minWidth = "0";
        streamEl.style.width = "100%";
        streamEl.muted = true;
        streamEl.controls = false;
        streamEl.allowExifRotation = true;
        mediaRow.appendChild(streamEl);

        // Some printers' embedded WebRTC signaling servers are unreliable
        // with a genuine browser SDP offer (observed: the SPARKX i7's own
        // endpoint intermittently resets the connection on a real offer
        // while happily accepting small synthetic ones - a firmware-side
        // quirk, not something fixable from here). Rather than leaving an
        // indefinite blank/black box when that happens, give it a few
        // seconds then fall back to just the preview thumbnail (if any).
        setTimeout(() => {
          const player = streamEl.shadowRoot?.querySelector("ha-web-rtc-player, ha-hls-player");
          const video = player?.shadowRoot?.querySelector("video");
          const connected = video && (video.readyState >= 2 || video.videoWidth > 0);
          if (!connected) {
            streamEl.style.display = "none";
            const previewWrap = mediaRow.querySelector(".preview-wrap");
            if (previewWrap) previewWrap.style.maxWidth = "100%";
          }
        }, 6000);
      }
      if (havePreview) {
        const wrap = document.createElement("div");
        wrap.className = "preview-wrap";
        if (!haveCamera) wrap.style.maxWidth = "50%";
        const img = document.createElement("img");
        img.id = "preview-img";
        img.alt = "preview";
        wrap.appendChild(img);
        mediaRow.appendChild(wrap);
      }
      mediaRow.dataset.built = "1";
      mediaRow.style.display = haveCamera || havePreview ? "flex" : "none";
    }
    const streamEl = root.getElementById("camera-stream");
    if (streamEl && c.camera_entity && hass.states[c.camera_entity]) {
      streamEl.hass = hass;
      streamEl.stateObj = hass.states[c.camera_entity];
    }
    const previewImg = root.getElementById("preview-img");
    if (previewImg && c.image_entity && hass.states[c.image_entity]) {
      const st = hass.states[c.image_entity];
      if (st.attributes.entity_picture) {
        previewImg.src = st.attributes.entity_picture;
      }
    }

    // Filename
    const filenameEl = root.getElementById("filename");
    if (c.file_entity && hass.states[c.file_entity]?.state) {
      const full = hass.states[c.file_entity].state;
      filenameEl.textContent = full.split("/").pop();
      filenameEl.hidden = false;
    } else {
      filenameEl.hidden = true;
    }

    // Progress
    const progress = c.progress_entity ? Number(hass.states[c.progress_entity]?.state) : NaN;
    const progressPct = Number.isFinite(progress) ? progress : 0;
    root.getElementById("progress-bar").style.width = `${progressPct}%`;
    root.getElementById("progress-pct").textContent = Number.isFinite(progress)
      ? `${progress}%`
      : "-";
    const remainingSeconds = c.time_remaining_entity
      ? hass.states[c.time_remaining_entity]?.state
      : null;
    root.getElementById("time-remaining").textContent = c.time_remaining_entity
      ? this._fmtDuration(remainingSeconds)
      : "";
    const finishEl = root.getElementById("finish-time");
    const finishTime = remainingSeconds != null ? this._fmtFinishTime(remainingSeconds) : null;
    finishEl.textContent = finishTime ? `เสร็จ ~${finishTime}` : "";

    // Temperature / status pills
    const pills = root.getElementById("pills");
    const pillDefs = [];
    if (c.nozzle_temp_entity) {
      const v = hass.states[c.nozzle_temp_entity]?.state;
      pillDefs.push(`🔥 ${v ?? "-"}°C`);
    }
    if (c.bed_temp_entity) {
      const v = hass.states[c.bed_temp_entity]?.state;
      pillDefs.push(`🛏️ ${v ?? "-"}°C`);
    }
    pills.innerHTML = pillDefs.map((t) => `<div class="pill">${t}</div>`).join("");

    // Buttons
    const buttons = root.getElementById("buttons");
    if (!buttons.dataset.built) {
      const defs = [];
      if (c.pause_entity) defs.push(["pause", "⏸ Pause", c.pause_entity, "button"]);
      if (c.resume_entity) defs.push(["resume", "▶ Resume", c.resume_entity, "button"]);
      if (c.cancel_entity) defs.push(["cancel", "⏹ Cancel", c.cancel_entity, "button"]);
      if (c.light_entity) defs.push(["light", "💡 Light", c.light_entity, "switch"]);
      buttons.innerHTML = defs
        .map(
          ([key, label]) =>
            `<button id="btn-${key}" class="${key === "resume" ? "accent" : ""}">${label}</button>`
        )
        .join("");
      for (const [key, , entityId, domain] of defs) {
        const btn = root.getElementById(`btn-${key}`);
        btn.addEventListener("click", () => {
          if (domain === "switch") this._toggleLight(entityId);
          else this._callButton(entityId);
        });
      }
      buttons.dataset.built = "1";
    }
  }
}

customElements.define("creality-sparkx-card", CrealitySparkXCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "creality-sparkx-card",
  name: "Creality SPARKX Card",
  description: "Status, controls and live camera preview for a Creality SPARKX / K-series printer (ha-creality-sparkx).",
});
