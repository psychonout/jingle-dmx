import sys

from loguru import logger
from pyudmx.pyudmx import uDMXDevice

logger.remove()
logger.add(sys.stderr, level="INFO")


class BaseDMX:
    status = False

    def __init__(self, device_index: int = 0) -> None:
        """Initialize DMX device

        Args:
            device_index: Index of the uDMX device to use (0 for first device)
        """
        self.device_index = device_index
        self._dev = uDMXDevice()
        self._dev.open()
        logger.info(f"DMX device {device_index} opened successfully")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._dev.close()
        logger.info(f"DMX device {self.device_index} closed")

    def _send(self, channel: int, value: int) -> None:
        """sends a value to a channel

        Args:
            channel (int): channel number
            value (int): value to send

        """
        try:
            self._dev.send_single_value(channel, value)
            logger.debug(f"Device {self.device_index} - Channel {channel}: {value}")
        except Exception as e:
            logger.error(f"Device {self.device_index} - Channel {channel} failed: {e}")
            pass
