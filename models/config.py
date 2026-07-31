"""Centralized configuration for TCP data formats and signal processing parameters.

Consolidating these constants ensures consistent data parsing, buffering,
and visualization across all modules, while providing a single source of truth
for project setup and documentation.
"""

# --- TCP Packet Format (Fixed protocol spec) ------------------------------
NUM_CHANNELS = 32
SAMPLES_PER_PACKET = 18          # samples per channel, per packet
DTYPE = "float64"                 # 8 bytes per value
BYTES_PER_VALUE = 8
PACKET_SIZE_BYTES = NUM_CHANNELS * SAMPLES_PER_PACKET * BYTES_PER_VALUE  # 4608

# --- Sampling Rate -----------------------------------------------------------
# Matches the recording device (Muovi) used in recording.pkl
# (device_information['sampling_frequency']) and streamed by tcp_server/server.py.
SAMPLE_RATE_HZ = 2000.0

# --- TCP Connection Defaults ---------------------------------------------------
# Configured to connect to the local streaming server in tcp_server/server.py.
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 12345

# --- Live view ----------------------------------------------------------------
ROLLING_WINDOW_SECONDS = 10.0      # how many seconds of history the live plot shows
ROLLING_WINDOW_SAMPLES = int(ROLLING_WINDOW_SECONDS * SAMPLE_RATE_HZ)

# --- Signal processing ---------------------------------------------------------
# RMS: a sliding window RMS envelope of the raw signal.
RMS_WINDOW_SECONDS = 0.05          # 50 ms window
RMS_WINDOW_SAMPLES = max(1, int(RMS_WINDOW_SECONDS * SAMPLE_RATE_HZ))

# Filter: 4th-order Butterworth low-pass, applied per channel.
FILTER_ORDER = 4
FILTER_CUTOFF_HZ = 40.0

# --- Vertical Spacing for All-Channel Plot -------------------------------------
# Channels are normalized (zero mean, unit std) and clipped to +/- ALL_CHANNELS_CLIP_STD
# before being offset vertically by ALL_CHANNELS_LANE_HEIGHT.
# Clipping post-normalization guarantees channels won't overlap regardless of raw amplitude:
# the minimum gap between adjacent lanes is always
# (ALL_CHANNELS_LANE_HEIGHT - 2 * ALL_CHANNELS_CLIP_STD) > 0.
# Used in LivePlotWidget.update_all_channels().
ALL_CHANNELS_CLIP_STD = 3.5
ALL_CHANNELS_LANE_HEIGHT = 8.0
