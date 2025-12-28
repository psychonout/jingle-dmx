from __future__ import annotations
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from loguru import logger
from audio_model import AudioFrame
from config import ShowProfile
from eurolite_strobe import EuroliteStrobe
from laser import Laser
from light_strip import VUMeter
from spotlight import Spotlight
from stinger import StingerII
from strobe import Strobe
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
        """Helper to clamp values."""
        return min(value, cap)
    @abstractmethod
    def can_apply(self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile) -> bool:
        """Determine if this strategy should be applied based on current conditions."""
        pass
    @abstractmethod
    def apply(self, devices: Devices, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile, rng: random.Random) -> None:
        """Apply the effect to the devices."""
        pass
class BeatEffectStrategy(EffectStrategy):
    priority = 100
    name = "beat"
    def can_apply(self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile) -> bool:
        return (
            frame.beat_detected
            and frame.rms > thresholds.min_threshold
            and profile.enable_beat
        )
    def apply(self, devices: Devices, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile, rng: random.Random) -> None:
        logger.debug(f"BEAT TRIGGERED! RMS: {frame.rms:.1f}, Peak: {frame.peak:.1f}")
        strobe = devices.strobe
        eurolite_strobe = devices.eurolite_strobe
        spotlight = devices.spotlight
        laser = devices.laser
        stinger = devices.stinger
        if frame.total_energy == 0:
            total_energy = frame.bass_energy + frame.mid_energy + frame.high_energy
        else:
            total_energy = frame.total_energy
        # Inline logic from original EffectEngine._beat_effects
        is_bass_beat = False
        if total_energy > 0 and (frame.bass_energy / total_energy) > 0.4:
            is_bass_beat = True
        if strobe:
            # Beats: favor warm/yellowish white rather than cold white.
            strobe.set_warm_white(self._cap(220, profile.max_strobe_level))
            if is_bass_beat:
                strobe.set_dimmer(self._cap(200, profile.max_dimmer_level))
                strobe.set_strobe(self._cap(100, profile.max_strobe_level))  # Reduced from 255
                strobe.set_color(90)
            else:
                strobe.set_dimmer(self._cap(180, profile.max_dimmer_level))
                strobe.set_strobe(self._cap(80, profile.max_strobe_level))  # Reduced from 255
                strobe.set_color(rng.randint(40, 120))
        if eurolite_strobe:
            eurolite_strobe.open_gates()
            eurolite_strobe.set_dimmer(self._cap(255, profile.max_dimmer_level))

            if is_bass_beat:
                eurolite_strobe.set_strobe_effect(200)  # Fast strobe effect
            else:
                eurolite_strobe.set_strobe_effect(rng.randint(128, 200))  # Strobe effect
            # Reduce intensity significantly for more saturated colors (multiply by 0.4)
            red = self._cap(int(frame.bass_energy * 255 * 0.4), profile.max_dimmer_level)
            green = self._cap(int(frame.mid_energy * 255 * 0.4), profile.max_dimmer_level)
            blue = self._cap(int(frame.high_energy * 255 * 0.4), profile.max_dimmer_level)
            eurolite_strobe.set_color(red, green, blue)
            if profile.enable_ambient:
                eurolite_strobe.set_sound_control(rng.randint(100, 200))
        if spotlight:
            spotlight.random_color()
            spotlight.set_brightness(self._cap(255, profile.max_dimmer_level))
            spotlight.set_strobe(rng.randint(192, 223))
        if laser:
            laser.set_mode_level(self._cap(rng.randint(200, 255), profile.max_laser_level))
            laser.pattern(rng.randint(128, 255))
            laser.color(rng.randint(128, 255))
            laser.speed(rng.randint(220, 255))
        if stinger:
            if frame.rms >= thresholds.strobe_threshold:
                # STRONG BEAT: Laser + LED strobe + moonflower
                stinger.set_show_mode(0)  # Manual control
                stinger.set_show_speed(200, sound_active=False)
                stinger.set_color_macro("change")  # Fast color changes
                stinger.set_led_strobe(self._cap(rng.randint(80, 150), profile.max_strobe_level))  # LED strobe
                stinger.set_uv(self._cap(255, profile.max_uv_level))
                stinger.set_uv_chase(self._cap(127, profile.max_uv_level), strobing=True)  # Max strobing
                stinger.set_laser_output(strobe_speed=rng.randint(100, 180), rotation_raw=rng.randint(40, 80))  # Dynamic laser
                stinger.set_moonflower_rotation(
                    direction="ccw" if rng.randint(0, 1) else "cw",
                    speed=rng.randint(40, 70),
                )
            else:
                # REGULAR BEAT: Moonflower only, smooth
                stinger.set_show_mode(0)  # Manual control
                stinger.set_color_macro("fade1")  # Smooth color blending
                stinger.set_led_strobe(0)  # NO strobe for smooth look
                stinger.set_uv(self._cap(240, profile.max_uv_level))
                stinger.set_uv_chase(self._cap(110, profile.max_uv_level), strobing=False)  # No strobing
                stinger.set_laser_output(strobe_speed=0, rotation_raw=0)  # Laser OFF
                stinger.set_moonflower_rotation(
                    direction="cw",
                    speed=rng.randint(35, 60),
                )
