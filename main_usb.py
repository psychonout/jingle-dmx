import time
from random import randint

from loguru import logger

from laser import Laser, all_random
from strobe import Strobe
from usb_mic import USBMicrophone, list_usb_microphones


def main():
    # List available USB microphones first
    logger.debug("Available USB microphones:")
    list_usb_microphones()

    # You can specify a device name or index here
    # For example: USBMicrophone(device_name="USB Audio Device")
    # Or: USBMicrophone(device_index=1)

    # Volume thresholds for different effects
    laser_threshold = 15  # Lower threshold for laser effects
    strobe_threshold = 25  # Higher threshold for strobe effects
    combo_threshold = 35  # Even higher threshold for combined effects
    max_vol = 0

    with USBMicrophone() as usb_mic:
        if not usb_mic.is_open:
            logger.debug("Failed to open USB microphone")
            return

        with Laser(device_index=0) as laser, Strobe(device_index=0) as strobe:
            laser.set_mode("manual")
            strobe.set_dimmer(255)  # Set strobe to full brightness
            logger.debug("Starting audio-reactive laser and strobe show...")

            while True:
                volume = usb_mic.read()
                logger.debug(volume)

                if volume > max_vol:
                    max_vol = volume
                    logger.debug(f"New max volume: {max_vol}")

                # Combined effects for very loud sounds
                if volume >= combo_threshold:
                    logger.debug(f"COMBO EFFECT! Volume: {volume}")
                    # Trigger both laser and strobe effects
                    all_random(laser)
                    strobe.set_strobe(randint(192, 223))  # Random strobe effect
                    strobe.set_color(randint(0, 255))  # Random color
                    strobe.set_macro(randint(0, 255))  # Random macro

                # Strobe effects for moderately loud sounds
                elif volume >= strobe_threshold:
                    logger.debug(f"STROBE EFFECT! Volume: {volume}")
                    strobe.set_strobe(randint(64, 159))  # Simple strobe or pulse
                    strobe.set_color(randint(0, 255))  # Random color
                    if randint(0, 1):  # 50% chance to also trigger laser
                        all_random(laser)

                # Laser effects for quieter sounds
                elif volume >= laser_threshold:
                    logger.debug(f"LASER EFFECT! Volume: {volume}")
                    all_random(laser)
                    # Turn off strobe for subtle effects
                    strobe.set_strobe(0)  # Strobe off

                # No effects for very quiet sounds
                else:
                    # Optionally turn off effects when volume is too low
                    if volume < 5:  # Very quiet
                        strobe.set_strobe(0)  # Turn off strobe
                        laser.set_mode_level(0)  # Turn off laser

                # Small delay to prevent overwhelming the system
                time.sleep(0.01)


if __name__ == "__main__":
    main()
