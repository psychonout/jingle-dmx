#!/usr/bin/env python3
"""
Jingle DMX Main Entry Point

This script handles service startup, environment checks, logging configuration,
and runs the main light show controller.
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from loguru import logger

from config import DeviceConfig, load_default_profile
from runtime_control import RuntimeControl
from show_controller import LightShowController

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")
# Use absolute path for log file to ensure it works when running as service
LOG_FILE = Path("/home/pi/jingle-dmx/service.log")
logger.add(
    str(LOG_FILE),
    level="INFO",
    rotation="10 MB",
    retention="7 days",
)


def check_permissions() -> bool:
    """Check if we have the necessary permissions"""
    # Check if we have the necessary permissions
    if os.geteuid() == 0:
        logger.debug("Running as root, skipping group checks")
        return True

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

        logger.debug("All required group permissions present")
        return True

    except Exception as e:
        logger.error(f"Error checking permissions: {e}")
        return False


def wait_for_devices() -> bool:
    """Wait for required devices to be available"""
    max_wait = 30
    wait_count = 0

    while wait_count < max_wait:
        # Check for USB devices
        if os.path.exists("/dev/bus/usb"):
            logger.debug("USB subsystem available")

            # Check for audio devices
            if os.path.exists("/dev/snd"):
                logger.debug("Audio subsystem available")

                # Check for GPIO access
                if os.path.exists("/dev/gpiomem"):
                    logger.debug("GPIO access available")
                    return True

        logger.debug(f"Waiting for devices... ({wait_count + 1}/{max_wait})")
        time.sleep(1)
        wait_count += 1

    logger.warning("Not all devices available, proceeding anyway")
    return False


def run_controller() -> None:
    """Initialize and run the light show controller"""
    # Note: DeviceConfig is now imported from config.py
    # We can eventually move this hardcoded config to config.py or env vars as well
    config = DeviceConfig(
        use_laser=True,
        use_strobe=True,
        use_spotlight=True,
        use_stinger=True,
        use_vu_meter=True,
        use_eurolite_strobe=True,
    )
    profile = load_default_profile()
    runtime_control = RuntimeControl(config, profile)
    controller = LightShowController(
        device_config=config,
        show_profile=profile,
        runtime_control=runtime_control,
    )

    web_enabled = os.getenv("WEB_CONTROLLER_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    if web_enabled:
        try:
            import uvicorn

            from web_controller import create_app

            host = os.getenv("WEB_CONTROLLER_HOST", "0.0.0.0")
            port = int(os.getenv("WEB_CONTROLLER_PORT", "8080"))
            app = create_app(runtime_control)

            def run_web() -> None:
                uvicorn.run(app, host=host, port=port, log_level="warning")

            web_thread = threading.Thread(target=run_web, daemon=True)
            web_thread.start()
            logger.info(f"Web controller running on http://{host}:{port}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to start web controller: {exc}")

    controller.run()


def main() -> None:
    """Main startup function"""
    logger.debug("Starting jingle-dmx service")

    # Ensure we are running from the script directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    logger.debug(f"Working directory set to: {script_dir}")

    # Check permissions
    check_permissions()

    # Wait for devices
    wait_for_devices()

    # Additional startup delay to ensure system is fully settled
    logger.debug("Final startup delay...")
    time.sleep(5)

    # Start the main application
    logger.debug("Starting main application...")
    try:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--profile", action="store_true", help="Run with cProfile")
        parser.add_argument(
            "--profile-file",
            default="jingle_dmx.prof",
            help="Output file for profile data",
        )
        args = parser.parse_args()

        if args.profile:
            import cProfile
            import pstats

            logger.info(
                f"Profiling enabled. Output will be saved to {args.profile_file}"
            )
            profiler = cProfile.Profile()
            profiler.enable()

            try:
                run_controller()
            except KeyboardInterrupt:
                pass
            finally:
                profiler.disable()
                stats = pstats.Stats(profiler).sort_stats("cumtime")
                stats.dump_stats(args.profile_file)
                logger.info(f"Profile data saved to {args.profile_file}")
                # Print top 20 time-consuming functions
                stats.print_stats(20)
        else:
            run_controller()
    except KeyboardInterrupt:
        logger.debug("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Error in main application: {e}")
        logger.exception("Full traceback:")

        # Wait before exit to prevent rapid restart if managed by systemd
        time.sleep(10)
        raise


if __name__ == "__main__":
    main()
