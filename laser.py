import enum
import math
import sys
import time
from random import randint
from typing import Iterable, Sequence, Tuple

from loguru import logger

from base_dmx import BaseDMX

logger.remove()
logger.add(sys.stderr, level="INFO")


class LaserMode(enum.Enum):
    """DMX mode values for CH1 of the laser."""

    OFF = 0
    MANUAL = 64
    AUTO = 128
    SOUND = 192


class LaserColorMode(enum.Enum):
    """DMX color-mode ranges for CH9.

    IMPORTANT: Color only takes effect in auto/sound modes (CH1=128 or 192).
    In manual mode (CH1=64), CH9 is ignored by the hardware.

    Monochrome range (0–63) is split into three equal segments:
      - 0–20:   Red intensity (0=off, 20=max red)
      - 21–41:  Green intensity (21=off, 41=max green)
      - 42–63:  Blue intensity (42=off, 63=max blue)

    Other ranges:
      - 64–127: Colour mixing
      - 128–192: Monochrome auto-cycle
      - 193–255: Full auto colour cycle
    """

    MONOCHROME = (0, 63)  # RGB segments: R 0-20, G 21-41, B 42-63
    COLOR_MIX = (64, 127)  # Colour mixing
    MONOCHROME_AUTO = (128, 192)  # Monochrome auto-cycle
    FULL_AUTO = (193, 255)  # Full auto colour cycle


# Monochrome RGB segment boundaries within CH9 range 0–63.
MONO_RED_MIN = 0
MONO_RED_MAX = 20
MONO_GREEN_MIN = 21
MONO_GREEN_MAX = 41
MONO_BLUE_MIN = 42
MONO_BLUE_MAX = 63


class LaserPatternFamily(enum.Enum):
    """DMX pattern-family ranges for CH10."""

    DOTS_LINES = (0, 127)  # Dots and lines patterns
    DOTS_STRIPS = (128, 255)  # Dots and wireless strips patterns


# ---------------------------------------------------------------------------
# Manual-mode preset indices (CH2 values 0–255 map to ~51 presets).
# These are the most useful ones identified from the hardware manual.
# ---------------------------------------------------------------------------
MANUAL_PRESETS = {
    "square": (0, 5),
    "circle": (6, 10),
    "line_horizontal": (11, 15),
    "line_vertical": (16, 20),
    "line_diagonal": (21, 25),
    "crescent_vertical": (26, 30),
    "crescent_horizontal": (31, 35),
    "triangle": (36, 40),
    "less_than": (41, 45),
    "equals": (46, 50),
    "double_bar": (51, 55),
    "dash": (56, 60),
    "pipe": (61, 65),
    "zigzag_horizontal": (66, 70),
    "zigzag_vertical": (71, 75),
    "notes": (76, 80),
    "circle_small": (81, 85),
    "christmas_tree": (86, 90),
    "three": (91, 95),
    "circle_large": (96, 100),
    "star": (101, 105),
    "sinewave_horizontal": (106, 110),
    "two": (111, 115),
    "one": (116, 120),
    "heart": (121, 125),
    "apple": (131, 135),
    "dotted_circle": (136, 140),
    "two_circles": (141, 145),
    "pokeball": (146, 150),
    "plus_sign": (156, 160),
    "trippy_circle": (161, 165),
    "trippy_triangle": (166, 170),
    "dpad": (196, 200),
    "arrow_left": (201, 205),
    "rhombus": (231, 235),
    "sawtooth_wave": (236, 240),
}


