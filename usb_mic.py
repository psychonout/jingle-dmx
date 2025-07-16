import time
from typing import Any, Optional

import numpy as np
import pyaudio
from loguru import logger

MIC_RATE = 44100
FPS = 60
FRAMES_PER_BUFFER = int(MIC_RATE / FPS)


def list_usb_microphones():
    """List all available USB audio input devices"""
    p = pyaudio.PyAudio()
    usb_devices = []

    logger.debug("Available audio devices:")
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        if device_info["maxInputChannels"] > 0:
            logger.debug(f"Device {i}: {device_info['name']}")
            logger.debug(f"  Max input channels: {device_info['maxInputChannels']}")
            logger.debug(f"  Default sample rate: {device_info['defaultSampleRate']}")
            usb_devices.append(
                {
                    "index": i,
                    "name": device_info["name"],
                    "channels": device_info["maxInputChannels"],
                    "sample_rate": device_info["defaultSampleRate"],
                }
            )

    p.terminate()
    return usb_devices


def get_usb_microphone(
    device_name: Optional[str] = None, device_index: Optional[int] = None
):
    """Get a USB microphone by name or index"""
    p = pyaudio.PyAudio()

    if device_index is not None:
        # Use specific device index
        device_info = p.get_device_info_by_index(device_index)
        logger.debug(f"Using device {device_index}: {device_info['name']}")
    elif device_name is not None:
        # Find device by name
        device_index = None
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            if (
                device_name.lower() in device_info["name"].lower()
                and device_info["maxInputChannels"] > 0
            ):
                device_index = i
                break

        if device_index is None:
            logger.debug(f"Device '{device_name}' not found. Available devices:")
            list_usb_microphones()
            p.terminate()
            return None

        device_info = p.get_device_info_by_index(device_index)
        logger.debug(f"Found device: {device_info['name']}")
    else:
        # Use default input device
        device_info = p.get_default_input_device_info()
        device_index = device_info["index"]
        logger.debug(f"Using default device: {device_info['name']}")

    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=min(device_info["maxInputChannels"], 2),  # Use mono or stereo
            rate=int(device_info["defaultSampleRate"])
            if device_info["defaultSampleRate"] <= MIC_RATE
            else MIC_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        return stream, p
    except Exception as e:
        logger.debug(f"Error opening microphone: {e}")
        p.terminate()
        return None, None


def read_usb_microphone(stream: Any, sample_rate: int = MIC_RATE):
    """Read audio data from USB microphone and return average volume"""
    overflows = 0
    prev_ovf_time = time.time()

    try:
        # Read audio data
        audio_data = stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)

        # Convert to numpy array
        y = np.frombuffer(audio_data, dtype=np.int16)
        y = y.astype(np.float32)

        # Clear any remaining buffer
        available = stream.get_read_available()
        if available > 0:
            stream.read(available, exception_on_overflow=False)

        # Calculate average absolute value (volume level)
        avg = np.average(np.abs(y))
        return avg

    except IOError as e:
        logger.debug(f"Audio buffer overflow: {e}")
        overflows += 1
        if time.time() > prev_ovf_time + 1:
            prev_ovf_time = time.time()
            logger.debug(f"Audio buffer has overflowed {overflows} times")
        return 0


def close_usb_microphone(stream: Any, pyaudio_instance: Any):
    """Properly close the microphone stream"""
    if stream:
        stream.stop_stream()
        stream.close()
    if pyaudio_instance:
        pyaudio_instance.terminate()


class USBMicrophone:
    """Class for managing USB microphone operations"""

    def __init__(
        self, device_name: Optional[str] = None, device_index: Optional[int] = None
    ):
        self.device_name = device_name
        self.device_index = device_index
        self.stream = None
        self.pyaudio_instance = None
        self.is_open = False

    def open(self):
        """Open the USB microphone"""
        self.stream, self.pyaudio_instance = get_usb_microphone(
            device_name=self.device_name, device_index=self.device_index
        )
        if self.stream and self.pyaudio_instance:
            self.is_open = True
            logger.debug("USB microphone opened successfully")
            return True
        else:
            logger.debug("Failed to open USB microphone")
            return False

    def read(self):
        """Read volume level from microphone"""
        if not self.is_open:
            logger.debug("Microphone not open")
            return 0
        return read_usb_microphone(self.stream)

    def close(self):
        """Close the microphone"""
        if self.is_open:
            close_usb_microphone(self.stream, self.pyaudio_instance)
            self.is_open = False
            logger.debug("USB microphone closed")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # List available microphones
    logger.debug("Listing available USB microphones:")
    devices = list_usb_microphones()

    # Test with context manager
    logger.debug("\nTesting USB microphone with context manager:")
    with USBMicrophone() as usb_mic:
        if usb_mic.is_open:
            logger.debug("Recording for 5 seconds...")
            start_time = time.time()
            max_volume = 0

            while time.time() - start_time < 5:
                volume = usb_mic.read()
                if volume > max_volume:
                    max_volume = volume
                logger.debug(f"Volume: {volume:.2f}, Max: {max_volume:.2f}")
                time.sleep(0.1)
