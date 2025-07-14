#!/usr/bin/env python3
"""
Test script to detect and test multiple uDMX devices
"""

import sys
import time
from typing import Optional

from loguru import logger
from pyudmx.pyudmx import uDMXDevice

logger.remove()
logger.add(sys.stderr, level="INFO")


def list_usb_devices():
    """List all USB devices to help identify uDMX devices"""
    try:
        import usb.core
        import usb.util

        logger.info("=== USB Devices ===")
        devices = usb.core.find(find_all=True)

        for device in devices:
            try:
                manufacturer = (
                    usb.util.get_string(device, device.iManufacturer)
                    if device.iManufacturer
                    else "Unknown"
                )
                product = (
                    usb.util.get_string(device, device.iProduct)
                    if device.iProduct
                    else "Unknown"
                )
                logger.info(
                    f"Device: {manufacturer} - {product} (VID: {hex(device.idVendor)}, PID: {hex(device.idProduct)})"
                )
            except Exception as e:
                logger.debug(f"Could not read device info: {e}")

    except ImportError:
        logger.warning("pyusb not available for detailed USB device listing")
    except Exception as e:
        logger.error(f"Error listing USB devices: {e}")


def test_single_device(device_id: Optional[int] = None) -> bool:
    """Test a single uDMX device"""
    try:
        logger.info(f"Testing uDMX device {device_id if device_id else 'default'}...")

        # Create device instance
        if device_id is not None:
            # If pyudmx supports device selection, use it
            dev = uDMXDevice()
        else:
            dev = uDMXDevice()

        # Try to open the device
        dev.open()
        logger.info("✓ Device opened successfully")

        # Test basic communication by sending values to different channels
        test_channels = [1, 2, 3, 4, 5]
        test_values = [255, 128, 64, 32, 0]

        logger.info("Testing channel communication...")
        for channel, value in zip(test_channels, test_values):
            try:
                dev.send_single_value(channel, value)
                logger.info(f"✓ Channel {channel}: sent value {value}")
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"✗ Channel {channel}: failed to send value {value} - {e}")

        # Test sending all channels to 0 (reset)
        logger.info("Resetting all channels to 0...")
        for channel in range(1, 513):  # DMX has 512 channels
            try:
                dev.send_single_value(channel, 0)
            except Exception as e:
                logger.debug(f"Channel {channel} reset failed: {e}")
                break

        logger.info("✓ Reset complete")

        # Close device
        dev.close()
        logger.info("✓ Device closed successfully")

        return True

    except Exception as e:
        logger.error(f"✗ Device test failed: {e}")
        return False


def test_multiple_devices():
    """Attempt to test multiple uDMX devices"""
    logger.info("=== Testing Multiple uDMX Devices ===")

    devices_found = []

    # Try to find and test multiple devices
    for device_num in range(5):  # Test up to 5 potential devices
        logger.info(f"\n--- Testing Device {device_num} ---")

        try:
            # Create separate device instances
            dev = uDMXDevice()
            dev.open()

            # Test if device responds
            dev.send_single_value(1, 255)
            time.sleep(0.1)
            dev.send_single_value(1, 0)

            devices_found.append(dev)
            logger.info(f"✓ Device {device_num} is working")

        except Exception as e:
            logger.debug(f"Device {device_num} not found or failed: {e}")
            break

    logger.info(f"\nFound {len(devices_found)} working uDMX device(s)")

    # Close all devices
    for i, dev in enumerate(devices_found):
        try:
            dev.close()
            logger.info(f"✓ Closed device {i}")
        except Exception as e:
            logger.error(f"✗ Failed to close device {i}: {e}")

    return len(devices_found)


def interactive_test():
    """Interactive test to manually control channels"""
    logger.info("=== Interactive uDMX Test ===")

    try:
        dev = uDMXDevice()
        dev.open()
        logger.info("Device opened for interactive testing")

        logger.info("Commands:")
        logger.info("  set <channel> <value>  - Set channel to value (1-512, 0-255)")
        logger.info("  reset                  - Set all channels to 0")
        logger.info("  test                   - Run test pattern")
        logger.info("  quit                   - Exit")

        while True:
            try:
                cmd = input("\nEnter command: ").strip().lower()

                if cmd == "quit":
                    break
                elif cmd == "reset":
                    logger.info("Resetting all channels...")
                    for ch in range(1, 513):
                        dev.send_single_value(ch, 0)
                    logger.info("✓ All channels reset")
                elif cmd == "test":
                    logger.info("Running test pattern...")
                    for ch in range(1, 11):
                        dev.send_single_value(ch, 255)
                        time.sleep(1)
                        dev.send_single_value(ch, 0)
                    logger.info("✓ Test pattern complete")
                elif cmd.startswith("set "):
                    parts = cmd.split()
                    if len(parts) == 3:
                        channel = int(parts[1])
                        value = int(parts[2])
                        if 1 <= channel <= 512 and 0 <= value <= 255:
                            dev.send_single_value(channel, value)
                            logger.info(f"✓ Channel {channel} set to {value}")
                        else:
                            logger.error("Channel must be 1-512, value must be 0-255")
                    else:
                        logger.error("Usage: set <channel> <value>")
                else:
                    logger.error("Unknown command")

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")

        dev.close()
        logger.info("Device closed")

    except Exception as e:
        logger.error(f"Interactive test failed: {e}")


def main():
    """Main test function"""
    logger.info("=== uDMX Device Test Suite ===")

    # List USB devices
    list_usb_devices()

    # Test single device
    logger.info("\n=== Single Device Test ===")
    if test_single_device():
        logger.info("✓ Single device test passed")
    else:
        logger.error("✗ Single device test failed")

    # Test multiple devices
    logger.info("\n=== Multiple Device Test ===")
    device_count = test_multiple_devices()

    if device_count > 0:
        logger.info(f"✓ Found {device_count} working uDMX device(s)")

        # Ask if user wants interactive test
        try:
            response = (
                input("\nWould you like to run interactive test? (y/n): ")
                .strip()
                .lower()
            )
            if response == "y":
                interactive_test()
        except KeyboardInterrupt:
            pass
    else:
        logger.error("✗ No working uDMX devices found")

    logger.info("\n=== Test Complete ===")


if __name__ == "__main__":
    main()
