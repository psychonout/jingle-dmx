from dataclasses import dataclass


@dataclass(frozen=True)
class AudioFrame:
    """Single snapshot of analyzed audio used for effect decisions."""

    timestamp: float
    rms: float
    peak: float
    beat_detected: bool
    bass_energy: float
    mid_energy: float
    high_energy: float
    total_energy: float

