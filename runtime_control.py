from __future__ import annotations

import json
import os
from dataclasses import asdict, replace
from pathlib import Path
from threading import Lock
from typing import Any, Dict

from config import DeviceConfig, ShowProfile


class RuntimeControl:
    """Thread-safe runtime state shared by the show loop and web API.

    State changes made via the web UI are persisted to a JSON file so they
    survive restarts.
    """

    def __init__(self, device_config: DeviceConfig, show_profile: ShowProfile) -> None:
        self._lock = Lock()
        self._state_file = Path(
            os.getenv("JINGLE_STATE_FILE", "runtime_state.json")
        )
        self._device_flags = {
            "use_laser": device_config.use_laser,
            "use_strobe": device_config.use_strobe,
            "use_spotlight": device_config.use_spotlight,
            "use_stinger": device_config.use_stinger,
            "use_vu_meter": device_config.use_vu_meter,
            "use_eurolite_strobe": device_config.use_eurolite_strobe,
            "use_smoke_machine": device_config.use_smoke_machine,
        }
        self._profile = replace(show_profile)
        self._master_intensity = 1.0
        self._blackout = False
        self._load_state()

    def _load_state(self) -> None:
        """Restore persisted device flags, profile caps and runtime settings."""
        if not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            for key, value in data.get("devices", {}).items():
                if key in self._device_flags:
                    self._device_flags[key] = bool(value)
            for key, value in data.get("profile", {}).items():
                if hasattr(self._profile, key):
                    setattr(self._profile, key, value)
            runtime = data.get("runtime", {})
            self._master_intensity = max(
                0.0, min(1.0, float(runtime.get("master_intensity", 1.0)))
            )
            self._blackout = bool(runtime.get("blackout", False))
        except Exception:
            # If the file is corrupt, ignore it and start fresh.
            pass

    def _save_state(self) -> None:
        """Persist current state to disk."""
        try:
            self._state_file.write_text(
                json.dumps(self.state(), indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    @staticmethod
    def _clamp_level(value: int) -> int:
        return max(0, min(255, int(value)))

    @staticmethod
    def _clamp_scale(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def update_profile(self, updates: Dict[str, Any]) -> None:
        with self._lock:
            for key, value in updates.items():
                if not hasattr(self._profile, key):
                    continue
                if key.startswith("max_"):
                    setattr(self._profile, key, self._clamp_level(value))
                else:
                    setattr(self._profile, key, value)
        self._save_state()

    def update_devices(self, updates: Dict[str, bool]) -> None:
        with self._lock:
            for key, value in updates.items():
                if key in self._device_flags:
                    self._device_flags[key] = bool(value)
        self._save_state()

    def update_runtime(self, *, master_intensity: float | None, blackout: bool | None) -> None:
        with self._lock:
            if master_intensity is not None:
                self._master_intensity = self._clamp_scale(master_intensity)
            if blackout is not None:
                self._blackout = bool(blackout)
        self._save_state()

    def is_blackout(self) -> bool:
        with self._lock:
            return self._blackout

    def device_flags(self) -> Dict[str, bool]:
        with self._lock:
            return dict(self._device_flags)

    def effective_profile(self) -> ShowProfile:
        with self._lock:
            profile = replace(self._profile)
            scale = self._master_intensity

        profile.max_strobe_level = self._clamp_level(profile.max_strobe_level * scale)
        profile.max_dimmer_level = self._clamp_level(profile.max_dimmer_level * scale)
        profile.max_uv_level = self._clamp_level(profile.max_uv_level * scale)
        profile.max_laser_level = self._clamp_level(profile.max_laser_level * scale)
        profile.max_vu_level = self._clamp_level(profile.max_vu_level * scale)
        profile.max_eurolite_level = self._clamp_level(
            profile.max_eurolite_level * scale
        )
        profile.max_smoke_level = self._clamp_level(profile.max_smoke_level * scale)
        profile.max_smoke_led_level = self._clamp_level(
            profile.max_smoke_led_level * scale
        )
        return profile

    def state(self) -> Dict[str, Any]:
        with self._lock:
            profile = asdict(self._profile)
            devices = dict(self._device_flags)
            runtime = {
                "master_intensity": self._master_intensity,
                "blackout": self._blackout,
            }

        return {
            "profile": profile,
            "devices": devices,
            "runtime": runtime,
        }
