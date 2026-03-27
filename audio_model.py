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

    # Music pattern detection state (optional).
    on_bar: bool = False
    on_phrase: bool = False
    building_energy: bool = False
    energy_drop: bool = False
    pattern_detected: bool = False
    pattern_confidence: float = 0.0
    beat_index: int = 0
