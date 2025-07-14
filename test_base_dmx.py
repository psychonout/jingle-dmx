#!/usr/bin/env python3
"""
Simple test script for BaseDMX class with multiple devices
"""

import sys
import time

from loguru import logger

from base_dmx import BaseDMX

logger.remove()
logger.add(sys.stderr, level="INFO")


class TestDMX(BaseDMX):
    """Test class that extends BaseDMX for testing purposes"""

    def __init__(self, device_name: str = "Device"):
        self.device_name = device_name
        super().__init__()

    def test_channels(self, start_channel: int = 1, num_channels: int = 10):
        """Test a range of channels"""
        logger.info(
            f"Testing {self.device_name} - Channels {start_channel} to {start_channel + num_channels - 1}"
        )

        # Test each channel with full brightness
        for i in range(num_channels):
            channel = start_channel + i
            try:
                logger.info(f"  Channel {channel}: ON (255)")
                self._send(channel, 255)
                time.sleep(0.5)

                logger.info(f"  Channel {channel}: OFF (0)")
                self._send(channel, 0)
                time.sleep(0.2)

            except Exception as e:
                logger.error(f"  Channel {channel}: ERROR - {e}")

    def test_fade(self, channel: int = 1):
        """Test fading on a specific channel"""
        logger.info(f"Testing {self.device_name} - Fade on channel {channel}")

        # Fade up
        for value in range(0, 256, 10):
            self._send(channel, value)
            time.sleep(0.1)

        # Fade down
        for value in range(255, -1, -10):
            self._send(channel, value)
            time.sleep(0.1)

    def reset_all(self):
        """Reset all channels to 0"""
        logger.info(f"Resetting all channels for {self.device_name}")
        for channel in range(1, 513):
            self._send(channel, 0)


def test_single_device():
    """Test a single uDMX device"""
    logger.info("=== Testing Single uDMX Device ===")

    try:
        with TestDMX("Primary Device") as device:
            logger.info("✓ Device opened successfully")

            # Test basic channels
            device.test_channels(1, 5)

            # Test fade effect
            device.test_fade(1)

            # Reset all channels
            device.reset_all()

            logger.info("✓ Single device test completed")
            return True

    except Exception as e:
        logger.error(f"✗ Single device test failed: {e}")
        return False


def test_two_devices():
    """Test two uDMX devices with different channel assignments"""
    logger.info("=== Testing Two uDMX Devices ===")

    try:
        # Note: This assumes you can distinguish devices somehow
        # You may need to modify this based on your setup

        device1 = TestDMX("Device 1")
        device2 = TestDMX("Device 2")

        logger.info("Testing Device 1...")
        device1.test_channels(1, 3)  # Test channels 1-3
        device1.reset_all()

        time.sleep(1)

        logger.info("Testing Device 2...")
        device2.test_channels(4, 3)  # Test channels 4-6
        device2.reset_all()

        # Test both devices simultaneously
        logger.info("Testing both devices simultaneously...")
        device1._send(1, 255)  # Device 1, channel 1
        device2._send(4, 255)  # Device 2, channel 4
        time.sleep(2)

        device1._send(1, 0)
        device2._send(4, 0)

        device1._dev.close()
        device2._dev.close()

        logger.info("✓ Two device test completed")
        return True

    except Exception as e:
        logger.error(f"✗ Two device test failed: {e}")
        return False


def interactive_device_test():
    """Interactive test for manual device control"""
    logger.info("=== Interactive Device Test ===")

    try:
        device = TestDMX("Interactive Device")
        logger.info("Device ready for interactive testing")

        logger.info("Commands:")
        logger.info("  set <channel> <value>  - Set channel to value (1-512, 0-255)")
        logger.info("  test <channel>         - Test specific channel")
        logger.info("  fade <channel>         - Fade test on channel")
        logger.info("  reset                  - Reset all channels")
        logger.info("  quit                   - Exit")

        while True:
            try:
                cmd = input("\nEnter command: ").strip().lower()

                if cmd == "quit":
                    break
                elif cmd == "reset":
                    device.reset_all()
                elif cmd.startswith("set "):
                    parts = cmd.split()
                    if len(parts) == 3:
                        channel = int(parts[1])
                        value = int(parts[2])
                        if 1 <= channel <= 512 and 0 <= value <= 255:
                            device._send(channel, value)
                            logger.info(f"✓ Channel {channel} set to {value}")
                        else:
                            logger.error("Channel must be 1-512, value must be 0-255")
                    else:
                        logger.error("Usage: set <channel> <value>")
                elif cmd.startswith("test "):
                    parts = cmd.split()
                    if len(parts) == 2:
                        channel = int(parts[1])
                        device.test_channels(channel, 1)
                    else:
                        logger.error("Usage: test <channel>")
                elif cmd.startswith("fade "):
                    parts = cmd.split()
                    if len(parts) == 2:
                        channel = int(parts[1])
                        device.test_fade(channel)
                    else:
                        logger.error("Usage: fade <channel>")
                else:
                    logger.error("Unknown command")

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")

        device._dev.close()
        logger.info("Device closed")

    except Exception as e:
        logger.error(f"Interactive test failed: {e}")


def main():
    """Main test function"""
    logger.info("=== BaseDMX Device Test Suite ===")

    # Test single device
    logger.info("\n1. Testing single device...")
    single_success = test_single_device()

    # Test two devices (if available)
    logger.info("\n2. Testing two devices...")
    dual_success = test_two_devices()

    # Summary
    logger.info("\n=== Test Summary ===")
    logger.info(f"Single device test: {'✓ PASSED' if single_success else '✗ FAILED'}")
    logger.info(f"Dual device test: {'✓ PASSED' if dual_success else '✗ FAILED'}")

    # Interactive test option
    if single_success:
        try:
            response = (
                input("\nWould you like to run interactive test? (y/n): ")
                .strip()
                .lower()
            )
            if response == "y":
                interactive_device_test()
        except KeyboardInterrupt:
            pass

    logger.info("\n=== Test Complete ===")


if __name__ == "__main__":
    main()
