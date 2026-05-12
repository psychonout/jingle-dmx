from __future__ import annotations

import colorsys
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from loguru import logger

from audio_model import AudioFrame
from config import ShowProfile
from eurolite_strobe import EuroliteStrobe
from laser import (
    MONO_BLUE_MAX,
    MONO_BLUE_MIN,
    MONO_GREEN_MAX,
    MONO_GREEN_MIN,
    MONO_RED_MAX,
    Laser,
)
from light_strip import VUMeter
from spotlight import Spotlight
from stinger import StingerII
from strobe import Strobe

STINGER_LASER_BASE_SPEED = 130
STINGER_LASER_BOOST_SPEED = 200
STINGER_LASER_SLOW_SPEED = 85

# ---------------------------------------------------------------------------
# Laser speed profiles – adjust these to change laser movement speed globally.
# Each profile has a base speed and rotation speed (min, max tuples).
# ---------------------------------------------------------------------------
LASER_SPEED_BEAT_FAST = (50, 58)            # Fast beat effects
LASER_SPEED_BEAT_NORMAL = (46, 55)          # Normal beat effects
LASER_SPEED_BEAT_BASE = 46                  # Used with intensity multiplier

LASER_SPEED_BASS = (46, 58)                 # Bass-heavy effects
LASER_ROTATION_BASS = (40, 65)              # Bass rotation

LASER_SPEED_MID = (46, 60)                  # Mid-range effects
LASER_ROTATION_MID = (30, 55)               # Mid rotation

LASER_SPEED_HIGH = (46, 55)                 # High-energy effects
LASER_ROTATION_HIGH = (50, 78)              # High rotation

LASER_SPEED_MEGA_COMBO = 50                 # Mega combo base (+ intensity * 15)
LASER_ROTATION_MEGA = (60, 78)              # Mega combo rotation

LASER_SPEED_COMBO = 46                      # Combo base (+ intensity * 20)
LASER_ROTATION_COMBO = (40, 70)             # Combo rotation

LASER_SPEED_STROBE = 46                     # Strobe effect
LASER_ROTATION_STROBE = (50, 78)            # Strobe rotation

LASER_SPEED_AMBIENT = 46                    # Ambient/subtle
LASER_ROTATION_AMBIENT_ACTIVE = (20, 40)   # Ambient rotation (active)
LASER_ROTATION_AMBIENT_SUBTLE = (15, 35)   # Ambient rotation (subtle)

# ---------------------------------------------------------------------------
# Named DMX intensity bands – replaces bare magic numbers in effect logic.
# ---------------------------------------------------------------------------
_DIMMER_FULL: int = 255  # 100 % brightness
_DIMMER_HIGH: int = 220  # ~86 % – punchy fill
_DIMMER_MED: int = 180  # ~71 % – warm ambient
_DIMMER_LOW: int = 120  # ~47 % – background glow
_STROBE_FAST: int = 200  # Fast burst (beat-sync)
_STROBE_MED: int = 130  # Mid-tempo pulse
_STROBE_SLOW: int = 80  # Slow sweep
_EUROLITE_DIMMER_MAX: int = 170
_EUROLITE_COLOR_MIN: int = 90
_EUROLITE_COLOR_MAX: int = 165

# ---------------------------------------------------------------------------
# Laser colour palette — uses the hardware's monochrome RGB segments.
# CH9 0-63 is split: R 0-20, G 21-41, B 42-63.
# Values 64-127 = colour mixing, 128-192 = mono auto, 193-255 = full auto.
# Colour only takes effect in auto/sound modes (CH1=128 or 192).
# In manual mode (CH1=64), CH9 is ignored by the hardware.
# ---------------------------------------------------------------------------
_LASER_RED: int = MONO_RED_MAX  # 20 — max red
_LASER_GREEN: int = MONO_GREEN_MAX  # 41 — max green
_LASER_BLUE: int = MONO_BLUE_MAX  # 63 — max blue
_LASER_COLOR_MIX_START: int = 64  # start of colour-mixing range
_LASER_COLOR_MIX_END: int = 127  # end of colour-mixing range
_LASER_MONO_AUTO_START: int = 128  # start of monochrome auto-cycle
_LASER_MONO_AUTO_END: int = 192  # end of monochrome auto-cycle
_LASER_FULL_AUTO_START: int = 193  # start of full auto colour cycle

# Named laser presets (CH2 values) for variety.
_LASER_PRESET_CIRCLE: int = 8
_LASER_PRESET_STAR: int = 103
_LASER_PRESET_HEART: int = 123
_LASER_PRESET_TRIANGLE: int = 38
_LASER_PRESET_ZIGZAG_H: int = 68
_LASER_PRESET_ZIGZAG_V: int = 73
_LASER_PRESET_SINEWAVE: int = 108
_LASER_PRESET_DOTTED_CIRCLE: int = 138
_LASER_PRESET_PLUS: int = 158
_LASER_PRESET_TRIPPY_CIRCLE: int = 163
_LASER_PRESET_TRIPPY_TRIANGLE: int = 168
_LASER_PRESET_ARROW: int = 203
_LASER_PRESET_RHOMBUS: int = 233

# Curated preset lists by mood.
_LASER_PRESETS_CHILL: list[int] = [
    _LASER_PRESET_CIRCLE,
    _LASER_PRESET_DOTTED_CIRCLE,
    _LASER_PRESET_TRIANGLE,
    _LASER_PRESET_PLUS,
]
_LASER_PRESETS_ENERGETIC: list[int] = [
    _LASER_PRESET_STAR,
    _LASER_PRESET_ZIGZAG_H,
    _LASER_PRESET_ZIGZAG_V,
    _LASER_PRESET_SINEWAVE,
    _LASER_PRESET_TRIPPY_CIRCLE,
    _LASER_PRESET_TRIPPY_TRIANGLE,
]
_LASER_PRESETS_DRAMATIC: list[int] = [
    _LASER_PRESET_HEART,
    _LASER_PRESET_ARROW,
    _LASER_PRESET_RHOMBUS,
    _LASER_PRESET_TRIPPY_TRIANGLE,
    _LASER_PRESET_STAR,
]


