import numpy as np

from models.config import NUM_CHANNELS, ROLLING_WINDOW_SAMPLES, SAMPLE_RATE_HZ


class RollingBuffer:
    """Circular numpy buffer of shape (NUM_CHANNELS, capacity_samples) for real-time signal storage."""

    def __init__(self, num_channels: int = NUM_CHANNELS, capacity_samples: int = ROLLING_WINDOW_SAMPLES):
        self.num_channels = num_channels
        self.capacity = capacity_samples
        self._data = np.zeros((num_channels, capacity_samples), dtype=np.float64)
        self._filled = 0  # how many samples have been written in total (caps at capacity)

    def append(self, chunk: np.ndarray) -> None:
        """Appends a new data chunk of shape (num_channels, num_new_samples), sliding the buffer window forward."""
        n = chunk.shape[1]
        if n >= self.capacity:
            # If the incoming chunk exceeds total buffer capacity, retain only the newest tail samples.
            self._data[:] = chunk[:, -self.capacity:]
        else:
            self._data = np.concatenate([self._data[:, n:], chunk], axis=1)
        self._filled = min(self.capacity, self._filled + n)

    def get(self) -> np.ndarray:
        """Returns the active portion of the buffer with shape (num_channels, filled)."""
        if self._filled < self.capacity:
            return self._data[:, self.capacity - self._filled:]
        return self._data

    def time_axis(self, sample_rate_hz: float = SAMPLE_RATE_HZ) -> np.ndarray:
        """Generates a relative time axis in seconds ending at 0, matching the length of `get()`."""
        n = self.get().shape[1]
        return (np.arange(n) - n) / sample_rate_hz

    def clear(self) -> None:
        self._data[:] = 0.0
        self._filled = 0


class RecordingBuffer:
    """Dynamic buffer storing the full streaming session for post-hoc analysis."""

    def __init__(self, num_channels: int = NUM_CHANNELS):
        self.num_channels = num_channels
        self._chunks: list[np.ndarray] = []
        self._total_samples = 0

    def append(self, chunk: np.ndarray) -> None:
        self._chunks.append(chunk.copy())
        self._total_samples += chunk.shape[1]

    def get(self) -> np.ndarray:
        """Returns the complete session recording with shape (num_channels, total_samples).

        Data chunks are concatenated lazily on request to keep per-packet appends
        fast and lightweight.
        """
        if not self._chunks:
            return np.zeros((self.num_channels, 0), dtype=np.float64)
        return np.concatenate(self._chunks, axis=1)

    def time_axis(self, sample_rate_hz: float = SAMPLE_RATE_HZ) -> np.ndarray:
        return np.arange(self._total_samples) / sample_rate_hz

    def has_data(self) -> bool:
        return self._total_samples > 0

    def clear(self) -> None:
        self._chunks.clear()
        self._total_samples = 0
