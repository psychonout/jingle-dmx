import os
import time
from typing import Dict, Optional

import random

from loguru import logger

from audio_model import AudioFrame
from config import DeviceConfig, ShowProfile, load_default_profile
from effect_engine import Devices, EffectEngine, Thresholds
from dynamic_thresholds import AdaptiveThresholds
from laser import Laser
from light_strip import VUMeter
from spotlight import Spotlight
from stinger import StingerII
from strobe import Strobe
from usb_mic import USBMicrophone
from eurolite_strobe import EuroliteStrobe


class LightShowController:
    def __init__(
        self,
        device_config: Optional[DeviceConfig] = None,
        show_profile: Optional[ShowProfile] = None,
    ) -> None:
        self.config = device_config or DeviceConfig()

        # Show profile controls which effect families are active and how
        # randomness behaves. If not provided explicitly, we pick one
        # based on the SHOW_PROFILE environment variable.
        self.profile: ShowProfile = show_profile or load_default_profile()

        self.threshold_system = AdaptiveThresholds(
            smoothing_factor=0.95,
            sensitivity=2,
            min_change_threshold=5.0,  # Increased from 2.0 to better ignore noise floor
            threshold_update_interval=0.5,
        )

        self.max_vol = 0.0
        self.last_effect_time = 0.0
        # How long we sleep per loop iteration (seconds). Lower values mean
        # more frequent updates and lower end-to-end latency but higher CPU.
        # Default effect loop interval (seconds). Can be overridden with
        # environment variable EFFECT_INTERVAL to quickly test responsiveness.
        self.effect_interval = float(os.getenv("EFFECT_INTERVAL", "0.01"))
        self.last_rms = 0.0
        self.last_effect_type: Optional[str] = None
        # Treat lower RMS as meaningful so VU meter shows more detail.
        # Can be overridden for calibration.
        # Increased default from 5.0 to 15.0 to account for typical microphone noise floor
        self.silence_threshold = float(os.getenv("SILENCE_THRESHOLD", "25.0"))
        # Once we consider the input silent, keep it silent for a short time.
        # This prevents rapid retriggers from near-silence noise.
        self.silence_hold_seconds = float(os.getenv("SILENCE_HOLD_SECONDS", "0.5"))
        self._silence_until = 0.0

        self.devices: Dict[str, object] = {}

        # Centralized effect engine.
        self.effect_engine = EffectEngine(self.profile)

    # --- device lifecycle -------------------------------------------------

    def _open_devices(self) -> None:
        if self.config.use_laser:
            laser = Laser(dmx_channel=1)
            laser.__enter__()
            self.devices["laser"] = laser

        if self.config.use_strobe:
            strobe = Strobe(dmx_channel=11)
            strobe.__enter__()
            self.devices["strobe"] = strobe

        if self.config.use_spotlight:
            spotlight = Spotlight(dmx_channel=22)
            spotlight.__enter__()
            self.devices["spotlight"] = spotlight

        if self.config.use_stinger:
            stinger = StingerII(dmx_channel=33)
            stinger.__enter__()
            self.devices["stinger"] = stinger

        if self.config.use_eurolite_strobe:
            eurolite_strobe = EuroliteStrobe(dmx_channel=44)
            eurolite_strobe.__enter__()
            self.devices["eurolite_strobe"] = eurolite_strobe

        if self.config.use_vu_meter:
            # Allow configuration of the VU color palette via environment variables
            # Make the VU meter more purple by default with higher saturation
            color_start_hue = float(os.getenv("VU_COLOR_START_HUE", "0.78"))
            color_end_hue = float(os.getenv("VU_COLOR_END_HUE", "0.78"))
            # Default to saturated purples to avoid a washed out appearance
            min_saturation = float(os.getenv("VU_MIN_SATURATION", "0.9"))
            max_saturation = float(os.getenv("VU_MAX_SATURATION", "1.0"))
            # Keep brightness moderate so purple hue remains visible
            min_brightness = float(os.getenv("VU_MIN_BRIGHTNESS", "0.15"))
            max_brightness = float(os.getenv("VU_MAX_BRIGHTNESS", "0.35"))

            vu_meter = VUMeter(
                brightness=0.3,
                decay_rate=0.9,
                auto_scale=True,
                min_bars=0,
                reverse=False,
                color_start_hue=color_start_hue,
                color_end_hue=color_end_hue,
                min_saturation=min_saturation,
                max_saturation=max_saturation,
                min_brightness=min_brightness,
                max_brightness=max_brightness,
            )
            vu_meter.__enter__()
            self.devices["vu_meter"] = vu_meter

    def _close_devices(self) -> None:
        for name, device in self.devices.items():
            try:
                device.__exit__(None, None, None)
                logger.debug(f"Closed {name}")
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Error closing {name}: {exc}")

    # --- main loop --------------------------------------------------------

    def run(self) -> None:
        logger.debug("Starting optimized audio-reactive light show...")
        # Allow tuning of microphone/reader parameters via environment
        # variables to avoid editing code for quick experimentation.
        frames_per_buffer = int(os.getenv("MIC_FRAMES_PER_BUFFER", "64"))
        smoothing_factor = float(os.getenv("MIC_SMOOTHING_FACTOR", "0.3"))
        enable_reader_thread = os.getenv("ENABLE_READER_THREAD", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        reader_beat_detection = os.getenv("READER_BEAT_DETECTION", "true").lower() in (
            "1",
            "true",
            "yes",
        )

        with USBMicrophone(
            enable_frequency_analysis=True,
            enable_beat_detection=True,
            enable_reader_thread=enable_reader_thread,
            reader_beat_detection=reader_beat_detection,
            frames_per_buffer=frames_per_buffer,
            smoothing_factor=smoothing_factor,
            reader_threshold_ratio=1.3,
        ) as usb_mic:
            if not usb_mic.is_open:
                logger.error("Failed to open enhanced USB microphone")
                return

            self._open_devices()
            try:
                self._run_loop(usb_mic)
            finally:
                self._close_devices()

    # --- loop helpers -----------------------------------------------------

    def _run_loop(self, usb_mic: USBMicrophone) -> None:
        laser: Optional[Laser] = self.devices.get("laser")  # type: ignore[assignment]
        strobe: Optional[Strobe] = self.devices.get("strobe")  # type: ignore[assignment]
        spotlight: Optional[Spotlight] = self.devices.get("spotlight")  # type: ignore[assignment]
        stinger: Optional[StingerII] = self.devices.get("stinger")  # type: ignore[assignment]
        vu_meter: Optional[VUMeter] = self.devices.get("vu_meter")  # type: ignore[assignment]
        eurolite_strobe: Optional[EuroliteStrobe] = self.devices.get("eurolite_strobe")  # type: ignore[assignment]

        if strobe:
            strobe.set_dimmer(0)
            strobe.set_strobe(0)  # Explicitly disable strobe effect
            strobe.set_warm_white(0)
            strobe.set_cold_white(0)
            strobe.set_color(0)
            strobe.set_macro(0)
            strobe.set_macro_speed(0)

        if spotlight:
            spotlight.set_brightness(0)
            spotlight.set_strobe(0)

        if laser:
            laser.set_mode("manual")
            laser.set_mode_level(0)
            laser.color(0)
            laser.pattern(0)

        if stinger:
            # Base look: manual control, laser off, moonflower only
            stinger.reset()
            stinger.set_show_mode(0)  # Manual control - no automatic laser
            stinger.set_show_speed(120, sound_active=False)
            stinger.set_color_macro("fade1")
            stinger.set_led_strobe(0)
            stinger.set_uv(180)
            stinger.set_uv_chase(60, strobing=False)
            stinger.set_laser_output(strobe_speed=0, rotation_raw=0)  # Laser fully off
            stinger.set_moonflower_rotation(direction="cw", speed=30)

        logger.debug("Starting enhanced audio-reactive show...")
        logger.debug(f"Active devices: {', '.join(self.devices.keys())}")

        while True:
            current_time = time.time()
            min_thresh, strobe_thresh, combo_thresh = self.threshold_system.get_thresholds()
            audio_data = usb_mic.read()

            rms = audio_data["rms"]
            peak = audio_data["peak"]
            beat_detected = audio_data["beat_detected"]

            if rms < self.silence_threshold:
                self._silence_until = max(self._silence_until, current_time + self.silence_hold_seconds)

            if current_time < self._silence_until:
                rms = 0
                peak = 0
                beat_detected = False

            if rms > 0:
                bass_energy = usb_mic.get_bass_energy()
                mid_energy = usb_mic.get_mid_energy()
                high_energy = usb_mic.get_high_energy()
                total_energy = bass_energy + mid_energy + high_energy
            else:
                bass_energy = mid_energy = high_energy = total_energy = 0

            # Use the microphone read timestamp if available to measure true
            # end-to-end latency. Fall back to current loop time otherwise.
            frame_timestamp = audio_data.get("timestamp", current_time) if isinstance(audio_data, dict) else current_time
            frame = AudioFrame(
                timestamp=frame_timestamp,
                rms=rms,
                peak=peak,
                beat_detected=beat_detected,
                bass_energy=bass_energy,
                mid_energy=mid_energy,
                high_energy=high_energy,
                total_energy=total_energy,
            )

            if int(current_time * 10) % 3 == 0:
                self.threshold_system.update(frame.rms)

            min_threshold, strobe_threshold, combo_threshold = (
                self.threshold_system.get_thresholds()
            )

            if vu_meter:
                vu_meter.update(frame.rms)

            self.last_rms = frame.rms

            if frame.rms > self.max_vol:
                self.max_vol = frame.rms
                logger.debug(f"New max RMS: {self.max_vol:.1f}")

            devices = Devices(
                laser=laser,
                strobe=strobe,
                spotlight=spotlight,
                stinger=stinger,
                vu_meter=vu_meter,
                eurolite_strobe=eurolite_strobe,
            )
            thresholds = Thresholds(
                min_threshold=min_threshold,
                strobe_threshold=strobe_threshold,
                combo_threshold=combo_threshold,
            )

            # Route all effect decisions through the shared engine.
            self.last_effect_type = self.effect_engine.apply_effects(
                frame=frame,
                thresholds=thresholds,
                devices=devices,
            )

            # Log a human-readable snapshot roughly once per second.
            if int(current_time) != int(self.last_effect_time):
                msg = (
                    f"Audio Analysis - RMS: {frame.rms:.1f}, Peak: {frame.peak:.1f} | "
                    f"Thresholds - Min: {min_threshold:.1f}, Strobe: {strobe_threshold:.1f}, "
                    f"Combo: {combo_threshold:.1f}"
                )
                logger.debug(msg)

            time.sleep(self.effect_interval)
            self.last_effect_time = current_time