class Laser(BaseDMX):
    """10-channel DMX laser controller with input validation and safe defaults.

    Channel map (offsets 0–9 relative to the start address):

    ======  ============  ==============================================
    Offset  Name          Value ranges
    ======  ============  ==============================================
    0       Mode          0=off, 64=manual, 128=auto, 192=sound
    1       Mode Level    0–255 (meaning depends on mode; see set_mode_level)
    2       Rotation      0–127=angle, 128–255=speed
    3       H Angle       0–127=angle, 128–255=speed
    4       V Angle       0–127=angle, 128–255=speed
    5       H Position    0–127=pos, 128–255=speed
    6       V Position    0–127=pos, 128–255=speed
    7       Size/Speed    0–63=size, 64–127=enlarge, 128–191=shrink,
                          192–255=speed/zoom
    8       Color         0–63=mono (R 0-20, G 21-41, B 42-63),
                          64–127=mix, 128–192=mono auto, 193–255=auto.
                          **Only effective in auto/sound modes (CH1=128/192).**
    9       Pattern       0–127=dots/lines, 128–255=dots/strips
    ======  ============  ==============================================
    """

    # Named DMX value constants for clarity.
    MODE_OFF = 0
    MODE_MANUAL = 64
    MODE_AUTO = 128
    MODE_SOUND = 192

    # Size channel sub-ranges (CH7).
    SIZE_FIXED_MIN = 0
    SIZE_FIXED_MAX = 63
    SIZE_ENLARGE_MIN = 64
    SIZE_ENLARGE_MAX = 127
    SIZE_SHRINK_MIN = 128
    SIZE_SHRINK_MAX = 191
    SIZE_SPEED_MIN = 192
    SIZE_SPEED_MAX = 255

    def __init__(self, dmx_channel: int = 1):
        """Initialize Laser with specific DMX channel.

        Args:
            dmx_channel: Start address on the DMX universe (1-based).
        """
        super().__init__(dmx_channel, num_channels=10)
        self.status: bool = False
        self._mode: LaserMode = LaserMode.OFF

    def __repr__(self) -> str:
        return (
            f"Laser(ch={self.dmx_channel}, mode={self._mode.name}, "
            f"status={'ON' if self.status else 'OFF'})"
        )

    # ------------------------------------------------------------------
    # Mode control
    # ------------------------------------------------------------------

    def on(self):
        """Turn laser on with sensible defaults (manual mode, circle preset)."""
        self.set_mode("manual")
        self.set_mode_level(8)  # circle preset
        self.color(12)  # monochrome single colour
        self.size(30)  # moderate fixed size
        self.pattern(8)  # dots/lines pattern
        self.status = True

    def off(self):
        """Turn laser off."""
        self._send(0, 0)
        self.status = False

    def set_mode(self, mode: str | LaserMode) -> None:
        """Set the laser operating mode.

        Args:
            mode: One of 'off', 'manual', 'auto', 'sound', or a LaserMode enum.
        """
        if isinstance(mode, LaserMode):
            value = mode.value
        else:
            mode_lower = mode.lower()
            mode_map = {
                "off": LaserMode.OFF,
                "manual": LaserMode.MANUAL,
                "auto": LaserMode.AUTO,
                "sound": LaserMode.SOUND,
            }
            if mode_lower not in mode_map:
                raise ValueError(
                    f"Unknown laser mode '{mode}'. "
                    f"Choose from: {', '.join(mode_map.keys())}"
                )
            value = mode_map[mode_lower].value

        self._mode = LaserMode(value)
        self._send(0, value)
        if value == 0:
            self.status = False

    # ------------------------------------------------------------------
    # Mode level / preset selection
    # ------------------------------------------------------------------

    def set_mode_level(self, level: int) -> None:
        """Set the mode level (CH2).

        In manual mode (0–255): selects one of ~51 preset patterns.
        In auto/sound mode: 0, 64, 128, 192 select one of 4 show programs.

        Args:
            level: DMX value 0–255.
        """
        level = max(0, min(255, int(level)))
        if level == 0:
            self.status = False
        else:
            self.status = True
        self._send(1, level)

    def set_preset(self, name: str, variation: int = 0) -> None:
        """Select a named manual-mode preset by name.

        Args:
            name: Key from MANUAL_PRESETS (e.g. 'circle', 'star', 'heart').
            variation: Offset within the preset range (0 = first variant).

        Raises:
            ValueError: If the preset name is not found.
        """
        if name not in MANUAL_PRESETS:
            raise ValueError(
                f"Unknown preset '{name}'. "
                f"Available: {', '.join(sorted(MANUAL_PRESETS.keys()))}"
            )
        lo, hi = MANUAL_PRESETS[name]
        level = max(lo, min(hi, lo + variation))
        self.set_mode_level(level)

    # ------------------------------------------------------------------
    # Rotation (CH3)
    # ------------------------------------------------------------------

    def rotate(self, angle: int) -> None:
        """Set rotation to a fixed angle.

        Args:
            angle: Angle in DMX units, 0–127. Values above 127 set speed instead.
        """
        angle = max(0, min(127, int(angle)))
        self._send(2, angle)

    def rotation_speed(self, speed: int) -> None:
        """Set continuous rotation speed.

        Args:
            speed: Speed value 128–255. Higher = faster.
        """
        speed = max(128, min(255, int(speed)))
        self._send(2, speed)

    # ------------------------------------------------------------------
    # Horizontal angle (CH4)
    # ------------------------------------------------------------------

    def horizontal_angle(self, angle: int) -> None:
        """Set horizontal flip angle to a fixed position.

        Args:
            angle: Angle in DMX units, 0–127.
        """
        angle = max(0, min(127, int(angle)))
        self._send(3, angle)

    def horizontal_angle_speed(self, speed: int) -> None:
        """Set horizontal flip speed.

        Args:
            speed: Speed value 128–255. Higher = faster.
        """
        speed = max(128, min(255, int(speed)))
        self._send(3, speed)

    # ------------------------------------------------------------------
    # Vertical angle (CH5)
    # ------------------------------------------------------------------

    def vertical_angle(self, angle: int) -> None:
        """Set vertical flip angle to a fixed position.

        Args:
            angle: Angle in DMX units, 0–127.
        """
        angle = max(0, min(127, int(angle)))
        self._send(4, angle)

    def vertical_angle_speed(self, speed: int) -> None:
        """Set vertical flip speed.

        Args:
            speed: Speed value 128–255. Higher = faster.
        """
        speed = max(128, min(255, int(speed)))
        self._send(4, speed)

    # ------------------------------------------------------------------
    # Horizontal position (CH6)
    # ------------------------------------------------------------------

    def horizontal_position(self, position: int) -> None:
        """Set horizontal position.

        Args:
            position: Position value 0–127.
        """
        position = max(0, min(127, int(position)))
        self._send(5, position)

    def horizontal_speed(self, speed: int) -> None:
        """Set horizontal movement speed.

        Args:
            speed: Speed value 128–255. Higher = faster.
        """
        speed = max(128, min(255, int(speed)))
        self._send(5, speed)

    # ------------------------------------------------------------------
    # Vertical position (CH7)
    # ------------------------------------------------------------------

    def vertical_position(self, position: int) -> None:
        """Set vertical position.

        Args:
            position: Position value 0–127.
        """
        position = max(0, min(127, int(position)))
        self._send(6, position)

    def vertical_speed(self, speed: int) -> None:
        """Set vertical movement speed.

        Args:
            speed: Speed value 128–255. Higher = faster.
        """
        speed = max(128, min(255, int(speed)))
        self._send(6, speed)

    def set_position(self, horizontal: int, vertical: int) -> None:
        """Set horizontal and vertical position in one call.

        Args:
            horizontal: Horizontal position (0–127).
            vertical: Vertical position (0–127).
        """
        horizontal = max(0, min(127, int(horizontal)))
        vertical = max(0, min(127, int(vertical)))
        self.horizontal_position(horizontal)
        self.vertical_position(vertical)

    # ------------------------------------------------------------------
    # Size / animation (CH8) — multiplexed channel
    # ------------------------------------------------------------------

    def size(self, size: int) -> None:
        """Set fixed pattern size (CH8, range 0–63).

        Lower values = larger projection; 63 = smallest.

        Args:
            size: Size value 0–63.
        """
        size = max(0, min(63, int(size)))
        self._send(7, size)

    def enlarge(self, speed: int) -> None:
        """Animate the pattern enlarging (CH8, range 64–127).

        Args:
            speed: Animation speed 64–127. Higher = faster enlargement.
        """
        speed = max(64, min(127, int(speed)))
        self._send(7, speed)

    def shrink(self, speed: int) -> None:
        """Animate the pattern shrinking (CH8, range 128–191).

        Args:
            speed: Animation speed 128–191. Higher = faster shrinking.
        """
        speed = max(128, min(191, int(speed)))
        self._send(7, speed)

    def speed(self, speed: int) -> None:
        """Set pattern animation speed (CH8, range 192–255).

        Args:
            speed: Speed value 192–255. Higher = faster.
        """
        speed = max(192, min(255, int(speed)))
        self._send(7, speed)

    def zoom(self, speed: int) -> None:
        """Zoom the pattern (CH8, range 192–255).

        This is the same DMX range as speed(); it is an alias for
        hardware that interprets these values as zoom.

        Args:
            speed: Zoom speed 192–255. Higher = faster zoom.
        """
        speed = max(192, min(255, int(speed)))
        self._send(7, speed)

    # ------------------------------------------------------------------
    # Color (CH9)
    # ------------------------------------------------------------------

    def color(self, color: int) -> None:
        """Set laser colour (CH9).

        **Only effective in auto/sound modes (CH1=128 or 192).**
        In manual mode, the hardware ignores this channel.

        Monochrome range (0–63) is split into three RGB segments:
            0–20:   Red intensity (0=off, 20=max red)
            21–41:  Green intensity (21=off, 41=max green)
            42–63:  Blue intensity (42=off, 63=max blue)

        Other ranges:
            64–127: Colour mixing
            128–192: Monochrome auto-cycle
            193–255: Full auto colour cycle

        Args:
            color: DMX value 0–255.
        """
        color = max(0, min(255, int(color)))
        self._send(8, color)

    def color_red(self, intensity: int = 20) -> None:
        """Set monochrome red (CH9, range 0–20).

        Args:
            intensity: Red intensity 0–20 (0=off, 20=max red).
        """
        self.color(max(0, min(MONO_RED_MAX, int(intensity))))

    def color_green(self, intensity: int = 41) -> None:
        """Set monochrome green (CH9, range 21–41).

        Args:
            intensity: Green intensity 21–41 (21=off, 41=max green).
        """
        self.color(max(MONO_GREEN_MIN, min(MONO_GREEN_MAX, int(intensity))))

    def color_blue(self, intensity: int = 63) -> None:
        """Set monochrome blue (CH9, range 42–63).

        Args:
            intensity: Blue intensity 42–63 (42=off, 63=max blue).
        """
        self.color(max(MONO_BLUE_MIN, min(MONO_BLUE_MAX, int(intensity))))

    def color_monochrome(self, index: int) -> None:
        """Select a monochrome colour by index (CH9, range 0–63).

        The 0–63 range is split into three RGB segments:
            0–20:   Red
            21–41:  Green
            42–63:  Blue

        Args:
            index: Colour index 0–63.
        """
        self.color(max(0, min(63, int(index))))

    def color_mix(self, index: int) -> None:
        """Select a colour-mixing mode by index (CH9, range 64–127).

        Args:
            index: Mix index 0–63 (mapped to DMX 64–127).
        """
        self.color(64 + max(0, min(63, int(index))))

    def color_auto(self, speed: int = 0) -> None:
        """Enable monochrome auto-cycle (CH9, range 128–192).

        Args:
            speed: Cycle speed 0–64 (mapped to DMX 128–192).
        """
        self.color(128 + max(0, min(64, int(speed))))

    def color_full_auto(self, speed: int = 0) -> None:
        """Enable full auto colour cycle (CH9, range 193–255).

        Args:
            speed: Cycle speed 0–62 (mapped to DMX 193–255).
        """
        self.color(193 + max(0, min(62, int(speed))))

    # ------------------------------------------------------------------
    # Pattern (CH10)
    # ------------------------------------------------------------------

    def pattern(self, pattern: int) -> None:
        """Set laser pattern (CH10).

        Ranges:
            0–127:   Dots and lines patterns
            128–255: Dots and wireless strips patterns

        Args:
            pattern: DMX value 0–255.
        """
        pattern = max(0, min(255, int(pattern)))
        self._send(9, pattern)

    # ------------------------------------------------------------------
    # Shape drawing
    # ------------------------------------------------------------------

    def draw_dot_shape(
        self,
        points: Sequence[Tuple[int, int]],
        dwell_seconds: float = 0.03,
        loops: int = 1,
        dot_size: int = 63,
    ) -> None:
        """Trace a shape by moving through dot coordinates.

        Important: this laser is a pattern projector — CH6/CH7 move the
        centre of whichever preset pattern is active, they don't draw free
        vectors.  To get the closest thing to a single dot, call this with
        the mode_level already set to a low value (0–4 = first preset) and
        dot_size=63 (CH8 fixed-size range: higher value = smaller pattern).

        Args:
            points: Sequence of (x, y) points where x and y are in 0..127.
            dwell_seconds: How long to hold each position.
            loops: Number of times to replay the point list.
            dot_size: CH8 value (0–63) written before each move; 63 = smallest.
        """
        if not points:
            return

        dot_size = max(0, min(63, int(dot_size)))
        for _ in range(max(1, int(loops))):
            for x, y in points:
                self.size(dot_size)
                self.set_position(x, y)
                if dwell_seconds > 0:
                    time.sleep(dwell_seconds)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def sweep_presets(
    dwell_seconds: float = 1.5,
    start: int = 0,
    end: int = 255,
    color: int = 0,
    pattern: int = 0,
    size: int = 63,
) -> None:
    """Step through mode_level (CH2) values to identify each preset visually.

    Walks through DMX values for CH2 while holding all other channels
    fixed, so you can see what each preset looks like and note which one
    gives the simplest single-colour output for colour mapping.

    Args:
        dwell_seconds: Seconds to hold each preset before advancing.
        start: First mode_level value (default 0).
        end: Last mode_level value (default 255).
        color: CH9 colour value to hold constant (default 0 = first monochrome).
        pattern: CH10 pattern value to hold constant (default 0).
        size: CH8 size value to hold constant (default 63 = smallest).
    """
    with Laser() as laser:
        laser.set_mode("manual")
        laser.color(color)
        laser.pattern(pattern)
        laser.size(size)
        laser.rotate(0)
        laser.set_position(63, 63)

        for value in range(start, end + 1):
            laser.set_mode_level(value)
            logger.info(f"Preset CH2={value:3d}  ({value}/{end})")
            time.sleep(dwell_seconds)


