import queue
import threading
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


def get_usb_microphone(device_name: str | None = None, device_index: int | None = None):
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
    """Read audio data from USB microphone and return enhanced volume level"""
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

        if len(y) == 0:
            return 0

        # Enhanced audio analysis
        # 1. RMS (Root Mean Square) - better represents perceived loudness
        rms = np.sqrt(np.mean(y**2))

        # 2. Peak level - captures transients and beats
        peak = np.max(np.abs(y))

        # 3. Dynamic range consideration
        # Use a combination of RMS and peak for more responsive volume reading
        dynamic_volume = (rms * 0.7) + (peak * 0.3)

        # 4. Apply slight smoothing to reduce noise
        # Simple exponential moving average (you could make this more sophisticated)
        if not hasattr(read_usb_microphone, "_last_volume"):
            read_usb_microphone._last_volume = dynamic_volume
        else:
            smoothing_factor = 0.85  # Adjust for more/less smoothing
            read_usb_microphone._last_volume = (
                smoothing_factor * read_usb_microphone._last_volume
                + (1 - smoothing_factor) * dynamic_volume
            )

        # 5. Enhance low-level signals while preserving high-level signals
        # Apply a gentle compression curve
        enhanced_volume = read_usb_microphone._last_volume
        if enhanced_volume > 0:
            # Gentle compression: y = x^0.8 * scale
            # This makes quiet sounds more audible while preserving loud sounds
            compression_factor = 0.85
            scale_factor = 1.2
            enhanced_volume = (enhanced_volume**compression_factor) * scale_factor

        return enhanced_volume

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
    """
    Unified USB microphone class with optional advanced audio analysis capabilities.
    Provides basic volume reading and optional RMS, peak detection, frequency analysis, and beat detection.

    Backwards compatible with the original USBMicrophone class while offering enhanced features.
    """

    def __init__(
        self,
        device_name: Optional[str] = None,
        device_index: Optional[int] = None,
        enable_frequency_analysis: bool = False,
        enable_beat_detection: bool = False,
        buffer_history: int = 10,
    ):
        self.device_name = device_name
        self.device_index = device_index
        self.stream = None
        self.pyaudio_instance = None
        self.is_open = False

        # Enhanced features (optional)
        self.enable_frequency_analysis = enable_frequency_analysis
        self.enable_beat_detection = enable_beat_detection
        self.buffer_history = buffer_history

        # Audio analysis data (only initialized if enhanced features are enabled)
        if self.enable_frequency_analysis or self.enable_beat_detection:
            self.audio_buffer = queue.Queue(maxsize=buffer_history)
            self.rms_history = []
            self.peak_history = []
            self.beat_detected = False
            self.last_beat_time = 0
            self.frequency_bands = {}

            # Analysis parameters
            self.rms_smoothing = 0.8
            self.peak_threshold_ratio = 1.5
            self.beat_cooldown = 0.2  # Minimum time between beats

            # Threading for background processing
            self.processing_thread = None
            self.stop_processing = False

    def open(self):
        """Open the USB microphone"""
        self.stream, self.pyaudio_instance = get_usb_microphone(
            device_name=self.device_name, device_index=self.device_index
        )

        if self.stream and self.pyaudio_instance:
            self.is_open = True
            logger.debug("USB microphone opened successfully")

            # Start background processing thread if enhanced features are enabled
            if (
                self.enable_frequency_analysis or self.enable_beat_detection
            ) and hasattr(self, "audio_buffer"):
                self.start_processing_thread()

            return True
        else:
            logger.debug("Failed to open USB microphone")
            return False

    def start_processing_thread(self):
        """Start background thread for audio processing"""
        if not hasattr(self, "audio_buffer"):
            return

        self.stop_processing = False
        self.processing_thread = threading.Thread(target=self._process_audio_background)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        logger.debug("Started audio processing thread")

    def _process_audio_background(self):
        """Background thread for processing audio data"""
        while not self.stop_processing and self.is_open:
            try:
                if not self.audio_buffer.empty():
                    audio_data = self.audio_buffer.get_nowait()
                    self._analyze_audio(audio_data)
                else:
                    time.sleep(0.001)  # Small delay to prevent CPU spinning
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in audio processing thread: {e}")

    def _analyze_audio(self, audio_data):
        """Analyze audio data for frequency content and beat detection"""
        if len(audio_data) == 0:
            return

        # Frequency analysis
        if self.enable_frequency_analysis:
            self._analyze_frequency_content(audio_data)

        # Beat detection
        if self.enable_beat_detection:
            self._detect_beats(audio_data)

    def _analyze_frequency_content(self, audio_data):
        """Analyze frequency content using FFT"""
        try:
            # Apply window function to reduce spectral leakage
            windowed = audio_data * np.hanning(len(audio_data))

            # Compute FFT
            fft = np.fft.rfft(windowed)
            magnitude = np.abs(fft)

            # Define frequency bands (in Hz)
            freq_bins = np.fft.rfftfreq(len(audio_data), 1 / MIC_RATE)

            # Common frequency bands for music
            bands = {
                "sub_bass": (20, 60),  # Sub-bass
                "bass": (60, 250),  # Bass
                "low_mid": (250, 500),  # Low midrange
                "mid": (500, 2000),  # Midrange
                "high_mid": (2000, 4000),  # High midrange
                "presence": (4000, 6000),  # Presence
                "brilliance": (6000, 20000),  # Brilliance
            }

            # Calculate energy in each band
            for band_name, (low_freq, high_freq) in bands.items():
                mask = (freq_bins >= low_freq) & (freq_bins <= high_freq)
                band_energy = np.sum(magnitude[mask] ** 2)
                self.frequency_bands[band_name] = band_energy

        except Exception as e:
            logger.debug(f"Error in frequency analysis: {e}")

    def _detect_beats(self, audio_data):
        """Simple beat detection based on energy changes"""
        try:
            current_time = time.time()

            # Skip if in cooldown period
            if current_time - self.last_beat_time < self.beat_cooldown:
                self.beat_detected = False
                return

            # Calculate RMS energy
            rms = np.sqrt(np.mean(audio_data**2))

            # Keep history of RMS values
            self.rms_history.append(rms)
            if len(self.rms_history) > 20:  # Keep last 20 values
                self.rms_history.pop(0)

            # Beat detection: current energy vs average of recent history
            if len(self.rms_history) >= 10:
                avg_rms = np.mean(self.rms_history[:-1])  # Average excluding current

                # Beat detected if current RMS is significantly higher than average
                if rms > avg_rms * self.peak_threshold_ratio:
                    self.beat_detected = True
                    self.last_beat_time = current_time
                    logger.debug(f"Beat detected! RMS: {rms:.2f}, Avg: {avg_rms:.2f}")
                else:
                    self.beat_detected = False

        except Exception as e:
            logger.debug(f"Error in beat detection: {e}")

    def read(self) -> Any:
        """
        Read audio data from microphone.

        Returns:
            - If enhanced features disabled: returns simple volume level (float)
            - If enhanced features enabled: returns dict with comprehensive analysis
        """
        if not self.is_open:
            logger.debug("Microphone not open")
            if self.enable_frequency_analysis or self.enable_beat_detection:
                return {
                    "volume": 0,
                    "rms": 0,
                    "peak": 0,
                    "frequency_bands": {},
                    "beat_detected": False,
                }
            else:
                return 0

        # For backwards compatibility, use simple read if no enhanced features
        if not (self.enable_frequency_analysis or self.enable_beat_detection):
            return read_usb_microphone(self.stream)

        # Enhanced reading with comprehensive analysis
        try:
            # Read audio data
            audio_data = self.stream.read(
                FRAMES_PER_BUFFER, exception_on_overflow=False
            )

            # Convert to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)

            # Clear any remaining buffer
            available = self.stream.get_read_available()
            if available > 0:
                self.stream.read(available, exception_on_overflow=False)

            # Calculate basic metrics
            if len(audio_array) > 0:
                rms = np.sqrt(np.mean(audio_array**2))
                peak = np.max(np.abs(audio_array))
                volume = np.mean(np.abs(audio_array))  # For backwards compatibility

                # Add to processing queue for background analysis
                if hasattr(self, "audio_buffer") and not self.audio_buffer.full():
                    self.audio_buffer.put_nowait(audio_array.copy())

            else:
                rms = peak = volume = 0

            # Get current beat detection status
            beat_detected = getattr(self, "beat_detected", False)
            if hasattr(self, "beat_detected"):
                self.beat_detected = False  # Reset after reading

            return {
                "volume": volume,
                "rms": rms,
                "peak": peak,
                "frequency_bands": getattr(self, "frequency_bands", {}).copy(),
                "beat_detected": beat_detected,
            }

        except IOError as e:
            logger.debug(f"Audio buffer overflow: {e}")
            return {
                "volume": 0,
                "rms": 0,
                "peak": 0,
                "frequency_bands": {},
                "beat_detected": False,
            }

    def get_bass_energy(self) -> float:
        """Get the energy in bass frequencies"""
        if not hasattr(self, "frequency_bands"):
            return 0
        return self.frequency_bands.get("bass", 0) + self.frequency_bands.get(
            "sub_bass", 0
        )

    def get_mid_energy(self) -> float:
        """Get the energy in mid frequencies"""
        if not hasattr(self, "frequency_bands"):
            return 0
        return self.frequency_bands.get("mid", 0) + self.frequency_bands.get(
            "low_mid", 0
        )

    def get_high_energy(self) -> float:
        """Get the energy in high frequencies"""
        if not hasattr(self, "frequency_bands"):
            return 0
        return self.frequency_bands.get("high_mid", 0) + self.frequency_bands.get(
            "presence", 0
        )

    def close(self):
        """Close the microphone"""
        if hasattr(self, "processing_thread") and self.processing_thread:
            self.stop_processing = True
            self.processing_thread.join(timeout=1.0)

        if self.is_open:
            close_usb_microphone(self.stream, self.pyaudio_instance)
            self.is_open = False
            logger.debug("USB microphone closed")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Beat detection variables (module-level)
