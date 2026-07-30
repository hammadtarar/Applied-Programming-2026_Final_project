
import colorsys

import numpy as np
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vispy import scene

from models.config import ALL_CHANNELS_CLIP_STD, ALL_CHANNELS_LANE_HEIGHT, NUM_CHANNELS


def _distinct_colors(n: int):
    """n evenly-spaced, readable colors (used for the 32 stacked channel lines)."""
    return [colorsys.hsv_to_rgb(i / n, 0.65, 0.85) for i in range(n)]


class LivePlotWidget(QWidget):
    """Qt widget wrapping a VisPy SceneCanvas with proper x/y axes."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._canvas = scene.SceneCanvas(keys=None, show=False, bgcolor="white")
        self._canvas.native.setMinimumHeight(300)

        grid = self._canvas.central_widget.add_grid(margin=10)
        self._view = grid.add_view(row=0, col=1, camera="panzoom")
        self._view.camera.interactive = False  # data drives the range, not the mouse

        y_axis = scene.AxisWidget(orientation="left", axis_label="Amplitude", text_color="black")
        y_axis.width_max = 60
        grid.add_widget(y_axis, row=0, col=0)
        y_axis.link_view(self._view)

        x_axis = scene.AxisWidget(orientation="bottom", axis_label="Time (s)", text_color="black")
        x_axis.height_max = 40
        grid.add_widget(x_axis, row=1, col=1)
        x_axis.link_view(self._view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas.native)

        self._single_line = None
        self._channel_lines: list = []
        self._colors = _distinct_colors(NUM_CHANNELS)
        self._mode = None  # "single" | "all"

    def _ensure_single_mode(self) -> None:
        if self._mode == "single":
            return
        for line in self._channel_lines:
            line.parent = None
        self._channel_lines = []
        if self._single_line is None:
            self._single_line = scene.visuals.Line(color="#1f6feb", parent=self._view.scene, width=1.5)
        self._mode = "single"

    def _ensure_all_mode(self) -> None:
        if self._mode == "all":
            return
        if self._single_line is not None:
            self._single_line.parent = None
            self._single_line = None
        self._mode = "all"

    def update_single_channel(self, time_axis: np.ndarray, data: np.ndarray) -> None:
        """Draw one channel's signal. `data` shape: (num_samples,)."""
        if time_axis.size < 2:
            return
        self._ensure_single_mode()
        positions = np.column_stack([time_axis, data]).astype(np.float32)
        self._single_line.set_data(pos=positions)
        self._view.camera.set_range(
            x=(float(time_axis[0]), float(time_axis[-1])),
            y=(float(data.min()) - 1e-6, float(data.max()) + 1e-6),
            margin=0.05,
        )

    def update_all_channels(self, time_axis: np.ndarray, data: np.ndarray) -> None:
        """Draw all channels stacked with a vertical offset. `data` shape: (num_channels, num_samples)."""
        if time_axis.size < 2:
            return
        self._ensure_all_mode()
        num_channels = data.shape[0]

        # Lazily (re)create one Line visual per channel.
        if len(self._channel_lines) != num_channels:
            for line in self._channel_lines:
                line.parent = None
            self._channel_lines = [
                scene.visuals.Line(color=self._colors[ch % len(self._colors)], parent=self._view.scene, width=1.0)
                for ch in range(num_channels)
            ]

        # Normalize each channel to zero mean, unit std, then clip to a fixed
        # range before stacking. This guarantees channels can never overlap
        # into a neighbor's lane, *and* keeps every channel equally readable
        # regardless of its raw amplitude -- real recordings often have one
        # channel that's far noisier than the rest (yours has one ~20x
        # louder), and comparing raw amplitudes let that channel swamp its
        # neighbors. On a normalized scale it no longer can.
        centered = data - data.mean(axis=1, keepdims=True)
        channel_std = np.std(centered, axis=1, keepdims=True)
        channel_std[channel_std == 0] = 1.0  # avoid divide-by-zero for flat/dead channels
        normalized = centered / channel_std
        clipped = np.clip(normalized, -ALL_CHANNELS_CLIP_STD, ALL_CHANNELS_CLIP_STD)

        for ch in range(num_channels):
            offset = (num_channels - 1 - ch) * ALL_CHANNELS_LANE_HEIGHT
            positions = np.column_stack([time_axis, clipped[ch] + offset]).astype(np.float32)
            self._channel_lines[ch].set_data(pos=positions)

        top = (num_channels - 1) * ALL_CHANNELS_LANE_HEIGHT + ALL_CHANNELS_CLIP_STD
        bottom = -ALL_CHANNELS_CLIP_STD
        self._view.camera.set_range(
            x=(float(time_axis[0]), float(time_axis[-1])),
            y=(float(bottom), float(top)),
            margin=0.02,
        )