def sweep_patterns(
    dwell_seconds: float = 1.5,
    mode_level: int = 8,
    color: int = 0,
    size: int = 63,
) -> None:
    """Step through pattern (CH10) values to identify each pattern visually.

    Walks through DMX values 0–255 for CH10 while holding all other
    channels fixed, so you can see what each pattern looks like and
    find one that gives a single-colour single-dot output.

    Args:
        dwell_seconds: Seconds to hold each pattern before advancing.
        mode_level: CH2 preset to hold constant (default 8 = circle).
        color: CH9 colour value to hold constant (default 0).
        size: CH8 size value to hold constant (default 63 = smallest).
    """
    with Laser() as laser:
        laser.set_mode("manual")
        laser.set_mode_level(mode_level)
        laser.color(color)
        laser.size(size)
        laser.rotate(0)
        laser.set_position(63, 63)

        for value in range(256):
            laser.pattern(value)
            family = "dots/lines" if value <= 127 else "dots/strips"
            logger.info(f"Pattern CH10={value:3d}  [{family}]  ({value}/255)")
            time.sleep(dwell_seconds)


def sweep_monochrome_colors(
    dwell_seconds: float = 2.0,
    start: int = 0,
    end: int = 63,
    mode_level: int = 128,
    pattern: int = 0,
    size: int = 63,
) -> dict[int, str]:
    """Step through monochrome colour values (CH9, 0–63) one by one.

    **Must be run in auto or sound mode** — color is ignored in manual mode.
    Defaults to auto mode (mode_level=128).

    The 0–63 range is split into three RGB segments:
        0–20:   Red intensity
        21–41:  Green intensity
        42–63:  Blue intensity

    Returns a dict mapping each DMX value to a placeholder string
    ``"<describe>"`` that you can fill in with your observations.

    Args:
        dwell_seconds: Seconds to hold each colour before advancing.
        start: First monochrome index to test (default 0).
        end: Last monochrome index to test (default 63).
        mode_level: CH2 mode level (default 128 = auto mode program 1).
        pattern: CH10 pattern value (default 0).
        size: CH8 fixed-size value (default 63 = smallest).

    Returns:
        Dict[int, str] with every tested DMX value mapped to ``"<describe>"``.
    """
    start = max(0, min(63, int(start)))
    end = max(start, min(63, int(end)))

    color_map: dict[int, str] = {}

    with Laser() as laser:
        # Must use auto or sound mode — color is ignored in manual mode.
        laser.set_mode("auto")
        laser.set_mode_level(mode_level)
        laser.pattern(pattern)
        laser.size(size)
        laser.rotate(0)
        laser.set_position(63, 63)

        for value in range(start, end + 1):
            if value <= MONO_RED_MAX:
                segment = "RED"
            elif value <= MONO_GREEN_MAX:
                segment = "GREEN"
            else:
                segment = "BLUE"
            laser.color_monochrome(value)
            logger.info(
                f"Monochrome CH9={value:2d}  [{segment:5s}]  " f"({value}/{end})"
            )
            color_map[value] = "<describe>"
            time.sleep(dwell_seconds)

    logger.info("Done. Edit the returned dict to record your observations.")
    return color_map