_beat_history = []
_last_beat_time = 0
_beat_threshold_ratio = 1.4


def detect_beat(current_volume, cooldown_time=0.2):
    """
    Simple beat detection based on volume spikes.

    Args:
        current_volume: Current volume level
        cooldown_time: Minimum time between beats in seconds

    Returns:
        bool: True if beat detected
    """
    global _beat_history, _last_beat_time, _beat_threshold_ratio

    current_time = time.time()

    # Cooldown check
    if current_time - _last_beat_time < cooldown_time:
        return False

    # Keep history of recent volumes
    _beat_history.append(current_volume)
    if len(_beat_history) > 20:  # Keep last 20 readings
        _beat_history.pop(0)

    # Need enough history for beat detection
    if len(_beat_history) < 10:
        return False

    # Calculate average of recent history (excluding current)
    recent_avg = np.mean(_beat_history[:-1])

    # Beat detected if current volume significantly exceeds recent average
    if current_volume > recent_avg * _beat_threshold_ratio and recent_avg > 10:
        _last_beat_time = current_time
        logger.debug(
            f"Beat detected! Volume: {current_volume:.1f} vs Avg: {recent_avg:.1f}"
        )
        return True

    return False


def read_usb_microphone_with_beat_detection(stream: Any, sample_rate: int = MIC_RATE):
    """
    Enhanced microphone reading with beat detection.

    Returns:
        tuple: (volume, beat_detected)
    """
    volume = read_usb_microphone(stream, sample_rate)
    beat = detect_beat(volume)
    return volume, beat