class FrequencyEffectStrategy(EffectStrategy):
    priority = 90
    name = "frequency"
    def can_apply(self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile) -> bool:
        return (
            frame.total_energy > 1000
            and frame.rms > thresholds.min_threshold
            and profile.enable_frequency
        )
    def apply(self, devices: Devices, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile, rng: random.Random) -> None:
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
        laser = devices.laser
        strobe = devices.strobe
        spotlight = devices.spotlight
        stinger = devices.stinger
        eurolite_strobe = devices.eurolite_strobe
        if bass_ratio > 0.5:
            self._bass_heavy_effects(frame.rms, laser, strobe, spotlight, stinger, eurolite_strobe, profile, rng)
        elif mid_ratio > 0.4:
            self._mid_heavy_effects(frame.rms, laser, strobe, spotlight, stinger, eurolite_strobe, profile, rng)
        elif high_ratio > 0.3:
            self._high_heavy_effects(frame.rms, laser, strobe, spotlight, stinger, eurolite_strobe, profile, rng)
    def _bass_heavy_effects(self, rms, laser, strobe, spotlight, stinger, eurolite_strobe, profile, rng):
        logger.debug("BASS-HEAVY EFFECT!")

        if strobe:
            # Turn off strobe for smooth moonflower effect
            strobe.set_dimmer(0)
            strobe.set_strobe(0)
        if spotlight:
            spotlight.set_color_rgb(
                rng.randint(200, 255),
                rng.randint(0, 100),
                rng.randint(0, 50),
                rng.randint(0, 50),
            )
            spotlight.set_brightness(self._cap(255, profile.max_dimmer_level))
            spotlight.set_strobe(rng.randint(64, 95))
            spotlight.set_macro(rng.randint(100, 150))
        if laser:
            laser.set_mode_level(self._cap(rng.randint(150, 200), profile.max_laser_level))
            laser.color(rng.randint(0, 63))
            laser.pattern(rng.randint(0, 127))
            laser.speed(rng.randint(150, 200))
        if stinger:
            # BASS: Moonflower only, no strobe
            stinger.set_show_mode(0)
            stinger.set_color_macro("fade1")  # Smooth color blending
            stinger.set_led_strobe(0)  # No strobe
            stinger.set_uv(self._cap(rng.randint(220, 255), profile.max_uv_level))
            stinger.set_uv_chase(self._cap(rng.randint(100, 127), profile.max_uv_level), strobing=False)
            stinger.set_laser_output(strobe_speed=0, rotation_raw=0)  # No laser
            stinger.set_moonflower_rotation("cw", speed=rng.randint(40, 65))
        if eurolite_strobe:
            eurolite_strobe.open_gates()
            eurolite_strobe.set_strobe_effect(rng.randint(80, 102))
            # Pure red with very minimal orange tint
            eurolite_strobe.set_color(120, rng.randint(0, 20), 0)
    def _mid_heavy_effects(self, rms, laser, strobe, spotlight, stinger, eurolite_strobe, profile, rng):
        logger.debug("MID-HEAVY EFFECT!")

        if strobe:
            # Turn off strobe for smooth moonflower effect
            strobe.set_dimmer(0)
            strobe.set_strobe(0)
        if spotlight:
            spotlight.set_color_rgb(
                rng.randint(0, 100),
                rng.randint(100, 255),
                rng.randint(100, 255),
                rng.randint(0, 50),
            )
            spotlight.set_brightness(self._cap(200, profile.max_dimmer_level))
            spotlight.set_strobe(rng.randint(128, 159))
        if laser:
            laser.set_mode_level(self._cap(rng.randint(120, 180), profile.max_laser_level))
            laser.color(rng.randint(64, 127))
            laser.pattern(rng.randint(64, 191))
        if stinger:
            # MID: Moonflower only, no strobe
            stinger.set_show_mode(0)
            stinger.set_color_macro("fade2")  # Smooth color blending
            stinger.set_led_strobe(0)  # No strobe
            stinger.set_uv(self._cap(255, profile.max_uv_level))
            stinger.set_uv_chase(self._cap(rng.randint(110, 127), profile.max_uv_level), strobing=False)
            stinger.set_laser_output(strobe_speed=0, rotation_raw=0)  # No laser
            stinger.set_moonflower_rotation("cw", speed=rng.randint(45, 75))
        if eurolite_strobe:
            eurolite_strobe.open_gates()
            eurolite_strobe.set_strobe_effect(rng.randint(34, 56))
            # Darker, more saturated colors - emphasize magenta/purple tones
            eurolite_strobe.set_color(rng.randint(60, 120), rng.randint(0, 40), rng.randint(80, 140))
    def _high_heavy_effects(self, rms, laser, strobe, spotlight, stinger, eurolite_strobe, profile, rng):
        logger.debug("HIGH-HEAVY EFFECT!")

        if strobe:
            strobe.set_warm_white(self._cap(200, profile.max_strobe_level))
            strobe.set_dimmer(self._cap(220, profile.max_dimmer_level))
            strobe.set_strobe(self._cap(rng.randint(50, 75), profile.max_strobe_level))  # Reduced
            strobe.set_color(100)
        if spotlight:
            spotlight.set_color_rgb(
                rng.randint(100, 255),
                rng.randint(100, 255),
                rng.randint(200, 255),
                rng.randint(100, 255),
            )
            spotlight.set_brightness(self._cap(255, profile.max_dimmer_level))
            spotlight.set_strobe(rng.randint(224, 255))
        if laser:
            laser.set_mode_level(self._cap(rng.randint(180, 255), profile.max_laser_level))
            laser.color(rng.randint(193, 255))
            laser.pattern(rng.randint(200, 255))
            laser.speed(rng.randint(240, 255))
        if stinger:
            # HIGH: Maximum laser intensity
            stinger.set_show_mode(0)
            stinger.set_show_speed(220, sound_active=False)
            stinger.set_color_macro("fade2")
            stinger.set_led_strobe(self._cap(rng.randint(120, 200), profile.max_strobe_level))
            stinger.set_uv(self._cap(255, profile.max_uv_level))
            stinger.set_uv_chase(self._cap(rng.randint(90, 127), profile.max_uv_level), strobing=True)
            stinger.set_laser_output(
                strobe_speed=self._cap(rng.randint(120, 200), profile.max_laser_level),
                rotation_raw=self._cap(rng.randint(30, 60), profile.max_laser_level),
            )
            stinger.set_moonflower_rotation("ccw", speed=rng.randint(50, 80))
        if eurolite_strobe:
            eurolite_strobe.open_gates()
            eurolite_strobe.set_strobe_effect(rng.randint(128, 200))
            # Pure saturated blue with minimal other colors
            eurolite_strobe.set_color(rng.randint(0, 20), rng.randint(0, 20), 140)
