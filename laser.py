import sys
import time
from random import randint

from loguru import logger

from base_dmx import BaseDMX

logger.remove()
logger.add(sys.stderr, level="INFO")


class Laser(BaseDMX):
    def __init__(self, dmx_channel: int = 1):
        """Initialize Laser with specific DMX channel

        Args:
            device_index: Index of the uDMX device to use (0 for first device)
        """
        super().__init__(dmx_channel)

    def on(self):
        self._send(1, 64)
        self._send(2, 255)

    def off(self):
        self._send(1, 0)

    def set_mode(self, mode: str) -> None:
        """sets the mode of the laser

        there are 4 modes, they start at 0, 64, 128 and 192

        Args:
            mode (str): supports off, manual, auto and sound
        """
        match mode:
            case "off":
                self._send(1, 0)
            case "manual":
                self._send(1, 64)
            case "auto":
                self._send(1, 128)
            case "sound":
                self._send(1, 192)

    def set_mode_level(self, level: int) -> None:
        """sets the mode level

        manual mode has a level from 0 to 255 - 51 patterns
        auto and sound modes have 4 levels, 0, 64, 128, 192

        Args:
            level (int): level from 0 to 255
        """
        if level == 0:
            self.status = False
        else:
            self.status = True
        self._send(2, level)

    def rotate(self, angle: int) -> None:
        """rotates the laser

        Args:
            angle (int): angle in degrees, 0 to 127
        """
        self._send(3, angle)

    def horizontal_angle(self, angle: int) -> None:
        """sets the horizontal flip position

        Args:
            angle (int): angle in degrees, 0 to 127
        """
        self._send(4, angle)

    def horizontal_angle_speed(self, position: int) -> None:
        """sets the horizontal angle position speed

        Args:
            position (int): position from 127 to 255
        """
        self._send(4, position)

    def vertical_angle(self, angle: int) -> None:
        """sets the vertical angle

        Args:
            angle (int): angle in degrees, 0 to 127
        """
        self._send(5, angle)

    def horizontal_position(self, position: int) -> None:
        """sets the horizontal position

        Args:
            position (int): position from 0 to 127
        """
        self._send(6, position)

    def horizontal_speed(self, speed: int) -> None:
        """sets the horizontal speed

        Args:
            speed (int): speed from 128 to 255
        """
        self._send(6, speed)

    def vertical_position(self, position: int) -> None:
        """sets the vertical position

        Args:
            position (int): position from 0 to 127
        """
        self._send(7, position)

    def vertical_speed(self, speed: int) -> None:
        """sets the vertical speed

        Args:
            speed (int): speed from 128 to 255
        """
        self._send(7, speed)

    def size(self, size: int) -> None:
        """sets the size of the laser

        Args:
            size (int): size from 0 to 63, the smaller value the bigger size
        """
        self._send(8, size)

    def enlarge(self, duration: int) -> None:
        """enlarges the figure

        Args:
            size (int): size from 64 to 127, the larger the value, the faster the speed
        """
        self._send(8, duration)

    def shrink(self, duration: int) -> None:
        """shrinks the figure

        Args:
            size (int): size from 128 to 196, the larger the value, the faster the speed
        """
        self._send(8, duration)

    def speed(self, speed: int) -> None:
        """sets the speed of the laser

        Args:
            speed (int): speed from 192 to 255, the larger the value, the faster the speed
        """
        self._send(8, speed)

    def zoom(self, duration: int) -> None:
        """zooms the figure

        Args:
            size (int): size from 192 to 255, the larger the value, the faster the speed
        """
        self._send(8, duration)

    def color(self, color: int) -> None:
        """sets the color of the laser

        monochrome color selection 0 to 63
        color mixing 64 to 127
        monochrome auto 128 to 192
        auto? 193 to 255

        Args:
            color (int): color from 0 to 255
        """
        self._send(9, color)

    def pattern(self, pattern: int) -> None:
        """sets the pattern of the laser

        pattern of dots and lines 0 to 127
        pattern of dots and wireless strips 128 to 255

        Args:
            pattern (int): pattern from 0 to 255
        """
        self._send(10, pattern)


def all_random(laser: Laser):
    laser.pattern(randint(0, 255))
    laser.color(randint(0, 255))
    laser.set_mode_level(randint(0, 255))
    laser.speed(randint(0, 255))


def random_fun():
    with Laser() as laser:
        laser.set_mode("manual")

        while True:
            laser.pattern(randint(0, 255))
            laser.color(randint(0, 255))
            laser.set_mode_level(randint(0, 255))
            laser.speed(randint(0, 255))


def draw_something():
    with Laser() as laser:
        laser.set_mode("manual")
        while True:
            mode_level = randint(0, 256)
            logger.info(mode_level)
            laser.set_mode_level(mode_level)

            for i in range(0, 128):
                laser.horizontal_angle(i)
                time.sleep(0.5)
                laser.horizontal_position(i)
                time.sleep(0.5)
                laser.horizontal_angle_speed(i + 128)
                time.sleep(0.5)
                laser.horizontal_speed(i + 128)
                time.sleep(0.5)
                # for i in range(0, 128):
                #     laser.vertical_position(i)


if __name__ == "__main__":
    # draw_something()
    # sys.exit()
    random_fun()
    with Laser() as laser:
        laser.set_mode("manual")
        laser.set_mode_level(64)
        # laser.zoom(randint(192, 255))
        for i in range(0, 256):
            laser.pattern(i)
            laser.color(i)
            laser.set_mode_level(i)
            laser.speed(randint(64, 196))
            # for i in range(255):
            #     laser.color(i)
            #     time.sleep(0.1)
            logger.info(f"pattern: {i}")
            time.sleep(0.5)
