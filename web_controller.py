from __future__ import annotations

import ipaddress
import os
from typing import Optional

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from config import PROFILE_NAMES
from runtime_control import LASER_SHAPES, RuntimeControl


class ProfileUpdate(BaseModel):
    enable_beat: Optional[bool] = None
    enable_frequency: Optional[bool] = None
    enable_combo: Optional[bool] = None
    enable_mega_combo: Optional[bool] = None
    enable_strobe_only: Optional[bool] = None
    enable_ambient: Optional[bool] = None
    enable_subtle: Optional[bool] = None
    max_strobe_level: Optional[int] = Field(default=None, ge=0, le=255)
    max_dimmer_level: Optional[int] = Field(default=None, ge=0, le=255)
    max_uv_level: Optional[int] = Field(default=None, ge=0, le=255)
    max_laser_level: Optional[int] = Field(default=None, ge=0, le=255)
    max_vu_level: Optional[int] = Field(default=None, ge=0, le=255)
    max_eurolite_level: Optional[int] = Field(default=None, ge=0, le=255)
    max_smoke_level: Optional[int] = Field(default=None, ge=0, le=255)
    max_smoke_led_level: Optional[int] = Field(default=None, ge=0, le=255)


class DeviceUpdate(BaseModel):
    use_laser: Optional[bool] = None
    use_strobe: Optional[bool] = None
    use_spotlight: Optional[bool] = None
    use_stinger: Optional[bool] = None
    use_vu_meter: Optional[bool] = None
    use_eurolite_strobe: Optional[bool] = None
    use_smoke_machine: Optional[bool] = None


class RuntimeUpdate(BaseModel):
    master_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    blackout: Optional[bool] = None
    laser_shape: Optional[str] = None


class ChannelTestRequest(BaseModel):
    device: str
    channel_offset: int = Field(..., ge=1)
    value: int = Field(default=255, ge=0, le=255)


class PresetRequest(BaseModel):
    name: str


# (start address, channel count) per DMX fixture - must stay in sync with
# the dmx_channel/num_channels used in show_controller.py._open_devices.
# The VU meter isn't listed: it's a Blinkt GPIO LED strip, not a DMX fixture.
_DEVICE_CHANNELS: dict[str, tuple[int, int]] = {
    "laser": (1, 10),
    "strobe": (11, 7),
    "spotlight": (22, 7),
    "stinger": (33, 9),
    "eurolite_strobe": (44, 6),
    "smoke_machine": (55, 9),
}


def _is_truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _parse_allowed_networks(
    raw_value: str | None,
) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    if not raw_value:
        return []

    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for token in raw_value.split(","):
        candidate = token.strip()
        if not candidate:
            continue
        try:
            networks.append(ipaddress.ip_network(candidate, strict=False))
        except ValueError:
            # Ignore malformed CIDR entries rather than failing startup.
            continue
    return networks


