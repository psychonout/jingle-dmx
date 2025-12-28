#!/usr/bin/env python3
"""
Dynamic threshold system for audio-reactive lighting
"""

import statistics
import time
from collections import deque
from typing import Deque

from loguru import logger


class DynamicThresholds:
    """
    Dynamic threshold system that adapts to audio environment
    """

    def __init__(
        self,
        history_size: int = 300,  # ~5 seconds at 60fps
        update_interval: float = 1.0,  # Update every second
        min_threshold_ratio: float = 0.3,  # 30% of average
        strobe_threshold_ratio: float = 0.6,  # 60% of average
        combo_threshold_ratio: float = 0.8,
    ):  # 80% of average
        self.history_size = history_size
        self.update_interval = update_interval
        self.min_threshold_ratio = min_threshold_ratio
        self.strobe_threshold_ratio = strobe_threshold_ratio
        self.combo_threshold_ratio = combo_threshold_ratio

        # Volume history for dynamic calculation
        self.volume_history: Deque[float] = deque(maxlen=history_size)
        self.last_update = time.time()

        # Current thresholds
        self.min_threshold = 25
        self.strobe_threshold = 100
        self.combo_threshold = 150

        # Statistics
        self.current_average = 0
        self.current_max = 0
        self.current_std_dev = 0

        logger.debug("Dynamic threshold system initialized")

    def update(self, volume: float) -> None:
        """Update thresholds based on current volume"""
        # Add to history
        self.volume_history.append(volume)

        # Update thresholds periodically
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            self._recalculate_thresholds()
            self.last_update = current_time

    def _recalculate_thresholds(self) -> None:
        """Recalculate thresholds based on volume history"""
        if len(self.volume_history) < 10:  # Need some history first
            return

        # Calculate statistics
        volumes = list(self.volume_history)
        self.current_average = statistics.mean(volumes)
        self.current_max = max(volumes)

        try:
            self.current_std_dev = statistics.stdev(volumes)
        except statistics.StatisticsError:
            self.current_std_dev = 0

        # Calculate new thresholds based on statistics
        # Method 1: Based on percentiles
        sorted_volumes = sorted(volumes)
        n = len(sorted_volumes)

        # Use percentiles for more robust thresholds
        percentile_50 = sorted_volumes[int(n * 0.5)]
        percentile_75 = sorted_volumes[int(n * 0.75)]
        percentile_90 = sorted_volumes[int(n * 0.9)]

        # Set thresholds based on percentiles
        self.min_threshold = max(5, percentile_50 * 0.6)  # Lower for more activity
        self.strobe_threshold = max(
            self.min_threshold + 5, percentile_75 * 0.8
        )  # Much lower
        self.combo_threshold = max(
            self.strobe_threshold + 5, percentile_90 * 0.9
        )  # Lower

        logger.debug(
            f"Updated thresholds - Min: {self.min_threshold:.1f}, "
            f"Strobe: {self.strobe_threshold:.1f}, "
            f"Combo: {self.combo_threshold:.1f}"
        )
        logger.debug(
            f"Stats - Avg: {self.current_average:.1f}, "
            f"Max: {self.current_max:.1f}, "
            f"StdDev: {self.current_std_dev:.1f}"
        )

    def get_thresholds(self) -> tuple[float, float, float]:
        """Get current thresholds"""
        return self.min_threshold, self.strobe_threshold, self.combo_threshold

    def get_stats(self) -> dict:
        """Get current statistics"""
        return {
            "average": self.current_average,
            "max": self.current_max,
            "std_dev": self.current_std_dev,
            "min_threshold": self.min_threshold,
            "strobe_threshold": self.strobe_threshold,
            "combo_threshold": self.combo_threshold,
            "history_size": len(self.volume_history),
        }