@dataclass
class Devices:
    laser: Optional[Laser]
    strobe: Optional[Strobe]
    spotlight: Optional[Spotlight]
    stinger: Optional[StingerII]
    vu_meter: Optional[VUMeter] | None = None
    eurolite_strobe: Optional[EuroliteStrobe] = None


@dataclass
class Thresholds:
    min_threshold: float
    strobe_threshold: float
    combo_threshold: float


class EffectStrategy(ABC):
    """Abstract base class for all effect strategies."""

    priority: int = 0
    name: str = "base"

    def _cap(self, value: int, cap: int) -> int:
        """Clamp *value* so it never exceeds *cap*."""
        return min(value, cap)

    @staticmethod
    def _rms_scale(rms: float, reference: float) -> float:
        """Normalise *rms* to ``[0.0, 1.0]`` relative to *reference*.

        A value of 1.0 means audio is at or above the reference level.
        Returns 0.0 when *reference* is zero to avoid division by zero."""
        return min(1.0, rms / reference) if reference > 0 else 0.0

    @staticmethod
    def _random_eurolite_color(
        rng: random.Random, *, brightness: int
    ) -> tuple[int, int, int]:
        """Generate a uniformly random hue to avoid channel bias (e.g. green lock)."""

        hue = rng.random()
        saturation = 0.88
        value = max(20, min(255, int(brightness))) / 255.0
        red_f, green_f, blue_f = colorsys.hsv_to_rgb(hue, saturation, value)
        return int(red_f * 255), int(green_f * 255), int(blue_f * 255)

    def _eurolite_dimmer_level(self, intensity: float, profile: ShowProfile) -> int:
        target = int(_DIMMER_LOW + intensity * 50)
        return self._cap(target, min(profile.max_dimmer_level, _EUROLITE_DIMMER_MAX))

    @staticmethod
    def _laser_color(rng: random.Random, intensity: float = 1.0) -> int:
        """Pick a varied laser colour (CH9) based on intensity.

        Uses the hardware's RGB segments and colour-mixing ranges to
        produce visually distinct colours.  Higher intensity biases toward
        brighter, more saturated colours; lower intensity toward softer hues.

        Colour only takes effect in auto/sound modes (CH1=128 or 192).
        """
        roll = rng.random()
        if roll < 0.35:
            # Red segment — bias toward bright end (10-20) for visibility
            return rng.randint(10, MONO_RED_MAX)
        elif roll < 0.55:
            # Green segment — bias toward bright end
            return rng.randint(MONO_GREEN_MIN + 7, MONO_GREEN_MAX)
        elif roll < 0.75:
            # Blue segment — bias toward bright end
            return rng.randint(MONO_BLUE_MIN + 7, MONO_BLUE_MAX)
        elif roll < 0.90:
            # Colour mixing — varied blends
            return rng.randint(_LASER_COLOR_MIX_START, _LASER_COLOR_MIX_END)
        else:
            # Monochrome auto-cycle — hardware cycles through colours
            return rng.randint(_LASER_MONO_AUTO_START, _LASER_MONO_AUTO_END)

    @staticmethod
    def _laser_color_for_mood(
        rng: random.Random,
        mood: str = "neutral",
    ) -> int:
        """Pick a laser colour biased toward a mood.

        Args:
            mood: One of 'warm' (red/gold), 'cool' (green/blue),
                  'dramatic' (red/blue), 'neutral' (any).
        """
        if mood == "warm":
            # Strong red bias — red is the narrowest segment so needs weight
            roll = rng.random()
            if roll < 0.60:
                return rng.randint(10, MONO_RED_MAX)  # bright red
            elif roll < 0.80:
                return rng.randint(_LASER_COLOR_MIX_START, _LASER_COLOR_MIX_START + 20)
            else:
                return rng.randint(_LASER_MONO_AUTO_START, _LASER_MONO_AUTO_START + 32)
        elif mood == "cool":
            # Bias toward green and blue
            roll = rng.random()
            if roll < 0.40:
                return rng.randint(MONO_GREEN_MIN + 7, MONO_GREEN_MAX)
            elif roll < 0.80:
                return rng.randint(MONO_BLUE_MIN + 7, MONO_BLUE_MAX)
            else:
                return rng.randint(_LASER_COLOR_MIX_START + 30, _LASER_COLOR_MIX_END)
        elif mood == "dramatic":
            # Red and blue equally — high contrast
            roll = rng.random()
            if roll < 0.55:
                return rng.randint(10, MONO_RED_MAX)  # bright red
            elif roll < 0.90:
                return rng.randint(MONO_BLUE_MIN + 7, MONO_BLUE_MAX)
            else:
                return rng.randint(_LASER_MONO_AUTO_START, _LASER_MONO_AUTO_END)
        else:
            return EffectStrategy._laser_color(rng)

    @abstractmethod
    def can_apply(
        self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile
    ) -> bool:
        """Determine if this strategy should be applied based on current conditions."""
        pass

    @abstractmethod
    def apply(
        self,
        devices: Devices,
        frame: AudioFrame,
        thresholds: Thresholds,
        profile: ShowProfile,
        rng: random.Random,
    ) -> None:
        """Apply the effect to the devices."""
        pass


