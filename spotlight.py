import random
import time

from base_dmx import BaseDMX


class Spotlight(BaseDMX):
    # This is a BeamZ BT430 PAR strobe (see manuals/bt430.pdf), run in its
    # 7-channel DMX mode. It has no RGB - only warm/cold white LEDs - and
    # its real channel layout is: 0 dimmer, 1 strobe, 2 warm white,
    # 3 cold white, 4 colour temperature, 5 macro run, 6 macro run speed.
    # Channel 4 (colour temp) and 5 (macro run) must stay at 0 ("no
    # function") or the fixture ignores the warm/cold levels below and
    # runs its own auto/sound-reactive program instead.
    def __init__(self, dmx_channel: int = 22) -> None:
        super().__init__(dmx_channel, num_channels=7)
        self.current_color = (0, 0, 0, 0)  # R, G, B, W (approximated - see set_color_rgb)
        self.current_brightness = 0

    def set_brightness(self, value: int) -> None:
        """Set the master dimmer."""
        value = max(0, min(255, value))
        self.current_brightness = value
        self._send(0, value)

    def fade_off(self, step: int = 12) -> None:
        """Step brightness down toward 0 instead of cutting abruptly.

        Call once per frame while fading; safe to keep calling once it
        reaches 0. Strobing stops immediately so the fade reads as a
        smooth dim rather than a flicker trailing off.
        """
        self.set_strobe(0)
        new_brightness = max(0, self.current_brightness - step)
        self.set_brightness(new_brightness)

    def fade_in(self, target: int, step: int = 40) -> None:
        """Step brightness up toward *target* instead of snapping instantly.

        Only smooths the rising edge - if already at or above target it
        holds steady immediately, so this is safe to call every frame in
        place of set_brightness().
        """
        new_brightness = min(target, self.current_brightness + step)
        self.set_brightness(new_brightness)

    def set_strobe(self, value: int) -> None:
        """Set the strobe effect (0 = steady, higher = faster strobe)."""
        if value <= 0:
            self._send(1, 0)
            return
        # Map onto the fixture's "064-095 strobe effect slow to fast" band
        # so any 0-255 intensity produces an actual strobe, not one of the
        # hardware's "full on"/"no function" plateaus.
        self._send(1, 64 + int(min(255, value) / 255 * 31))

    def set_red(self, value: int) -> None:
        """Set the warm white channel (used as this fixture's "red").

        This fixture's warm LEDs read visibly dimmer than the cold ones at
        the same DMX value, so boost the warm output to compensate.
        """
        self._send(2, min(255, int(value * 1.3)))

    def set_cold_white(self, value: int) -> None:
        """Set the cold white channel, capped to 66% of current brightness."""
        cap = int(self.current_brightness * 0.66)
        self._send(3, min(value, cap))

    def set_macro(self, value: int) -> None:
        """Set the macro run program (0 = manual/off)."""
        self._send(5, value)

    def set_macro_speed(self, value: int) -> None:
        """Set the speed of the macro run program."""
        self._send(6, value)

    def set_color_rgb(self, red: int, green: int, blue: int, white: int = 0) -> None:
        """Approximate an RGB+W color as a warm/cold white mix.

        The fixture can't produce hue - only blend warm and cold white -
        so this biases red/warm inputs toward the warm channel and
        blue/cool inputs toward the cold channel.
        """
        # Keep colour temp and macro run in manual mode so the warm/cold
        # levels below actually take effect instead of being overridden.
        self._send(4, 0)
        self.set_macro(0)
        self.set_macro_speed(0)

        warm = min(255, int(red + green * 0.2 + white * 0.5))
        cold = min(255, int(blue * 0.8 + green * 0.2 + white * 0.5))
        self.set_red(warm)
        self.set_cold_white(cold)
        self.current_color = (red, green, blue, white)

    def set_color_preset(self, preset: str) -> None:
        """Set predefined color presets."""
        presets = {
            "red": (255, 0, 0, 0),
            "green": (0, 255, 0, 0),
            "blue": (0, 0, 255, 0),
            "white": (0, 0, 0, 255),
            "yellow": (255, 255, 0, 0),
            "cyan": (0, 255, 255, 0),
            "magenta": (255, 0, 255, 0),
            "orange": (255, 128, 0, 0),
            "pink": (255, 0, 128, 0),
            "purple": (128, 0, 255, 0),
            "warm_white": (255, 200, 100, 100),
            "cool_white": (200, 255, 255, 150),
        }

        if preset in presets:
            r, g, b, w = presets[preset]
            self.set_color_rgb(r, g, b, w)

    def random_color(self) -> None:
        """Set a random vibrant color."""
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        w = random.randint(0, 100)  # Less white for more vibrant colors
        self.set_color_rgb(r, g, b, w)

    def turn_on(self, brightness: int = 255) -> None:
        """Turn on spotlight with specified brightness."""
        self.set_brightness(brightness)
        self.current_brightness = brightness

    def turn_off(self) -> None:
        """Turn off spotlight."""
        self.set_brightness(0)
        self.set_color_rgb(0, 0, 0, 0)
        self.set_strobe(0)
        self.set_macro(0)
        self.set_macro_speed(0)
        self.current_brightness = 0

    def reset(self) -> None:
        """Reset the spotlight to default state."""
        self.turn_off()

    def flash_color(self, color_preset: str, duration: float = 0.3) -> None:
        """Flash a specific color briefly."""
        self.set_color_preset(color_preset)
        self.set_brightness(255)
        time.sleep(duration)
        self.turn_off()

    def strobe_effect(self, speed: int = 128, duration: float = 2.0) -> None:
        """Activate strobe effect for specified duration."""
        self.set_strobe(speed)
        self.set_brightness(255)
        time.sleep(duration)
        self.set_strobe(0)

    def rainbow_cycle(self, speed: int = 100) -> None:
        """Cycle through rainbow colors."""
        colors = [
            "red",
            "orange",
            "yellow",
            "green",
            "cyan",
            "blue",
            "purple",
            "magenta",
        ]
        for color in colors:
            self.set_color_preset(color)
            self.set_brightness(255)
            time.sleep(0.2)

    def pulse_effect(self, color_preset: str = "white", cycles: int = 3) -> None:
        """Pulse effect with specified color."""
        self.set_color_preset(color_preset)

        for _ in range(cycles):
            # Fade in
            for brightness in range(0, 256, 20):
                self.set_brightness(brightness)
                time.sleep(0.02)

            # Fade out
            for brightness in range(255, -1, -20):
                self.set_brightness(brightness)
                time.sleep(0.02)

    def shuffle_all_fast(self) -> None:
        """Fast chaotic effect with random colors, strobe, and macro."""
        self.random_color()
        self.set_brightness(255)
        self.set_strobe(random.randint(200, 255))  # Fast strobe
        self.set_macro(random.randint(1, 255))
        self.set_macro_speed(random.randint(200, 255))  # Fast macro speed

    def shuffle_all_slow(self) -> None:
        """Slower, more controlled effect."""
        self.random_color()
        self.set_brightness(random.randint(150, 255))
        self.set_strobe(random.randint(50, 150))  # Moderate strobe
        self.set_macro(random.randint(1, 100))
        self.set_macro_speed(random.randint(50, 150))  # Moderate macro speed

    def music_reactive_color(self, volume: float, max_volume: float = 200) -> None:
        """Color that reacts to music volume."""
        # Normalize volume to 0-1
        normalized_volume = min(volume / max_volume, 1.0)

        # Map volume to color intensity
        if normalized_volume < 0.3:
            # Low volume: cool colors
            self.set_color_rgb(
                0, int(normalized_volume * 255), int(normalized_volume * 255), 0
            )
        elif normalized_volume < 0.7:
            # Medium volume: warm colors
            self.set_color_rgb(
                int(normalized_volume * 255), int(normalized_volume * 200), 0, 0
            )
        else:
            # High volume: hot colors
            self.set_color_rgb(255, int((1 - normalized_volume) * 255), 0, 0)

        # Set brightness based on volume
        self.set_brightness(int(normalized_volume * 255))

    def bass_impact_effect(self, intensity: float = 1.0) -> None:
        """Special effect for bass hits."""
        # Intense white flash
        self.set_color_rgb(255, 255, 255, 255)
        self.set_brightness(255)
        self.set_strobe(255)  # Maximum strobe

        # Brief duration based on intensity
        time.sleep(0.1 * intensity)

        # Quick fade to red
        self.set_color_rgb(255, 0, 0, 0)
        self.set_strobe(0)

    def ambient_mode(self, volume: float) -> None:
        """Subtle ambient lighting that responds to music."""
        # Soft, warm colors that gently respond to music
        base_brightness = 50
        volume_brightness = min(int(volume * 2), 100)  # Subtle volume response

        # More varied color palette with reds and random elements
        # Using time to slowly cycle through base colors
        t = time.time() * 0.2  # Slow cycle

        # Generate a slowly changing color
        import math

        r = int(127 + 127 * math.sin(t))
        g = int(127 + 127 * math.sin(t + 2.0))
        b = int(127 + 127 * math.sin(t + 4.0))

        # Bias towards red/warm colors for ambient
        r = min(255, int(r * 1.2))
        b = int(b * 0.7)  # Reduce blue

        # Add some white for softness
        w = 30

        self.set_color_rgb(r, g, b, w)
        self.set_strobe(0)
        self.set_brightness(base_brightness + volume_brightness)
