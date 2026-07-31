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
    """Calculates a sliding-window RMS envelope independently per channel.

    Parameters
    ----------
    data : np.ndarray, shape (num_channels, num_samples)
        Multi-channel raw signal input.
    window_samples : int
        Window width in samples (e.g., 50 samples for 0.05 s at 1 kHz;
        see `RMS_WINDOW_SECONDS` in models/config.py).

    Returns
    -------
    np.ndarray, shape matching `data`
         RMS envelope computed via a centered sliding mean of squared values.
         Uses nearest-edge padding (`mode="nearest"`) to preserve array length,
         avoiding dimension mismatches in downstream plots or buffers.

    Notes
    -----
    Utilizes `scipy.ndimage.uniform_filter1d` for efficient C-level sliding
    window filtering. Avoiding Python-level loops keeps RMS computation
    fast enough for real-time GUI updates.
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
    """Applies a zero-phase low-pass Butterworth filter across all channels.

    Parameters
    ----------
    data : np.ndarray, shape (num_channels, num_samples)
        Multi-channel input signal data.
    sample_rate_hz, cutoff_hz, order : float/int
        Filter specification parameters (defaults set in models/config.py:
        4th-order Butterworth with a 40 Hz cutoff).

    Returns
    -------
    np.ndarray, shape matching `data`
       Filtered signal array. Falls back to raw data if the sample count is
       too small for `scipy.signal.filtfilt` padding (e.g., initial live packets).
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
    """Helper module for routing update events across both live and offline views."""
    if mode is SignalMode.ORIGINAL:
        return data
    if mode is SignalMode.RMS:
        return compute_rms(data)
    if mode is SignalMode.FILTERED:
        return compute_filtered(data)
    raise ValueError(f"Unknown signal mode: {mode!r}")
