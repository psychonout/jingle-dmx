#!/usr/bin/env python3
"""
Beatz B480 Strobe Configuration Guide and Test Script
"""

import time
import sys

from loguru import logger
from strobe import Strobe

logger.remove()
logger.add(sys.stderr, level="INFO")


def beatz_b480_setup_guide():
    """Setup guide for Beatz B480 strobe"""

    logger.debug("=== Beatz B480 Strobe Setup Guide ===")

    logger.debug("\n1. PHYSICAL SETUP:")
    logger.debug("   • Connect DMX cable from uDMX interface to strobe DMX IN")
    logger.debug("   • Power on the strobe")
    logger.debug("   • Check that the strobe display shows DMX address")

    logger.debug("\n2. DMX ADDRESS SETTING:")
    logger.debug("   • Press MENU button on strobe")
    logger.debug("   • Navigate to DMX address setting (usually 'd001' or 'Addr')")
    logger.debug("   • Set DMX address to 001 (first DMX channel)")
    logger.debug("   • Press ENTER to confirm")

    logger.debug("\n3. DMX MODE SETTING:")
    logger.debug("   • In menu, look for 'Mode' or 'CH' setting")
    logger.debug("   • Common modes for B480:")
    logger.debug("     - 1CH: Single channel control")
    logger.debug("     - 2CH: Dimmer + Strobe")
    logger.debug("     - 3CH: Dimmer + Strobe + Color")
    logger.debug("     - 7CH: Full control (recommended)")
    logger.debug("   • Set to 7CH mode for full control")

    logger.debug("\n4. TYPICAL B480 CHANNEL LAYOUT (7CH mode):")
    logger.debug("   Channel 1: Dimmer (0-255)")
    logger.debug("   Channel 2: Strobe Rate (0-255)")
    logger.debug("   Channel 3: Red (0-255)")
    logger.debug("   Channel 4: Green (0-255)")
    logger.debug("   Channel 5: Blue (0-255)")
    logger.debug("   Channel 6: White (0-255)")
    logger.debug("   Channel 7: Macro/Programs (0-255)")

    logger.debug("\n5. SAVE SETTINGS:")
    logger.debug("   • Press MENU to exit")
    logger.debug("   • Settings should be saved automatically")

    logger.debug("\n6. TEST CONNECTION:")
    logger.debug("   • Run this script with test functions")
    logger.debug("   • Check if strobe responds to DMX commands")


class BeatzB480(Strobe):
    """Beatz B480 specific strobe control"""

    def __init__(self, device_index: int = 0):
        """Initialize B480 strobe"""
        super().__init__(device_index)
        logger.debug("Beatz B480 initialized")

    def set_dimmer(self, value: int) -> None:
        """Set dimmer (Channel 1)"""
        self._send(1, value)

    def set_strobe_rate(self, value: int) -> None:
        """Set strobe rate (Channel 2)
        0-10: Off
        11-255: Strobe rate slow to fast
        """
        self._send(2, value)

    def set_red(self, value: int) -> None:
        """Set red color (Channel 3)"""
        self._send(3, value)

    def set_green(self, value: int) -> None:
        """Set green color (Channel 4)"""
        self._send(4, value)

    def set_blue(self, value: int) -> None:
        """Set blue color (Channel 5)"""
        self._send(5, value)

    def set_white(self, value: int) -> None:
        """Set white color (Channel 6)"""
        self._send(6, value)

    def set_macro(self, value: int) -> None:
        """Set macro programs (Channel 7)
        0-10: Off
        11-255: Various built-in programs
        """
        self._send(7, value)

    def set_rgb_color(self, r: int, g: int, b: int) -> None:
        """Set RGB color combination"""
        self.set_red(r)
        self.set_green(g)
        self.set_blue(b)

    def flash_white(self, duration: float = 0.1) -> None:
        """Quick white flash"""
        self.set_dimmer(255)
        self.set_white(255)
        time.sleep(duration)
        self.set_dimmer(0)
        self.set_white(0)