class MegaComboEffectStrategy(EffectStrategy):
    priority = 80
    name = "mega_combo"
    def can_apply(self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile) -> bool:
        return (
            frame.rms >= thresholds.combo_threshold * 1.3
            and profile.enable_mega_combo
        )
    def apply(self, devices: Devices, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile, rng: random.Random) -> None:
        logger.debug(f"MEGA COMBO! RMS: {frame.rms:.1f}")
        strobe = devices.strobe
        spotlight = devices.spotlight
        laser = devices.laser
        stinger = devices.stinger
        if strobe:
            strobe.set_dimmer(self._cap(220, profile.max_dimmer_level))
            strobe.set_strobe(self._cap(120, profile.max_strobe_level))  # Reduced from 255
            strobe.set_color(70)
            strobe.set_warm_white(self._cap(200, profile.max_strobe_level))
        if spotlight:
            spotlight.set_color_rgb(255, 255, 255, 255)
            spotlight.set_brightness(self._cap(255, profile.max_dimmer_level))
            spotlight.set_strobe(self._cap(255, profile.max_strobe_level))
        if laser:
            laser.set_mode_level(self._cap(255, profile.max_laser_level))
            laser.color(rng.randint(193, 255))
            laser.pattern(rng.randint(200, 255))
            laser.speed(self._cap(255, profile.max_laser_level))
        if stinger:
            # MEGA COMBO: Everything maxed
            stinger.set_show_mode(0)
            stinger.set_show_speed(240, sound_active=True)
            stinger.set_color_macro("random")
            stinger.set_led_strobe(self._cap(220, profile.max_strobe_level))
            stinger.set_uv(self._cap(255, profile.max_uv_level))
            stinger.set_uv_chase(self._cap(127, profile.max_uv_level), strobing=True)
            stinger.set_laser_output(
                strobe_speed=self._cap(240, profile.max_laser_level),
                chase_speed=self._cap(60, profile.max_laser_level),
            )
            stinger.set_moonflower_rotation("ccw", speed=70)