class BeatEffectStrategy(EffectStrategy):
    priority = 100
    name = "beat"

    def can_apply(
        self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile
    ) -> bool:
        return (
            frame.beat_detected
            and frame.rms > thresholds.min_threshold
            and profile.enable_beat
        )

    def apply(
        self,
        devices: Devices,
        frame: AudioFrame,
        thresholds: Thresholds,
        profile: ShowProfile,
        rng: random.Random,
    ) -> None:
        logger.debug(f"BEAT TRIGGERED! RMS: {frame.rms:.1f}, Peak: {frame.peak:.1f}")
        strobe = devices.strobe
        eurolite_strobe = devices.eurolite_strobe
        spotlight = devices.spotlight
        laser = devices.laser
        stinger = devices.stinger

        total_energy = frame.total_energy or (
            frame.bass_energy + frame.mid_energy + frame.high_energy
        )
        is_bass_beat = total_energy > 0 and (frame.bass_energy / total_energy) > 0.4

        # Scale 0–1: how hard this beat hits relative to the strobe threshold.
        intensity = self._rms_scale(frame.rms, thresholds.strobe_threshold)
        # Phrase boundaries always fire at full brightness regardless of RMS.
        if frame.on_phrase:
            intensity = 1.0
        # A building energy trend nudges intensity up so volume ramps feel alive.
        elif frame.building_energy:
            intensity = min(1.0, intensity * 1.2)

        dimmer_level = self._cap(
            int(_DIMMER_MED + intensity * 75), profile.max_dimmer_level
        )
        strobe_level = self._cap(
            int(_STROBE_SLOW + intensity * 120), profile.max_strobe_level
        )
        # Bar and phrase beats get a faster laser sweep for rhythmic impact.
        laser_speed = (
            rng.randint(*LASER_SPEED_BEAT_FAST)
            if (frame.on_bar or frame.building_energy)
            else rng.randint(*LASER_SPEED_BEAT_NORMAL)
        )

        if strobe:
            # Beats: favour warm/yellowish white rather than cold white.
            strobe.set_warm_white(self._cap(_DIMMER_HIGH, profile.max_strobe_level))
            if is_bass_beat:
                strobe.set_dimmer(dimmer_level)
                strobe.set_strobe(strobe_level)
                strobe.set_color(90)
            else:
                strobe.set_dimmer(
                    self._cap(int(dimmer_level * 0.9), profile.max_dimmer_level)
                )
                strobe.set_strobe(
                    self._cap(int(strobe_level * 0.8), profile.max_strobe_level)
                )
                strobe.set_color(rng.randint(40, 120))
        if eurolite_strobe:
            eurolite_strobe.open_gates()
            eurolite_strobe.set_dimmer(self._eurolite_dimmer_level(intensity, profile))
            strobe_effect = (
                rng.randint(110, 175) if is_bass_beat else rng.randint(90, 145)
            )
            # Phrase hits always trigger the fastest strobe burst.
            if frame.on_phrase:
                strobe_effect = 180
            eurolite_strobe.set_strobe_effect(
                self._cap(strobe_effect, profile.max_strobe_level)
            )
            brightness = int(
                _EUROLITE_COLOR_MIN
                + intensity * (_EUROLITE_COLOR_MAX - _EUROLITE_COLOR_MIN)
            )
            red, green, blue = self._random_eurolite_color(rng, brightness=brightness)
            eurolite_strobe.set_color(red, green, blue)
            if profile.enable_ambient:
                eurolite_strobe.set_sound_control(rng.randint(60, 130))
        if spotlight:
            spotlight.random_color()
            spotlight.set_brightness(dimmer_level)
            # Phrase = full strobe burst; bar = stronger flash; normal = regular.
            if frame.on_phrase:
                spotlight.set_strobe(self._cap(_DIMMER_FULL, profile.max_strobe_level))
            elif frame.on_bar:
                spotlight.set_strobe(
                    self._cap(rng.randint(210, 240), profile.max_strobe_level)
                )
            else:
                spotlight.set_strobe(
                    self._cap(rng.randint(192, 223), profile.max_strobe_level)
                )
        if laser:
            # Beat: switch to auto mode so colour takes effect, pick a
            # varied colour, and select a preset from the energetic list.
            laser.set_mode("auto")
            laser.set_mode_level(
                self._cap(rng.randint(128, 192), profile.max_laser_level)
            )
            laser.color(
                self._laser_color_for_mood(
                    rng,
                    mood="dramatic" if is_bass_beat else "neutral",
                )
            )
            laser.pattern(rng.choice(_LASER_PRESETS_ENERGETIC))
            laser.speed(laser_speed)
            # Bass beats: fast spin; other beats: moderate rotation.
            if is_bass_beat:
                laser.rotation_speed(rng.randint(*LASER_ROTATION_HIGH))
            else:
                laser.rotate(rng.randint(0, 127))
        if stinger:
            if frame.rms >= thresholds.strobe_threshold:
                # STRONG BEAT: laser + LED strobe + moonflower
                stinger.set_show_mode(0)
                stinger.set_show_speed(
                    self._cap(int(180 + intensity * 60), 255), sound_active=False
                )
                stinger.set_color_macro("change")
                stinger.set_led_strobe(
                    self._cap(rng.randint(80, 150), profile.max_strobe_level)
                )
                stinger.set_uv(self._cap(_DIMMER_FULL, profile.max_uv_level))
                stinger.set_uv_chase(
                    self._cap(127, profile.max_uv_level), strobing=True
                )
                stinger.set_laser_output(
                    strobe_speed=STINGER_LASER_BOOST_SPEED,
                    rotation_raw=135,
                )
                stinger.set_moonflower_rotation(
                    direction="ccw" if rng.randint(0, 1) else "cw",
                    speed=self._cap(int(40 + intensity * 30), 70),
                )
            else:
                # REGULAR BEAT: moonflower with subtle laser
                stinger.set_show_mode(0)
                stinger.set_color_macro("fade1")
                stinger.set_led_strobe(0)
                stinger.set_uv(self._cap(_DIMMER_HIGH, profile.max_uv_level))
                stinger.set_uv_chase(
                    self._cap(110, profile.max_uv_level), strobing=False
                )
                stinger.set_laser_output(
                    strobe_speed=STINGER_LASER_BASE_SPEED,
                    rotation_raw=135,
                )
                stinger.set_moonflower_rotation(
                    direction="cw",
                    speed=rng.randint(35, 60),
                )


