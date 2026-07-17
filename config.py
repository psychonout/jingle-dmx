import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DeviceConfig:
    use_laser: bool = True
    use_strobe: bool = True
    use_spotlight: bool = True
    use_stinger: bool = True
    use_vu_meter: bool = True
    use_eurolite_strobe: bool = True


@dataclass
class ShowProfile:
    """Configuration for which effect families are active and how random.

    This gives us a coarse but useful way to shape the overall feel of
    a show ("chill" vs "club") and to make behaviour more repeatable by
    fixing the random seed and which effect families are allowed.
    """

    name: str = "default"

    # Effect family toggles
    enable_beat: bool = True
    enable_frequency: bool = True
    enable_combo: bool = True
    enable_mega_combo: bool = True
    enable_strobe_only: bool = True
    enable_ambient: bool = True
    enable_subtle: bool = True

    # Randomness / repeatability
    random_seed: Optional[int] = None

    # Very coarse brightness / intensity caps. These are not wired into
    # every device call yet, but give us clear knobs to extend into.
    max_strobe_level: int = 255
    max_dimmer_level: int = 255
    max_uv_level: int = 255
    max_laser_level: int = 255
    max_vu_level: int = 255
    max_eurolite_level: int = 255


def load_default_profile() -> ShowProfile:
    """Select a default profile based on environment.

    For now we support a handful of hard-coded profiles and pick them
    via the SHOW_PROFILE env var. This keeps things very simple but
    already gives us a repeatable way to run "chill" vs "club" shows.
    """
    env_name = os.getenv("SHOW_PROFILE", "club").strip().lower() or "club"

    if env_name == "chill":
        return ShowProfile(
            name="chill",
            enable_beat=True,
            enable_frequency=True,
            enable_combo=False,
            enable_mega_combo=False,
            enable_strobe_only=False,
            enable_ambient=True,
            enable_subtle=True,
            random_seed=42,
            max_strobe_level=160,
            max_dimmer_level=180,
            max_uv_level=180,
            max_laser_level=180,
            max_vu_level=180,
            max_eurolite_level=180,
        )
    if env_name == "bass_party":
        return ShowProfile(
            name="bass_party",
            enable_beat=True,
            enable_frequency=True,
            enable_combo=True,
            enable_mega_combo=False,
            enable_strobe_only=False,
            enable_ambient=True,
            enable_subtle=False,
            random_seed=1337,
            max_strobe_level=220,
            max_dimmer_level=220,
            max_uv_level=255,
            max_laser_level=220,
            max_vu_level=220,
            max_eurolite_level=220,
        )
    if env_name == "ambient_subtle":
        return ShowProfile(
            name="ambient_subtle",
            enable_beat=False,
            enable_frequency=False,
            enable_combo=False,
            enable_mega_combo=False,
            enable_strobe_only=False,
            enable_ambient=True,
            enable_subtle=True,
            random_seed=2025,
            max_strobe_level=80,
            max_dimmer_level=100,
            max_uv_level=80,
            max_laser_level=80,
            max_vu_level=100,
            max_eurolite_level=80,
        )
    # Default "club" profile: everything on, high energy.
    return ShowProfile(
        name="club",
        enable_beat=True,
        enable_frequency=True,
        enable_combo=True,
        enable_mega_combo=True,
        enable_strobe_only=True,
        enable_ambient=True,
        enable_subtle=True,
        random_seed=None,
        max_strobe_level=255,
        max_dimmer_level=255,
        max_uv_level=255,
        max_laser_level=255,
        max_vu_level=255,
        max_eurolite_level=255,
    )