class ComboEffectStrategy(EffectStrategy):
    priority = 70
    name = "combo"
    def can_apply(self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile) -> bool:
        return (
            frame.rms >= thresholds.combo_threshold
            and profile.enable_combo
        )
    def apply(self, devices: Devices, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile, rng: random.Random) -> None:
        logger.debug(f"COMBO EFFECT! RMS: {frame.rms:.1f}")
        combo_threshold = thresholds.combo_threshold
        intensity = min(1.0, frame.rms / combo_threshold) if combo_threshold > 0 else 0.5

        strobe = devices.strobe
        spotlight = devices.spotlight
        laser = devices.laser
        stinger = devices.stinger
        if strobe:
            strobe.set_warm_white(self._cap(int(150 + (intensity * 105)), profile.max_strobe_level))
            strobe.set_dimmer(self._cap(int(150 + (intensity * 105)), profile.max_dimmer_level))
            strobe.set_strobe(self._cap(rng.randint(32, 95), profile.max_strobe_level))
        if spotlight:
            spotlight.random_color()
            spotlight.set_brightness(self._cap(int(200 + (intensity * 55)), profile.max_dimmer_level))
            spotlight.set_strobe(self._cap(int(150 + (intensity * 105)), profile.max_strobe_level))
        if laser:
            laser.set_mode_level(self._cap(int(150 + (intensity * 105)), profile.max_laser_level))
            laser.color(rng.randint(64, 192))
            laser.pattern(rng.randint(100, 200))
            laser.speed(self._cap(int(200 + (intensity * 55)), profile.max_laser_level))
        if stinger:
            if intensity > 0.8:
                # COMBO HIGH: Laser active
                stinger.set_show_mode(0)
                stinger.set_show_speed(int(180 + (intensity * 60)), sound_active=False)
                stinger.set_color_macro("fade2")
                stinger.set_led_strobe(self._cap(int(140 + (intensity * 100)), profile.max_strobe_level))
                stinger.set_uv(self._cap(255, profile.max_uv_level))
                stinger.set_uv_chase(self._cap(int(intensity * 127), profile.max_uv_level), strobing=True)
                stinger.set_laser_output(strobe_speed=0, rotation_raw=0)  # No laser
                stinger.set_moonflower_rotation("ccw", speed=int(45 + intensity * 25))
            elif intensity > 0.5:
                # COMBO MID: Smooth moonflower only
                stinger.set_show_mode(0)
                stinger.set_color_macro("fade2")  # Smooth color blending
                stinger.set_led_strobe(0)  # NO strobe
                stinger.set_uv(self._cap(int(200 + (intensity * 55)), profile.max_uv_level))
                stinger.set_uv_chase(self._cap(int(100 + (intensity * 27)), profile.max_uv_level), strobing=False)
                stinger.set_laser_output(strobe_speed=0, rotation_raw=0)
                stinger.set_moonflower_rotation("cw", speed=int(35 + intensity * 30))