class FrequencyEffectStrategy(EffectStrategy):
    priority = 90
    name = "frequency"

    def can_apply(
        self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile
    ) -> bool:
        return (
            frame.total_energy > 1000
            and frame.rms > thresholds.min_threshold
            and profile.enable_frequency
        )

    def apply(
        self,
        devices: Devices,
        frame: AudioFrame,
        thresholds: Thresholds,
        profile: ShowProfile,
        rng: random.Random,
    ) -> None:
        if frame.total_energy == 0:
            return
        bass_ratio = frame.bass_energy / frame.total_energy
        mid_ratio = frame.mid_energy / frame.total_energy
        high_ratio = frame.high_energy / frame.total_energy
        logger.debug(
            "Frequency ratios - Bass: %.2f, Mid: %.2f, High: %.2f",
            bass_ratio,
            mid_ratio,
            high_ratio,
        )
        # Scale 0–1: how active the audio is relative to the detection floor.
        intensity = self._rms_scale(frame.rms, thresholds.min_threshold)
        if frame.building_energy:
            intensity = min(1.0, intensity * 1.15)

        if bass_ratio > 0.5:
            self._bass_heavy_effects(frame, devices, profile, rng, intensity)
        elif mid_ratio > 0.4:
            self._mid_heavy_effects(frame, devices, profile, rng, intensity)
        elif high_ratio > 0.3:
            self._high_heavy_effects(frame, devices, profile, rng, intensity)

        # Keep Eurolite colours uniformly random in hue to avoid persistent
        # single-channel bias from spectrum-heavy tracks.
        if devices.eurolite_strobe:
            devices.eurolite_strobe.set_dimmer(
                self._eurolite_dimmer_level(intensity, profile)
            )
            brightness = int(
                _EUROLITE_COLOR_MIN
                + intensity * (_EUROLITE_COLOR_MAX - _EUROLITE_COLOR_MIN)
            )
            red, green, blue = self._random_eurolite_color(rng, brightness=brightness)
            devices.eurolite_strobe.set_color(red, green, blue)
            if frame.building_energy:
                devices.eurolite_strobe.set_strobe_effect(
                    self._cap(rng.randint(120, 170), profile.max_strobe_level)
                )

    def _bass_heavy_effects(
        self,
        frame: AudioFrame,
        devices: Devices,
        profile: ShowProfile,
        rng: random.Random,
        intensity: float,
    ) -> None:
        logger.debug("BASS-HEAVY EFFECT!")
        laser = devices.laser
        strobe = devices.strobe
        spotlight = devices.spotlight
        stinger = devices.stinger
        eurolite_strobe = devices.eurolite_strobe

        if strobe:
            # Bass: smooth pulse – no strobe flicker
            strobe.set_dimmer(0)
            strobe.set_strobe(0)
        if spotlight:
            spotlight.set_color_rgb(
                rng.randint(200, 255),
                rng.randint(0, 100),
                rng.randint(0, 50),
                rng.randint(0, 50),
            )
            spotlight.set_brightness(
                self._cap(int(_DIMMER_MED + intensity * 75), profile.max_dimmer_level)
            )
            spotlight.set_strobe(rng.randint(64, 95))
            spotlight.set_macro(rng.randint(100, 150))
        if laser:
            # Bass: auto mode with warm red/gold colour, dramatic presets.
            laser.set_mode("auto")
            laser.set_mode_level(
                self._cap(int(128 + intensity * 64), profile.max_laser_level)
            )
            laser.color(self._laser_color_for_mood(rng, mood="warm"))
            laser.pattern(rng.choice(_LASER_PRESETS_DRAMATIC))
            laser.speed(rng.randint(*LASER_SPEED_BASS))
            laser.rotation_speed(rng.randint(*LASER_ROTATION_BASS))
        if stinger:
            # Bass: moonflower only, no strobe
            stinger.set_show_mode(0)
            stinger.set_color_macro("fade1")
            stinger.set_led_strobe(0)
            stinger.set_uv(
                self._cap(int(_DIMMER_MED + intensity * 75), profile.max_uv_level)
            )
            stinger.set_uv_chase(
                self._cap(int(100 + intensity * 27), profile.max_uv_level),
                strobing=False,
            )
            stinger.set_laser_output(
                strobe_speed=STINGER_LASER_BASE_SPEED, rotation_raw=135
            )
            stinger.set_moonflower_rotation("cw", speed=int(40 + intensity * 25))
        if eurolite_strobe:
            eurolite_strobe.open_gates()
            eurolite_strobe.set_strobe_effect(rng.randint(80, 102))
            # Placeholder colour; overridden by proportional blend in apply().
            eurolite_strobe.set_color(120, rng.randint(0, 20), 0)

    def _mid_heavy_effects(
        self,
        frame: AudioFrame,
        devices: Devices,
        profile: ShowProfile,
        rng: random.Random,
        intensity: float,
    ) -> None:
        logger.debug("MID-HEAVY EFFECT!")
        laser = devices.laser
        strobe = devices.strobe
        spotlight = devices.spotlight
        stinger = devices.stinger
        eurolite_strobe = devices.eurolite_strobe

        if strobe:
            # Mid: smooth sweep – no strobe flicker
            strobe.set_dimmer(0)
            strobe.set_strobe(0)
        if spotlight:
            spotlight.set_color_rgb(
                rng.randint(0, 100),
                rng.randint(100, 255),
                rng.randint(100, 255),
                rng.randint(0, 50),
            )
            spotlight.set_brightness(
                self._cap(int(_DIMMER_LOW + intensity * 100), profile.max_dimmer_level)
            )
            spotlight.set_strobe(rng.randint(128, 159))
        if laser:
            # Mid: auto mode with cool green/blue colour, flowing presets.
            laser.set_mode("auto")
            laser.set_mode_level(
                self._cap(int(128 + intensity * 64), profile.max_laser_level)
            )
            laser.color(self._laser_color_for_mood(rng, mood="cool"))
            laser.pattern(rng.choice(_LASER_PRESETS_CHILL))
            laser.speed(rng.randint(*LASER_SPEED_MID))
            laser.rotation_speed(rng.randint(*LASER_ROTATION_MID))
        if stinger:
            # Mid: moonflower with smooth colour blend
            stinger.set_show_mode(0)
            stinger.set_color_macro("fade2")
            stinger.set_led_strobe(0)
            stinger.set_uv(
                self._cap(int(_DIMMER_MED + intensity * 75), profile.max_uv_level)
            )
            stinger.set_uv_chase(
                self._cap(int(110 + intensity * 17), profile.max_uv_level),
                strobing=False,
            )
            stinger.set_laser_output(
                strobe_speed=STINGER_LASER_BASE_SPEED, rotation_raw=135
            )
            stinger.set_moonflower_rotation("cw", speed=int(45 + intensity * 30))
        if eurolite_strobe:
            eurolite_strobe.open_gates()
            eurolite_strobe.set_strobe_effect(rng.randint(34, 56))
            # Placeholder colour; overridden by proportional blend in apply().
            eurolite_strobe.set_color(
                rng.randint(60, 120), rng.randint(0, 40), rng.randint(80, 140)
            )

    def _high_heavy_effects(
        self,
        frame: AudioFrame,
        devices: Devices,
        profile: ShowProfile,
        rng: random.Random,
        intensity: float,
    ) -> None:
        logger.debug("HIGH-HEAVY EFFECT!")
        laser = devices.laser
        strobe = devices.strobe
        spotlight = devices.spotlight
        stinger = devices.stinger
        eurolite_strobe = devices.eurolite_strobe

        if strobe:
            strobe.set_warm_white(self._cap(_DIMMER_MED, profile.max_strobe_level))
            strobe.set_dimmer(
                self._cap(int(_DIMMER_MED + intensity * 75), profile.max_dimmer_level)
            )
            strobe.set_strobe(
                self._cap(int(50 + intensity * 70), profile.max_strobe_level)
            )
            strobe.set_color(100)
        if spotlight:
            spotlight.set_color_rgb(
                rng.randint(100, 255),
                rng.randint(100, 255),
                rng.randint(200, 255),
                rng.randint(100, 255),
            )
            spotlight.set_brightness(
                self._cap(int(_DIMMER_MED + intensity * 75), profile.max_dimmer_level)
            )
            spotlight.set_strobe(rng.randint(224, 255))
        if laser:
            # High: auto mode with dramatic red/blue, energetic presets.
            laser.set_mode("auto")
            laser.set_mode_level(
                self._cap(int(160 + intensity * 95), profile.max_laser_level)
            )
            laser.color(self._laser_color_for_mood(rng, mood="dramatic"))
            laser.pattern(rng.choice(_LASER_PRESETS_ENERGETIC))
            laser.speed(rng.randint(*LASER_SPEED_HIGH))
            laser.rotation_speed(rng.randint(*LASER_ROTATION_HIGH))
        if stinger:
            # High: maximum energy – laser + strobe + fast moonflower
            stinger.set_show_mode(0)
            stinger.set_show_speed(int(180 + intensity * 40), sound_active=False)
            stinger.set_color_macro("fade2")
            stinger.set_led_strobe(
                self._cap(int(120 + intensity * 80), profile.max_strobe_level)
            )
            stinger.set_uv(
                self._cap(int(_DIMMER_MED + intensity * 75), profile.max_uv_level)
            )
            stinger.set_uv_chase(
                self._cap(int(90 + intensity * 37), profile.max_uv_level), strobing=True
            )
            stinger.set_laser_output(
                strobe_speed=STINGER_LASER_BOOST_SPEED,
                rotation_raw=self._cap(135, profile.max_laser_level),
            )
            stinger.set_moonflower_rotation("ccw", speed=int(50 + intensity * 30))
        if eurolite_strobe:
            eurolite_strobe.open_gates()
            eurolite_strobe.set_strobe_effect(int(_STROBE_MED + intensity * 70))
            # Placeholder colour; overridden by proportional blend in apply().
            eurolite_strobe.set_color(rng.randint(0, 20), rng.randint(0, 20), 140)