def test_enhanced_microphone():
    """Test function for the enhanced microphone features"""
    logger.info("Testing enhanced USB microphone...")

    with USBMicrophone(
        enable_frequency_analysis=True, enable_beat_detection=True
    ) as mic:
        if mic.is_open:
            logger.info("Recording for 10 seconds with enhanced analysis...")
            start_time = time.time()

            while time.time() - start_time < 10:
                data = mic.read()

                if isinstance(data, dict) and data["beat_detected"]:
                    logger.info(
                        f"BEAT! Volume: {data['volume']:.2f}, RMS: {data['rms']:.2f}"
                    )

                # Log frequency analysis every 2 seconds
                if (
                    int(time.time() - start_time) % 2 == 0
                    and (time.time() - start_time) % 2 < 0.1
                ):
                    bass = mic.get_bass_energy()
                    mid = mic.get_mid_energy()
                    high = mic.get_high_energy()
                    logger.info(
                        f"Frequency - Bass: {bass:.1f}, Mid: {mid:.1f}, High: {high:.1f}"
                    )

                time.sleep(0.016)  # ~60 FPS
        else:
            logger.error("Failed to open enhanced microphone")


# Backwards compatibility alias
EnhancedUSBMicrophone = USBMicrophone


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "enhanced":
        # Test enhanced features
        test_enhanced_microphone()
    else:
        # Original test for backwards compatibility
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
