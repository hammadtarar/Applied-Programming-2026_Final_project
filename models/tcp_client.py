"""Non-blocking TCP client for streaming EMG data.

Adapted from the Exercise 5 server setup. Designed for polling via a UI timer
(e.g., QTimer) rather than a background receive thread. This single-threaded approach
avoids complex multi-threading primitives like mutexes and thread-safe signals while
keeping the GUI responsive.

This class manages socket state and byte parsing exclusively—it has no direct
dependency on Qt. The ViewModel handles the polling timer, periodically calling
`receive_data()` and retrieving parsed packets via `take_new_packets()`.
"""

import socket

import numpy as np

from models.config import NUM_CHANNELS, PACKET_SIZE_BYTES, SAMPLES_PER_PACKET


class TcpClientModel:
    """Connects to the TCP server and reconstructs raw byte streams into (NUM_CHANNELS, SAMPLES_PER_PACKET) data packets."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: socket.socket | None = None
        self.is_connected = False

        self._byte_buffer = bytearray()
        self._new_packets: list[np.ndarray] = []

    def connect(self) -> None:
        """Connects to the TCP server.

        Raises
        ------
        OSError
            If the underlying socket connection fails (e.g., connection refused,
            host unreachable). Caught by the ViewModel to display UI status messages.
        """
        if self.is_connected:
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

        # Non-blocking socket: recv() returns immediately if no data is available,
        # allowing the QTimer to poll receive_data() without blocking the GUI thread.
        self.socket.setblocking(False)
        self.is_connected = True

    def disconnect(self) -> None:
        """Close the connection, if one is open."""
        self.is_connected = False
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def receive_data(self) -> None:
        """Drains all incoming data currently available on the non-blocking socket.

        Appends raw bytes to an internal buffer (`_byte_buffer`) since TCP data arrives
        as an unstructured stream. Complete packets of size `PACKET_SIZE_BYTES` are
        parsed out incrementally as enough bytes accumulate.
        """
        if not self.is_connected or self.socket is None:
            return

        while True:
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    # Connection closed gracefully by the remote peer.
                    self.disconnect()
                    return
                self._byte_buffer.extend(chunk)
            except BlockingIOError:
                # No data available on the non-blocking socket right now; retry on the next timer tick.
                break
            except OSError:
                # Connection reset by peer mid-stream (e.g., WinError 10054 on Windows).
                # Treat as a graceful disconnect rather than letting an exception propagate.
                self.disconnect()
                return

        self._extract_packets_from_buffer()

    def _extract_packets_from_buffer(self) -> None:
        """Parses all complete byte packets in the buffer into structured arrays."""
        while len(self._byte_buffer) >= PACKET_SIZE_BYTES:
            packet_bytes = bytes(self._byte_buffer[:PACKET_SIZE_BYTES])
            del self._byte_buffer[:PACKET_SIZE_BYTES]

            array = np.frombuffer(packet_bytes, dtype=np.float64)
            array = array.reshape(NUM_CHANNELS, SAMPLES_PER_PACKET)
            self._new_packets.append(array)

    def take_new_packets(self) -> list:
        """Drains and returns all packets reconstructed since the last call."""
        packets, self._new_packets = self._new_packets, []
        return packets