class MegaComboEffectStrategy(EffectStrategy):
    priority = 80
    name = "mega_combo"

    def can_apply(
        self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile
    ) -> bool:
        return (
            frame.rms >= thresholds.combo_threshold * 1.3 and profile.enable_mega_combo
        )

    def apply(
        self,
        devices: Devices,
        frame: AudioFrame,
        thresholds: Thresholds,
        profile: ShowProfile,
        rng: random.Random,
    ) -> None:
        logger.debug(f"MEGA COMBO! RMS: {frame.rms:.1f}")
        # Scale 0–1 from the combo threshold onward; phrase hits always max out.
        intensity = self._rms_scale(frame.rms, thresholds.combo_threshold * 1.3)
        if frame.on_phrase:
            intensity = 1.0
        strobe = devices.strobe
        spotlight = devices.spotlight
        laser = devices.laser
        stinger = devices.stinger
        if strobe:
            strobe.set_dimmer(
                self._cap(int(_DIMMER_MED + intensity * 75), profile.max_dimmer_level)
            )
            strobe.set_strobe(
                self._cap(int(100 + intensity * 55), profile.max_strobe_level)
            )
            strobe.set_color(70)
            strobe.set_warm_white(self._cap(_DIMMER_MED, profile.max_strobe_level))
        if spotlight:
            spotlight.set_color_rgb(255, 255, 255, 255)
            spotlight.set_brightness(
                self._cap(int(_DIMMER_HIGH + intensity * 35), profile.max_dimmer_level)
            )
            spotlight.set_strobe(self._cap(_DIMMER_FULL, profile.max_strobe_level))
        if laser:
            # Mega combo: sound mode for maximum reactivity, dramatic colour.
            laser.set_mode("sound")
            laser.set_mode_level(
                self._cap(int(192 + intensity * 63), profile.max_laser_level)
            )
            laser.color(self._laser_color_for_mood(rng, mood="dramatic"))
            laser.pattern(rng.choice(_LASER_PRESETS_DRAMATIC))
            laser.speed(self._cap(int(LASER_SPEED_MEGA_COMBO + intensity * 15), 255))
            laser.rotation_speed(rng.randint(*LASER_ROTATION_MEGA))
        if stinger:
            # Mega combo: everything at high intensity, scaled by RMS
            stinger.set_show_mode(0)
            stinger.set_show_speed(
                self._cap(int(200 + intensity * 55), 255), sound_active=True
            )
            stinger.set_color_macro("random")
            stinger.set_led_strobe(
                self._cap(int(160 + intensity * 95), profile.max_strobe_level)
            )
            stinger.set_uv(self._cap(_DIMMER_FULL, profile.max_uv_level))
            stinger.set_uv_chase(self._cap(127, profile.max_uv_level), strobing=True)
            stinger.set_laser_output(
                strobe_speed=STINGER_LASER_BOOST_SPEED,
                chase_speed=self._cap(
                    int(50 + intensity * 10), profile.max_laser_level
                ),
            )
            stinger.set_moonflower_rotation("ccw", speed=int(60 + intensity * 10))


