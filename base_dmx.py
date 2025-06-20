import sys

from loguru import logger
from pyudmx.pyudmx import uDMXDevice

logger.remove()
logger.add(sys.stderr, level="INFO")


class BaseDMX:
    status = False

    def __init__(self) -> None:
        self._dev = uDMXDevice()
        self._dev.open()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._dev.close()

    def _send(self, channel: int, value: int) -> None:
        """sends a value to a channel

        Args:
            channel (int): channel number
            value (int): value to send

        """
        try:
            self._dev.send_single_value(channel, value)
        except Exception as e:
            logger.debug(e)
            pass

