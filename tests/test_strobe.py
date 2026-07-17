#!/usr/bin/env python3
"""
Simple strobe test script to debug DMX communication
"""

import sys
import time

from loguru import logger

from strobe import Strobe

logger.remove()
logger.add(sys.stderr, level="INFO")


def test_strobe_basic():
    """Test basic strobe functionality"""
    logger.debug("=== Basic Strobe Test ===")

    try:
        with Strobe() as strobe:
            logger.debug("Strobe device opened successfully")

            # Test dimmer
            logger.debug("Setting dimmer to maximum (255)")
            strobe.set_dimmer(255)
            time.sleep(1)

            # Test strobe effect
            logger.debug("Setting strobe to simple strobe (80)")
            strobe.set_strobe(80)
            time.sleep(3)

            # Test different colors
            colors = [255, 128, 64, 32, 0]
            for color in colors:
                logger.debug(f"Setting color to {color}")
                strobe.set_color(color)
                time.sleep(1)

            # Test warm white
            logger.debug("Setting warm white to 255")
            strobe.set_warm_white(255)
            time.sleep(2)

            # Test cold white
            logger.debug("Setting cold white to 255")
            strobe.set_cold_white(255)
            time.sleep(2)

            # Turn off strobe
            logger.debug("Turning off strobe")
            strobe.set_strobe(0)
            strobe.set_dimmer(0)

            logger.debug("✓ Basic strobe test completed successfully")
            return True

    except Exception as e:
        logger.error(f"✗ Basic strobe test failed: {e}")
        return False


def test_strobe_channels():
    """Test individual channels"""
    logger.debug("=== Strobe Channel Test ===")

    try:
        with Strobe() as strobe:
            channels = [
                (1, "Dimmer"),
                (2, "Strobe"),
                (3, "Warm White"),
                (4, "Cold White"),
                (5, "Color"),
                (6, "Macro"),
                (7, "Macro Speed"),
            ]

            for channel, name in channels:
                logger.debug(f"Testing Channel {channel} ({name})")

                # Set to maximum
                strobe._send(channel, 255)
                time.sleep(1)

                # Set to medium
                strobe._send(channel, 128)
                time.sleep(1)

                # Set to off
                strobe._send(channel, 0)
                time.sleep(0.5)

            logger.debug("✓ Channel test completed")
            return True

    except Exception as e:
        logger.error(f"✗ Channel test failed: {e}")
        return False


def test_strobe_effects():
    """Test different strobe effects"""
    logger.debug("=== Strobe Effects Test ===")

    try:
        with Strobe() as strobe:
            # Set dimmer to full
            strobe.set_dimmer(255)

            effects = [
                (0, "Off"),
                (50, "Full On"),
                (80, "Simple Strobe"),
                (120, "Full On"),
                (140, "Pulse Effect"),
                (180, "Full On"),
                (200, "Random Strobe"),
                (240, "Full On"),
            ]

            for value, description in effects:
                logger.debug(f"Testing strobe effect: {description} (value: {value})")
                strobe.set_strobe(value)
                if value != 0:
                    strobe.set_color(255)  # Set color for visibility
                time.sleep(3)

            # Turn off
            strobe.set_strobe(0)
            strobe.set_dimmer(0)

            logger.debug("✓ Effects test completed")
            return True

    except Exception as e:
        logger.error(f"✗ Effects test failed: {e}")
        return False


def interactive_strobe_test():
    """Interactive strobe control"""
    logger.debug("=== Interactive Strobe Test ===")

    try:
        with Strobe() as strobe:
            logger.debug("Strobe ready for interactive testing")
            logger.debug("Commands:")
            logger.debug("  dimmer <value>     - Set dimmer (0-255)")
            logger.debug("  strobe <value>     - Set strobe (0-255)")
            logger.debug("  color <value>      - Set color (0-255)")
            logger.debug("  warm <value>       - Set warm white (0-255)")
            logger.debug("  cold <value>       - Set cold white (0-255)")
            logger.debug("  macro <value>      - Set macro (0-255)")
            logger.debug("  speed <value>      - Set macro speed (0-255)")
            logger.debug("  reset             - Reset all channels")
            logger.debug("  quit              - Exit")

            while True:
                try:
                    cmd = input("\nEnter command: ").strip().lower()

                    if cmd == "quit":
                        break
                    elif cmd == "reset":
                        for ch in range(1, 8):
                            strobe._send(ch, 0)
                        logger.debug("✓ All channels reset")
                    elif cmd.startswith("dimmer "):
                        value = int(cmd.split()[1])
                        strobe.set_dimmer(value)
                        logger.debug(f"✓ Dimmer set to {value}")
                    elif cmd.startswith("strobe "):
                        value = int(cmd.split()[1])
                        strobe.set_strobe(value)
                        logger.debug(f"✓ Strobe set to {value}")
                    elif cmd.startswith("color "):
                        value = int(cmd.split()[1])
                        strobe.set_color(value)
                        logger.debug(f"✓ Color set to {value}")
                    elif cmd.startswith("warm "):
                        value = int(cmd.split()[1])
                        strobe.set_warm_white(value)
                        logger.debug(f"✓ Warm white set to {value}")
                    elif cmd.startswith("cold "):
                        value = int(cmd.split()[1])
                        strobe.set_cold_white(value)
                        logger.debug(f"✓ Cold white set to {value}")
                    elif cmd.startswith("macro "):
                        value = int(cmd.split()[1])
                        strobe.set_macro(value)
                        logger.debug(f"✓ Macro set to {value}")
                    elif cmd.startswith("speed "):
                        value = int(cmd.split()[1])
                        strobe.set_macro_speed(value)
                        logger.debug(f"✓ Macro speed set to {value}")
                    else:
                        logger.error("Unknown command")

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Error: {e}")

            logger.debug("Interactive test ended")

    except Exception as e:
        logger.error(f"Interactive test failed: {e}")


def main():
    """Main test function"""
    logger.debug("=== Strobe Debug Test Suite ===")

    # Run basic tests
    basic_success = test_strobe_basic()
    channel_success = test_strobe_channels()
    effects_success = test_strobe_effects()

    # Summary
    logger.debug("\n=== Test Summary ===")
    logger.debug(f"Basic test: {'✓ PASSED' if basic_success else '✗ FAILED'}")
    logger.debug(f"Channel test: {'✓ PASSED' if channel_success else '✗ FAILED'}")
    logger.debug(f"Effects test: {'✓ PASSED' if effects_success else '✗ FAILED'}")

    # Interactive test
    if any([basic_success, channel_success, effects_success]):
        try:
            response = (
                input("\nWould you like to run interactive test? (y/n): ")
                .strip()
                .lower()
            )
            if response == "y":
                interactive_strobe_test()
        except KeyboardInterrupt:
            pass

    logger.debug("\n=== Test Complete ===")


if __name__ == "__main__":
    main()