class ComboEffectStrategy(EffectStrategy):
    priority = 70
    name = "combo"

    def can_apply(
        self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile
    ) -> bool:
        return frame.rms >= thresholds.combo_threshold and profile.enable_combo

    def apply(
        self,
        devices: Devices,
        frame: AudioFrame,
        thresholds: Thresholds,
        profile: ShowProfile,
        rng: random.Random,
    ) -> None:
        logger.debug(f"COMBO EFFECT! RMS: {frame.rms:.1f}")
        combo_threshold = thresholds.combo_threshold
        intensity = (
            min(1.0, frame.rms / combo_threshold) if combo_threshold > 0 else 0.5
        )

        strobe = devices.strobe
        spotlight = devices.spotlight
        laser = devices.laser
        stinger = devices.stinger
        if strobe:
            strobe.set_warm_white(
                self._cap(int(150 + (intensity * 105)), profile.max_strobe_level)
            )
            strobe.set_dimmer(
                self._cap(int(150 + (intensity * 105)), profile.max_dimmer_level)
            )
            strobe.set_strobe(self._cap(rng.randint(32, 95), profile.max_strobe_level))
        if spotlight:
            spotlight.random_color()
            spotlight.set_brightness(
                self._cap(int(200 + (intensity * 55)), profile.max_dimmer_level)
            )
            spotlight.set_strobe(
                self._cap(int(150 + (intensity * 105)), profile.max_strobe_level)
            )
        if laser:
            # Combo: auto mode with varied colour, energetic presets.
            laser.set_mode("auto")
            laser.set_mode_level(
                self._cap(int(128 + intensity * 127), profile.max_laser_level)
            )
            laser.color(self._laser_color(rng, intensity))
            laser.pattern(rng.choice(_LASER_PRESETS_ENERGETIC))
            laser.speed(self._cap(int(LASER_SPEED_COMBO + (intensity * 20)), 255))
            laser.rotation_speed(rng.randint(*LASER_ROTATION_COMBO))
        if stinger:
            if intensity > 0.8:
                # COMBO HIGH: Laser active
                stinger.set_show_mode(0)
                stinger.set_show_speed(int(180 + (intensity * 60)), sound_active=False)
                stinger.set_color_macro("fade2")
                stinger.set_led_strobe(
                    self._cap(int(140 + (intensity * 100)), profile.max_strobe_level)
                )
                stinger.set_uv(self._cap(255, profile.max_uv_level))
                stinger.set_uv_chase(
                    self._cap(int(intensity * 127), profile.max_uv_level), strobing=True
                )
                stinger.set_laser_output(
                    strobe_speed=STINGER_LASER_BOOST_SPEED,
                    rotation_raw=135,
                )  # Laser active
                stinger.set_moonflower_rotation("ccw", speed=int(45 + intensity * 25))
            elif intensity > 0.5:
                # COMBO MID: Smooth moonflower only
                stinger.set_show_mode(0)
                stinger.set_color_macro("fade2")  # Smooth color blending
                stinger.set_led_strobe(0)  # NO strobe
                stinger.set_uv(
                    self._cap(int(200 + (intensity * 55)), profile.max_uv_level)
                )
                stinger.set_uv_chase(
                    self._cap(int(intensity * 127), profile.max_uv_level),
                    strobing=False,
                )
                stinger.set_laser_output(
                    strobe_speed=STINGER_LASER_SLOW_SPEED,
                    rotation_raw=135,
                )  # Light laser glow
                stinger.set_moonflower_rotation("cw", speed=int(35 + intensity * 30))


