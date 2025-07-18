from base_dmx import BaseDMX


class Strobe(BaseDMX):
    def __init__(self, dmx_channel: int = 11) -> None:
        """Initialize Strobe with specific device index"""
        super().__init__(dmx_channel)

    def set_dimmer(self, value: int | None = None) -> None:
        self._send(0, value)

    def set_strobe(self, value: int | None = None) -> None:
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
