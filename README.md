# TCP Signal Visualization Application

Final project for Applied Programming (2026) — live and offline visualization
of a 32-channel EMG signal stream received over TCP.

## Group

**Group 19**

- Syed Askari Abbas Rizvi (ik51ymek)
- Zohran Ahmed (bu11lixo)
- Hammad Ashraf Tarar (cy73xuno)

Work was split roughly evenly across the three areas of the project:

- **Syed Askari Abbas Rizvi** — TCP client and backend (`models/`): socket
  handling, packet reconstruction, buffering, and signal processing
  (RMS and filtering).
- **Zohran Ahmed** — Live and offline visualization (`views/`): the VisPy
  live plot (single-channel and all-channels), the Matplotlib offline plot,
  and the main window UI.
- **Hammad Ashraf Tarar** — ViewModel integration (`viewmodels/`), error
  handling, testing against the TCP server, and this documentation.

## Overview

The application connects to the Exercise 5 TCP server, which streams
recorded EMG data (`recording.pkl`) in packets of 32 channels × 18 samples
(`float64`, 4608 bytes/packet, sampled at 2000 Hz). It shows the incoming
data live with **VisPy**, lets the user switch between the **original**,
**RMS**, and **filtered** signal, and — once streaming stops — lets the user
inspect the whole recorded session offline with **Matplotlib**.

