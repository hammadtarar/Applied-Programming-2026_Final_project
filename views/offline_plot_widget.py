import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget


class OfflinePlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._figure = Figure(figsize=(5, 3))
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._ax = self._figure.add_subplot(111)
        self._ax.set_xlabel("Time (s)")
        self._ax.set_ylabel("Amplitude")
        self._ax.set_title("No recording yet")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def plot(self, time_axis: np.ndarray, data: np.ndarray, channel: int, mode_label: str) -> None:
        """Redraws the plot using data from a single selected channel.

        Parameters
        ----------
        data : ndarray
            Full recorded dataset with shape (num_channels, num_samples).
        channel : int
           Index of the channel row to extract and plot.
        """
        self._ax.clear()
        self._ax.set_xlabel("Time (s)")
        self._ax.set_ylabel("Amplitude")

        if time_axis.size == 0 or data.size == 0:
            self._ax.set_title("No recording available")
            self._canvas.draw_idle()
            return

        channel = min(max(channel, 0), data.shape[0] - 1)
        self._ax.plot(time_axis, data[channel], color="#1f6feb", linewidth=0.8)
        self._ax.set_title(f"Channel {channel} -- {mode_label} -- offline recording")
        self._canvas.draw_idle()

    def clear(self) -> None:
        self._ax.clear()
        self._ax.set_xlabel("Time (s)")
        self._ax.set_ylabel("Amplitude")
        self._ax.set_title("No recording yet")
        self._canvas.draw_idle()
