import sys

from loguru import logger
from pyudmx.pyudmx import uDMXDevice

logger.remove()
logger.add(sys.stderr, level="INFO")


class BaseDMX:
    status = False

    def __init__(self) -> None:
        """Initialize DMX device"""
        self._dev = uDMXDevice()
        self._dev.open()

    def __enter__(self):
        self.reset()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.reset()
        self._dev.close()

    def _send(self, channel: int, value: int) -> None:
        """sends a value to a channel

        Args:
            channel (int): channel number
            value (int): value to send

        """
        try:
            self._dev.send_single_value(channel, value)
            logger.debug(f"DMX: Channel {channel} = {value}")
        except Exception as e:
            logger.error(f"DMX send error: {e}")
            pass

    def reset(self) -> None:
        """Reset the DMX device to default settings."""
        for i in range(1, 513):
            self._send(i, 0)
        logger.debug("DMX device reset to default settings.")
