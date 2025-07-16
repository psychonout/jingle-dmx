import time
from random import randint

from loguru import logger

from base_dmx import BaseDMX


class Strobe(BaseDMX):
    def __init__(self):
        """Initialize Strobe with specific device index"""
        super().__init__()

    def set_dimmer(self, value: int | None = None) -> None:
        self._send(1, value)

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
        self._send(2, value)

    def set_warm_white(self, value: int) -> None:
        self._send(3, value)

    def set_cold_white(self, value: int) -> None:
        self._send(4, value)

    def set_color(self, value: int) -> None:
        self._send(5, value)

    def set_macro(self, value: int) -> None:
        self._send(6, value)

    def set_macro_speed(self, value: int) -> None:
        self._send(7, value)

    def reset(self) -> None:
        """Reset the strobe device to default settings."""
        self.set_dimmer(0)
        self.set_strobe(0)
        self.set_warm_white(0)
        self.set_cold_white(0)
        self.set_color(0)
        self.set_macro(0)
        self.set_macro_speed(0)

if __name__ == "__main__":
    with Strobe() as strobe:
        strobe.reset()