def sweep_all_colors(
    dwell_seconds: float = 1.5,
    mode_level: int = 128,
    pattern: int = 0,
    size: int = 63,
) -> dict[int, str]:
    """Step through *all* 256 colour values (CH9, 0–255).

    **Must be run in auto or sound mode** — color is ignored in manual mode.
    Defaults to auto mode (mode_level=128).

    Walks through every DMX value for the colour channel, crossing all
    four colour-mode boundaries:

    - 0–20:   Red intensity (monochrome R segment)
    - 21–41:  Green intensity (monochrome G segment)
    - 42–63:  Blue intensity (monochrome B segment)
    - 64–127: Colour mixing
    - 128–192: Monochrome auto-cycle
    - 193–255: Full auto colour cycle

    Args:
        dwell_seconds: Seconds to hold each colour before advancing.
        mode_level: CH2 mode level (default 128 = auto mode program 1).
        pattern: CH10 pattern value (default 0).
        size: CH8 fixed-size value (default 63 = smallest).

    Returns:
        Dict[int, str] with every DMX value 0–255 mapped to ``"<describe>"``.
    """
    color_map: dict[int, str] = {}

    with Laser() as laser:
        # Must use auto or sound mode — color is ignored in manual mode.
        laser.set_mode("auto")
        laser.set_mode_level(mode_level)
        laser.pattern(pattern)
        laser.size(size)
        laser.rotate(0)
        laser.set_position(63, 63)

        for value in range(256):
            laser.color(value)
            if value <= MONO_RED_MAX:
                mode_label = "RED"
            elif value <= MONO_GREEN_MAX:
                mode_label = "GREEN"
            elif value <= 63:
                mode_label = "BLUE"
            elif value <= 127:
                mode_label = "MIX"
            elif value <= 192:
                mode_label = "MONO_AUTO"
            else:
                mode_label = "FULL_AUTO"
            logger.info(f"Colour CH9={value:3d}  [{mode_label}]  " f"({value}/255)")
            color_map[value] = "<describe>"
            time.sleep(dwell_seconds)

    logger.info("Done. Edit the returned dict to record your observations.")
    return color_map