class StrobeEffectStrategy(EffectStrategy):
    priority = 60
    name = "strobe"

    def can_apply(
        self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile
    ) -> bool:
        return frame.rms >= thresholds.strobe_threshold and profile.enable_strobe_only

    def apply(
        self,
        devices: Devices,
        frame: AudioFrame,
        thresholds: Thresholds,
        profile: ShowProfile,
        rng: random.Random,
    ) -> None:
        logger.debug(f"STROBE EFFECT! RMS: {frame.rms:.1f}")

        strobe_threshold = thresholds.strobe_threshold
        effect_intensity = frame.rms / strobe_threshold

        strobe = devices.strobe
        spotlight = devices.spotlight
        laser = devices.laser
        stinger = devices.stinger
        if strobe:
            # Only strobe if intensity is reasonably high
            if effect_intensity >= 1.1:
                strobe.set_warm_white(
                    self._cap(
                        int(180 + (min(effect_intensity, 1.0) * 75)),
                        profile.max_strobe_level,
                    )
                )
                strobe.set_dimmer(self._cap(255, profile.max_dimmer_level))
                strobe.set_strobe(
                    self._cap(
                        int(150 + (effect_intensity * 105)), profile.max_strobe_level
                    )
                )
            else:
                # Turn off strobe if intensity drops
                strobe.set_dimmer(0)
                strobe.set_strobe(0)
        if spotlight:
            if effect_intensity > 1.2:
                spotlight.set_brightness(self._cap(255, profile.max_dimmer_level))
                spotlight.set_strobe(
                    self._cap(
                        int(64 + min(95, effect_intensity * 95)),
                        profile.max_strobe_level,
                    )
                )
                spotlight.random_color()
            else:
                spotlight.set_brightness(0)
                spotlight.set_strobe(0)
        if laser:
            # Strobe: auto mode with punchy colour, dramatic presets.
            laser.set_mode("auto")
            laser.set_mode_level(
                self._cap(int(128 + (effect_intensity * 127)), profile.max_laser_level)
            )
            laser.color(self._laser_color_for_mood(rng, mood="dramatic"))
            laser.pattern(rng.choice(_LASER_PRESETS_ENERGETIC))
            laser.speed(self._cap(int(LASER_SPEED_STROBE + (effect_intensity * 20)), 255))
            laser.rotation_speed(rng.randint(*LASER_ROTATION_STROBE))
        if stinger:
            if effect_intensity > 0.7:
                # STROBE HIGH: Laser + heavy strobing
                stinger.set_show_mode(0)
                stinger.set_show_speed(
                    int(180 + (effect_intensity * 60)), sound_active=False
                )
                stinger.set_color_macro("change")
                stinger.set_led_strobe(
                    self._cap(
                        int(120 + (effect_intensity * 120)), profile.max_strobe_level
                    )
                )
                stinger.set_uv(
                    self._cap(int(200 + (effect_intensity * 55)), profile.max_uv_level)
                )
                stinger.set_uv_chase(
                    self._cap(int(60 + (effect_intensity * 67)), profile.max_uv_level),
                    strobing=True,
                )
                stinger.set_laser_output(
                    strobe_speed=STINGER_LASER_BOOST_SPEED,
                    rotation_raw=135,
                )  # Strobe laser active
                stinger.set_moonflower_rotation(
                    "ccw", speed=int(45 + effect_intensity * 25)
                )
            else:
                # STROBE LOW: Smooth moonflower only
                stinger.set_show_mode(0)
                stinger.set_show_speed(
                    int(130 + (effect_intensity * 50)), sound_active=False
                )
                stinger.set_color_macro("fade1")  # Slow color drift
                stinger.set_led_strobe(0)  # NO strobe
                stinger.set_uv(
                    self._cap(int(200 + (effect_intensity * 55)), profile.max_uv_level)
                )
                stinger.set_uv_chase(
                    self._cap(int(100 + (effect_intensity * 27)), profile.max_uv_level),
                    strobing=False,
                )
                stinger.set_laser_output(
                    strobe_speed=STINGER_LASER_SLOW_SPEED,
                    rotation_raw=135,
                )  # Dim laser glow
                stinger.set_moonflower_rotation(
                    "cw", speed=int(35 + effect_intensity * 30)
                )


class AmbientEffectStrategy(EffectStrategy):
    priority = 50
    name = "ambient"

    def __init__(self):
        super().__init__()
        self._last_refresh = 0.0
        self._cached_laser_color = 128
        self._cached_laser_pattern = 28

    def can_apply(
        self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile
    ) -> bool:
        return frame.rms >= thresholds.min_threshold * 1.5 and profile.enable_ambient

    def apply(
        self,
        devices: Devices,
        frame: AudioFrame,
        thresholds: Thresholds,
        profile: ShowProfile,
        rng: random.Random,
    ) -> None:
        logger.debug(f"AMBIENT EFFECT! RMS: {frame.rms:.1f}")

        min_threshold = thresholds.min_threshold
        strobe = devices.strobe
        spotlight = devices.spotlight
        laser = devices.laser
        stinger = devices.stinger
        eurolite_strobe = devices.eurolite_strobe
        if strobe:
            strobe.set_dimmer(0)
            strobe.set_strobe(0)
        if spotlight:
            spotlight.set_brightness(0)
            spotlight.set_strobe(0)
        if laser:
            now = time.time()
            if now - self._last_refresh > 1.25:
                # Hold values briefly to avoid frantic random flicker.
                self._cached_laser_color = self._laser_color_for_mood(rng, mood="cool")
                self._cached_laser_pattern = rng.choice(_LASER_PRESETS_CHILL)
                self._last_refresh = now

            # Ambient: auto mode with gentle colour, chill presets.
            laser.set_mode("auto")
            laser.set_mode_level(
                self._cap(
                    int(128 + (frame.rms / min_threshold) * 32), profile.max_laser_level
                )
            )
            laser.color(self._cached_laser_color)
            laser.pattern(self._cached_laser_pattern)
            laser.speed(LASER_SPEED_AMBIENT)
            laser.rotation_speed(rng.randint(*LASER_ROTATION_AMBIENT_ACTIVE))
        if stinger:
            # AMBIENT: Smooth moonflower
            stinger.set_show_mode(0)
            stinger.set_color_macro("fade1")  # Slow color drift
            stinger.set_led_strobe(0)  # NO strobe
            stinger.set_uv(
                self._cap(
                    int(180 + (frame.rms / min_threshold) * 75), profile.max_uv_level
                )
            )
            stinger.set_uv_chase(rng.randint(100, 120), strobing=False)
            stinger.set_laser_output(
                strobe_speed=STINGER_LASER_BASE_SPEED, rotation_raw=135
            )  # Ambient laser
            stinger.set_moonflower_rotation("cw", speed=rng.randint(30, 55))
        if eurolite_strobe:
            eurolite_strobe.open_gates()
            eurolite_strobe.set_dimmer(
                self._cap(110, min(profile.max_dimmer_level, _EUROLITE_DIMMER_MAX))
            )
            eurolite_strobe.set_strobe_effect(rng.randint(34, 79))
            red, green, blue = self._random_eurolite_color(
                rng, brightness=_EUROLITE_COLOR_MIN
            )
            eurolite_strobe.set_color(red, green, blue)


