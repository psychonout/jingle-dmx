from base_dmx import BaseDMX
from loguru import logger


class EuroliteStrobe(BaseDMX):
    def __init__(self, dmx_channel: int = 44) -> None:
        """
        Initialize the Eurolite Strobe SMD PRO 132 with a specific DMX starting channel.

        :param dmx_channel: The starting DMX channel for this device.
        """
        super().__init__(dmx_channel, num_channels=6)

    def set_dimmer(self, value: int) -> None:
        """
        Set the dimmer intensity (Channel 1).

        :param value: DMX value (0-255) for dimmer intensity.
        """
        self._send(0, value)

    def set_strobe_effect(self, value: int) -> None:
        """
        Set the strobe effect (Channel 2).

        0-5  LEDs on
        6-10 LEDs off
        11-33 Random puls effect with increasing speed
        34-56 Random fade in with increasing speed
        57-79 Random fade out with increasing speed
        80-102 Random strobe effect with increasing speed
        103-127 Lightning 5 s to 1 s
        128-250 Strobe effect with increasing speed
        251-255 LEDs on

        :param value: DMX value (0-255) for strobe effect.
        """
        self._send(1, value)

    def set_color(self, red: int, green: int, blue: int) -> None:
        """
        Set the RGB color (Channels 3, 4, 5).

        :param red: DMX value (0-255) for red intensity.
        :param green: DMX value (0-255) for green intensity.
        :param blue: DMX value (0-255) for blue intensity.
        """
        logger.debug(f"Setting color: R={red}, G={green}, B={blue}")
        self._send(2, red)
        self._send(3, green)
        self._send(4, blue)

    def set_sound_control(self, value: int) -> None:
        """
        Set the sound-controlled strobe effect (Channel 6).

        :param value: DMX value (0-255) for sound control.
        """
        self._send(5, value)

    def open_gates(self) -> None:
        """
        Open the gates to enable the strobe output.
        This sets the required channels to allow color and effects to be visible.
        """
        logger.debug("Opening gates for Eurolite Strobe")
        # Channel 1: Dimmer -> 100%
        self._send(0, 255)
        # Channel 2: Strobe -> Solid on (no flashing)
        self._send(1, 255)
        # Channel 6: Sound Control -> OFF
        self._send(5, 0)

    def close_gates(self) -> None:
        """Force the fixture into an 'off' state.

        Some effects (notably sound-controlled modes) can keep running on the
        fixture unless the relevant channels are reset.
        """

        # Channel 6: Sound Control -> OFF
        self._send(5, 0)
        # Channel 2: Strobe Effect -> LEDs off region
        self._send(1, 10)
        # Channel 3/4/5: Color -> off
        self._send(2, 0)
        self._send(3, 0)
        self._send(4, 0)
        # Channel 1: Dimmer -> 0
        self._send(0, 0)
