import colorsys
import threading
import time
import random
from typing import Optional

from blinkt import NUM_PIXELS, clear, set_brightness, set_pixel, show
from loguru import logger


class VUMeter:
    """
    A VU meter class for displaying volume levels on a Blinkt! LED strip.
    Shows volume as a percentage with color-coded levels.

    Optimized to run LED updates in a background thread to avoid blocking
    the main audio processing loop.
    """

    def __init__(
        self,
        brightness=0.2,
        decay_rate=0.8,
        min_bars=1,
        auto_scale=False,
        reverse=False,
        color_start_hue: float = 0.75,
        color_end_hue: float = 1,
        min_saturation: float = 0.85,
        max_saturation: float = 1.0,
        min_brightness: float = 0.03,
        max_brightness: float = 0.25,
    ):
        self.brightness = brightness
        self.decay_rate = decay_rate
        self.min_bars = min_bars
        self.auto_scale = auto_scale
        self.reverse = reverse
        self.max_volume = 500
        self.max_volume_decay = 0.995
        self.current_level = 0
        self.peak_level = 0
        self.is_initialized = False
        self.last_update_time = time.time()

        # Threading support
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._latest_volume = 0.0
        self._lock = threading.Lock()

        self._initialize_strip()

        self.color_start_hue = color_start_hue
        self.color_end_hue = color_end_hue
        self.min_saturation = min_saturation
        self.max_saturation = max_saturation
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self._led_caps = None
        self.was_on = False

    def _initialize_strip(self):
        try:
            set_brightness(self.brightness)
            clear()
            show()
            self.is_initialized = True
            logger.debug("VU meter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize VU meter: {e}")
            self.is_initialized = False

    def start(self):
        """Start the background update thread"""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()
        logger.debug("VU meter background thread started")

    def stop(self):
        """Stop the background update thread"""
        if self._thread is None:
            return

        self._stop_event.set()
        self._thread.join(timeout=1.0)
        self._thread = None
        logger.debug("VU meter background thread stopped")

    def _update_loop(self):
        """Background loop to update LEDs at a fixed rate"""
        target_fps = 60
        frame_time = 1.0 / target_fps

        while not self._stop_event.is_set():
            start_time = time.time()

            # Get latest volume safely
            with self._lock:
                volume = self._latest_volume

            self._process_frame(volume)

            # Sleep to maintain frame rate
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_time - elapsed)
            time.sleep(sleep_time)

    def _map_value(self, value, in_min, in_max, out_min, out_max):
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def _get_color_for_level(self, level_percentage):
        hue = self.color_start_hue + (self.color_end_hue - self.color_start_hue) * level_percentage

        min_sat, max_sat = (
            (self.min_saturation, self.max_saturation)
            if self.min_saturation <= self.max_saturation
            else (self.max_saturation, self.min_saturation)
        )
        saturation = min_sat + (max_sat - min_sat) * level_percentage

        min_b, max_b = (
            (self.min_brightness, self.max_brightness)
            if self.min_brightness <= self.max_brightness
            else (self.max_brightness, self.min_brightness)
        )
        brightness = min_b + (max_b - min_b) * level_percentage

        r, g, b = colorsys.hsv_to_rgb(hue, saturation, brightness)
        return int(r * 255), int(g * 255), int(b * 255)

    def _cap_color_per_led(self, rgb, pixel_index):
        if self._led_caps is None:
            lower_count = max(0, NUM_PIXELS - 3)
            caps = [64] * lower_count
            ramp_steps = NUM_PIXELS - lower_count
            for i in range(ramp_steps):
                pct = (i + 1) / float(ramp_steps)
                caps.append(int(64 + pct * (128 - 64)))
            self._led_caps = caps

        cap = self._led_caps[pixel_index]
        r, g, b = rgb
        max_channel = max(r, g, b)
        if max_channel <= cap or max_channel == 0:
            return r, g, b
        scale = cap / float(max_channel)
        return int(r * scale), int(g * scale), int(b * scale)

    def update(self, volume):
        """Update the target volume (thread-safe)"""
        if not self.is_initialized:
            return

        with self._lock:
            self._latest_volume = volume

    def _process_frame(self, volume):
        """Internal method to render one frame (called by background thread)"""
        current_time = time.time()
        time_delta = current_time - self.last_update_time
        self.last_update_time = current_time

        if self.auto_scale:
            if volume > self.max_volume:
                self.max_volume = volume * 1.1
            else:
                self.max_volume *= self.max_volume_decay
                self.max_volume = max(self.max_volume, 100)

        if volume > self.peak_level:
            self.peak_level = volume
        else:
            decay_factor = self.decay_rate ** (time_delta * 30)
            self.peak_level *= decay_factor

        level_percentage = min(1.0, self.peak_level / self.max_volume)
        num_bars = max(self.min_bars, int(level_percentage * NUM_PIXELS))
        num_bars = min(NUM_PIXELS, num_bars)

        if num_bars == 0:
            if self.was_on:
                shift = random.random()
                self.color_start_hue = (self.color_start_hue + shift) % 1.0
                self.color_end_hue = (self.color_end_hue + shift) % 1.0
                self.was_on = False
            clear()
            show()
        else:
            self.was_on = True
            clear()
            for i in range(num_bars):
                bar_percentage = (i + 1) / NUM_PIXELS
                r, g, b = self._get_color_for_level(bar_percentage)
                pixel_index = (NUM_PIXELS - 1 - i) if self.reverse else i
                r, g, b = self._cap_color_per_led((r, g, b), pixel_index)
                set_pixel(pixel_index, r, g, b)

            if num_bars > 1:
                peak_bar = min(NUM_PIXELS - 1, int(level_percentage * NUM_PIXELS))
                r, g, b = self._get_color_for_level(level_percentage)
                r = min(255, int(r * 1.25))
                g = min(255, int(g * 1.25))
                b = min(255, int(b * 1.25))
                pixel_index = (NUM_PIXELS - 1 - peak_bar) if self.reverse else peak_bar
                r, g, b = self._cap_color_per_led((r, g, b), pixel_index)
                set_pixel(pixel_index, r, g, b)

            show()

    def set_max_volume(self, max_volume):
        self.max_volume = max_volume

    def reset(self):
        if self.is_initialized:
            clear()
            show()
            self.peak_level = 0
            self.current_level = 0

    def cleanup(self):
        self.stop()
        if self.is_initialized:
            clear()
            show()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def set_color_range(
        self,
        start_hue: float,
        end_hue: float,
        min_saturation: Optional[float] = None,
        max_saturation: Optional[float] = None,
        min_brightness: Optional[float] = None,
        max_brightness: Optional[float] = None,
    ) -> None:
        self.color_start_hue = start_hue
        self.color_end_hue = end_hue
        if min_saturation is not None:
            self.min_saturation = min_saturation
        if max_saturation is not None:
            self.max_saturation = max_saturation
        if min_brightness is not None:
            self.min_brightness = min_brightness
        if max_brightness is not None:
            self.max_brightness = max_brightness


def test_vu_meter():
    logger.debug("Testing VU meter...")
    with VUMeter(brightness=0.3, decay_rate=0.9) as vu:
        test_volumes = [0, 50, 100, 200, 500, 800, 1000, 1200, 800, 400, 100, 0]
        for volume in test_volumes:
            logger.debug(f"Testing volume: {volume}")
            vu.update(volume)
            time.sleep(0.5)
    logger.debug("VU meter test complete")


if __name__ == "__main__":
    test_vu_meter()