def test_b480_basic():
    """Test basic B480 functionality"""
    logger.debug("=== B480 Basic Test ===")

    try:
        with BeatzB480() as strobe:
            logger.debug("B480 device opened")

            # Test dimmer
            logger.debug("Testing dimmer...")
            strobe.set_dimmer(255)
            time.sleep(2)
            strobe.set_dimmer(0)
            time.sleep(1)

            # Test white strobe
            logger.debug("Testing white strobe...")
            strobe.set_dimmer(255)
            strobe.set_white(255)
            strobe.set_strobe_rate(100)  # Medium strobe
            time.sleep(3)
            strobe.set_strobe_rate(0)    # Stop strobe
            time.sleep(1)

            # Test RGB colors
            colors = [
                (255, 0, 0, "Red"),
                (0, 255, 0, "Green"),
                (0, 0, 255, "Blue"),
                (255, 255, 0, "Yellow"),
                (255, 0, 255, "Magenta"),
                (0, 255, 255, "Cyan"),
                (255, 255, 255, "White")
            ]

            logger.debug("Testing RGB colors...")
            for r, g, b, name in colors:
                logger.debug(f"  {name}")
                strobe.set_rgb_color(r, g, b)
                time.sleep(1)

            # Test macro programs
            logger.debug("Testing macro programs...")
            strobe.set_macro(50)   # Try a macro program
            time.sleep(3)
            strobe.set_macro(0)    # Turn off macro

            # Reset all
            strobe.set_dimmer(0)
            strobe.set_strobe_rate(0)
            strobe.set_rgb_color(0, 0, 0)
            strobe.set_white(0)
            strobe.set_macro(0)

            logger.debug("✓ B480 basic test completed")
            return True

    except Exception as e:
        logger.error(f"✗ B480 basic test failed: {e}")
        return False


def interactive_b480_test():
    """Interactive B480 control"""
    logger.debug("=== Interactive B480 Test ===")

    try:
        with BeatzB480() as strobe:
            logger.debug("B480 ready for interactive testing")
            logger.debug("Commands:")
            logger.debug("  dimmer <value>     - Set dimmer (0-255)")
            logger.debug("  strobe <value>     - Set strobe rate (0-255)")
            logger.debug("  red <value>        - Set red (0-255)")
            logger.debug("  green <value>      - Set green (0-255)")
            logger.debug("  blue <value>       - Set blue (0-255)")
            logger.debug("  white <value>      - Set white (0-255)")
            logger.debug("  rgb <r> <g> <b>    - Set RGB color")
            logger.debug("  macro <value>      - Set macro program (0-255)")
            logger.debug("  flash              - Quick white flash")
            logger.debug("  reset              - Reset all channels")
            logger.debug("  quit               - Exit")

            while True:
                try:
                    cmd = input("\nEnter command: ").strip().lower()

                    if cmd == "quit":
                        break
                    elif cmd == "reset":
                        for ch in range(1, 8):
                            strobe._send(ch, 0)
                        logger.debug("✓ All channels reset")
                    elif cmd == "flash":
                        strobe.flash_white()
                        logger.debug("✓ Flash executed")
                    elif cmd.startswith("dimmer "):
                        value = int(cmd.split()[1])
                        strobe.set_dimmer(value)
                        logger.debug(f"✓ Dimmer set to {value}")
                    elif cmd.startswith("strobe "):
                        value = int(cmd.split()[1])
                        strobe.set_strobe_rate(value)
                        logger.debug(f"✓ Strobe rate set to {value}")
                    elif cmd.startswith("red "):
                        value = int(cmd.split()[1])
                        strobe.set_red(value)
                        logger.debug(f"✓ Red set to {value}")
                    elif cmd.startswith("green "):
                        value = int(cmd.split()[1])
                        strobe.set_green(value)
                        logger.debug(f"✓ Green set to {value}")
                    elif cmd.startswith("blue "):
                        value = int(cmd.split()[1])
                        strobe.set_blue(value)
                        logger.debug(f"✓ Blue set to {value}")
                    elif cmd.startswith("white "):
                        value = int(cmd.split()[1])
                        strobe.set_white(value)
                        logger.debug(f"✓ White set to {value}")
                    elif cmd.startswith("rgb "):
                        parts = cmd.split()
                        if len(parts) == 4:
                            r, g, b = int(parts[1]), int(parts[2]), int(parts[3])
                            strobe.set_rgb_color(r, g, b)
                            logger.debug(f"✓ RGB set to ({r}, {g}, {b})")
                        else:
                            logger.error("Usage: rgb <r> <g> <b>")
                    elif cmd.startswith("macro "):
                        value = int(cmd.split()[1])
                        strobe.set_macro(value)
                        logger.debug(f"✓ Macro set to {value}")
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
    """Main function"""
    logger.debug("=== Beatz B480 Test Suite ===")

    # Show setup guide
    beatz_b480_setup_guide()

    # Ask if user wants to proceed with tests
    try:
        response = input("\nHave you configured the strobe? Ready to test? (y/n): ").strip().lower()
        if response != 'y':
            logger.debug("Please configure the strobe first, then run this script again.")
            return
    except KeyboardInterrupt:
        return

    # Run basic test
    basic_success = test_b480_basic()

    # Summary
    logger.debug("\n=== Test Summary ===")
    logger.debug(f"Basic test: {'✓ PASSED' if basic_success else '✗ FAILED'}")

    # Interactive test
    if basic_success:
        try:
            response = input("\nWould you like to run interactive test? (y/n): ").strip().lower()
            if response == 'y':
                interactive_b480_test()
        except KeyboardInterrupt:
            pass

    logger.debug("\n=== Test Complete ===")


if __name__ == "__main__":
    main()
