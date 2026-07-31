"""Single source of truth for application state and the MVVM seam.

Mediates communication between the UI views and low-level data/signal processing
models (`TcpClientModel`, `RollingBuffer`, etc.). Views bind to this ViewModel's
signals and slots rather than interacting with backend models directly, ensuring
models remain completely decoupled from Qt and GUI dependencies.

Operates single-threaded without background workers: a QTimer periodically invokes
`_poll_tcp` to fetch reconstructed packets from the non-blocking `TcpClientModel`
without blocking the UI thread (see `models/tcp_client.py` for design details).
"""

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from models.config import NUM_CHANNELS, SAMPLE_RATE_HZ
from models.signal_buffer import RecordingBuffer, RollingBuffer
from models.signal_processing import SignalMode, apply_mode
from models.tcp_client import TcpClientModel

# QTimer polling interval in milliseconds (10 ms, matching Exercise 5).
POLL_INTERVAL_MS = 10


class MainViewModel(QObject):
    """Manages the TCP client and buffers while exposing state to views."""

    # --- Signals consumed by Views ----------------------------------------
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

    # --- Slots called by Views --------------------------------------------

    @Slot(str, int)
    def connect_requested(self, host: str, port: int) -> None:
        """Connects to the TCP server, emitting status updates on failure."""
        if self.is_connected:
            self.status_changed.emit("Already connected.")
            return

        if not (0 < port < 65536):
            self.status_changed.emit(f"Invalid port: {port}. Choose a value between 1 and 65535.")
            return

        # Reset state so each new connection starts with a fresh recording.
        self.rolling_buffer.clear()
        self.recording_buffer.clear()
        self.offline_data_available.emit(False)

        self.status_changed.emit(f"Connecting to {host}:{port} ...")
        model = TcpClientModel(host, port)
        try:
            model.connect()
        except OSError as error:
            # Handles common connection failures (e.g., server offline, invalid port, unreachable host).
            self.status_changed.emit(f"Could not connect: {error}")
            return

        self._model = model
        self.is_connected = True
        self.connection_state_changed.emit(True)
        self.status_changed.emit(f"Connected to {host}:{port}")
        self._timer.start(POLL_INTERVAL_MS)

    @Slot()
    def disconnect_requested(self) -> None:
        """Stops socket polling and closes the active TCP connection."""
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

    # --- Offline View Data Access -----------------------------------------

    def get_offline_data(self):
        """Returns the complete session's time axis and processed data arrays.

        Returns
        -------
        time_axis : ndarray
            Time vector corresponding to recorded samples.
        processed_data : ndarray
            Processed signals with shape (NUM_CHANNELS, num_samples).

        Notes
        -----
        The offline view selects specific channels or display modes from
        `processed_data` as needed, matching live view behavior.
        """
        raw = self.recording_buffer.get()
        time_axis = self.recording_buffer.time_axis(SAMPLE_RATE_HZ)
        processed = apply_mode(raw, self.current_mode) if raw.size else raw
        return time_axis, processed

    # --- Internal: TCP Polling Loop ---------------------------------------

    def _poll_tcp(self) -> None:
        """Polls the non-blocking TCP socket on each QTimer interval.

        Drains pending bytes and buffers all newly reconstructed packets prior to
        checking connection status. Processing buffered data first ensures packets
        received immediately before a connection teardown are preserved. Updates
        connection state afterwards if the server closed the socket.
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
        # Server terminated the connection unexpectedly.
        self._timer.stop()
        self._model = None
        was_connected = self.is_connected
        self.is_connected = False
        self.connection_state_changed.emit(False)
        if was_connected:
            self.status_changed.emit("Error: Connection closed by server.")
        self.offline_data_available.emit(self.recording_buffer.has_data())

    def _refresh_live_view(self) -> None:
        """Recomputes processed data for the active display mode and emits update signals."""
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