def all_random(laser: Laser):
    """Set random pattern, colour, mode level, and speed on the laser.

    Only randomises parameters that are safe in manual mode — avoids
    accidentally switching to auto/sound mode or turning the laser off.
    """
    laser.pattern(randint(0, 255))
    laser.color(randint(0, 255))
    # Keep mode_level in the manual-preset range (1–255) to avoid
    # accidentally switching modes or turning the laser off.
    laser.set_mode_level(randint(1, 255))
    laser.speed(randint(192, 255))


def random_fun():
    with Laser() as laser:
        laser.set_mode("manual")

        while True:
            all_random(laser)


def _normalized_shape_to_points(
    normalized_points: Iterable[Tuple[float, float]],
    center_x: int = 63,
    center_y: int = 63,
    scale: int = 28,
) -> list[Tuple[int, int]]:
    """Convert normalized points (-1..1) into DMX position points (0..127)."""
    out: list[Tuple[int, int]] = []
    for nx, ny in normalized_points:
        x = max(0, min(127, center_x + int(nx * scale)))
        # Invert Y so +1 appears visually higher.
        y = max(0, min(127, center_y - int(ny * scale)))
        out.append((x, y))
    return out


def draw_something():
    # A simple five-point star in normalized coordinates (-1..1).
    star_shape = [
        (0.00, 1.00),
        (0.22, 0.30),
        (0.95, 0.30),
        (0.36, -0.12),
        (0.58, -0.90),
        (0.00, -0.40),
        (-0.58, -0.90),
        (-0.36, -0.12),
        (-0.95, 0.30),
        (-0.22, 0.30),
        (0.00, 1.00),
    ]
    star_points = _normalized_shape_to_points(star_shape, scale=34)

    with Laser() as laser:
        laser.set_mode("manual")
        # CH2 = 0 → first of the 51 manual presets (simplest/smallest pattern).
        laser.set_mode_level(0)
        # CH10 = 0 → dots-and-lines family, lowest index = most minimal.
        laser.pattern(0)
        # CH9 = 12 → monochrome single-colour beam.
        laser.color(12)
        # CH8 = 63 → fixed-size range (0-63); highest value = smallest projection.
        laser.size(63)

        while True:
            # dot_size=63 keeps every point at minimum projection size, making
            # the active hardware preset appear as close to a single dot as possible.
            for i in range(255):
                print(i)
                laser.color(i)
                laser.draw_dot_shape(
                    star_points, dwell_seconds=0.05, loops=1, dot_size=196
                )
                time.sleep(0.025)

        # laser.pattern(8)  # Dot-like pattern family for tracing shapes.
        # laser.color(12)
        # laser.set_mode_level(220)
        # laser.speed(205)


