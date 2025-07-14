import time
from random import randint

from icecream import ic

from laser import Laser, all_random
from mic import get_pyaudio_microphone, start_stream


def main():
    microphone = get_pyaudio_microphone()
    trigger_size_at = 20
    trigger_pattern_at = 30
    trigger_color_at = 25
    trigger_mode_level_at = 20
    max_vol = 0
    with Laser() as laser:
        laser.set_mode("manual")
        while True:
            volume = start_stream(microphone)
            if volume > max_vol:
                max_vol = volume
                logger.debug(max_vol)
            if volume >= trigger_size_at:
                # trigger_mode_level_at = (volume + trigger_mode_level_at) / 2
                all_random(laser)
            # if volume >= trigger_size_at:
            #     size = randint(0, 256)
            #     laser.size(size)
            # elif volume >= trigger_pattern_at:
            #     mode = randint(0, 256)
            #     laser.set_mode_level(mode)
            # elif volume >= trigger_color_at:
            #     color = randint(0, 256)
            #     laser.color(color)
            # elif volume >= trigger_mode_level_at:
            #     pattern = randint(0, 256)
            #     laser.pattern(pattern)
            # time.sleep(0.5)


if __name__ == "__main__":
    main()
