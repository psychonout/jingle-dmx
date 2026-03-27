"""ADJ Stinger II DMX Adapter (9-channel mode).

Mapping based on manual (pages 21-22):

- CH1  Show Mode
    000-009: no function
    010-044: Show 1
    045-079: Show 2
    080-114: Show 3
    115-149: Show 4
    150-184: Show 5
    185-219: Show 6
    220-255: Random show

- CH2  Show Speed / Sound Sense
    000-247: show speed (slow → fast)
    248-255: sound active

- CH3  Color Macro
    000-009: no function
    010-198: color change
    199-225: color fade 1
    226-255: color fade 2

- CH4  LED Strobe (main LEDs)
    000-009: no strobe
    010-244: strobe (slow → fast)
    245-255: sound-active strobing

- CH5  UV LEDs
    000-134: blackout
    135-255: UV chase

- CH6  UV LED Strobe & Chase Speed
    000-127: chase, no strobe (slow → fast)
    128-255: chase, strobing (slow → fast)

- CH7  Laser Strobe Control
    000-009: no strobe
    010-244: strobe (slow → fast)
    245-255: sound-active strobing

- CH8  LED Rotation (moonflower rotation)
    000-009: no rotation
    010-127: clockwise, slow → fast
    128-255: counter-clockwise, slow → fast

- CH9  Laser Rotation / Patterns
    000-127: laser patterns
    128-255: pattern chase, slow → fast
"""

import random

from base_dmx import BaseDMX


def _clamp(value: int, min_value: int = 0, max_value: int = 255) -> int:
    return max(min_value, min(max_value, int(value)))


