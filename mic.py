import time
from typing import Any

import numpy as np
import pyaudio
import soundcard
from icecream import ic

MIC_RATE = 44100
FPS = 60
FRAMES_PER_BUFFER = int(MIC_RATE / FPS)


def get_microphone(mic_name: str = "Microphone Mic | Line | Instrument 1"):
    microphones = soundcard.all_microphones(include_loopback=True)

    ic(microphones)

    return [microphone for microphone in microphones if mic_name in str(microphone)][0]


def listen(microphone: Any = get_microphone()):
    samples = 5600
    duration = 50

    with microphone.recorder(samplerate=samples, channels=1) as mic:
        audio = mic.record(numframes=duration)
        return np.average(np.abs(audio))


def get_pyaudio_microphone():
    p = pyaudio.PyAudio()
    device_info = p.get_default_input_device_info()
    ic(device_info)
    return p.open(
        format=pyaudio.paInt16,
        channels=device_info["maxInputChannels"],
        rate=MIC_RATE,
        input=True,
        frames_per_buffer=FRAMES_PER_BUFFER,
    )
    p.stop_stream()
    p.close()
    p.terminate()


def start_stream(stream: Any):
    overflows = 0
    prev_ovf_time = time.time()
    try:
        y = np.fromstring(
            stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False),
            dtype=np.int16,
        )
        y = y.astype(np.float32)
        stream.read(stream.get_read_available(), exception_on_overflow=False)
        avg = np.average(y)
        return avg * -1 if avg < 0 else avg
    except IOError:
        print("Audio buffer has overflowed")
        overflows += 1
        if time.time() > prev_ovf_time + 1:
            prev_ovf_time = time.time()
            print("Audio buffer has overflowed {} times".format(overflows))


if __name__ == "__main__":
    # while True:
    #     ic(listen())
    stream = get_pyaudio_microphone()
    while True:
        ic(start_stream(stream))
