import sys
import threading
import time
import atexit

from loguru import logger
from pyudmx.pyudmx import uDMXDevice

logger.remove()
logger.add(sys.stderr, level="INFO")


class DMXUniverse:
    """
    Singleton class to manage the DMX universe state and background transmission.
    This prevents multiple devices from fighting over the USB connection and
    allows for efficient batched updates.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DMXUniverse, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 512 channels, initialized to 0
        self._buffer = [0] * 512
        self._dirty = False
        self._dev = None
        self._thread = None
        self._stop_event = threading.Event()

        self._connect()
        atexit.register(self.close)

    def _connect(self):
        try:
            self._dev = uDMXDevice()
            self._dev.open()
            logger.info("DMXUniverse: Connected to uDMX device")
            self._start_thread()
        except Exception as e:
            logger.error(f"DMXUniverse: Failed to connect: {e}")

    def _start_thread(self):
        if self._thread is None:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._transmission_loop, daemon=True)
            self._thread.start()
            logger.debug("DMX transmission thread started")

    def _transmission_loop(self):
        # Target ~40Hz update rate (25ms)
        interval = 0.025

        while not self._stop_event.is_set():
            start_time = time.time()

            if self._dirty and self._dev:
                try:
                    # Send the entire buffer. uDMX should handle 512 bytes.
                    # If this fails, we might need to chunk it, but standard uDMX
                    # usually accepts the full frame.
                    self._dev.send_multi_value(1, self._buffer)
                    self._dirty = False
                except Exception as e:
                    logger.error(f"DMX transmission error: {e}")
                    # Try to reconnect on error
                    try:
                        self._dev.close()
                        self._dev.open()
                    except Exception:
                        pass

            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)

    def set_channel(self, channel: int, value: int):
        """Set a DMX channel value (1-512)"""
        if 1 <= channel <= 512:
            idx = channel - 1
            # Clamp value to 0-255
            value = max(0, min(255, int(value)))

            if self._buffer[idx] != value:
                self._buffer[idx] = value
                self._dirty = True

    def close(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._dev:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None


class BaseDMX:
    def __init__(self, dmx_channel: int = 1, num_channels: int = 1) -> None:
        """Initialize DMX device"""
        self.dmx_channel = dmx_channel
        self.num_channels = num_channels
        # Get the singleton universe instance
        self.universe = DMXUniverse()

    def __enter__(self):
        # We don't reset on enter anymore to avoid clearing other devices
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        # Send 0 to all channels
        for i in range(self.num_channels):
            self._send(i, 0)

    def _send(self, channel_offset: int, value: int) -> None:
        """Sends a value to a channel relative to the device's start address

        Args:
            channel_offset (int): Offset from start address (0-based)
            value (int): Value to send (0-255)
        """
        # Calculate absolute DMX address
        # dmx_channel is the start address (e.g. 1)
        # channel_offset 0 -> Address 1
        target_channel = self.dmx_channel + channel_offset

        self.universe.set_channel(target_channel, value)
        # logger.debug(f"DMX: Ch {target_channel} = {value}")

    def reset(self) -> None:
        """Reset the DMX device to default settings (0)."""
        # This is tricky with a shared buffer. We probably only want to reset
        # the channels belonging to this device, but we don't know how many there are.
        # For now, let's assume a safe range or just rely on the controller to set 0s.
        pass


def test_device():
    dmx = BaseDMX()
    logger.info("Testing DMX output...")
    for i in range(1, 10):
        dmx._send(i, 255)
        time.sleep(0.1)
        dmx._send(i, 0)


if __name__ == "__main__":
    test_device()
