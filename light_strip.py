import colorsys
import time

from blinkt import NUM_PIXELS, clear, set_brightness, set_pixel, show
from loguru import logger


class VUMeter:
    """
    A VU meter class for displaying volume levels on a Blinkt! LED strip.
    Shows volume as a percentage with color-coded levels.
    """

    def __init__(self, brightness=0.2, decay_rate=0.8, min_bars=1, auto_scale=True):
        """
        Initialize the VU meter.

        Args:
            brightness (float): LED brightness (0.0 to 1.0)
            decay_rate (float): How fast the bars fade (0.0 to 1.0)
            min_bars (int): Minimum number of bars to always show
            auto_scale (bool): Whether to automatically scale max volume
        """
        self.brightness = brightness
        self.decay_rate = decay_rate
        self.min_bars = min_bars
        self.auto_scale = auto_scale
        self.max_volume = 500  # Starting max volume
        self.max_volume_decay = 0.998  # Slow decay for max volume
        self.current_level = 0
        self.peak_level = 0
        self.is_initialized = False
        self.last_update_time = time.time()

        # Initialize the LED strip
        self._initialize_strip()

    def _initialize_strip(self):
        """Initialize the LED strip"""
        try:
            set_brightness(self.brightness)
            clear()
            show()
            self.is_initialized = True
            logger.debug("VU meter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize VU meter: {e}")
            self.is_initialized = False

    def _map_value(self, value, in_min, in_max, out_min, out_max):
        """Map a value from one range to another"""
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def _get_color_for_level(self, level_percentage):
        """
        Get color based on volume level percentage.

        Args:
            level_percentage (float): Volume level as percentage (0.0 to 1.0)

        Returns:
            tuple: RGB color values (0-255)
        """
        if level_percentage < 0.3:
            # Green for low levels
            hue = 0.33  # Green
        elif level_percentage < 0.7:
            # Yellow for medium levels
            hue = 0.16  # Yellow
        else:
            # Red for high levels
            hue = 0.0  # Red

        # Adjust saturation and brightness based on level
        saturation = 0.8 + (level_percentage * 0.2)  # 0.8 to 1.0
        brightness = 0.5 + (level_percentage * 0.5)  # 0.5 to 1.0

        r, g, b = colorsys.hsv_to_rgb(hue, saturation, brightness)
        return int(r * 255), int(g * 255), int(b * 255)

    def update(self, volume):
        """
        Update the VU meter with a new volume reading.

        Args:
            volume (float): Current volume level
        """
        if not self.is_initialized:
            logger.warning("VU meter not initialized, skipping update")
            return

        current_time = time.time()
        time_delta = current_time - self.last_update_time
        self.last_update_time = current_time

        # Auto-scale max volume with decay
        if self.auto_scale:
            # If current volume is higher than max, increase max
            if volume > self.max_volume:
                self.max_volume = volume * 1.1  # Add 10% headroom
                logger.debug(f"Max volume increased to: {self.max_volume:.1f}")
            else:
                # Slowly decay max volume so it can adjust downward
                self.max_volume *= self.max_volume_decay
                # Don't let max volume go below a reasonable minimum
                self.max_volume = max(self.max_volume, 100)

        # Calculate current level with decay
        if volume > self.peak_level:
            self.peak_level = volume
        else:
            # Apply decay based on time elapsed
            decay_factor = self.decay_rate ** (time_delta * 60)  # Adjust for frame rate
            self.peak_level *= decay_factor

        # Calculate percentage (0.0 to 1.0)
        level_percentage = min(1.0, self.peak_level / self.max_volume)

        # Calculate number of bars to light up
        num_bars = max(self.min_bars, int(level_percentage * NUM_PIXELS))
        num_bars = min(NUM_PIXELS, num_bars)

        # Clear all pixels
        clear()

        # Light up the appropriate number of bars (reversed order)
        for i in range(num_bars):
            # Each bar gets progressively brighter color
            bar_percentage = (i + 1) / NUM_PIXELS
            r, g, b = self._get_color_for_level(bar_percentage)
            # Set pixel from the end (NUM_PIXELS - 1 - i) to reverse the direction
            set_pixel(NUM_PIXELS - 1 - i, r, g, b)

        # Add a peak indicator (brightest pixel at current level)
        if num_bars > 0:
            peak_bar = min(NUM_PIXELS - 1, int(level_percentage * NUM_PIXELS))
            r, g, b = self._get_color_for_level(level_percentage)
            # Make peak bar brighter
            r = min(255, int(r * 1.5))
            g = min(255, int(g * 1.5))
            b = min(255, int(b * 1.5))
            # Set peak pixel from the end to reverse the direction
            set_pixel(NUM_PIXELS - 1 - peak_bar, r, g, b)

        # Update the display
        show()

        # Log debug info occasionally
        if int(current_time * 2) % 10 == 0:  # Every 5 seconds
            logger.debug(
                f"VU: vol={volume:.1f}, level={level_percentage:.2f}, bars={num_bars}, max_vol={self.max_volume:.1f}"
            )

    def set_max_volume(self, max_volume):
        """
        Manually set the maximum volume level.

        Args:
            max_volume (float): Maximum volume level for scaling
        """
        self.max_volume = max_volume
        logger.debug(f"Max volume set to: {max_volume}")

    def reset(self):
        """Reset the VU meter to initial state"""
        if self.is_initialized:
            clear()
            show()
            self.peak_level = 0
            self.current_level = 0
            logger.debug("VU meter reset")

    def cleanup(self):
        """Clean up the VU meter"""
        if self.is_initialized:
            clear()
            show()
            logger.debug("VU meter cleaned up")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()


def test_vu_meter():
    """Test function for the VU meter"""
    logger.info("Testing VU meter...")

    with VUMeter(brightness=0.3, decay_rate=0.9) as vu:
        # Test with increasing volume levels
        test_volumes = [0, 50, 100, 200, 500, 800, 1000, 1200, 800, 400, 100, 0]

        for volume in test_volumes:
            logger.info(f"Testing volume: {volume}")
            vu.update(volume)
            time.sleep(0.5)

    logger.info("VU meter test complete")


if __name__ == "__main__":
    test_vu_meter()
