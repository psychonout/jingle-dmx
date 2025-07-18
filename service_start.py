#!/usr/bin/env python3
"""
Enhanced startup script for jingle-dmx with better error handling and logging.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

# Configure logger for service
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(
    "/home/pi/jingle-dmx/service.log",
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
)


def check_permissions():
    """Check if we have the necessary permissions"""
    # Check if we're in the required groups
    try:
        result = subprocess.run(["groups"], capture_output=True, text=True)
        groups = result.stdout.strip()

        required_groups = ["audio", "plugdev", "gpio"]
        missing_groups = []

        for group in required_groups:
            if group not in groups:
                missing_groups.append(group)

        if missing_groups:
            logger.warning(f"User not in required groups: {missing_groups}")
            return False

        logger.info("All required group permissions present")
        return True

    except Exception as e:
        logger.error(f"Error checking permissions: {e}")
        return False


def wait_for_devices():
    """Wait for required devices to be available"""
    max_wait = 30
    wait_count = 0

    while wait_count < max_wait:
        # Check for USB devices
        if os.path.exists("/dev/bus/usb"):
            logger.info("USB subsystem available")

            # Check for audio devices
            if os.path.exists("/dev/snd"):
                logger.info("Audio subsystem available")

                # Check for GPIO access
                if os.path.exists("/dev/gpiomem"):
                    logger.info("GPIO access available")
                    return True

        logger.info(f"Waiting for devices... ({wait_count + 1}/{max_wait})")
        time.sleep(1)
        wait_count += 1

    logger.warning("Not all devices available, proceeding anyway")
    return False


def main():
    """Main startup function"""
    logger.info("Starting jingle-dmx service")

    # Change to correct directory
    os.chdir("/home/pi/jingle-dmx")

    # Check permissions
    check_permissions()

    # Wait for devices
    wait_for_devices()

    # Additional startup delay
    logger.info("Final startup delay...")
    time.sleep(5)

    # Start the main application
    logger.info("Starting main application...")
    try:
        from main import main as main_app

        main_app()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Error in main application: {e}")
        logger.exception("Full traceback:")

        # Wait before exit to prevent rapid restart
        time.sleep(10)
        raise


if __name__ == "__main__":
    main()
