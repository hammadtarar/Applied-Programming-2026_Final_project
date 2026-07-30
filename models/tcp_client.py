"""TCP client model -- adapted from the Exercise 5 solution.

Exercise 5 deliberately avoids a background receive thread and instead uses
a non-blocking socket polled by a QTimer in the ViewModel: "why this exercise
uses a QTimer and non-blocking socket instead of a receive thread" (see the
Exercise 5 README, Part 11). This keeps the client simple: no shared-state
locking, no thread-safe signal emission to worry about, just a socket that
never blocks the GUI.

This class only knows about sockets and bytes -- no Qt, no GUI code. The
ViewModel owns a QTimer that calls `receive_data()` on every tick and then
reads off whatever new packets were reconstructed via `take_new_packets()`.
"""

import socket

import numpy as np

from models.config import NUM_CHANNELS, PACKET_SIZE_BYTES, SAMPLES_PER_PACKET


class TcpClientModel:
    """Connects to the Exercise 5 / course-provided TCP server and
    reconstructs (NUM_CHANNELS, SAMPLES_PER_PACKET) packets from the raw
    byte stream it sends.
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: socket.socket | None = None
        self.is_connected = False

        self._byte_buffer = bytearray()
        self._new_packets: list[np.ndarray] = []

    def connect(self) -> None:
        """Connect to the TCP server.

        Raises whatever `OSError` the underlying socket call raises (e.g.
        connection refused, unknown host) -- the ViewModel catches this and
        turns it into a status message, per the assignment's error-handling
        requirement.
        """
        if self.is_connected:
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

        # Non-blocking: recv() never waits for data, so a QTimer can call
        # receive_data() on every tick without ever freezing the GUI.
        self.socket.setblocking(False)
        self.is_connected = True

    def disconnect(self) -> None:
        """Close the connection, if one is open."""
        self.is_connected = False
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def receive_data(self) -> None:
        """Drain everything currently available on the socket.

        TCP is a byte stream, so one `recv()` call does not necessarily
        contain exactly one packet -- bytes accumulate in `_byte_buffer`
        until a full packet's worth (PACKET_SIZE_BYTES) is available.
        """
        if not self.is_connected or self.socket is None:
            return

        while True:
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    # Peer closed the connection cleanly.
                    self.disconnect()
                    return
                self._byte_buffer.extend(chunk)
            except BlockingIOError:
                # No more data available right now -- try again next tick.
                break
            except OSError:
                # Connection reset/aborted by the peer mid-stream (e.g. the
                # "WinError 10054" you can see on Windows) -- treat exactly
                # like a clean disconnect rather than letting it propagate
                # up as an unhandled exception.
                self.disconnect()
                return

        self._extract_packets_from_buffer()

    def _extract_packets_from_buffer(self) -> None:
        """Convert as many complete byte packets as are buffered into arrays."""
        while len(self._byte_buffer) >= PACKET_SIZE_BYTES:
            packet_bytes = bytes(self._byte_buffer[:PACKET_SIZE_BYTES])
            del self._byte_buffer[:PACKET_SIZE_BYTES]

            array = np.frombuffer(packet_bytes, dtype=np.float64)
            array = array.reshape(NUM_CHANNELS, SAMPLES_PER_PACKET)
            self._new_packets.append(array)

    def take_new_packets(self) -> list:
        """Return and clear the packets reconstructed since the last call."""
        packets, self._new_packets = self._new_packets, []
        return packets
