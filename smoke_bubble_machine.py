import random

from base_dmx import BaseDMX


class SmokeBubbleMachine(BaseDMX):
    # BeamZ SB2000LED smoke + bubble machine (see
    # manuals/160.524_160.527-Smoke-Bubble-machine_manual_V1.6.pdf), 9-channel
    # DMX mode: 0 smoke output, 1 fan, 2 bubble wheel speed, 3 LED master
    # dimmer, 4-6 LED red/green/blue, 7 LED strobe, 8 auto program.
    #
    # Channel 8 (auto program) must stay at 0 ("manual") or the fixture runs
    # its own built-in chase instead of the dimmer/colour values below - the
    # same manual-mode requirement as this rig's Laser mode channel and
    # Spotlight macro channel.
    def __init__(self, dmx_channel: int = 55) -> None:
        super().__init__(dmx_channel, num_channels=9)
        self.current_brightness = 0

    def set_smoke(self, value: int) -> None:
        """Set smoke output (channel 1, 0-100%)."""
        self._send(0, max(0, min(255, value)))

    def set_fan(self, value: int) -> None:
        """Set fan speed, low to high (channel 2)."""
        self._send(1, max(0, min(255, value)))

    def set_bubble_speed(self, value: int) -> None:
        """Set bubble wheel rotation speed (channel 3).

        0 stops the wheel. The hardware's actual "on" range is 010-255, so
        any nonzero request is floored to 10 to avoid landing in the
        009-and-below dead zone where the wheel doesn't turn.
        """
        value = max(0, min(255, value))
        if value <= 0:
            self._send(2, 0)
            return
        self._send(2, max(10, value))

    def set_dimmer(self, value: int) -> None:
        """Set the LED master dimmer (channel 4, 0-100%)."""
        value = max(0, min(255, value))
        self.current_brightness = value
        self._send(3, value)

    def set_color_rgb(self, red: int, green: int, blue: int) -> None:
        """Set the LED colour (channels 5-7)."""
        self._send(4, max(0, min(255, red)))
        self._send(5, max(0, min(255, green)))
        self._send(6, max(0, min(255, blue)))

    def set_strobe(self, value: int) -> None:
        """Set the LED strobe speed, slow to fast (channel 8, 0 = steady)."""
        self._send(7, max(0, min(255, value)))

    def set_auto_program(self, value: int) -> None:
        """Set the built-in auto/sound-active program (channel 9).

        Leave at 0 whenever set_dimmer/set_color_rgb should take effect -
        see the manual-mode note on the class docstring above.
        """
        self._send(8, max(0, min(255, value)))

    def random_color(self) -> None:
        """Set a random vibrant LED colour."""
        self.set_color_rgb(
            random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
        )

    def fade_off(self, step: int = 12) -> None:
        """Step the LED dimmer down toward 0 instead of cutting abruptly."""
        new_brightness = max(0, self.current_brightness - step)
        self.set_dimmer(new_brightness)

    def fade_in(self, target: int, step: int = 40) -> None:
        """Step the LED dimmer up toward *target* instead of snapping instantly."""
        new_brightness = min(target, self.current_brightness + step)
        self.set_dimmer(new_brightness)

    def turn_off(self) -> None:
        """Turn off smoke, bubbles, fan, and LEDs."""
        self.set_smoke(0)
        self.set_fan(0)
        self.set_bubble_speed(0)
        self.set_dimmer(0)
        self.set_color_rgb(0, 0, 0)
        self.set_strobe(0)
        self.set_auto_program(0)
        self.current_brightness = 0

    def reset(self) -> None:
        """Reset the fixture to default (off) state."""
        self.turn_off()
