from enum import Enum

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, filtfilt

from models.config import FILTER_CUTOFF_HZ, FILTER_ORDER, RMS_WINDOW_SAMPLES, SAMPLE_RATE_HZ


class SignalMode(Enum):
    """The three signal modes required by the assignment."""

    ORIGINAL = "Original"
    RMS = "RMS"
    FILTERED = "Filtered"


def compute_rms(data: np.ndarray, window_samples: int = RMS_WINDOW_SAMPLES) -> np.ndarray:
    """Sliding-window RMS envelope, computed independently per channel (row).

    Parameters
    ----------
    data : np.ndarray, shape (num_channels, num_samples)
        Raw signal.
    window_samples : int
        Width of the sliding window, in samples. See RMS_WINDOW_SECONDS in
        models/config.py for how this is chosen (0.05 s -> 50 samples at 1 kHz).

    Returns
    -------
    np.ndarray, same shape as `data`
        RMS envelope (a centered sliding-window mean of the squared signal,
        then square-rooted). Edge samples use `mode="nearest"` padding so the
        output length always matches the input length -- nothing downstream
        (plots, buffers) needs to special-case a shorter array.

    Implementation note
    --------------------
    Uses `scipy.ndimage.uniform_filter1d`, a vectorized (C-level) sliding
    window, rather than a per-sample Python loop -- this matters because RMS
    is recomputed over the whole rolling window on every incoming packet for
    the live view, so it needs to stay fast enough to not lag the GUI.
    """
    if data.size == 0:
        return data.copy()

    data = np.atleast_2d(data)
    window_samples = max(1, int(window_samples))
    squared = data.astype(np.float64) ** 2
    mean_squared = uniform_filter1d(squared, size=window_samples, axis=1, mode="nearest")
    return np.sqrt(mean_squared)


def compute_filtered(
    data: np.ndarray,
    sample_rate_hz: float = SAMPLE_RATE_HZ,
    cutoff_hz: float = FILTER_CUTOFF_HZ,
    order: int = FILTER_ORDER,
) -> np.ndarray:
    """Zero-phase low-pass Butterworth filter, applied independently per channel.

    Parameters
    ----------
    data : np.ndarray, shape (num_channels, num_samples)
    sample_rate_hz, cutoff_hz, order : filter design parameters
        Defaults come from models/config.py (4th-order Butterworth, 40 Hz cutoff).

    Returns
    -------
    np.ndarray, same shape as `data`
        Filtered signal. Falls back to the unfiltered signal if there are too
        few samples for `filtfilt`'s padding requirement (this happens only
        for the first couple of live-view updates right after connecting).
    """
    if data.size == 0:
        return data.copy()

    data = np.atleast_2d(data)
    nyquist = 0.5 * sample_rate_hz
    normalized_cutoff = min(cutoff_hz / nyquist, 0.99)
    b, a = butter(order, normalized_cutoff, btype="low")

    min_len = 3 * (max(len(a), len(b)) - 1)
    if data.shape[1] <= min_len:
        return data.copy()

    return filtfilt(b, a, data, axis=1)


def apply_mode(data: np.ndarray, mode: SignalMode) -> np.ndarray:
    """Dispatch helper used by both the live and offline views."""
    if mode is SignalMode.ORIGINAL:
        return data
    if mode is SignalMode.RMS:
        return compute_rms(data)
    if mode is SignalMode.FILTERED:
        return compute_filtered(data)
    raise ValueError(f"Unknown signal mode: {mode!r}")
