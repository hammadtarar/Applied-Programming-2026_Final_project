"""MainViewModel: the single source of truth for application state.

Views bind to this ViewModel's signals and call its slots; it is the only
place that talks to both the TCP model and the buffer/signal-processing
models. Views never touch `TcpClientModel`, `RollingBuffer`, etc. directly,
and the models never import any GUI code -- this ViewModel is the seam
between them (the "VM" in MVVM).

Following Exercise 5's approach, there is no background thread: a QTimer
calls `_poll_tcp` regularly, which asks the (non-blocking) `TcpClientModel`
for any newly arrived data. See models/tcp_client.py for why this is safe
without freezing the GUI.
"""

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from models.config import NUM_CHANNELS, SAMPLE_RATE_HZ
from models.signal_buffer import RecordingBuffer, RollingBuffer
from models.signal_processing import SignalMode, apply_mode
from models.tcp_client import TcpClientModel

# How often the QTimer polls the socket, in milliseconds -- matches the
# 10 ms interval used in the Exercise 5 solution.
POLL_INTERVAL_MS = 10


class MainViewModel(QObject):
    """Owns the TCP client and both buffers; exposes state to the Views."""

    # --- Signals consumed by Views ---------------------------------------
    status_changed = Signal(str)
    connection_state_changed = Signal(bool)        # True once connected
    live_view_updated = Signal(object, object)      # (time_axis, data) for the *current* display
    offline_data_available = Signal(bool)           # True once a finished recording can be inspected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rolling_buffer = RollingBuffer(NUM_CHANNELS)
        self.recording_buffer = RecordingBuffer(NUM_CHANNELS)

        self.current_channel = 0
        self.current_mode = SignalMode.ORIGINAL
        self.show_all_channels = False
        self.is_connected = False

        self._model: TcpClientModel | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_tcp)

    # --- Slots called by the View in response to user actions -------------

    @Slot(str, int)
    def connect_requested(self, host: str, port: int) -> None:
        """Connect to the TCP server. Emits an error via status_changed on failure."""
        if self.is_connected:
            self.status_changed.emit("Already connected.")
            return

        if not (0 < port < 65536):
            self.status_changed.emit(f"Invalid port: {port}. Choose a value between 1 and 65535.")
            return

        # A fresh connection starts a fresh recording.
        self.rolling_buffer.clear()
        self.recording_buffer.clear()
        self.offline_data_available.emit(False)

        self.status_changed.emit(f"Connecting to {host}:{port} ...")
        model = TcpClientModel(host, port)
        try:
            model.connect()
        except OSError as error:
            # e.g. server not running, wrong port, unreachable host.
            self.status_changed.emit(f"Could not connect: {error}")
            return

        self._model = model
        self.is_connected = True
        self.connection_state_changed.emit(True)
        self.status_changed.emit(f"Connected to {host}:{port}")
        self._timer.start(POLL_INTERVAL_MS)

    @Slot()
    def disconnect_requested(self) -> None:
        """Stop polling and close the connection."""
        if not self.is_connected or self._model is None:
            self.status_changed.emit("Not connected.")
            return

        self._timer.stop()
        self._model.disconnect()
        self._model = None
        self.is_connected = False
        self.connection_state_changed.emit(False)
        self.status_changed.emit("Disconnected.")
        self.offline_data_available.emit(self.recording_buffer.has_data())

    @Slot(int)
    def channel_changed(self, channel_index: int) -> None:
        self.current_channel = channel_index
        self._refresh_live_view()

    @Slot(str)
    def mode_changed(self, mode_value: str) -> None:
        self.current_mode = SignalMode(mode_value)
        self._refresh_live_view()

    @Slot(bool)
    def show_all_channels_changed(self, show_all: bool) -> None:
        self.show_all_channels = show_all
        self._refresh_live_view()

    # --- Data the offline (Matplotlib) view pulls on demand ----------------

    def get_offline_data(self):
        """Return (time_axis, processed_data) for the whole recorded session.

        `processed_data` has shape (NUM_CHANNELS, num_samples); the offline
        view picks whichever channel/mode it currently wants to display, the
        same way the live view does.
        """
        raw = self.recording_buffer.get()
        time_axis = self.recording_buffer.time_axis(SAMPLE_RATE_HZ)
        processed = apply_mode(raw, self.current_mode) if raw.size else raw
        return time_axis, processed

    # --- Internal: polling the (non-blocking) TCP model ---------------------

    def _poll_tcp(self) -> None:
        """Called every POLL_INTERVAL_MS ms by the QTimer.

        Asks the model to drain the socket, then pulls off and buffers any
        newly reconstructed packets -- *before* checking connection status,
        so a batch of packets received in the same tick as a disconnect is
        still buffered rather than silently dropped. If the server closed
        the connection since the last tick, `model.is_connected` will now
        be False.
        """
        if self._model is None:
            return

        self._model.receive_data()

        for packet in self._model.take_new_packets():
            self.rolling_buffer.append(packet)
            self.recording_buffer.append(packet)

        if not self._model.is_connected:
            self._handle_connection_lost()
            return

        self._refresh_live_view()

    def _handle_connection_lost(self) -> None:
        """The server closed the connection (not a user-requested disconnect)."""
        self._timer.stop()
        self._model = None
        was_connected = self.is_connected
        self.is_connected = False
        self.connection_state_changed.emit(False)
        if was_connected:
            self.status_changed.emit("Error: Connection closed by server.")
        self.offline_data_available.emit(self.recording_buffer.has_data())

    def _refresh_live_view(self) -> None:
        """Recompute the processed data for the current display choice and emit it."""
        raw = self.rolling_buffer.get()
        if raw.size == 0:
            return
        time_axis = self.rolling_buffer.time_axis(SAMPLE_RATE_HZ)
        processed = apply_mode(raw, self.current_mode)
        if self.show_all_channels:
            self.live_view_updated.emit(time_axis, processed)
        else:
            channel = min(self.current_channel, processed.shape[0] - 1)
            self.live_view_updated.emit(time_axis, processed[channel])
