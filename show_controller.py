import math
import os
import time
from typing import Dict, Optional

from loguru import logger

from audio_model import AudioFrame
from config import DeviceConfig, ShowProfile, load_default_profile
from dynamic_thresholds import AdaptiveThresholds
from effect_engine import Devices, EffectEngine, Thresholds
from eurolite_strobe import EuroliteStrobe
from laser import (
    MONO_BLUE_MAX,
    MONO_GREEN_MAX,
    MONO_RED_MAX,
    Laser,
)
from light_strip import VUMeter
from runtime_control import RuntimeControl
from smoke_bubble_machine import SmokeBubbleMachine
from spotlight import Spotlight
from stinger import StingerII
from strobe import Strobe
from usb_mic import MusicPatternDetector, USBMicrophone


class LightShowController:
    # Normalized closed polyline used for star tracing mode.
    _STAR_POINTS = [
        (0.00, 1.00),
        (0.22, 0.30),
        (0.95, 0.30),
        (0.36, -0.12),
        (0.58, -0.90),
        (0.00, -0.40),
        (-0.58, -0.90),
        (-0.36, -0.12),
        (-0.95, 0.30),
        (-0.22, 0.30),
        (0.00, 1.00),
    ]

    def __init__(
        self,
        device_config: Optional[DeviceConfig] = None,
        show_profile: Optional[ShowProfile] = None,
        runtime_control: Optional[RuntimeControl] = None,
    ) -> None:
        self.config = device_config or DeviceConfig()

        # Show profile controls which effect families are active and how
        # randomness behaves. If not provided explicitly, we pick one
        # based on the SHOW_PROFILE environment variable.
        self.profile: ShowProfile = show_profile or load_default_profile()
        self.runtime_control = runtime_control or RuntimeControl(
            self.config, self.profile
        )

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
        # Keep a small amount of laser motion memory so position changes
        # remain smooth but can still jump on strong musical events.
        self._laser_h_pos = 63.0
        self._laser_v_pos = 63.0
        self._laser_kick_h = 0.0
        self._laser_kick_v = 0.0
        self._laser_shape_phase = 0.0
        self._laser_last_update_time = 0.0
        self._laser_last_beat = False
        self.laser_novelty_shape = os.getenv(
            "LASER_NOVELTY_SHAPE", "false"
        ).lower() in ("1", "true", "yes")
        # LASER_SHAPE selects the live-show laser mode.
        # "circle"  → circle preset locked, max angle speeds, position from music (default)
        # "novelty" → trace a star outline (same as LASER_NOVELTY_SHAPE=true)
        # "random"  → original audio-reactive pattern churn
        self.laser_shape = os.getenv("LASER_SHAPE", "circle")
        # Fixture calibration for circle mode. Many units are mechanically
        # biased upward when v_angle is near 0, so expose a downward bias.
        self.laser_circle_v_angle = int(os.getenv("LASER_CIRCLE_V_ANGLE", "64"))
        self.laser_circle_v_center = float(os.getenv("LASER_CIRCLE_V_CENTER", "82"))

        self.devices: Dict[str, object] = {}

        # Centralized effect engine.
        self.effect_engine = EffectEngine(self.profile)
        self.pattern_detector = MusicPatternDetector(
            effect_variations=self.effect_engine.get_effect_variation_count()
        )

    def _blackout_all_devices(
        self,
        laser: Optional[Laser],
        strobe: Optional[Strobe],
        spotlight: Optional[Spotlight],
        stinger: Optional[StingerII],
        vu_meter: Optional[VUMeter],
        eurolite_strobe: Optional[EuroliteStrobe],
        smoke_machine: Optional[SmokeBubbleMachine],
    ) -> None:
        if strobe:
            strobe.set_dimmer(0)
            strobe.set_strobe(0)
            strobe.set_warm_white(0)
            strobe.set_cold_white(0)
            strobe.set_color(0)
            strobe.set_macro(0)
            strobe.set_macro_speed(0)
        if spotlight:
            spotlight.turn_off()
        if laser:
            laser.set_mode("off")
            laser.set_mode_level(0)
        if stinger:
            stinger.blackout()
        if vu_meter:
            vu_meter.reset()
        if eurolite_strobe:
            eurolite_strobe.close_gates()
        if smoke_machine:
            smoke_machine.turn_off()

    def _enforce_device_disables(
        self,
        flags: Dict[str, bool],
        laser: Optional[Laser],
        strobe: Optional[Strobe],
        spotlight: Optional[Spotlight],
        stinger: Optional[StingerII],
        vu_meter: Optional[VUMeter],
        eurolite_strobe: Optional[EuroliteStrobe],
        smoke_machine: Optional[SmokeBubbleMachine],
    ) -> None:
        if not flags.get("use_strobe", True) and strobe:
            strobe.set_dimmer(0)
            strobe.set_strobe(0)
            strobe.set_warm_white(0)
            strobe.set_cold_white(0)
        if not flags.get("use_spotlight", True) and spotlight:
            spotlight.turn_off()
        if not flags.get("use_laser", True) and laser:
            laser.set_mode("off")
            laser.set_mode_level(0)
        if not flags.get("use_stinger", True) and stinger:
            stinger.blackout()
        if not flags.get("use_vu_meter", True) and vu_meter:
            vu_meter.reset()
        if not flags.get("use_eurolite_strobe", True) and eurolite_strobe:
            eurolite_strobe.close_gates()
        if not flags.get("use_smoke_machine", True) and smoke_machine:
            smoke_machine.turn_off()

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

        if self.config.use_smoke_machine:
            smoke_machine = SmokeBubbleMachine(dmx_channel=55)
            smoke_machine.__enter__()
            self.devices["smoke_machine"] = smoke_machine
            logger.info(
                f"Smoke/bubble machine active on DMX channel {smoke_machine.dmx_channel}"
            )

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

    def _update_laser(
        self, laser: Laser, frame: AudioFrame, current_time: float
    ) -> None:
        """Map audio features to laser parameters for dynamic visualization.

        Creates a responsive laser show that:
        - Reacts strongly to beats and energy drops
        - Morphs patterns based on audio energy
        - Maintains minimal activity during silence to keep hardware healthy
        """
        if not laser:
            return

        # --- Determine intensity state from audio features ---

        is_silent = frame.rms <= 0
        is_loud = (
            frame.rms > self.threshold_system.get_thresholds()[2]
        )  # combo threshold
        is_building = frame.building_energy
        is_drop = frame.energy_drop
        is_beat = frame.beat_detected
        is_phrase = frame.on_phrase

        # Silence gate: keep laser fully off until sound returns.
        if is_silent:
            laser.set_mode("off")
            laser.set_mode_level(0)
            return

        # --- Base pattern and color selection ---

        # Pattern: tie to beat position for rhythmic coherence, with energy influence.
        if self.laser_novelty_shape:
            base_pattern = 8
            pattern_speed = 192
        elif is_drop:
            # High energy drop: rapid chaotic patterns (128-255 = dots/strips for drama)
            base_pattern = 160 + (frame.beat_index % 4) * 20
            pattern_speed = 255
        elif is_loud:
            # Loud section: energetic patterns (dots/lines 0-127 with variety)
            base_pattern = (frame.beat_index * 16) % 128
            pattern_speed = 240
        elif is_building:
            # Building energy: gradually shift from simple to complex
            base_pattern = 40 + int(frame.bass_energy * 2) % 60
            pattern_speed = 225
        elif is_beat:
            # Regular beat: moderate pattern with beat-synced variety
            base_pattern = (frame.beat_index * 32) % 96
            pattern_speed = 230
        else:
            # Idle/quiet: gentle morphing pattern to keep hardware healthy
            # Cycle slowly through low-number patterns (simpler = less jarring)
            base_pattern = int(current_time * 2) % 32
            pattern_speed = 215

        # Color: map energy to colour — uses RGB segments (R 0-20, G 21-41, B 42-63)
        # and colour-mixing (64-127) / auto-cycle (128-192) ranges.
        # Colour only takes effect in auto/sound modes.
        if self.laser_novelty_shape:
            color_val = 12
        elif is_drop:
            # Drops: cycle through RGB segments for maximum colour variety
            beat_colors = [20, 41, 63, 10, 35, 55]
            color_val = beat_colors[frame.beat_index % len(beat_colors)]
        elif is_loud:
            # Loud sections: colour mixing range for blended colours
            color_val = 64 + (frame.beat_index * 8) % 64
        elif is_beat:
            # Beats: rotate through R, G, B segments with beat sync
            segment = frame.beat_index % 3
            if segment == 0:
                color_val = 10 + (frame.beat_index % 11)  # Red segment
            elif segment == 1:
                color_val = 21 + (frame.beat_index % 21)  # Green segment
            else:
                color_val = 42 + (frame.beat_index % 22)  # Blue segment
        elif is_building:
            # Building: transition from cool (blue) to warm (red)
            progress = min(1.0, frame.rms / max(1.0, self.silence_threshold * 3.0))
            if progress < 0.5:
                # Blue (42-63) → Green (21-41)
                color_val = MONO_BLUE_MAX - int(
                    progress * 2 * (MONO_BLUE_MAX - MONO_GREEN_MAX)
                )
            else:
                # Green (21-41) → Red (10-20) — use bright red only
                color_val = MONO_GREEN_MAX - int(
                    (progress - 0.5) * 2 * (MONO_GREEN_MAX - MONO_RED_MAX)
                )
                color_val = max(10, min(MONO_RED_MAX, color_val))
        else:
            # Idle: slow drift through all three RGB segments
            cycle = int(current_time * 2) % 64
            color_val = cycle

        # --- Mode level (intensity) ---
        # In auto mode, mode_level selects one of 4 auto programs:
        #   0, 64, 128, 192. We use 128 (auto program 1) as the base
        # and nudge it on beats for variety.

        if is_drop:
            # Full intensity on energy drops — sound mode for max reactivity
            mode_level = 192
        elif is_loud:
            # High intensity for loud sections
            mode_level = 192
        elif is_building:
            # Growing intensity — auto program 1
            mode_level = 128
        elif is_beat:
            # Pulse on beat — alternate between auto programs
            mode_level = 128 if frame.beat_index % 2 == 0 else 192
        elif is_silent:
            # Minimal but non-zero to keep hardware healthy
            mode_level = 128
        else:
            # Low but visible ambient activity
            mode_level = 128

        # --- Apply to laser device ---

        laser.set_mode("auto")

        if self.laser_shape == "circle":
            # Circle orbit mode: preset is locked, audio only drives position.
            # Nudge mode_level by 2 on beats for a subtle brightness pulse.
            circle_level = 8 + (2 if (is_beat or is_drop) else 0)
            laser.set_mode_level(circle_level)
            # Slow colour drift through RGB segments so it doesn't stay one flat hue.
            # Colour only works in auto/sound modes.
            color_cycle = int(current_time * 1.5) % 64
            laser.color(color_cycle)
            # Spin the circle but leave CH4/CH5 at fixed angle (0) so the
            # hardware flip doesn't bias motion toward the upper half.
            laser.rotation_speed(255)
            laser.horizontal_angle(0)
            laser.vertical_angle(self.laser_circle_v_angle)
            laser.size(18)

            # Audio-reactive orbit: slow sin/cos base orbit, beat kicks jump it.
            energy_norm = (
                0.0
                if is_silent
                else min(1.0, frame.rms / max(1.0, self.silence_threshold * 3.0))
            )
            spread = 14 + int(42 * energy_norm)
            if is_drop or is_beat:
                kick_mag = 22 + int(22 * energy_norm)
                kick_phase = current_time * 7.5 + (frame.beat_index * 0.9)
                self._laser_kick_h = math.sin(kick_phase) * kick_mag
                self._laser_kick_v = math.cos(kick_phase * 0.93) * kick_mag
            self._laser_kick_h *= 0.86
            self._laser_kick_v *= 0.86
            desired_h = int(
                63
                + math.sin(current_time * (1.5 + energy_norm * 3.0)) * spread
                + self._laser_kick_h
            )
            desired_v = int(
                self.laser_circle_v_center
                + math.cos(current_time * (1.25 + energy_norm * 2.6)) * spread
                + self._laser_kick_v
            )
            blend = 0.09 if is_silent else (0.6 if (is_drop or is_beat) else 0.34)
            self._laser_last_beat = is_beat

        else:
            # Original modes: pattern/color churn + optional star trace.
            laser.pattern(base_pattern)
            laser.color(color_val)
            laser.set_mode_level(mode_level)

            if self.laser_novelty_shape:
                # Trace the configured outline; audio controls traversal speed and scale.
                dt = (
                    self.effect_interval
                    if self._laser_last_update_time <= 0
                    else max(
                        0.001, min(0.2, current_time - self._laser_last_update_time)
                    )
                )
                self._laser_last_update_time = current_time
                energy_norm = (
                    0.0
                    if is_silent
                    else min(1.0, frame.rms / max(1.0, self.silence_threshold * 3.0))
                )
                trace_rate = 1.5 + (energy_norm * 4.0)
                if (is_beat and not self._laser_last_beat) or is_drop:
                    trace_rate += 3.0
                self._laser_last_beat = is_beat
                self._laser_shape_phase += trace_rate * dt

                point_count = len(self._STAR_POINTS)
                base_index = int(self._laser_shape_phase) % point_count
                next_index = (base_index + 1) % point_count
                frac = self._laser_shape_phase - int(self._laser_shape_phase)

                x0, y0 = self._STAR_POINTS[base_index]
                x1, y1 = self._STAR_POINTS[next_index]
                x = x0 + (x1 - x0) * frac
                y = y0 + (y1 - y0) * frac

                scale = 26 + int(20 * energy_norm)
                desired_h = 63 + int(x * scale)
                desired_v = 63 - int(y * scale)
                blend = 0.28 if is_silent else (0.42 if (is_beat or is_drop) else 0.32)
            else:
                # Symmetric center-orbit with audio-scaled spread.
                energy_norm = (
                    0.0
                    if is_silent
                    else min(1.0, frame.rms / max(1.0, self.silence_threshold * 3.0))
                )
                spread = 14 + int(42 * energy_norm)
                if is_drop or is_beat:
                    kick_mag = 22 + int(22 * energy_norm)
                    kick_phase = current_time * 7.5 + (frame.beat_index * 0.9)
                    self._laser_kick_h = math.sin(kick_phase) * kick_mag
                    self._laser_kick_v = math.cos(kick_phase * 0.93) * kick_mag
                self._laser_kick_h *= 0.86
                self._laser_kick_v *= 0.86
                base_h = 63 + int(
                    math.sin(current_time * (1.5 + energy_norm * 3.0)) * spread
                )
                base_v = 63 + int(
                    math.cos(current_time * (1.25 + energy_norm * 2.6)) * spread
                )
                desired_h = int(base_h + self._laser_kick_h)
                desired_v = int(base_v + self._laser_kick_v)
                blend = 0.09 if is_silent else (0.6 if (is_drop or is_beat) else 0.34)
                self._laser_last_beat = is_beat

            if self.laser_novelty_shape or is_drop or is_loud or is_beat:
                laser.speed(pattern_speed)
            else:
                laser.size(28 if is_silent else 18)

            if self.laser_novelty_shape:
                laser.rotate(0)
            elif is_loud or is_drop:
                rotation = int((current_time * 30) % 128)
                laser.rotate(rotation)

        desired_h = max(0, min(127, desired_h))
        desired_v = max(0, min(127, desired_v))
        self._laser_h_pos += (desired_h - self._laser_h_pos) * blend
        self._laser_v_pos += (desired_v - self._laser_v_pos) * blend
        laser.horizontal_position(int(self._laser_h_pos))
        laser.vertical_position(int(self._laser_v_pos))

    def _run_loop(self, usb_mic: USBMicrophone) -> None:
        laser: Optional[Laser] = self.devices.get("laser")  # type: ignore[assignment]
        strobe: Optional[Strobe] = self.devices.get("strobe")  # type: ignore[assignment]
        spotlight: Optional[Spotlight] = self.devices.get("spotlight")  # type: ignore[assignment]
        stinger: Optional[StingerII] = self.devices.get("stinger")  # type: ignore[assignment]
        vu_meter: Optional[VUMeter] = self.devices.get("vu_meter")  # type: ignore[assignment]
        eurolite_strobe: Optional[EuroliteStrobe] = self.devices.get("eurolite_strobe")  # type: ignore[assignment]
        smoke_machine: Optional[SmokeBubbleMachine] = self.devices.get("smoke_machine")  # type: ignore[assignment]

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

        if smoke_machine:
            # Base look: bubble wheel/LEDs off, fan idle, no smoke, manual
            # control (auto program left at 0 - see fixture docstring).
            smoke_machine.reset()

        if laser:
            laser.set_mode("auto")
            laser.set_mode_level(128)
            laser.color(42)  # Start in blue segment
            laser.pattern(8)

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
            min_thresh, strobe_thresh, combo_thresh = (
                self.threshold_system.get_thresholds()
            )
            audio_data = usb_mic.read()

            rms = audio_data["rms"]
            peak = audio_data["peak"]
            beat_detected = audio_data["beat_detected"]

            if rms < self.silence_threshold:
                self._silence_until = max(
                    self._silence_until, current_time + self.silence_hold_seconds
                )

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
            frame_timestamp = (
                audio_data.get("timestamp", current_time)
                if isinstance(audio_data, dict)
                else current_time
            )

            pattern_state = self.pattern_detector.update(
                rms=rms,
                beat_detected=beat_detected,
                bass_energy=bass_energy,
                mid_energy=mid_energy,
                high_energy=high_energy,
            )

            frame = AudioFrame(
                timestamp=frame_timestamp,
                rms=rms,
                peak=peak,
                beat_detected=beat_detected,
                bass_energy=bass_energy,
                mid_energy=mid_energy,
                high_energy=high_energy,
                total_energy=total_energy,
                on_bar=pattern_state["on_bar"],
                on_phrase=pattern_state["on_phrase"],
                building_energy=pattern_state["building_energy"],
                energy_drop=pattern_state["energy_drop"],
                pattern_detected=pattern_state["pattern_detected"],
                pattern_confidence=pattern_state["pattern_confidence"],
                beat_index=pattern_state["beat_index"],
            )

            if int(current_time * 10) % 3 == 0:
                self.threshold_system.update(frame.rms)

            min_threshold, strobe_threshold, combo_threshold = (
                self.threshold_system.get_thresholds()
            )

            control_profile = self.runtime_control.effective_profile()
            self.effect_engine.profile = control_profile
            device_flags = self.runtime_control.device_flags()

            def _push_telemetry(effect_type: Optional[str]) -> None:
                smoke_status = self.effect_engine.smoke_status()
                self.runtime_control.update_telemetry(
                    rms=frame.rms,
                    peak=frame.peak,
                    beat_detected=frame.beat_detected,
                    on_bar=frame.on_bar,
                    on_phrase=frame.on_phrase,
                    building_energy=frame.building_energy,
                    energy_drop=frame.energy_drop,
                    min_threshold=min_threshold,
                    strobe_threshold=strobe_threshold,
                    combo_threshold=combo_threshold,
                    last_effect_type=effect_type,
                    smoke_burst_active=smoke_status["burst_active"],
                    smoke_cooldown_remaining=round(smoke_status["cooldown_remaining"], 1),
                )

            if self.runtime_control.is_blackout():
                self._blackout_all_devices(
                    laser,
                    strobe,
                    spotlight,
                    stinger,
                    vu_meter,
                    eurolite_strobe,
                    smoke_machine,
                )
                self.last_effect_type = "blackout"
                _push_telemetry("blackout")
                time.sleep(self.effect_interval)
                self.last_effect_time = current_time
                continue

            self._enforce_device_disables(
                device_flags,
                laser,
                strobe,
                spotlight,
                stinger,
                vu_meter,
                eurolite_strobe,
                smoke_machine,
            )

            if vu_meter:
                if device_flags.get("use_vu_meter", True):
                    vu_scale = control_profile.max_vu_level / 255.0
                    vu_meter.update(frame.rms * vu_scale)
                else:
                    vu_meter.reset()

            self.last_rms = frame.rms

            if frame.rms > self.max_vol:
                self.max_vol = frame.rms
                logger.debug(f"New max RMS: {self.max_vol:.1f}")

            # In novelty tracing mode, keep laser control exclusive to _update_laser
            # so effect-engine randomization cannot scramble the traced shape.
            engine_laser = (
                None
                if (
                    self.laser_novelty_shape
                    or frame.rms <= 0
                    or not device_flags.get("use_laser", True)
                )
                else laser
            )
            devices = Devices(
                laser=engine_laser,
                strobe=strobe if device_flags.get("use_strobe", True) else None,
                spotlight=spotlight if device_flags.get("use_spotlight", True) else None,
                stinger=stinger if device_flags.get("use_stinger", True) else None,
                vu_meter=vu_meter if device_flags.get("use_vu_meter", True) else None,
                eurolite_strobe=(
                    eurolite_strobe
                    if device_flags.get("use_eurolite_strobe", True)
                    else None
                ),
                smoke_machine=(
                    smoke_machine
                    if device_flags.get("use_smoke_machine", True)
                    else None
                ),
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
            _push_telemetry(self.last_effect_type)

            # Activate laser based on audio features (fallback since effect engine
            # may not fully drive the laser device).
            if device_flags.get("use_laser", True):
                self._update_laser(laser, frame, current_time)

            # Manual channel test (web UI): re-assert the raw value last, so
            # it overrides whatever the effects above just wrote, for as
            # long as it stays active. Bypasses device_flags deliberately -
            # a test should work even for a fixture that's toggled off.
            active_test = self.runtime_control.get_channel_test()
            if active_test:
                test_device = self.devices.get(active_test["device"])
                if test_device is not None:
                    test_device._send(active_test["channel_offset"] - 1, active_test["value"])

            # Log a human-readable snapshot roughly once per second.
            if int(current_time) != int(self.last_effect_time):
                msg = (
                    f"Audio Analysis - RMS: {frame.rms:.1f}, Peak: {frame.peak:.1f} | "
                    f"Thresholds - Min: {min_threshold:.1f}, Strobe: {strobe_threshold:.1f}, "
                    f"Combo: {combo_threshold:.1f} | Pattern: {frame.pattern_detected} "
                    f"({frame.pattern_confidence:.2f})"
                )
                logger.debug(msg)

            time.sleep(self.effect_interval)
            self.last_effect_time = current_time