The code follows an **MVVM** structure (see [Project structure](#project-structure)).
Following Exercise 5's approach, the TCP client uses a **non-blocking socket
polled by a QTimer** rather than a background thread — this is the pattern
taught in that exercise, and it keeps the client simple (no thread-safety
concerns) while still never freezing the GUI.

## 1. Installation

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

We verified this project installs cleanly into a fresh virtual environment
using only `requirements.txt` (numpy, scipy, matplotlib, PySide6, vispy).

## 2. Running the application

```bash
python main.py
```

This opens the main window with a **Connection** panel, a **Display** panel,
and a **Live** / **Offline** tab view.

### Running the TCP server for testing

`tcp_server/server.py` is the Exercise 5 server, provided for the course and
included here for local testing/demo purposes. It streams the EMG data in
`tcp_server/recording.pkl` at the recording's real sampling rate (2000 Hz):

```bash
python tcp_server/server.py
```

It listens on `localhost:12345` by default — the same defaults already
pre-filled in the app's Connection panel, so you can just click **Connect**.

## 3. Connecting to the TCP server

1. Enter the **Host** (default `localhost`) and **Port** (default `12345`)
   in the Connection panel — these match `tcp_server/server.py` out of the
   box.
2. Click **Connect**. The status bar shows `Connecting...`, then
   `Connected to <host>:<port>` once the connection succeeds, or an error
   message (see [Error handling](#7-error-handling)) if it fails.
3. Streaming starts automatically — the **Live** tab begins updating.
4. Click **Disconnect** to stop streaming and cleanly close the socket.
   Once disconnected, the **Offline** tab becomes available with the full
   recorded session.

## 4. Using the live plot

- The **Live** tab shows a rolling window of the last 10 seconds of data
  (`ROLLING_WINDOW_SECONDS` in `models/config.py`), with a visible,
  auto-scaled y-axis and a time-labeled x-axis.
- Use the **Channel** spin box (0–31) to pick which channel is shown.
- Use the **Signal mode** dropdown to switch between **Original**, **RMS**,
  and **Filtered** — the live plot updates immediately.
- Click **Plot All Channels** to instead show all 32 channels at once,
  stacked with a small vertical offset for readability (this disables the
  single-channel selector, since it no longer applies). Click it again to
  return to the single-channel view.
  Each channel is normalized to zero mean and unit standard deviation, then
  clipped to ±3.5 std before being stacked (`ALL_CHANNELS_CLIP_STD` /
  `ALL_CHANNELS_LANE_HEIGHT` in `models/config.py`). This guarantees no
  channel can ever visually overlap a neighbor, regardless of its raw
  amplitude -- real EMG recordings often have one channel far noisier than
  the rest (comparing *raw* amplitudes would let that one channel dominate
  and bleed into its neighbors, which is what happened before this fix).

## 5. Using the offline plot

- Once you disconnect (or the connection is lost), switch to the
  **Offline** tab to inspect the entire recorded session with Matplotlib.
- The same **Channel** and **Signal mode** controls apply here too — change
  them while the Offline tab is active and the plot redraws from the full
  recording.
- If no data was recorded yet, the tab shows "No recording available"
  instead of an empty/broken plot.

## 6. RMS and filter parameters

Defined in `models/config.py` (single source of truth for both the live and
offline views, and both the VisPy and Matplotlib plots):

| Parameter | Value | Notes |
|---|---|---|
| Sample rate | 2000 Hz | Matches the recording device (see `recording.pkl`'s `device_information['sampling_frequency']`) and `tcp_server/server.py`. |
| RMS window | 50 ms (100 samples at 2 kHz) | Sliding-window RMS via `scipy.ndimage.uniform_filter1d` on the squared signal, then square-rooted. Vectorized (not a per-sample Python loop) so it stays fast enough for the live view. |
| Filter | 4th-order Butterworth low-pass, 40 Hz cutoff | Zero-phase (`scipy.signal.filtfilt`), applied per channel independently. |

## 7. Error handling

Implemented in `models/tcp_client.py` and `viewmodels/main_viewmodel.py`,
surfaced through the status label:

- **Server not running / wrong port** → `socket.connect` raises `OSError`,
  caught in `connect_requested` and shown as `Could not connect: <details>`.
- **Connection lost mid-stream** → detected when `recv()` returns no data;
  the model disconnects itself and the ViewModel shows `Error: Connection
  closed by server.`
- **No data for offline plotting** → the Offline tab shows "No recording
  available" instead of plotting an empty array.
- **Invalid channel / mode selection** → the channel spin box is hard-limited
  to 0–31 and the mode dropdown only offers the three valid modes, so an
  invalid value can't be entered through the GUI; `MainViewModel` also
  clamps the channel index defensively before indexing into the data.
- **Invalid port** → the port spin box only allows 1–65535; `connect_requested`
  double-checks this and reports back through the status label rather than
  letting a bad value reach the socket call.

None of these cases crash the application — the socket is closed cleanly,
the GUI returns to a normal, reconnectable state, and the QTimer stops
polling once disconnected.

## Project structure

MVVM: **Views** only build widgets and forward user actions; **ViewModels**
hold all application state and connect the two; **Models** know nothing
about the GUI.

```text
final_project/
├── main.py                        # wires Model/ViewModel/View together, starts Qt event loop
├── requirements.txt
├── tcp_server/                    # Exercise 5's server, for local testing (not part of the client)
│   ├── server.py
│   └── recording.pkl              # recorded EMG session the server streams
├── models/
│   ├── config.py                  # packet format, sample rate, RMS/filter parameters
│   ├── tcp_client.py               # TcpClientModel: non-blocking socket, packet reconstruction (Exercise 5 pattern)
│   ├── signal_buffer.py            # RollingBuffer (live window) + RecordingBuffer (full session)
│   └── signal_processing.py        # compute_rms, compute_filtered, SignalMode enum
├── viewmodels/
│   └── main_viewmodel.py           # MainViewModel: owns buffers + TCP model + QTimer, exposes Qt signals/slots
└── views/
    ├── main_window.py              # QMainWindow: connection panel, display panel, tabs, status bar
    ├── live_plot_widget.py         # VisPy SceneCanvas embedded in Qt, single-channel & all-channels modes
    └── offline_plot_widget.py      # Matplotlib FigureCanvasQTAgg embedded in Qt
```

- **View → ViewModel:** button clicks and combo-box changes call
  `MainViewModel` slots directly (e.g. `connect_requested`, `channel_changed`).
- **ViewModel → View:** `MainViewModel` emits Qt signals
  (`status_changed`, `connection_state_changed`, `live_view_updated`,
  `offline_data_available`) that `MainWindow` connects to in
  `_connect_view_model()`.
- **ViewModel → Model:** `MainViewModel` owns a `TcpClientModel` (polled by
  its own `QTimer`, no background thread), a `RollingBuffer`, and a
  `RecordingBuffer`; it is the only place that calls into `models/`.
- The View never touches a socket or a buffer directly, and nothing in
  `models/` imports `PySide6.QtWidgets`.