class StrobeEffectStrategy(EffectStrategy):
    priority = 60
    name = "strobe"
    def can_apply(self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile) -> bool:
        return (
            frame.rms >= thresholds.strobe_threshold
            and profile.enable_strobe_only
        )
    def apply(self, devices: Devices, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile, rng: random.Random) -> None:
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
                strobe.set_warm_white(self._cap(int(180 + (min(effect_intensity, 1.0) * 75)), profile.max_strobe_level))
                strobe.set_dimmer(self._cap(255, profile.max_dimmer_level))
                strobe.set_strobe(self._cap(int(150 + (effect_intensity * 105)), profile.max_strobe_level))
            else:
                # Turn off strobe if intensity drops
                strobe.set_dimmer(0)
                strobe.set_strobe(0)
        if spotlight:
            if effect_intensity > 1.2:
                spotlight.set_brightness(self._cap(255, profile.max_dimmer_level))
                spotlight.set_strobe(self._cap(int(64 + min(95, effect_intensity * 95)), profile.max_strobe_level))
                spotlight.random_color()
            else:
                spotlight.set_brightness(0)
                spotlight.set_strobe(0)
        if laser:
            laser.set_mode_level(self._cap(int(80 + (effect_intensity * 120)), profile.max_laser_level))
            laser.color(rng.randint(30, 100))
            laser.pattern(rng.randint(50, 150))
            laser.speed(self._cap(int(150 + (effect_intensity * 80)), profile.max_laser_level))
        if stinger:
            if effect_intensity > 0.7:
                # STROBE HIGH: Laser + heavy strobing
                stinger.set_show_mode(0)
                stinger.set_show_speed(int(180 + (effect_intensity * 60)), sound_active=False)
                stinger.set_color_macro("change")
                stinger.set_led_strobe(self._cap(int(120 + (effect_intensity * 120)), profile.max_strobe_level))
                stinger.set_uv(self._cap(int(200 + (effect_intensity * 55)), profile.max_uv_level))
                stinger.set_uv_chase(self._cap(int(60 + (effect_intensity * 67)), profile.max_uv_level), strobing=True)
                stinger.set_laser_output(strobe_speed=0, rotation_raw=0)  # No laser
                stinger.set_moonflower_rotation("ccw", speed=int(45 + effect_intensity * 25))
            else:
                # STROBE LOW: Smooth moonflower only
                stinger.set_show_mode(0)
                stinger.set_show_speed(int(130 + (effect_intensity * 50)), sound_active=False)
                stinger.set_color_macro("fade1")
                stinger.set_led_strobe(0)  # NO strobe
                stinger.set_uv(self._cap(int(200 + (effect_intensity * 55)), profile.max_uv_level))
                stinger.set_uv_chase(self._cap(int(100 + (effect_intensity * 27)), profile.max_uv_level), strobing=False)
                stinger.set_laser_output(strobe_speed=0, rotation_raw=0)
                stinger.set_moonflower_rotation("cw", speed=int(35 + effect_intensity * 30))
