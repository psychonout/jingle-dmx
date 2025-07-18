import time
from random import randint

from loguru import logger

from dynamic_thresholds import AdaptiveThresholds
from laser import Laser
from light_strip import VUMeter
from spotlight import Spotlight
from strobe import Strobe
from usb_mic import USBMicrophone  # Use enhanced microphone


def main():
    """Enhanced main function with better microphone input processing"""
    logger.debug("Starting enhanced audio-reactive light show...")

    # Initialize dynamic threshold system
    threshold_system = AdaptiveThresholds(
        smoothing_factor=0.95, sensitivity=3, min_change_threshold=5.0
    )

    max_vol = 0
    effect_cooldown = 0
    beat_effect_cooldown = 0
    frequency_effect_cooldown = 0

    with USBMicrophone(
        enable_frequency_analysis=True, enable_beat_detection=True
    ) as usb_mic:
        if not usb_mic.is_open:
            logger.error("Failed to open enhanced USB microphone")
            return

        with (
            Strobe() as strobe,
            Spotlight() as spotlight,
            Laser() as laser,
            VUMeter(brightness=0.3, decay_rate=0.85, auto_scale=True) as vu_meter,
        ):
            strobe.set_dimmer(255)
            spotlight.set_brightness(0)  # Start with spotlight off
            spotlight.set_strobe(0)

            # Initialize laser with manual mode for full control
            laser.set_mode("manual")
            laser.set_mode_level(0)  # Start with laser off
            laser.color(0)  # Start with red
            laser.pattern(0)  # Start with basic pattern

            logger.info("Starting enhanced audio-reactive show...")

            # Log initial thresholds
            min_thresh, strobe_thresh, combo_thresh = threshold_system.get_thresholds()
            logger.info(
                f"Initial thresholds - Min: {min_thresh:.1f}, "
                f"Strobe: {strobe_thresh:.1f}, Combo: {combo_thresh:.1f}"
            )

            while True:
                # Get enhanced audio data from the unified read() method
                audio_data = usb_mic.read()

                # Extract the enhanced data
                rms = audio_data["rms"]
                peak = audio_data["peak"]
                beat_detected = audio_data["beat_detected"]

                # Get frequency band energies
                bass_energy = usb_mic.get_bass_energy()
                mid_energy = usb_mic.get_mid_energy()
                high_energy = usb_mic.get_high_energy()

                # Update threshold system with RMS instead of simple volume
                threshold_system.update(rms)
                min_threshold, strobe_threshold, combo_threshold = (
                    threshold_system.get_thresholds()
                )

                # Update VU meter with RMS for better visual representation
                vu_meter.update(rms)

                if rms > max_vol:
                    max_vol = rms
                    logger.debug(f"New max RMS: {max_vol:.1f}")

                # Reduce cooldowns
                if effect_cooldown > 0:
                    effect_cooldown -= 1
                if beat_effect_cooldown > 0:
                    beat_effect_cooldown -= 1
                if frequency_effect_cooldown > 0:
                    frequency_effect_cooldown -= 1

                # BEAT-TRIGGERED EFFECTS (highest priority)
                if beat_detected and beat_effect_cooldown == 0:
                    logger.debug(f"BEAT TRIGGERED! RMS: {rms:.1f}, Peak: {peak:.1f}")

                    # Intense beat effect - strobe
                    strobe.set_strobe(randint(200, 255))
                    strobe.set_color(randint(0, 255))
                    strobe.set_macro(randint(180, 255))

                    # Intense beat effect - spotlight
                    spotlight.random_color()
                    spotlight.set_brightness(255)
                    spotlight.set_strobe(randint(200, 255))
                    spotlight.set_macro(randint(180, 255))
                    spotlight.set_macro_speed(randint(200, 255))

                    # Intense beat effect - laser (explosive patterns)
                    laser.set_mode_level(randint(200, 255))  # Maximum intensity
                    laser.pattern(
                        randint(128, 255)
                    )  # Complex patterns (dots and wireless strips)
                    laser.color(randint(128, 255))  # Auto color mixing for chaos
                    laser.speed(randint(220, 255))  # Maximum speed
                    laser.zoom(randint(220, 255))  # Fast zoom effects
                    # Quick movement for beat sync
                    laser.horizontal_position(randint(0, 127))
                    laser.vertical_position(randint(0, 127))

                    beat_effect_cooldown = 8  # Prevent beat spam

                # FREQUENCY-BASED EFFECTS
                elif frequency_effect_cooldown == 0:
                    total_energy = bass_energy + mid_energy + high_energy

                    if total_energy > 1000:  # Threshold for frequency effects
                        bass_ratio = (
                            bass_energy / total_energy if total_energy > 0 else 0
                        )
                        mid_ratio = mid_energy / total_energy if total_energy > 0 else 0
                        high_ratio = (
                            high_energy / total_energy if total_energy > 0 else 0
                        )

                        logger.debug(
                            f"Frequency ratios - Bass: {bass_ratio:.2f}, Mid: {mid_ratio:.2f}, High: {high_ratio:.2f}"
                        )

                        # Bass-heavy music
                        if bass_ratio > 0.5:
                            logger.debug("BASS-HEAVY EFFECT!")
                            strobe.set_strobe(randint(64, 127))  # Slower, more rhythmic
                            strobe.set_color(
                                randint(0, 50)
                            )  # Warmer colors (reds/oranges)
                            strobe.set_macro(randint(100, 150))

                            # Bass spotlight effect - warm, pulsing
                            spotlight.set_color_rgb(
                                255, randint(100, 200), randint(0, 50), 0
                            )  # Red/orange
                            spotlight.set_brightness(randint(200, 255))
                            spotlight.set_strobe(randint(50, 100))  # Slower pulse
                            spotlight.set_macro(randint(100, 150))

                            # Bass laser effect - warm colors, rhythmic patterns
                            laser.set_mode_level(randint(150, 200))
                            laser.color(randint(0, 63))  # Monochrome warm colors (reds)
                            laser.pattern(randint(0, 127))  # Lines and dots patterns
                            laser.speed(randint(150, 200))  # Moderate speed
                            laser.size(randint(40, 63))  # Medium to large size
                            # Slow rhythmic movement
                            laser.horizontal_speed(randint(128, 180))
                            laser.vertical_speed(randint(128, 180))

                        # Mid-heavy music (vocals, instruments)
                        elif mid_ratio > 0.4:
                            logger.debug("MID-HEAVY EFFECT!")
                            strobe.set_strobe(randint(96, 159))  # Medium speed
                            strobe.set_color(randint(80, 180))  # Mid-range colors
                            strobe.set_macro(randint(50, 150))

                            # Mid spotlight effect - balanced colors
                            spotlight.set_color_rgb(
                                randint(100, 255),
                                randint(100, 255),
                                randint(50, 150),
                                randint(0, 50),
                            )
                            spotlight.set_brightness(randint(150, 220))
                            spotlight.set_strobe(randint(80, 130))
                            spotlight.set_macro(randint(50, 150))

                            # Mid laser effect - balanced colors and movement
                            laser.set_mode_level(randint(120, 180))
                            laser.color(randint(64, 127))  # Color mixing for variety
                            laser.pattern(randint(64, 191))  # Mix of pattern types
                            laser.speed(randint(180, 220))  # Medium-fast speed
                            laser.size(randint(20, 50))  # Medium size
                            # Balanced movement
                            laser.horizontal_angle(randint(30, 90))
                            laser.vertical_angle(randint(30, 90))

                        # High-heavy music (cymbals, treble)
                        elif high_ratio > 0.3:
                            logger.debug("HIGH-HEAVY EFFECT!")
                            strobe.set_strobe(randint(128, 191))  # Faster strobe
                            strobe.set_color(
                                randint(200, 255)
                            )  # Cooler colors (blues/whites)
                            strobe.set_macro(randint(200, 255))

                            # High spotlight effect - bright, fast, cool colors
                            spotlight.set_color_rgb(
                                randint(0, 100),
                                randint(150, 255),
                                255,
                                randint(100, 200),
                            )  # Blue/white
                            spotlight.set_brightness(255)
                            spotlight.set_strobe(randint(150, 200))  # Fast strobe
                            spotlight.set_macro(randint(200, 255))
                            spotlight.set_macro_speed(randint(200, 255))

                            # High laser effect - sharp, fast, bright patterns
                            laser.set_mode_level(randint(180, 255))
                            laser.color(randint(193, 255))  # Auto bright colors
                            laser.pattern(
                                randint(200, 255)
                            )  # Complex wireless strip patterns
                            laser.speed(randint(240, 255))  # Maximum speed
                            laser.size(randint(0, 20))  # Small, sharp beams
                            # Fast, sharp movements
                            laser.horizontal_speed(randint(200, 255))
                            laser.vertical_speed(randint(200, 255))
                            laser.shrink(randint(150, 196))  # Fast shrinking effects

                        frequency_effect_cooldown = 5

                # MEGA COMBO effects for extremely loud sounds
                elif rms >= combo_threshold * 1.3 and effect_cooldown == 0:
                    logger.debug(
                        f"MEGA COMBO! RMS: {rms:.1f} (threshold: {combo_threshold * 1.3:.1f})"
                    )

                    # Use peak level for intensity calculation
                    intensity = min(1.0, peak / (max_vol * 0.8)) if max_vol > 0 else 0.5

                    # Maximum intensity effects - strobe
                    strobe.set_strobe(randint(220, 255))
                    strobe.set_color(randint(0, 255))
                    strobe.set_macro(randint(200, 255))

                    # Maximum intensity effects - spotlight
                    spotlight.shuffle_all_fast()  # Use built-in chaotic effect

                    # MEGA laser effect - complete chaos mode
                    laser.set_mode_level(255)  # Maximum intensity
                    laser.color(randint(193, 255))  # Full auto color chaos
                    laser.pattern(randint(200, 255))  # Most complex patterns
                    laser.speed(255)  # Maximum speed
                    laser.zoom(255)  # Maximum zoom speed
                    # Chaotic movement in all directions
                    laser.horizontal_speed(255)
                    laser.vertical_speed(255)
                    laser.rotate(randint(0, 127))  # Random rotation
                    laser.enlarge(randint(100, 127))  # Fast enlarging
                    laser.size(randint(0, 10))  # Very sharp beams

                    effect_cooldown = 10

                # Combined effects for very loud sounds
                elif rms >= combo_threshold and effect_cooldown == 0:
                    logger.debug(
                        f"COMBO EFFECT! RMS: {rms:.1f} (threshold: {combo_threshold:.1f})"
                    )

                    # Calculate intensity based on RMS vs threshold
                    intensity = (
                        (rms - combo_threshold) / (max_vol - combo_threshold)
                        if max_vol > combo_threshold
                        else 0.5
                    )

                    # Adaptive effects based on intensity - strobe
                    strobe_speed = int(192 + (intensity * 31))  # 192-223 range
                    strobe.set_strobe(strobe_speed)
                    strobe.set_color(randint(0, 255))
                    strobe.set_macro(randint(int(intensity * 100), 255))

                    # Adaptive effects based on intensity - spotlight
                    spotlight.random_color()
                    spotlight.set_brightness(
                        int(200 + (intensity * 55))
                    )  # 200-255 range
                    spotlight.set_strobe(int(150 + (intensity * 105)))  # 150-255 range
                    spotlight.set_macro(randint(int(intensity * 150), 255))
                    spotlight.set_macro_speed(int(150 + (intensity * 105)))

                    # Adaptive laser effects based on intensity
                    laser.set_mode_level(int(150 + (intensity * 105)))  # 150-255 range
                    laser.color(randint(64, 192))  # Color mixing to auto
                    laser.pattern(randint(100, 200))  # Progressive pattern complexity
                    laser.speed(int(200 + (intensity * 55)))  # 200-255 speed
                    laser.size(
                        int(40 - (intensity * 30))
                    )  # Smaller as intensity increases
                    # Dynamic movement based on intensity
                    movement_speed = int(150 + (intensity * 105))
                    laser.horizontal_speed(movement_speed)
                    laser.vertical_speed(movement_speed)
                    if intensity > 0.7:
                        laser.zoom(randint(200, 240))  # Add zoom for high intensity

                    effect_cooldown = 6

                # Strobe effects for moderately loud sounds
                elif rms >= strobe_threshold and effect_cooldown == 0:
                    logger.debug(
                        f"STROBE EFFECT! RMS: {rms:.1f} (threshold: {strobe_threshold:.1f})"
                    )

                    # Use both RMS and peak for effect calculation
                    rms_ratio = rms / strobe_threshold
                    peak_ratio = peak / (max_vol * 0.6) if max_vol > 0 else 0.5

                    # Combine RMS and peak for more dynamic effects
                    effect_intensity = (rms_ratio + peak_ratio) / 2

                    strobe_value = int(
                        64 + min(95, effect_intensity * 95)
                    )  # 64-159 range
                    strobe.set_strobe(strobe_value)
                    strobe.set_color(randint(0, 255))

                    # Spotlight moderate effects
                    spotlight.music_reactive_color(
                        rms, max_vol
                    )  # Use built-in music reactive color
                    spotlight.set_strobe(
                        int(32 + min(95, effect_intensity * 95))
                    )  # Gentler strobe
                    if effect_intensity > 0.7:
                        spotlight.set_macro(randint(50, 150))

                    # Moderate laser effects - reactive to music
                    laser_intensity = int(80 + (effect_intensity * 120))  # 80-200 range
                    laser.set_mode_level(laser_intensity)
                    laser.color(randint(30, 100))  # Moderate color range
                    laser.pattern(randint(50, 150))  # Moderate patterns
                    laser.speed(int(150 + (effect_intensity * 80)))  # 150-230 speed
                    laser.size(int(50 - (effect_intensity * 30)))  # 20-50 size range
                    # Moderate movement
                    if effect_intensity > 0.5:
                        laser.horizontal_position(randint(20, 100))
                        laser.vertical_position(randint(20, 100))

                    effect_cooldown = 3

                # Ambient effects for moderate sounds
                elif rms >= min_threshold * 1.5:
                    logger.debug(f"AMBIENT EFFECT! RMS: {rms:.1f}")

                    # Gentle, continuous effects - strobe
                    strobe.set_strobe(randint(32, 95))
                    strobe.set_color(randint(100, 255))

                    # Gentle, continuous effects - spotlight (ambient mode)
                    spotlight.ambient_mode(rms)  # Use built-in ambient mode
                    spotlight.set_strobe(0)  # No strobe in ambient mode

                    # Gentle laser effects - smooth, flowing patterns
                    ambient_level = int(50 + (rms / min_threshold) * 50)  # 50-100 range
                    laser.set_mode_level(ambient_level)
                    laser.color(randint(64, 127))  # Gentle color mixing
                    laser.pattern(randint(0, 100))  # Simple patterns
                    laser.speed(randint(100, 150))  # Slow, smooth speed
                    laser.size(randint(30, 60))  # Medium size for ambient
                    # Slow, flowing movement
                    laser.horizontal_speed(randint(128, 160))
                    laser.vertical_speed(randint(128, 160))

                # Subtle effects for quiet sounds
                elif rms >= min_threshold:
                    logger.debug(f"SUBTLE EFFECT! RMS: {rms:.1f}")

                    # Very gentle effects - strobe
                    strobe.set_strobe(randint(32, 63))
                    strobe.set_color(randint(150, 255))

                    # Very gentle effects - spotlight
                    spotlight.set_color_rgb(
                        randint(100, 200),
                        randint(100, 200),
                        randint(150, 255),
                        randint(50, 150),
                    )  # Soft, cool colors
                    spotlight.set_brightness(
                        int(50 + (rms / min_threshold) * 50)
                    )  # 50-100 brightness
                    spotlight.set_strobe(0)  # No strobe for subtle effects

                    # Very subtle laser effects - gentle breathing patterns
                    subtle_level = int(30 + (rms / min_threshold) * 40)  # 30-70 range
                    laser.set_mode_level(subtle_level)
                    laser.color(randint(0, 63))  # Gentle monochrome colors
                    laser.pattern(randint(0, 60))  # Simple line patterns
                    laser.speed(randint(80, 120))  # Very slow speed
                    laser.size(randint(40, 63))  # Larger, softer beams
                    # Minimal movement for subtle effects
                    laser.horizontal_position(randint(40, 80))
                    laser.vertical_position(randint(40, 80))

                # Silence mode
                else:
                    if rms < min_threshold * 0.3:
                        strobe.set_strobe(0)
                        spotlight.set_brightness(0)  # Turn off spotlight in silence
                        spotlight.set_strobe(0)

                        # Turn off laser in deep silence
                        laser.set_mode_level(0)
                    else:
                        # Keep very gentle strobe
                        strobe.set_strobe(randint(32, 50))
                        strobe.set_color(randint(200, 255))

                        # Keep very gentle spotlight
                        spotlight.set_color_rgb(200, 200, 255, 100)  # Soft cool white
                        spotlight.set_brightness(30)
                        spotlight.set_strobe(0)

                        # Keep very gentle laser - standby mode
                        laser.set_mode_level(20)  # Very low intensity
                        laser.color(randint(0, 30))  # Warm standby colors
                        laser.pattern(randint(0, 30))  # Simple patterns
                        laser.speed(randint(64, 100))  # Very slow
                        laser.size(63)  # Large, soft beam
                        # Static position for standby
                        laser.horizontal_position(64)
                        laser.vertical_position(64)

                # Periodic logging
                if int(time.time()) % 5 == 0 and int(time.time() * 10) % 10 == 0:
                    logger.info(
                        f"Audio Analysis - RMS: {rms:.1f}, Peak: {peak:.1f}, "
                        f"Bass: {bass_energy:.0f}, Mid: {mid_energy:.0f}, High: {high_energy:.0f} | "
                        f"Thresholds - Min: {min_threshold:.1f}, Strobe: {strobe_threshold:.1f}, Combo: {combo_threshold:.1f}"
                    )

                # Small delay
                time.sleep(0.005)  # Slightly longer delay due to more processing


if __name__ == "__main__":
    main()