def _is_allowed_client(
    client_host: str,
    *,
    local_only: bool,
    extra_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> bool:
    if not local_only:
        return True

    if not client_host:
        return False

    try:
        ip = ipaddress.ip_address(client_host)
    except ValueError:
        return False

    if ip.is_loopback or ip.is_private or ip.is_link_local:
        return True

    return any(ip in network for network in extra_networks)


def create_app(runtime_control: RuntimeControl) -> FastAPI:
    app = FastAPI(title="Jingle DMX Controller", version="0.1.0")
    local_only = _is_truthy(os.getenv("WEB_CONTROLLER_LOCAL_ONLY"), default=True)
    extra_networks = _parse_allowed_networks(os.getenv("WEB_CONTROLLER_ALLOWED_CIDRS"))

    @app.middleware("http")
    async def enforce_network_policy(request: Request, call_next):
        host = request.client.host if request.client else ""
        if not _is_allowed_client(
            host,
            local_only=local_only,
            extra_networks=extra_networks,
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "web controller is limited to local network"},
            )
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/state")
    def get_state() -> dict:
        return runtime_control.state()

    @app.put("/api/profile")
    def put_profile(update: ProfileUpdate) -> dict:
        runtime_control.update_profile(update.model_dump(exclude_none=True))
        return runtime_control.state()

    @app.put("/api/devices")
    def put_devices(update: DeviceUpdate) -> dict:
        runtime_control.update_devices(update.model_dump(exclude_none=True))
        return runtime_control.state()

    @app.put("/api/runtime")
    def put_runtime(update: RuntimeUpdate) -> JSONResponse:
        if update.laser_shape is not None and update.laser_shape not in LASER_SHAPES:
            return JSONResponse(
                status_code=400,
                content={"detail": f"laser_shape must be one of {list(LASER_SHAPES)}"},
            )
        runtime_control.update_runtime(
            master_intensity=update.master_intensity,
            blackout=update.blackout,
            laser_shape=update.laser_shape,
        )
        return JSONResponse(content=runtime_control.state())

    @app.get("/api/profile-presets")
    def get_profile_presets() -> list[str]:
        return PROFILE_NAMES

    @app.get("/api/laser-shapes")
    def get_laser_shapes() -> list[str]:
        return list(LASER_SHAPES)

    @app.post("/api/apply-preset")
    def post_apply_preset(req: PresetRequest) -> JSONResponse:
        if req.name not in PROFILE_NAMES:
            return JSONResponse(
                status_code=400,
                content={"detail": f"unknown preset '{req.name}', choose from {PROFILE_NAMES}"},
            )
        runtime_control.set_profile_preset(req.name)
        return JSONResponse(content=runtime_control.state())

    @app.post("/api/trigger-smoke-burst")
    def post_trigger_smoke_burst() -> dict:
        runtime_control.trigger_smoke_burst()
        return runtime_control.state()

    @app.get("/api/telemetry")
    def get_telemetry() -> dict:
        return runtime_control.get_telemetry() or {}

    @app.get("/api/device-channels")
    def get_device_channels() -> dict:
        return {
            name: {"base": base, "count": count}
            for name, (base, count) in _DEVICE_CHANNELS.items()
        }

    @app.post("/api/test-channel")
    def post_test_channel(req: ChannelTestRequest) -> JSONResponse:
        info = _DEVICE_CHANNELS.get(req.device)
        if info is None:
            return JSONResponse(
                status_code=404, content={"detail": f"unknown device '{req.device}'"}
            )
        _, count = info
        if req.channel_offset > count:
            return JSONResponse(
                status_code=400,
                content={"detail": f"{req.device} only has {count} channels"},
            )
        runtime_control.set_channel_test(req.device, req.channel_offset, req.value)
        return JSONResponse(content=runtime_control.state())

    @app.post("/api/test-channel/clear")
    def post_clear_test_channel() -> dict:
        runtime_control.clear_channel_test()
        return runtime_control.state()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _PAGE

    return app


_PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Jingle DMX Controller</title>
  <style>
    :root {
      --bg: #09121c;
      --bg2: #111f2a;
      --panel: #132838;
      --text: #e6f2ff;
      --muted: #9db6cc;
      --accent: #4fd1a8;
      --warn: #ffb347;
      --danger: #ff6666;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Trebuchet MS", "Segoe UI", sans-serif;
      background:
        radial-gradient(1200px 500px at 10% -20%, #1d3f57 0%, transparent 60%),
        radial-gradient(900px 500px at 90% 0%, #1d5647 0%, transparent 55%),
        linear-gradient(180deg, var(--bg), var(--bg2));
      color: var(--text);
      min-height: 100vh;
      padding: 20px;
    }
    .wrap {
      max-width: 1100px;
      margin: 0 auto;
      display: grid;
      gap: 14px;
    }
    .card {
      background: color-mix(in oklab, var(--panel), black 6%);
      border: 1px solid #29465c;
      border-radius: 12px;
      padding: 14px;
      box-shadow: 0 8px 25px rgba(0,0,0,0.25);
    }
    h1 { margin: 0 0 10px; font-size: 1.7rem; letter-spacing: 0.02em; }
    h2 { margin: 0 0 10px; font-size: 1.1rem; color: #b9d7ef; }
    .grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }
    .row { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 7px 0; }
    .row label { color: var(--muted); }
    input[type="range"] { width: 100%; }
    input[type="number"] {
      width: 82px; padding: 5px 7px; border-radius: 8px;
      border: 1px solid #3a5b73; background: #0f1f2c; color: var(--text);
    }
    select {
      padding: 5px 7px; border-radius: 8px;
      border: 1px solid #3a5b73; background: #0f1f2c; color: var(--text);
    }
    button {
      padding: 8px 12px; border-radius: 8px; border: 1px solid #35566f;
      background: #193347; color: var(--text); cursor: pointer;
      transition: transform .08s ease, background .2s ease;
    }
    button:hover { background: #244a64; transform: translateY(-1px); }
    .danger { border-color: #6c2f2f; background: #4b2323; }
    .danger:hover { background: #643131; }
    .status { color: var(--accent); font-size: 0.95rem; }
    .muted { color: var(--muted); font-size: 0.92rem; }
    .chip {
      display: inline-block; padding: 4px 9px; border-radius: 999px;
      font-size: 0.8rem; background: #17354a; color: #c3e1f8; border: 1px solid #2f5876;
    }
    .meter {
      height: 10px; border-radius: 6px; background: #0f1f2c;
      border: 1px solid #3a5b73; overflow: hidden; margin: 4px 0 10px;
      position: relative;
    }
    .meter-fill { height: 100%; background: var(--accent); transition: width 0.15s ease; }
    .meter-mark {
      position: absolute; top: 0; bottom: 0; width: 2px; background: var(--warn);
    }
    .telemetry-stale { color: var(--danger); }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Jingle DMX Live Control</h1>
      <div class="row">
        <span class="chip" id="profileName">profile</span>
        <span class="status" id="status">loading...</span>
      </div>
      <div class="muted">Changes are applied live without restarting the show loop.</div>
    </div>

    <div class="card">
      <h2>Live Status</h2>
      <div id="telemetryBody">
        <div class="muted">waiting for telemetry...</div>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Runtime</h2>
        <div class="row"><label>Master Intensity</label><span id="masterLabel">1.00</span></div>
        <input id="masterIntensity" type="range" min="0" max="1" step="0.01" value="1" />
        <div class="row" style="margin-top:10px;">
          <label><input id="blackout" type="checkbox" /> Blackout</label>
          <button class="danger" onclick="panicBlackout()">Panic Blackout</button>
        </div>
        <div class="row" style="margin-top:10px;">
          <label>Show Profile</label>
          <select id="profilePreset"></select>
        </div>
        <div class="row">
          <label>Laser Shape</label>
          <select id="laserShape"></select>
        </div>
      </div>

      <div class="card">
        <h2>Effect Families</h2>
        <div id="effectToggles"></div>
      </div>

      <div class="card">
        <h2>Devices</h2>
        <div id="deviceToggles"></div>
      </div>

      <div class="card">
        <h2>Intensity Caps</h2>
        <div id="caps"></div>
      </div>
    </div>

    <div class="card">
      <h2>Channel Test</h2>
      <div class="muted" style="margin-bottom:8px;">
        Sends a raw DMX value directly to one channel, bypassing the show
        loop, so you can confirm a fixture's address/wiring independent of
        the audio-reactive effects. Auto-releases after 20s if not cleared.
      </div>
      <div id="channelTestStatus" class="muted" style="margin-bottom:8px;"></div>
      <div id="channelTestRows"></div>
    </div>
  </div>

  <script>
    const state = { profile: {}, devices: {}, runtime: {}, channel_test: null };
    let deviceChannels = {};

    async function loadSelectOptions() {
      try {
        const [presets, shapes] = await Promise.all([
          call("GET", "/api/profile-presets"),
          call("GET", "/api/laser-shapes"),
        ]);
        const presetSelect = document.getElementById("profilePreset");
        presetSelect.innerHTML = presets.map((p) => `<option value="${p}">${p}</option>`).join("");
        const shapeSelect = document.getElementById("laserShape");
        shapeSelect.innerHTML = shapes.map((s) => `<option value="${s}">${s}</option>`).join("");
      } catch (err) {
        // Selects just stay empty; the rest of the page still works.
      }
    }

    const effectKeys = [
      "enable_beat", "enable_frequency", "enable_combo",
      "enable_mega_combo", "enable_strobe_only", "enable_ambient", "enable_subtle"
    ];
    const deviceOrder = [
      "use_laser",
      "use_strobe",
      "use_spotlight",
      "use_stinger",
      "use_vu_meter",
      "use_eurolite_strobe",
      "use_smoke_machine"
    ];
    const capsByDevice = {
      use_laser: "max_laser_level",
      use_strobe: "max_strobe_level",
      use_spotlight: "max_dimmer_level",
      use_stinger: "max_uv_level",
      use_vu_meter: "max_vu_level",
      use_eurolite_strobe: "max_eurolite_level",
      use_smoke_machine: ["max_smoke_level", "max_smoke_led_level"]
    };

    function setStatus(msg, ok = true) {
      const el = document.getElementById("status");
      el.textContent = msg;
      el.style.color = ok ? "#4fd1a8" : "#ffb347";
    }

    function keyLabel(k) {
      return k.replace(/^(enable_|max_|use_)/, "").replaceAll("_", " ");
    }

    async function call(method, url, body) {
      const r = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    }

    function render() {
      document.getElementById("profileName").textContent = state.profile.name || "profile";
      document.getElementById("masterIntensity").value = state.runtime.master_intensity ?? 1;
      document.getElementById("masterLabel").textContent = (state.runtime.master_intensity ?? 1).toFixed(2);
      document.getElementById("blackout").checked = !!state.runtime.blackout;
      if (state.profile.name) document.getElementById("profilePreset").value = state.profile.name;
      if (state.runtime.laser_shape) document.getElementById("laserShape").value = state.runtime.laser_shape;

      const effectDiv = document.getElementById("effectToggles");
      effectDiv.innerHTML = "";
      effectKeys.forEach((k) => {
        const row = document.createElement("div");
        row.className = "row";
        row.innerHTML = `<label>${keyLabel(k)}</label><input type="checkbox" ${state.profile[k] ? "checked" : ""} />`;
        row.querySelector("input").addEventListener("change", async (e) => {
          try {
            Object.assign(state, await call("PUT", "/api/profile", { [k]: e.target.checked }));
            setStatus("updated");
          } catch (err) {
            setStatus("update failed", false);
          }
        });
        effectDiv.appendChild(row);
      });

      const devDiv = document.getElementById("deviceToggles");
      devDiv.innerHTML = "";
      deviceOrder.filter((k) => Object.prototype.hasOwnProperty.call(state.devices, k)).forEach((k) => {
        const row = document.createElement("div");
        row.className = "row";
        row.innerHTML = `<label>${keyLabel(k)}</label><input type="checkbox" ${state.devices[k] ? "checked" : ""} />`;
        row.querySelector("input").addEventListener("change", async (e) => {
          try {
            Object.assign(state, await call("PUT", "/api/devices", { [k]: e.target.checked }));
            setStatus("updated");
          } catch (err) {
            setStatus("update failed", false);
          }
        });
        devDiv.appendChild(row);
      });

      const capsDiv = document.getElementById("caps");
      capsDiv.innerHTML = "";
      deviceOrder.filter((k) => Object.prototype.hasOwnProperty.call(capsByDevice, k)).forEach((deviceKey) => {
        const keys = Array.isArray(capsByDevice[deviceKey]) ? capsByDevice[deviceKey] : [capsByDevice[deviceKey]];
        keys.forEach((k) => {
          const row = document.createElement("div");
          row.className = "row";
          const val = state.profile[k] ?? 255;
          const label = keys.length > 1 ? keyLabel(k) : keyLabel(deviceKey);
          row.innerHTML = `<label>${label}</label><input type="number" min="0" max="255" value="${val}" />`;
          row.querySelector("input").addEventListener("change", async (e) => {
            const n = Math.max(0, Math.min(255, Number(e.target.value || 0)));
            e.target.value = n;
            try {
              Object.assign(state, await call("PUT", "/api/profile", { [k]: n }));
              setStatus("updated");
            } catch (err) {
              setStatus("update failed", false);
            }
          });
          capsDiv.appendChild(row);
        });
      });

      renderChannelTest();
    }

    function renderChannelTest() {
      const statusDiv = document.getElementById("channelTestStatus");
      const test = state.channel_test;
      if (test) {
        const info = deviceChannels[test.device];
        const absCh = info ? info.base + test.channel_offset - 1 : "?";
        statusDiv.textContent =
          `Testing ${keyLabel(test.device)}: offset ${test.channel_offset} ` +
          `(DMX ch ${absCh}) = ${test.value}`;
      } else {
        statusDiv.textContent = "No active test.";
      }

      const rowsDiv = document.getElementById("channelTestRows");
      rowsDiv.innerHTML = "";
      deviceOrder
        .filter((k) => Object.prototype.hasOwnProperty.call(state.devices, k))
        .forEach((deviceKey) => {
          const deviceName = deviceKey.replace(/^use_/, "");
          const info = deviceChannels[deviceName];
          if (!info) return; // e.g. the VU meter isn't a DMX fixture

          const row = document.createElement("div");
          row.className = "row";
          row.innerHTML = `
            <label>${keyLabel(deviceKey)}</label>
            <input type="number" min="1" max="${info.count}" value="1" style="width:60px" />
            <span class="chip"></span>
            <button>Test</button>
          `;
          const input = row.querySelector("input");
          const chip = row.querySelector(".chip");
          const button = row.querySelector("button");

          const updateChip = () => {
            const offset = Math.max(1, Math.min(info.count, Number(input.value || 1)));
            input.value = offset;
            chip.textContent = `ch ${info.base + offset - 1}`;
          };
          input.addEventListener("input", updateChip);
          updateChip();

          button.addEventListener("click", async () => {
            const offset = Math.max(1, Math.min(info.count, Number(input.value || 1)));
            try {
              Object.assign(
                state,
                await call("POST", "/api/test-channel", {
                  device: deviceName,
                  channel_offset: offset,
                  value: 255,
                })
              );
              render();
              setStatus(`testing ${deviceName} ch ${offset}`);
            } catch (err) {
              setStatus("test failed", false);
            }
          });
          rowsDiv.appendChild(row);
        });

      const clearRow = document.createElement("div");
      clearRow.className = "row";
      clearRow.innerHTML = `<span></span><button class="danger">Clear Test</button>`;
      clearRow.querySelector("button").addEventListener("click", async () => {
        try {
          Object.assign(state, await call("POST", "/api/test-channel/clear"));
          render();
          setStatus("test cleared");
        } catch (err) {
          setStatus("clear failed", false);
        }
      });
      rowsDiv.appendChild(clearRow);
    }

    async function loadDeviceChannels() {
      try {
        deviceChannels = await call("GET", "/api/device-channels");
      } catch (err) {
        // Channel test UI just won't populate rows; the rest of the page still works.
      }
    }

    function meterRow(label, value, reference) {
      const pct = Math.max(0, Math.min(100, (value / reference) * 100));
      return `
        <div class="row"><label>${label}</label><span>${value.toFixed(1)}</span></div>
        <div class="meter"><div class="meter-fill" style="width:${pct}%"></div></div>
      `;
    }

    function renderTelemetry(t) {
      const body = document.getElementById("telemetryBody");
      if (!t || !t.updated_at) {
        body.innerHTML = `<div class="muted">waiting for telemetry...</div>`;
        return;
      }

      const age = Date.now() / 1000 - t.updated_at;
      const stale = age > 3;

      const flags = [];
      if (t.beat_detected) flags.push("beat");
      if (t.on_bar) flags.push("bar");
      if (t.on_phrase) flags.push("phrase");
      if (t.building_energy) flags.push("building");
      if (t.energy_drop) flags.push("drop");

      const reference = Math.max(1, t.combo_threshold * 1.3, t.rms, t.peak);

      body.innerHTML = `
        ${stale ? `<div class="telemetry-stale">stale - no update in ${age.toFixed(0)}s (is the show loop running?)</div>` : ""}
        <div class="row"><label>Effect</label><span class="chip">${t.last_effect_type || "-"}</span></div>
        ${meterRow("RMS", t.rms, reference)}
        ${meterRow("Peak", t.peak, reference)}
        <div class="row"><label>Thresholds</label>
          <span class="muted">min ${t.min_threshold.toFixed(0)} / strobe ${t.strobe_threshold.toFixed(0)} / combo ${t.combo_threshold.toFixed(0)}</span>
        </div>
        <div class="row"><label>Pattern</label>
          <span class="muted">${flags.length ? flags.join(", ") : "-"}</span>
        </div>
        <div class="row"><label>Smoke machine</label>
          <span class="muted">${t.smoke_burst_active ? "bursting now" : `cooldown ${t.smoke_cooldown_remaining.toFixed(0)}s`}</span>
          <button id="fireSmokeBtn" ${t.smoke_burst_active ? "disabled" : ""}>Fire Smoke Now</button>
        </div>
      `;

      const fireBtn = document.getElementById("fireSmokeBtn");
      if (fireBtn) {
        fireBtn.addEventListener("click", async () => {
          try {
            await call("POST", "/api/trigger-smoke-burst");
            setStatus("smoke burst triggered");
          } catch (err) {
            setStatus("trigger failed", false);
          }
        });
      }
    }

    async function loadTelemetry() {
      try {
        const t = await call("GET", "/api/telemetry");
        renderTelemetry(t);
      } catch (err) {
        // Leave the last-known telemetry on screen rather than clearing it.
      }
    }

    async function loadState() {
      try {
        const fresh = await call("GET", "/api/state");
        Object.assign(state, fresh);
        render();
        setStatus("connected");
      } catch (err) {
        setStatus("controller not reachable", false);
      }
    }

    async function panicBlackout() {
      try {
        Object.assign(state, await call("PUT", "/api/runtime", { blackout: true }));
        render();
        setStatus("blackout active", false);
      } catch (err) {
        setStatus("panic failed", false);
      }
    }

    document.getElementById("masterIntensity").addEventListener("input", (e) => {
      document.getElementById("masterLabel").textContent = Number(e.target.value).toFixed(2);
    });
    document.getElementById("masterIntensity").addEventListener("change", async (e) => {
      try {
        Object.assign(state, await call("PUT", "/api/runtime", { master_intensity: Number(e.target.value) }));
        setStatus("updated");
      } catch (err) {
        setStatus("update failed", false);
      }
    });
    document.getElementById("blackout").addEventListener("change", async (e) => {
      try {
        Object.assign(state, await call("PUT", "/api/runtime", { blackout: e.target.checked }));
        setStatus(e.target.checked ? "blackout active" : "blackout cleared", !e.target.checked);
      } catch (err) {
        setStatus("update failed", false);
      }
    });
    document.getElementById("profilePreset").addEventListener("change", async (e) => {
      try {
        Object.assign(state, await call("POST", "/api/apply-preset", { name: e.target.value }));
        render();
        setStatus(`profile: ${e.target.value}`);
      } catch (err) {
        setStatus("preset failed", false);
      }
    });
    document.getElementById("laserShape").addEventListener("change", async (e) => {
      try {
        Object.assign(state, await call("PUT", "/api/runtime", { laser_shape: e.target.value }));
        render();
        setStatus(`laser shape: ${e.target.value}`);
      } catch (err) {
        setStatus("laser shape failed", false);
      }
    });

    loadSelectOptions().then(() => loadDeviceChannels().then(loadState));
    setInterval(loadState, 2000);
    loadTelemetry();
    setInterval(loadTelemetry, 500);
  </script>
</body>
</html>
"""
