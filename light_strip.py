import wave
import numpy as np
from blinkt import set_pixel, show, clear, set_brightness, NUM_PIXELS
import time
import colorsys # For nice color transitions
import sys

# --- Audio File Configuration ---
AUDIO_FILE = "test_audio.wav" # <-- CHANGE THIS to your WAV file path!

# --- Blinkt! Configuration ---
BL_BRIGHTNESS = 0.05 # Start with low brightness
PEAK_LEVEL_THRESHOLD = 5000 # Adjust this! Represents the amplitude that makes all LEDs light up
DECAY_RATE = 0.9 # How fast the bars fade down (0.0 to 1.0)
MIN_BARS = 1 # Minimum number of bars to always show (e.g., for "idle" state)

# --- DMX Control Placeholder (Same as before, just printing) ---
dmx_effect_state = "idle"

def map_value(value, in_min, in_max, out_min, out_max):
    """Maps a value from one range to another."""
    return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def get_color_from_hue(hue_normalized):
    """Converts a normalized hue (0-1) to an RGB tuple (0-255)."""
    r, g, b = colorsys.hsv_to_rgb(hue_normalized, 1.0, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)

def get_peak_color(level, max_level):
    """Returns a color (e.g., green-yellow-red) based on sound level."""
    # Hue from green (0.33) to red (0.0)
    hue = map_value(level, 0, max_level, 0.33, 0.0)
    hue = max(0.0, min(0.33, hue)) # Clamp hue
    return get_color_from_hue(hue)

# --- DMX Control Placeholder Functions ---
def set_dmx_effect(effect_type):
    global dmx_effect_state # Declare as global to modify the variable
    if dmx_effect_state == effect_type:
        return # No change needed

    dmx_effect_state = effect_type
    if effect_type == "idle":
        print("DMX: Setting effect to IDLE")
        # DMX_controller.set_scene("ambient_blue")
    elif effect_type == "medium":
        print("DMX: Setting effect to MEDIUM")
        # DMX_controller.set_scene("pulsing_green")
    elif effect_type == "intense":
        print("DMX: Setting effect to INTENSE")
        # DMX_controller.set_scene("flashing_red_strobe")
    # You'd add a call to your actual DMX library here, e.g.,
    # dmx.set_channel(1, value) or fixture.set_color(...)


def main():
    wf = None # Initialize to None for the finally block
    try:
        wf = wave.open(AUDIO_FILE, 'rb')

        # Get audio file parameters
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth() # Bytes per sample
        framerate = wf.getframerate()
        nframes = wf.getnframes()

        # Calculate chunk size (arbitrary, affects smoothness/responsiveness)
        # We'll use a chunk size that corresponds to roughly 1/30th of a second
        # for a smooth visual update, adjust as needed.
        CHUNK_SIZE = int(framerate / 30) # Roughly 30 frames per second
        if CHUNK_SIZE == 0: CHUNK_SIZE = 1 # Avoid zero division

        # Determine dtype for numpy based on sample width
        if sampwidth == 1:
            dtype = np.int8 # 8-bit unsigned, but we'll convert to signed for analysis
            print("Warning: 8-bit audio is often unsigned. Data might need normalization.")
        elif sampwidth == 2:
            dtype = np.int16 # 16-bit signed
        elif sampwidth == 3:
            dtype = 'int32' # 24-bit audio often read as 32-bit by wave
            print("Warning: 24-bit audio. PyAudio would handle it, but wave module might give 32-bit. Max val will be adjusted.")
        elif sampwidth == 4:
            dtype = np.int32 # 32-bit signed
        else:
            raise ValueError(f"Unsupported sample width: {sampwidth} bytes")

        print(f"Reading '{AUDIO_FILE}': Channels={nchannels}, Sample Width={sampwidth} bytes, Rate={framerate} Hz, Frames={nframes}")
        print(f"Processing in chunks of {CHUNK_SIZE} frames.")

        set_brightness(BL_BRIGHTNESS)
        clear()
        show()

        current_bars = 0
        last_peak = 0

        # Loop through the audio file
        frame_index = 0
        while frame_index < nframes:
            # Read a chunk of frames
            raw_data = wf.readframes(CHUNK_SIZE)
            if not raw_data: # End of file
                break

            # Convert bytes to numpy array
            # If stereo, take only one channel (e.g., left channel) for analysis
            samples = np.frombuffer(raw_data, dtype=dtype)
            if nchannels > 1:
                # Assuming interleaved stereo: [L, R, L, R, ...]
                samples = samples[::nchannels] # Take every 'nchannels'-th sample (e.g., left channel)

            # --- Core Peak Bar Logic (Same as with live microphone) ---
            # Calculate RMS (Root Mean Square) for overall loudness
            # Ensure samples are not empty before calculating RMS
            if samples.size > 0:
                rms = np.sqrt(np.mean(samples**2))
            else:
                rms = 0 # No samples, so no sound

            # Smooth the peak level for more stable bars and decay
            if rms > last_peak:
                last_peak = rms # New peak detected
            else:
                last_peak *= DECAY_RATE # Decay slowly

            # Map the peak level to the number of bars
            num_bars = int(map_value(last_peak, 0, PEAK_LEVEL_THRESHOLD, MIN_BARS, NUM_PIXELS))
            num_bars = max(MIN_BARS, min(NUM_PIXELS, num_bars)) # Clamp between MIN_BARS and NUM_PIXELS

            clear()
            for i in range(num_bars):
                r, g, b = get_peak_color(last_peak, PEAK_LEVEL_THRESHOLD)
                set_pixel(i, r, g, b)
            show()

            # --- DMX Trigger Logic (Same as before) ---
            if last_peak > PEAK_LEVEL_THRESHOLD * 0.8:
                set_dmx_effect("intense")
            elif last_peak < PEAK_LEVEL_THRESHOLD * 0.2:
                set_dmx_effect("idle")
            else:
                set_dmx_effect("medium")

            frame_index += CHUNK_SIZE
            # To simulate real-time playback, add a delay
            # This makes the visualization play at the actual speed of the audio file
            # If you want it to process as fast as possible, remove or reduce this sleep.
            # However, for a visual test, matching playback speed is often helpful.
            time.sleep(CHUNK_SIZE / framerate)

        print("\nFinished playing audio file.")

    except FileNotFoundError:
        print(f"Error: Audio file '{AUDIO_FILE}' not found.", file=sys.stderr)
        sys.exit(1)
    except wave.Error as e:
        print(f"Error reading WAV file: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopping playback and Blinkt!.")
    finally:
        if wf is not None:
            wf.close()
        clear()
        show()

if __name__ == "__main__":
    main()