def draw_circle_orbit():
    """Standalone demo: the circle preset orbits a slow figure-eight path.

    Channel settings:
      CH2 (mode_level) = 8     → circle preset
      CH3 (rotation)   = 255   → max spin speed (makes circle spin)
      CH4 (h_angle)    = 0     → fixed horizontal angle (no flip)
      CH5 (v_angle)    = 0     → fixed vertical angle (no flip)
      CH6 (h_pos)      = orbit → horizontal position driven by music/time
      CH7 (v_pos)      = orbit → vertical position driven by music/time
      CH8 (size)       = 18    → moderate fixed size
      CH9 (color)      = 0-63  → slow monochrome colour drift

    Note: CH4/CH5 flip-speed calls are intentionally omitted.  Sending
    128-255 to those channels causes the hardware to flip the pattern
    back and forth, which biases all visible motion toward the top half.
    Leaving them at 0 gives clean positional control over the full range.
    """
    # Physical fixtures are often vertically biased upward; these defaults
    # push the orbit downward so it reaches the lower half of the room.
    v_angle_center = 64
    v_pos_center = 64

    with Laser() as laser:
        laser.set_mode("manual")
        laser.set_mode_level(8)  # circle preset
        laser.rotation_speed(255)  # spin the circle
        laser.horizontal_angle(0)  # fixed angle — no flip
        laser.vertical_angle(v_angle_center)  # fixed angle with downward bias
        laser.size(18)

        start = time.time()
        while True:
            t = time.time() - start
            # Lissajous figure-eight using different H/V frequencies.
            # Amplitude 50 fills most of the 0-127 range in both axes.
            h = int(63 * math.sin(t * 0.6))
            v = int(v_pos_center * math.cos(t * 0.9))
            laser.set_position(h, v)
            # Drift through monochrome colours slowly
            laser.color(int(t * 3) % 64)
            time.sleep(0.03)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Laser DMX utility")
    parser.add_argument(
        "command",
        choices=[
            "sweep-mono",
            "sweep-all",
            "sweep-presets",
            "sweep-patterns",
            "star",
            "circle",
            "random",
        ],
        help="What to run: "
        "sweep-presets = step through CH2 presets to find simplest shape, "
        "sweep-patterns = step through CH10 patterns, "
        "sweep-mono = step through monochrome colours 0-63, "
        "sweep-all = step through all 256 colour values, "
        "star = draw star shape, circle = circle orbit demo, "
        "random = random parameters",
    )
    parser.add_argument(
        "--dwell",
        type=float,
        default=2.0,
        help="Seconds to hold each value in sweep mode (default: 2.0)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="First value for sweep-mono / sweep-presets (default: 0)",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=63,
        help="Last value for sweep-mono (default: 63) or sweep-presets (default: 255)",
    )
    parser.add_argument(
        "--mode-level",
        type=int,
        default=128,
        help="CH2 mode level for sweep-mono/sweep-all/sweep-patterns "
        "(default: 128 = auto mode; color is ignored in manual mode)",
    )
    parser.add_argument(
        "--pattern",
        type=int,
        default=0,
        help="CH10 pattern value for sweep-mono/sweep-all/sweep-presets (default: 0)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=63,
        help="CH8 size value for sweeps (default: 63 = smallest)",
    )
    parser.add_argument(
        "--color",
        type=int,
        default=0,
        help="CH9 colour value for sweep-presets/sweep-patterns (default: 0)",
    )
    args = parser.parse_args()

    if args.command == "sweep-presets":
        sweep_presets(
            dwell_seconds=args.dwell,
            start=args.start,
            end=args.end if args.end != 63 else 255,
            color=args.color,
            pattern=args.pattern,
            size=args.size,
        )
    elif args.command == "sweep-patterns":
        sweep_patterns(
            dwell_seconds=args.dwell,
            mode_level=args.mode_level,
            color=args.color,
            size=args.size,
        )
    elif args.command == "sweep-mono":
        result = sweep_monochrome_colors(
            dwell_seconds=args.dwell,
            start=args.start,
            end=args.end,
            mode_level=args.mode_level,
            pattern=args.pattern,
            size=args.size,
        )
        for dmx_val, desc in sorted(result.items()):
            if dmx_val <= MONO_RED_MAX:
                seg = "RED"
            elif dmx_val <= MONO_GREEN_MAX:
                seg = "GREEN"
            else:
                seg = "BLUE"
            print(f"  CH9={dmx_val:2d} [{seg:5s}] → {desc}")
    elif args.command == "sweep-all":
        result = sweep_all_colors(
            dwell_seconds=args.dwell,
            mode_level=args.mode_level,
            pattern=args.pattern,
            size=args.size,
        )
        for dmx_val, desc in sorted(result.items()):
            if dmx_val <= MONO_RED_MAX:
                mode = "RED"
            elif dmx_val <= MONO_GREEN_MAX:
                mode = "GREEN"
            elif dmx_val <= 63:
                mode = "BLUE"
            elif dmx_val <= 127:
                mode = "MIX"
            elif dmx_val <= 192:
                mode = "MONO_AUTO"
            else:
                mode = "FULL_AUTO"
            print(f"  CH9={dmx_val:3d} [{mode:10s}] → {desc}")
    elif args.command == "star":
        draw_something()
    elif args.command == "circle":
        draw_circle_orbit()
    elif args.command == "random":
        random_fun()
