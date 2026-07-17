# jingle-dmx

All sorts of lightning-producing fun
Built on Raspberry 4 2GB, uses a cheap microphone from aliexpress.
Also uses a cheap usb to dmx adapter from aliexpress

Converts microphone input into DMX output.

100% vibe-coded.

## Setup

on a fresh raspberry one needs to set the permissions for udmx device so that we can send signals through it

that's done by copying `98-udmx.rules` to `/etc/udev/rules.d/98-udmx.rules` and reloading udev rules / replugging udmx cable

```sh
cp 98-udmx.rules /etc/udev/rules.d/98-udmx.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Building and installing the wheel

This project ships a small Cython extension (`audio_core`) that speeds up
audio processing. To build it into a wheel and install it into your
virtualenv using `uv`:

```sh
cd /path/to/jingle-dmx

# Build a wheel using the PEP 517 build backend
uv build --wheel

# Install the freshly built wheel into the current environment
uv pip install dist/jingle_dmx-*.whl
```

What this does:

- `uv build --wheel` creates an isolated build environment using
	`pyproject.toml`'s `[build-system]` (setuptools, Cython, NumPy, etc.)
	and compiles `audio_core` into a shared object.
- The resulting wheel in `dist/` contains the compiled extension plus the
	Python modules (`usb_mic.py`, `show_controller.py`, etc.).
- When the wheel is installed, `usb_mic.py` will automatically use
	`audio_core.fast_rms_peak` if it is available, falling back to pure
	NumPy if not.

To sanity-check that the extension is available after installation, run:

```sh
uv run python -c "import audio_core; print(audio_core.fast_rms_peak.__name__)"
```

### Development workflow

When you change `audio_core.pyx` (or other build-related files like
`setup.py` or `pyproject.toml`), you need to rebuild and reinstall the
wheel so the compiled extension matches the Python code:

```sh
cd /path/to/jingle-dmx

# Rebuild the wheel after changing Cython sources
uv build --wheel

# Reinstall the updated wheel into your environment
uv pip install --force-reinstall dist/jingle_dmx-*.whl
```

After that, restart any running service or process that imports
`audio_core` (for example the systemd service running `main.py`) so it
picks up the new shared library.

## Service Management

To install or update the systemd service:

```sh
# Symlink the service file into the system directory
sudo ln -sf /home/pi/jingle-dmx/jingle-dmx.service /etc/systemd/system/jingle-dmx.service

# Reload systemd to see the changes
sudo systemctl daemon-reload

# Restart the service
sudo systemctl restart jingle-dmx

# Check status
sudo systemctl status jingle-dmx
```

## Web Controller

The project now includes a live web controller for runtime tweaks.

It supports:

- enabling or disabling effect families (beat/frequency/combo/etc.)
- per-device enable/disable flags
- live intensity caps for dimmer/strobe/UV/laser
- a master intensity slider (`0.0` to `1.0`)
- blackout / panic blackout

By default, the controller starts with the main process on:

```sh
http://0.0.0.0:8080/
```

By default, requests are accepted only from loopback and private/link-local
network IP ranges, so remote control works on your LAN but is blocked from
public internet addresses.

Environment variables:

- `WEB_CONTROLLER_ENABLED=true|false` (default: `true`)
- `WEB_CONTROLLER_HOST` (default: `0.0.0.0`)
- `WEB_CONTROLLER_PORT` (default: `8080`)
- `WEB_CONTROLLER_LOCAL_ONLY=true|false` (default: `true`)
- `WEB_CONTROLLER_ALLOWED_CIDRS` (optional comma-separated extra CIDRs to allow)

Example:

```sh
WEB_CONTROLLER_ENABLED=true WEB_CONTROLLER_HOST=0.0.0.0 WEB_CONTROLLER_LOCAL_ONLY=true WEB_CONTROLLER_PORT=8090 uv run python main.py
```
