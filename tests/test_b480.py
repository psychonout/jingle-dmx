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
    
    logger.info("=== Beatz B480 Strobe Setup Guide ===")
    
    logger.info("\n1. PHYSICAL SETUP:")
    logger.info("   • Connect DMX cable from uDMX interface to strobe DMX IN")
    logger.info("   • Power on the strobe")
    logger.info("   • Check that the strobe display shows DMX address")
    
    logger.info("\n2. DMX ADDRESS SETTING:")
    logger.info("   • Press MENU button on strobe")
    logger.info("   • Navigate to DMX address setting (usually 'd001' or 'Addr')")
    logger.info("   • Set DMX address to 001 (first DMX channel)")
    logger.info("   • Press ENTER to confirm")
    
    logger.info("\n3. DMX MODE SETTING:")
    logger.info("   • In menu, look for 'Mode' or 'CH' setting")
    logger.info("   • Common modes for B480:")
    logger.info("     - 1CH: Single channel control")
    logger.info("     - 2CH: Dimmer + Strobe")
    logger.info("     - 3CH: Dimmer + Strobe + Color")
    logger.info("     - 7CH: Full control (recommended)")
    logger.info("   • Set to 7CH mode for full control")
    
    logger.info("\n4. TYPICAL B480 CHANNEL LAYOUT (7CH mode):")
    logger.info("   Channel 1: Dimmer (0-255)")
    logger.info("   Channel 2: Strobe Rate (0-255)")
    logger.info("   Channel 3: Red (0-255)")
    logger.info("   Channel 4: Green (0-255)")
    logger.info("   Channel 5: Blue (0-255)")
    logger.info("   Channel 6: White (0-255)")
    logger.info("   Channel 7: Macro/Programs (0-255)")
    
    logger.info("\n5. SAVE SETTINGS:")
    logger.info("   • Press MENU to exit")
    logger.info("   • Settings should be saved automatically")
    
    logger.info("\n6. TEST CONNECTION:")
    logger.info("   • Run this script with test functions")
    logger.info("   • Check if strobe responds to DMX commands")


class BeatzB480(Strobe):
    """Beatz B480 specific strobe control"""
    
    def __init__(self, device_index: int = 0):
        """Initialize B480 strobe"""
        super().__init__(device_index)
        logger.info("Beatz B480 initialized")
    
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
    logger.info("=== B480 Basic Test ===")
    
    try:
        with BeatzB480() as strobe:
            logger.info("B480 device opened")
            
            # Test dimmer
            logger.info("Testing dimmer...")
            strobe.set_dimmer(255)
            time.sleep(2)
            strobe.set_dimmer(0)
            time.sleep(1)
            
            # Test white strobe
            logger.info("Testing white strobe...")
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
            
            logger.info("Testing RGB colors...")
            for r, g, b, name in colors:
                logger.info(f"  {name}")
                strobe.set_rgb_color(r, g, b)
                time.sleep(1)
            
            # Test macro programs
            logger.info("Testing macro programs...")
            strobe.set_macro(50)   # Try a macro program
            time.sleep(3)
            strobe.set_macro(0)    # Turn off macro
            
            # Reset all
            strobe.set_dimmer(0)
            strobe.set_strobe_rate(0)
            strobe.set_rgb_color(0, 0, 0)
            strobe.set_white(0)
            strobe.set_macro(0)
            
            logger.info("✓ B480 basic test completed")
            return True
            
    except Exception as e:
        logger.error(f"✗ B480 basic test failed: {e}")
        return False


def interactive_b480_test():
    """Interactive B480 control"""
    logger.info("=== Interactive B480 Test ===")
    
    try:
        with BeatzB480() as strobe:
            logger.info("B480 ready for interactive testing")
            logger.info("Commands:")
            logger.info("  dimmer <value>     - Set dimmer (0-255)")
            logger.info("  strobe <value>     - Set strobe rate (0-255)")
            logger.info("  red <value>        - Set red (0-255)")
            logger.info("  green <value>      - Set green (0-255)")
            logger.info("  blue <value>       - Set blue (0-255)")
            logger.info("  white <value>      - Set white (0-255)")
            logger.info("  rgb <r> <g> <b>    - Set RGB color")
            logger.info("  macro <value>      - Set macro program (0-255)")
            logger.info("  flash              - Quick white flash")
            logger.info("  reset              - Reset all channels")
            logger.info("  quit               - Exit")
            
            while True:
                try:
                    cmd = input("\nEnter command: ").strip().lower()
                    
                    if cmd == "quit":
                        break
                    elif cmd == "reset":
                        for ch in range(1, 8):
                            strobe._send(ch, 0)
                        logger.info("✓ All channels reset")
                    elif cmd == "flash":
                        strobe.flash_white()
                        logger.info("✓ Flash executed")
                    elif cmd.startswith("dimmer "):
                        value = int(cmd.split()[1])
                        strobe.set_dimmer(value)
                        logger.info(f"✓ Dimmer set to {value}")
                    elif cmd.startswith("strobe "):
                        value = int(cmd.split()[1])
                        strobe.set_strobe_rate(value)
                        logger.info(f"✓ Strobe rate set to {value}")
                    elif cmd.startswith("red "):
                        value = int(cmd.split()[1])
                        strobe.set_red(value)
                        logger.info(f"✓ Red set to {value}")
                    elif cmd.startswith("green "):
                        value = int(cmd.split()[1])
                        strobe.set_green(value)
                        logger.info(f"✓ Green set to {value}")
                    elif cmd.startswith("blue "):
                        value = int(cmd.split()[1])
                        strobe.set_blue(value)
                        logger.info(f"✓ Blue set to {value}")
                    elif cmd.startswith("white "):
                        value = int(cmd.split()[1])
                        strobe.set_white(value)
                        logger.info(f"✓ White set to {value}")
                    elif cmd.startswith("rgb "):
                        parts = cmd.split()
                        if len(parts) == 4:
                            r, g, b = int(parts[1]), int(parts[2]), int(parts[3])
                            strobe.set_rgb_color(r, g, b)
                            logger.info(f"✓ RGB set to ({r}, {g}, {b})")
                        else:
                            logger.error("Usage: rgb <r> <g> <b>")
                    elif cmd.startswith("macro "):
                        value = int(cmd.split()[1])
                        strobe.set_macro(value)
                        logger.info(f"✓ Macro set to {value}")
                    else:
                        logger.error("Unknown command")
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Error: {e}")
            
            logger.info("Interactive test ended")
            
    except Exception as e:
        logger.error(f"Interactive test failed: {e}")


def main():
    """Main function"""
    logger.info("=== Beatz B480 Test Suite ===")
    
    # Show setup guide
    beatz_b480_setup_guide()
    
    # Ask if user wants to proceed with tests
    try:
        response = input("\nHave you configured the strobe? Ready to test? (y/n): ").strip().lower()
        if response != 'y':
            logger.info("Please configure the strobe first, then run this script again.")
            return
    except KeyboardInterrupt:
        return
    
    # Run basic test
    basic_success = test_b480_basic()
    
    # Summary
    logger.info("\n=== Test Summary ===")
    logger.info(f"Basic test: {'✓ PASSED' if basic_success else '✗ FAILED'}")
    
    # Interactive test
    if basic_success:
        try:
            response = input("\nWould you like to run interactive test? (y/n): ").strip().lower()
            if response == 'y':
                interactive_b480_test()
        except KeyboardInterrupt:
            pass
    
    logger.info("\n=== Test Complete ===")


if __name__ == "__main__":
    main()