class AmbientEffectStrategy(EffectStrategy):
    priority = 50
    name = "ambient"
    def can_apply(self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile) -> bool:
        return (
            frame.rms >= thresholds.min_threshold * 1.5
            and profile.enable_ambient
        )
    def apply(self, devices: Devices, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile, rng: random.Random) -> None:
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
            laser.set_mode_level(self._cap(int(50 + (frame.rms / min_threshold) * 50), profile.max_laser_level))
            laser.color(rng.randint(64, 127))
            laser.pattern(rng.randint(0, 100))
            laser.speed(self._cap(rng.randint(100, 150), profile.max_laser_level))
        if stinger:
            # AMBIENT: Smooth moonflower
            stinger.set_show_mode(0)
            stinger.set_color_macro(rng.choice(["fade1", "fade2"]))  # Smooth color blending
            stinger.set_led_strobe(0)  # NO strobe
            stinger.set_uv(self._cap(int(180 + (frame.rms / min_threshold) * 75), profile.max_uv_level))
            stinger.set_uv_chase(rng.randint(100, 120), strobing=False)
            stinger.set_laser_output(strobe_speed=0, rotation_raw=0)
            stinger.set_moonflower_rotation("cw", speed=rng.randint(30, 55))
        if eurolite_strobe:
            eurolite_strobe.open_gates()
            eurolite_strobe.set_strobe_effect(255)  # Solid on
            eurolite_strobe.set_color(rng.randint(50, 150), rng.randint(50, 150), rng.randint(50, 150))
class SubtleEffectStrategy(EffectStrategy):
    priority = 40
    name = "subtle"
    def can_apply(self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile) -> bool:
        return (
            frame.rms >= thresholds.min_threshold
            and profile.enable_subtle
        )
    def apply(self, devices: Devices, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile, rng: random.Random) -> None:
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
                laser.set_mode_level(int(30 + (frame.rms / min_threshold) * 40))
                laser.color(rng.randint(0, 63))
                laser.pattern(rng.randint(0, 60))
            else:
                laser.set_mode_level(0)
        if stinger:
            if frame.rms > min_threshold * 0.8:  # Lower but reasonable threshold
                # SUBTLE: Gentle moonflower
                stinger.set_show_mode(0)
                stinger.set_color_macro("fade1")  # Smooth color blending
                stinger.set_led_strobe(0)  # NO strobe
                stinger.set_uv(rng.randint(180, 230))
                stinger.set_uv_chase(rng.randint(90, 115), strobing=False)
                stinger.set_laser_output(strobe_speed=0, rotation_raw=0)
                stinger.set_moonflower_rotation("cw", speed=rng.randint(25, 50))
            else:
                stinger.blackout()
        if eurolite_strobe:
            if frame.rms > min_threshold * 1.2:
                eurolite_strobe.open_gates()
                eurolite_strobe.set_strobe_effect(255)
                eurolite_strobe.set_color(rng.randint(20, 100), rng.randint(20, 100), rng.randint(20, 100))
            else:
                eurolite_strobe.set_dimmer(0)
class SilenceEffectStrategy(EffectStrategy):
    priority = 0
    name = "silence"

    def __init__(self):
        super().__init__()
        self.silence_start_time: Optional[float] = None

    def can_apply(self, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile) -> bool:
        return True  # Always applicable as fallback

    def apply(self, devices: Devices, frame: AudioFrame, thresholds: Thresholds, profile: ShowProfile, rng: random.Random) -> None:
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
            # Prefer explicit off to avoid leaving the fixture in sound/auto.
            try:
                laser.set_mode("off")
            except Exception:
                pass
            laser.set_mode_level(0)
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
    def apply_effects(
        self,
        frame: AudioFrame,
        thresholds: Thresholds,
        devices: Devices,
    ) -> Optional[str]:
        """Apply effects for a frame."""

        # Log low-latency metric if beat detected
        if frame.beat_detected and frame.rms > thresholds.min_threshold and self.profile.enable_beat:
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
