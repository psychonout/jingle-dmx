import time
from random import randint

from loguru import logger

from light_strip import VUMeter
from strobe import Strobe
from usb_mic import USBMicrophone


def main():
    # List available USB microphones first
    logger.debug("Available USB microphones:")
    # list_usb_microphones()

    # You can specify a device name or index here
    # For example: USBMicrophone(device_name="USB Audio Device")
    # Or: USBMicrophone(device_index=1)

    # Volume thresholds for different effects
    strobe_threshold = 100  # Higher threshold for strobe effects
    combo_threshold = 150  # Even higher threshold for combined effects
    min_threshold = 25
    max_vol = 0

    with USBMicrophone() as usb_mic:
        if not usb_mic.is_open:
            logger.debug("Failed to open USB microphone")
            return

        with (
            Strobe() as strobe,
            VUMeter(brightness=0.3, decay_rate=0.85, auto_scale=True) as vu_meter,
        ):
            strobe.set_dimmer(255)  # Set strobe to full brightness
            logger.debug(
                "Starting audio-reactive laser and strobe show with VU meter..."
            )

            while True:
                volume = usb_mic.read()
                logger.debug(volume)

                # Update VU meter with current volume
                vu_meter.update(volume)

                if volume > max_vol:
                    max_vol = volume
                    logger.debug(f"New max volume: {max_vol}")

                # Combined effects for very loud sounds
                if volume >= combo_threshold:
                    logger.debug(f"COMBO EFFECT! Volume: {volume}")
                    # Trigger both laser and strobe effects
                    strobe.set_strobe(randint(192, 223))  # Random strobe effect
                    strobe.set_color(randint(0, 255))  # Random color
                    strobe.set_macro(randint(0, 255))  # Random macro

                # Strobe effects for moderately loud sounds
                elif volume >= strobe_threshold:
                    logger.debug(f"STROBE EFFECT! Volume: {volume}")
                    strobe.set_strobe(randint(64, 159))  # Simple strobe or pulse
                    strobe.set_color(randint(0, 255))  # Random color

                # No effects for very quiet sounds
                else:
                    # Optionally turn off effects when volume is too low
                    if volume < min_threshold:  # Very quiet
                        strobe.set_strobe(0)  # Turn off strobe

                # Small delay to prevent overwhelming the system
                time.sleep(0.01)


if __name__ == "__main__":
    main()
