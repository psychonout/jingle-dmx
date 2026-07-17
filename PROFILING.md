# Profiling Jingle DMX

There are two main ways to profile the application to find performance bottlenecks.

## 1. Using Built-in cProfile (Easy)

The application now has built-in support for `cProfile`. You can run it directly with the `--profile` flag.

```bash
# Activate virtual environment
source .venv/bin/activate

# Run with profiling enabled
python main.py --profile
```

Run the show for a while (e.g., 30 seconds), then press `Ctrl+C` to stop.
The script will:
1. Print the top 20 time-consuming functions to the console.
2. Save the full profile data to `jingle_dmx.prof`.

### Analyzing the results

You can visualize the `jingle_dmx.prof` file using `snakeviz`:

```bash
pip install snakeviz
snakeviz jingle_dmx.prof
```

This will open a web browser with an interactive sunburst chart of your code's performance.

## 2. Using py-spy (Recommended for Production/Service)

[py-spy](https://github.com/benfred/py-spy) is a sampling profiler that can inspect a running python program without restarting it. It has very low overhead.

### Installation

```bash
pip install py-spy
# or if you are on a Pi and want a system-wide install:
# sudo pip3 install py-spy
```

### Usage

**Option A: Record a flamegraph while running the script**

> **⚠️ WARNING for Audio/Hardware Apps:**
> Running `sudo py-spy ... -- python main.py` runs your script as **root**.
> This often breaks audio access (ALSA) because the root user cannot see the audio devices owned by the `pi` user.
>
> **Recommended Approach:**
> 1. Start your app normally in one terminal:
>    ```bash
>    .venv/bin/python main.py
>    ```
> 2. In a **second terminal**, find the PID and attach `py-spy`:
>    ```bash
>    pgrep -f "python.*main.py"
>    # Output: 1234 (example)
>
>    sudo .venv/bin/py-spy record -o profile.svg --pid 1234 --duration 30
>    ```

**Option B: Attach to the running service**

**Option B: Attach to the running service**

If the service is already running (via systemd):

1. Find the PID of the process:
   ```bash
   pgrep -f "python.*main.py"
   ```
2. Record a profile for 30 seconds:
   ```bash
   sudo py-spy record -o profile.svg --pid <PID> --duration 30
   ```

### Viewing the Flamegraph

Open `profile.svg` in any web browser.
- **Width** represents the percentage of time spent in a function.
- **Color** is usually random (or heat-based).
- Look for wide bars at the bottom (entry points) and follow them up to find the "leaf" functions that are taking the most time (wide bars at the top).

## What to look for

- **High CPU usage in `_run_loop`**: This is expected, but check *what* inside the loop is slow.
- **Slow device writes**: If calls to `dmx.send` or similar are slow, the bottleneck is I/O.
- **Slow audio processing**: If `numpy` or `audio_core` functions are taking a long time, we might need to optimize the math or reduce the sample rate.