class AdaptiveThresholds:
    """
    More aggressive adaptive system that responds quickly to changes
    """

    def __init__(
        self,
        smoothing_factor: float = 0.95,  # Higher = more smoothing
        sensitivity: float = 1.5,  # Threshold sensitivity
        min_change_threshold: float = 5.0,
        threshold_update_interval: float = 5.0,  # Only update thresholds every 5 seconds
    ):  # Minimum change needed
        self.smoothing_factor = smoothing_factor
        self.sensitivity = sensitivity
        self.min_change_threshold = min_change_threshold
        self.threshold_update_interval = threshold_update_interval
        self.last_threshold_update = 0

        # Exponential moving averages
        self.ema_volume = 0
        self.ema_peak = 0
        self.ema_variance = 0

        # Current thresholds
        self.min_threshold = 10
        self.strobe_threshold = 30
        self.combo_threshold = 60

        logger.debug("Adaptive threshold system initialized")

    def update(self, volume: float) -> None:
        """Update thresholds with exponential moving averages"""
        # Update exponential moving averages
        if self.ema_volume == 0:  # First update
            self.ema_volume = max(volume, 10)
            self.ema_peak = max(volume, 10)
        else:
            # Update EMA for volume with asymmetric smoothing
            # Rise slowly (high smoothing) to maintain sensitivity during loud sections
            # Fall quickly (lower smoothing) to recover sensitivity during quiet sections
            if volume > self.ema_volume:
                # Rising: use base smoothing factor (e.g. 0.95)
                factor = self.smoothing_factor
            else:
                # Falling: use reduced smoothing factor for faster decay
                # e.g. if 0.95 -> 0.90, if 0.9 -> 0.8
                factor = max(0.8, self.smoothing_factor - 0.05)

            self.ema_volume = (
                factor * self.ema_volume
                + (1 - factor) * volume
            )

            # Update EMA for peak detection
            if volume > self.ema_peak:
                self.ema_peak = volume
            else:
                self.ema_peak = (
                    self.smoothing_factor * self.ema_peak
                    + (1 - self.smoothing_factor) * volume
                )

        # Calculate variance
        variance = abs(volume - self.ema_volume)
        self.ema_variance = (
            self.smoothing_factor * self.ema_variance
            + (1 - self.smoothing_factor) * variance
        )

        # Only update output thresholds periodically to prevent jitter
        current_time = time.time()
        if current_time - self.last_threshold_update < self.threshold_update_interval:
            return

        self.last_threshold_update = current_time

        # Calculate dynamic thresholds
        base_threshold = self.ema_volume + (self.ema_variance * self.sensitivity)

        # Hard cap: prevent thresholds drifting beyond a sane upper bound
        # so effects remain reachable without endlessly increasing volume.
        max_base = 220.0
        if base_threshold > max_base:
            base_threshold = max_base

        # Set thresholds with minimum spacing
        new_min = max(10, base_threshold * 0.7)
        new_strobe = max(new_min + 10, base_threshold * 1.0)
        new_combo = max(new_strobe + 10, base_threshold * 1.3)

        # Soft floor/ceiling to keep thresholds in a practical band
        max_threshold = 255.0
        new_min = min(new_min, max_threshold * 0.6)
        new_strobe = min(new_strobe, max_threshold * 0.8)
        new_combo = min(new_combo, max_threshold)

        # Apply smoothing to threshold changes
        self.min_threshold = self._smooth_threshold_change(self.min_threshold, new_min)
        self.strobe_threshold = self._smooth_threshold_change(
            self.strobe_threshold, new_strobe
        )
        self.combo_threshold = self._smooth_threshold_change(
            self.combo_threshold, new_combo
        )

    def _smooth_threshold_change(self, current: float, new: float) -> float:
        """Smooth threshold changes to prevent jitter"""
        change = abs(new - current)
        if change < self.min_change_threshold:
            return current

        # Gradual change
        return current + (new - current) * 0.1

    def get_thresholds(self) -> tuple[float, float, float]:
        """Get current thresholds"""
        return self.min_threshold, self.strobe_threshold, self.combo_threshold

    def get_stats(self) -> dict:
        """Get current statistics"""
        return {
            "ema_volume": self.ema_volume,
            "ema_peak": self.ema_peak,
            "ema_variance": self.ema_variance,
            "min_threshold": self.min_threshold,
            "strobe_threshold": self.strobe_threshold,
            "combo_threshold": self.combo_threshold,
        }


def test_dynamic_thresholds():
    """Test the dynamic threshold systems"""
    import random

    # Test both systems
    dynamic = DynamicThresholds(history_size=50)
    adaptive = AdaptiveThresholds()

    logger.debug("Testing dynamic threshold systems...")

    # Simulate different audio environments
    environments = [
        ("Quiet room", lambda: random.uniform(0, 30)),
        ("Normal conversation", lambda: random.uniform(10, 80)),
        ("Loud party", lambda: random.uniform(50, 200)),
        ("Concert", lambda: random.uniform(100, 300)),
    ]

    for env_name, volume_gen in environments:
        logger.debug(f"\n=== Simulating {env_name} ===")

        # Generate volume data for this environment
        for i in range(100):
            volume = volume_gen()

            dynamic.update(volume)
            adaptive.update(volume)

            if i % 20 == 0:  # Log every 20 updates
                dyn_stats = dynamic.get_stats()
                adp_stats = adaptive.get_stats()

                logger.debug(f"Volume: {volume:.1f}")
                logger.debug(
                    f"Dynamic - Min: {dyn_stats['min_threshold']:.1f}, "
                    f"Strobe: {dyn_stats['strobe_threshold']:.1f}, "
                    f"Combo: {dyn_stats['combo_threshold']:.1f}"
                )
                logger.debug(
                    f"Adaptive - Min: {adp_stats['min_threshold']:.1f}, "
                    f"Strobe: {adp_stats['strobe_threshold']:.1f}, "
                    f"Combo: {adp_stats['combo_threshold']:.1f}"
                )

        time.sleep(0.1)


if __name__ == "__main__":
    test_dynamic_thresholds()
