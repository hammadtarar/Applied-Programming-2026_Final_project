"""Shared constants describing the TCP data format and signal-processing parameters.

Keeping these in one place means the whole application (TCP parsing, buffering,
signal processing, plotting) agrees on the same numbers, and it gives us one
spot to document the choices for the README.
"""

# --- TCP / packet format (fixed by the Exercise 5 server) -------------------
NUM_CHANNELS = 32
SAMPLES_PER_PACKET = 18          # samples per channel, per packet
DTYPE = "float64"                 # 8 bytes per value
BYTES_PER_VALUE = 8
PACKET_SIZE_BYTES = NUM_CHANNELS * SAMPLES_PER_PACKET * BYTES_PER_VALUE  # 4608

# --- Sampling rate -----------------------------------------------------------
# Matches the recording device (Muovi) used to capture recording.pkl -- see
# its device_information['sampling_frequency'] -- and the Exercise 5 server
# that streams it (tcp_server/server.py).
SAMPLE_RATE_HZ = 2000.0

# --- TCP connection defaults ---------------------------------------------------
# Match the Exercise 5 / course-provided server in tcp_server/server.py.
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

# --- Plot-all-channels vertical spacing ----------------------------------------
# Each channel is normalized to zero mean, unit std, then clipped to
# +/- ALL_CHANNELS_CLIP_STD before being stacked ALL_CHANNELS_LANE_HEIGHT
# apart. Because clipping happens *after* normalizing, no channel -- however
# loud or quiet its raw amplitude -- can ever cross into a neighbor's lane:
# the minimum gap between any two adjacent channels is always
# (ALL_CHANNELS_LANE_HEIGHT - 2 * ALL_CHANNELS_CLIP_STD), which is positive
# by construction. See LivePlotWidget.update_all_channels().
ALL_CHANNELS_CLIP_STD = 3.5
ALL_CHANNELS_LANE_HEIGHT = 8.0
