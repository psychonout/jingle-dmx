from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, replace
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from config import DeviceConfig, ShowProfile

# How long a manual channel test holds before releasing control back to the
# show automatically, so a forgotten test tab can't silently freeze a
# fixture mid-show.
CHANNEL_TEST_HOLD_SECONDS: float = 20.0


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
        # Manual channel test override - deliberately NOT persisted to disk,
        # since a stale test from a previous session should never silently
        # re-apply itself on the next restart.
        self._channel_test: Optional[Dict[str, Any]] = None
        # Live show telemetry, pushed by the show loop every frame - purely
        # a readout for the web UI, never persisted or read back on load.
        self._telemetry: Optional[Dict[str, Any]] = None
        # One-shot flag: the show loop consumes and clears this on its next
        # frame, so a request never fires twice.
        self._smoke_trigger_requested = False
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

    def set_channel_test(self, device: str, channel_offset: int, value: int) -> None:
        """Start (or replace) a manual raw-channel test override.

        The show loop re-asserts this value on the given device/channel
        every frame, after its normal effect output, until it's cleared or
        expires - see CHANNEL_TEST_HOLD_SECONDS.
        """
        with self._lock:
            self._channel_test = {
                "device": device,
                "channel_offset": int(channel_offset),
                "value": self._clamp_level(value),
                "expires_at": time.time() + CHANNEL_TEST_HOLD_SECONDS,
            }

    def clear_channel_test(self) -> None:
        with self._lock:
            self._channel_test = None

    def _channel_test_locked(self) -> Optional[Dict[str, Any]]:
        """Read the active test, clearing it first if expired. Caller must hold self._lock."""
        if self._channel_test and time.time() >= self._channel_test["expires_at"]:
            self._channel_test = None
        return dict(self._channel_test) if self._channel_test else None

    def get_channel_test(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._channel_test_locked()

    def update_telemetry(self, **fields: Any) -> None:
        with self._lock:
            self._telemetry = {**fields, "updated_at": time.time()}

    def get_telemetry(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._telemetry) if self._telemetry else None

    def trigger_smoke_burst(self) -> None:
        with self._lock:
            self._smoke_trigger_requested = True

    def consume_smoke_trigger(self) -> bool:
        """Return True at most once per request - clears the flag on read."""
        with self._lock:
            requested = self._smoke_trigger_requested
            self._smoke_trigger_requested = False
            return requested

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
            channel_test = self._channel_test_locked()

        return {
            "profile": profile,
            "devices": devices,
            "runtime": runtime,
            "channel_test": channel_test,
        }