class SubtleEffectStrategy(EffectStrategy):
    priority = 40
    name = "subtle"

    def __init__(self):
        super().__init__()
        self._last_refresh = 0.0
        self._cached_laser_color = 127
        self._cached_laser_pattern = 12

    def can_apply(
        self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile
    ) -> bool:
        return frame.rms >= thresholds.min_threshold and profile.enable_subtle

    def apply(
        self,
        devices: Devices,
        frame: AudioFrame,
        thresholds: Thresholds,
        profile: ShowProfile,
        rng: random.Random,
    ) -> None:
        logger.debug(f"SUBTLE EFFECT! RMS: {frame.rms:.1f}")

        min_threshold = thresholds.min_threshold
        strobe = devices.strobe
        spotlight = devices.spotlight
        laser = devices.laser
        stinger = devices.stinger
        eurolite_strobe = devices.eurolite_strobe
        if strobe:
            strobe.set_dimmer(0)
            strobe.set_strobe(0)
        if spotlight:
            spotlight.set_brightness(0)
            spotlight.set_strobe(0)
        if laser:
            if frame.rms > min_threshold * 1.2:
                now = time.time()
                if now - self._last_refresh > 2.0:
                    self._cached_laser_color = self._laser_color_for_mood(
                        rng, mood="cool"
                    )
                    self._cached_laser_pattern = rng.choice(_LASER_PRESETS_CHILL)
                    self._last_refresh = now

                # Subtle: auto mode with soft colour, chill presets.
                laser.set_mode("auto")
                laser.set_mode_level(int(128 + (frame.rms / min_threshold) * 32))
                laser.color(self._cached_laser_color)
                laser.pattern(self._cached_laser_pattern)
                laser.speed(LASER_SPEED_AMBIENT)
                laser.rotation_speed(rng.randint(*LASER_ROTATION_AMBIENT_SUBTLE))
            else:
                laser.set_mode("auto")
                laser.set_mode_level(int(128 + (frame.rms / min_threshold) * 16))
        if stinger:
            if frame.rms > min_threshold * 0.8:  # Lower but reasonable threshold
                # SUBTLE: Gentle moonflower
                stinger.set_show_mode(0)
                stinger.set_color_macro("fade1")  # Slow color drift
                stinger.set_led_strobe(0)  # NO strobe
                stinger.set_uv(rng.randint(180, 230))
                stinger.set_uv_chase(rng.randint(90, 115), strobing=False)
                stinger.set_laser_output(
                    strobe_speed=STINGER_LASER_BASE_SPEED, rotation_raw=135
                )  # Keep laser subtle but visible
                stinger.set_moonflower_rotation("cw", speed=rng.randint(25, 50))
            else:
                stinger.blackout()
        if eurolite_strobe:
            if frame.rms > min_threshold * 1.2:
                eurolite_strobe.open_gates()
                eurolite_strobe.set_dimmer(
                    self._cap(
                        int(95 + (frame.rms / min_threshold) * 30),
                        min(profile.max_dimmer_level, _EUROLITE_DIMMER_MAX),
                    )
                )
                eurolite_strobe.set_strobe_effect(rng.randint(34, 79))
                red, green, blue = self._random_eurolite_color(
                    rng, brightness=_EUROLITE_COLOR_MIN
                )
                eurolite_strobe.set_color(red, green, blue)
            else:
                eurolite_strobe.close_gates()


class SilenceEffectStrategy(EffectStrategy):
    priority = 0
    name = "silence"

    def __init__(self):
        super().__init__()
        self.silence_start_time: Optional[float] = None

    def can_apply(
        self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile
    ) -> bool:
        return True  # Always applicable as fallback

    def apply(
        self,
        devices: Devices,
        frame: AudioFrame,
        thresholds: Thresholds,
        profile: ShowProfile,
        rng: random.Random,
    ) -> None:
        # Track how long we've been silent
        if self.silence_start_time is None:
            self.silence_start_time = time.time()

        silence_duration = time.time() - self.silence_start_time

        strobe = devices.strobe
        spotlight = devices.spotlight
        laser = devices.laser
        stinger = devices.stinger
        eurolite_strobe = devices.eurolite_strobe

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
            # Keep laser dimly visible even during silence.
            # Use auto mode so colour takes effect.
            laser.set_mode("auto")
            laser.set_mode_level(128)
            laser.color(_LASER_BLUE)
            laser.speed(LASER_SPEED_AMBIENT)

        if stinger:
            # Only blackout after 60 seconds of silence
            if silence_duration >= 5.0:
                stinger.blackout()
            # else: do nothing - keep whatever effect was running before silence

        if eurolite_strobe:
            eurolite_strobe.close_gates()


class EffectEngine:
    """Centralized effect selection logic.
    This class contains the decision logic for which effects to apply
    based on audio analysis and current thresholds.
    """

    def __init__(self, profile: ShowProfile) -> None:
        self.profile = profile
        self.last_effect_type: Optional[str] = None
        # Dedicated RNG for repeatable behaviour under a fixed seed.
        if self.profile.random_seed is not None:
            self._rng = random.Random(self.profile.random_seed)
        else:
            self._rng = random.Random()

        self.strategies: List[EffectStrategy] = sorted(
            [
                BeatEffectStrategy(),
                FrequencyEffectStrategy(),
                MegaComboEffectStrategy(),
                ComboEffectStrategy(),
                StrobeEffectStrategy(),
                AmbientEffectStrategy(),
                SubtleEffectStrategy(),
                SilenceEffectStrategy(),
            ],
            key=lambda s: s.priority,
            reverse=True,
        )

    def _cap(self, value: int, cap: int) -> int:
        return min(value, cap)

    def get_effect_variation_count(self) -> int:
        """Return number of non-silence strategies available for variation."""
        return sum(1 for strategy in self.strategies if strategy.name != "silence")

    def apply_effects(
        self,
        frame: AudioFrame,
        thresholds: Thresholds,
        devices: Devices,
    ) -> Optional[str]:
        """Apply effects for a frame."""

        # Log low-latency metric if beat detected
        if (
            frame.beat_detected
            and frame.rms > thresholds.min_threshold
            and self.profile.enable_beat
        ):
            now = time.time()
            logger.debug(f"Beat latency: {now - frame.timestamp:.3f}s")
        for strategy in self.strategies:
            if strategy.can_apply(frame, thresholds, self.profile):
                strategy.apply(devices, frame, thresholds, self.profile, self._rng)
                self.last_effect_type = strategy.name

                # Reset silence timer when any non-silence effect runs
                if strategy.name != "silence":
                    for s in self.strategies:
                        if isinstance(s, SilenceEffectStrategy):
                            s.silence_start_time = None

                return self.last_effect_type

        return self.last_effect_type