class StingerII(BaseDMX):
    """ADJ Stinger II 3-FX-IN-1 DMX Controller (9-channel profile)."""

    def __init__(self, dmx_channel: int = 33) -> None:
        super().__init__(dmx_channel, num_channels=9)
        self.name = "ADJ Stinger II"

        # Internal state (very lightweight, mainly for status/debugging)
        self.show_mode: int = 0
        self.show_speed: int = 0
        self.color_macro: int = 0
        self.led_strobe: int = 0
        self.uv_level: int = 0
        self.uv_chase_speed: int = 0
        self.laser_strobe: int = 0
        self.moonflower_rotation: int = 0
        self.laser_rotation: int = 0

        self.reset()

    # ------------------------------------------------------------------
    # low level helpers
    # ------------------------------------------------------------------

    def _ch(self, offset: int) -> int:
        """Translate 1-based fixture channel number to BaseDMX 0-based offset.

        BaseDMX._send expects a 0-based offset from the fixture start address:
        offset 0 -> fixture CH1, offset 1 -> fixture CH2, ...
        """

        return offset - 1

    def reset(self) -> None:
        """Reset all 9 channels used by the Stinger II."""

        for i in range(1, 10):
            self._send(self._ch(i), 0)

        self.show_mode = 0
        self.show_speed = 0
        self.color_macro = 0
        self.led_strobe = 0
        self.uv_level = 0
        self.uv_chase_speed = 0
        self.laser_strobe = 0
        self.moonflower_rotation = 0
        self.laser_rotation = 0

    # ------------------------------------------------------------------
    # high‑level semantic controls
    # ------------------------------------------------------------------

    def set_show_mode(self, mode: int = 7, *, random_on_top: bool = True) -> None:
        """Select one of the internal shows or turn shows off.

        `mode` values:
        - 0  → off (no function region)
        - 1‑6 → Show 1‑6
        - 7  → Random show (if ``random_on_top``)
        - "random" or 8 → Randomly select 1-7
        """

        if isinstance(mode, str) and mode.lower() == "random":
            mode = random.randint(1, 7)
        elif mode == 8:  # alias for random
            mode = random.randint(1, 7)

        if mode <= 0:
            value = 0
        elif 1 <= mode <= 6:
            # Map 1‑6 roughly into the documented ranges.
            ranges = [
                (10, 44),
                (45, 79),
                (80, 114),
                (115, 149),
                (150, 184),
                (185, 219),
            ]
            lo, hi = ranges[mode - 1]
            value = random.randint(lo, hi)  # Randomize within the range
        else:
            # Random show
            lo, hi = 220, 255
            value = random.randint(lo, hi) if random_on_top else lo

        value = _clamp(value)
        self.show_mode = value
        self._send(self._ch(1), value)

    def set_show_speed(self, speed: int = 128, *, sound_active: bool = False) -> None:
        """Set show speed or enable sound‑active shows on CH2.

        - ``sound_active=False``: ``speed`` is 0‑247, slow → fast.
        - ``sound_active=True``: CH2 is forced into 248‑255 region.
        """

        if sound_active:
            value = 250
        else:
            value = _clamp(speed, 0, 247)

        self.show_speed = value
        self._send(self._ch(2), value)

    def set_color_macro(self, mode: str = "random") -> None:
        """Control color macro behaviour on CH3.

        ``mode`` can be ``"off"``, ``"change"``, ``"fade1"``, ``"fade2"``, or ``"random"``.
        For "random", randomly selects between change, fade1, and fade2 with random values.
        """

        mode = (mode or "random").lower()
        if mode in {"off", "none"}:
            value = 0
        elif mode == "fade1":
            value = random.randint(199, 225)
        elif mode == "fade2":
            value = random.randint(226, 255)
        elif mode == "change":
            value = random.randint(10, 198)
        else:  # "random" default
            modes = ["change", "fade1", "fade2"]
            selected_mode = random.choice(modes)
            if selected_mode == "change":
                value = random.randint(10, 198)
            elif selected_mode == "fade1":
                value = random.randint(199, 225)
            else:  # fade2
                value = random.randint(226, 255)

        value = _clamp(value)
        self.color_macro = value
        self._send(self._ch(3), value)

    def set_led_strobe(self, speed: int = 0, *, sound_active: bool = False) -> None:
        """Main LED strobe on CH4.

        - ``speed=0`` and ``sound_active=False`` → no strobe.
        - Otherwise 10‑244 or 245‑255 for sound‑active.
        """

        if sound_active:
            value = 250
        elif speed <= 0:
            value = 0
        else:
            value = 10 + int(max(0, min(244 - 10, speed)))

        value = _clamp(value)
        self.led_strobe = value
        self._send(self._ch(4), value)

    def set_uv(self, level: int = 255) -> None:
        """Set UV chase intensity on CH5.

        - ``level <= 0`` → blackout.
        - ``level > 0`` → 135‑255 scaled by ``level``.
        """

        if level <= 0:
            value = 0
        else:
            level = _clamp(level)
            span = 255 - 135
            value = 135 + (span * level) // 255

        value = _clamp(value)
        self.uv_level = value
        self._send(self._ch(5), value)

    def set_uv_chase(self, speed: int = 128, *, strobing: bool = False) -> None:
        """Control UV chase / strobe on CH6.

        - ``strobing=False`` → 0‑127 (no strobe).
        - ``strobing=True`` → 128‑255 (with strobe).
        """

        speed = _clamp(speed, 0, 127)
        if strobing:
            value = 128 + speed
        else:
            value = speed

        value = _clamp(value)
        self.uv_chase_speed = value
        self._send(self._ch(6), value)

    def set_laser_output(
        self,
        *,
        mode: str = "both",
        strobe_speed: int = 0,
        strobe_sound_active: bool = False,
        rotation_raw: int | None = None,
        chase_speed: int | None = None,
    ) -> None:
        """Control laser behaviour using CH6, CH7 and CH9.

        CH6 controls which lasers are on:
        - 0-9: Blackout (laser OFF)
        - 10-49: Red Laser
        - 50-89: Green Laser
        - 90-129: Red and Green Lasers
        - 130+: Various flicker modes

        CH7 controls laser strobe.
        CH9 controls laser rotation/patterns.
        """

        # CH6 – Laser on/off and color selection
        # If strobe_speed and rotation are both 0, turn laser off completely
        if (
            strobe_speed <= 0
            and (rotation_raw is None or rotation_raw <= 0)
            and chase_speed is None
        ):
            laser_mode_val = 0  # Blackout
        else:
            # Laser on - use RED LASER ONLY
            laser_mode_val = 30  # Red Laser Only (10-49 range)

        self._send(self._ch(6), laser_mode_val)

        # CH7 – strobe
        if strobe_sound_active:
            strobe_val = 250
        elif strobe_speed <= 0:
            strobe_val = 0
        else:
            strobe_val = 10 + int(max(0, min(244 - 10, strobe_speed)))

        strobe_val = _clamp(strobe_val)
        self.laser_strobe = strobe_val
        self._send(self._ch(7), strobe_val)

        # CH9 – rotation/patterns
        if rotation_raw is None and chase_speed is None:
            # Default to off when no parameters provided
            value = 0
        elif rotation_raw is not None:
            value = _clamp(rotation_raw)
        else:  # chase_speed provided
            assert chase_speed is not None
            chase_val = _clamp(chase_speed, 0, 127)
            value = 128 + chase_val

        self.laser_rotation = value
        self._send(self._ch(9), value)

    def set_moonflower_rotation(
        self, direction: str = "cw", *, speed: int = 127
    ) -> None:
        """Set moonflower rotation via CH8.

        - ``direction="stop"`` → no rotation region (0‑9).
        - ``direction="cw"`` → 10‑127 (slow → fast).
        - ``direction="ccw"`` → 128‑255 (slow → fast).
        """

        direction = (direction or "cw").lower()
        speed = _clamp(speed, 0, 127)

        if direction in {"stop", "none", "off"}:
            value = 0
        elif direction == "ccw":
            value = 128 + speed
        else:  # "cw" default
            value = max(10, min(127, 10 + speed))

        value = _clamp(value)
        self.moonflower_rotation = value
        self._send(self._ch(8), value)

    # ------------------------------------------------------------------
    # convenience scenes used by the audio show
    # ------------------------------------------------------------------

    def blackout(self) -> None:
        """Turn off all 9 DMX channels used by the Stinger II."""

        for i in range(1, 10):
            self._send(self._ch(i), 0)

        self.show_mode = 0
        self.show_speed = 0
        self.color_macro = 0
        self.led_strobe = 0
        self.uv_level = 0
        self.uv_chase_speed = 0
        self.laser_strobe = 0
        self.moonflower_rotation = 0
        self.laser_rotation = 0

    def party_mode(self) -> None:
        """A bright, busy look: internal show, UV, laser and rotation."""

        self.set_show_mode(7)  # random show
        self.set_show_speed(180, sound_active=True)
        self.set_color_macro("change")
        self.set_led_strobe(150)
        self.set_uv(255)
        self.set_uv_chase(100, strobing=True)
        self.set_laser_output(strobe_speed=150, strobe_sound_active=True)
        self.set_moonflower_rotation(direction="cw", speed=100)

    def get_status(self) -> dict:
        """Return a small status snapshot for debugging / tests."""

        return {
            "name": self.name,
            "dmx_channel": self.dmx_channel,
            "show_mode": self.show_mode,
            "show_speed": self.show_speed,
            "color_macro": self.color_macro,
            "led_strobe": self.led_strobe,
            "uv_level": self.uv_level,
            "uv_chase_speed": self.uv_chase_speed,
            "laser_strobe": self.laser_strobe,
            "moonflower_rotation": self.moonflower_rotation,
            "laser_rotation": self.laser_rotation,
        }
