from __future__ import annotations

import ipaddress
import os
from typing import Optional

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from runtime_control import RuntimeControl


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


class DeviceUpdate(BaseModel):
    use_laser: Optional[bool] = None
    use_strobe: Optional[bool] = None
    use_spotlight: Optional[bool] = None
    use_stinger: Optional[bool] = None
    use_vu_meter: Optional[bool] = None
    use_eurolite_strobe: Optional[bool] = None


class RuntimeUpdate(BaseModel):
    master_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    blackout: Optional[bool] = None


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
    def put_runtime(update: RuntimeUpdate) -> dict:
        runtime_control.update_runtime(
            master_intensity=update.master_intensity,
            blackout=update.blackout,
        )
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

    <div class="grid">
      <div class="card">
        <h2>Runtime</h2>
        <div class="row"><label>Master Intensity</label><span id="masterLabel">1.00</span></div>
        <input id="masterIntensity" type="range" min="0" max="1" step="0.01" value="1" />
        <div class="row" style="margin-top:10px;">
          <label><input id="blackout" type="checkbox" /> Blackout</label>
          <button class="danger" onclick="panicBlackout()">Panic Blackout</button>
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
  </div>

  <script>
    const state = { profile: {}, devices: {}, runtime: {} };

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
      "use_eurolite_strobe"
    ];
    const capsByDevice = {
      use_laser: "max_laser_level",
      use_strobe: "max_strobe_level",
      use_spotlight: "max_dimmer_level",
      use_stinger: "max_uv_level",
      use_vu_meter: "max_vu_level",
      use_eurolite_strobe: "max_eurolite_level"
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
        const k = capsByDevice[deviceKey];
        const row = document.createElement("div");
        row.className = "row";
        const val = state.profile[k] ?? 255;
        row.innerHTML = `<label>${keyLabel(deviceKey)}</label><input type="number" min="0" max="255" value="${val}" />`;
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

    loadState();
    setInterval(loadState, 2000);
  </script>
</body>
</html>
"""
