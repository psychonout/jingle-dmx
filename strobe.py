from base_dmx import BaseDMX


class Strobe(BaseDMX):
    def __init__(self, dmx_channel: int = 11) -> None:
        """Initialize Strobe with specific device index"""
        super().__init__(dmx_channel, num_channels=7)
        self.current_dimmer = 0

    def set_dimmer(self, value: int) -> None:
        value = max(0, min(255, value))
        self.current_dimmer = value
        self._send(0, value)

    def fade_off(self, step: int = 12) -> None:
        """Step dimmer down toward 0 instead of cutting abruptly."""
        self.set_strobe(0)
        self.set_dimmer(max(0, self.current_dimmer - step))

    def fade_in(self, target: int, step: int = 40) -> None:
        """Step dimmer up toward *target* instead of snapping instantly."""
        self.set_dimmer(min(target, self.current_dimmer + step))

    def set_strobe(self, value: int) -> None:
        """
        Set the strobe effect.
        0-31 - Strobe off
        32-63 - Strobe full on
        64-95 - Simple strobe, increasing speed
        96-127 - Strobe full on
        128-159 - Pulse effect increasing speed
        160-191 - Strobe full on
        192-223 - Random strobe effect
        224-255 - Strobe full on
        """
        self._send(1, value)

    def set_warm_white(self, value: int) -> None:
        self._send(2, value)

    def set_cold_white(self, value: int) -> None:
        self._send(3, value)

    def set_color(self, value: int) -> None:
        self._send(4, value)

    def set_macro(self, value: int) -> None:
        self._send(5, value)

    def set_macro_speed(self, value: int) -> None:
        self._send(6, value)
