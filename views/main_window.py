import numpy as np
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from models.config import DEFAULT_HOST, DEFAULT_PORT
from models.signal_processing import SignalMode
from viewmodels.main_viewmodel import MainViewModel
from views.live_plot_widget import LivePlotWidget
from views.offline_plot_widget import OfflinePlotWidget


class MainWindow(QMainWindow):
    def __init__(self, view_model: MainViewModel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TCP Signal Visualization")
        self.resize(1000, 700)
        self._vm = view_model

        self._build_ui()
        self._connect_view_model()

    # --- UI Construction ---------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        root_layout.addWidget(self._build_connection_group())
        root_layout.addWidget(self._build_display_group())

        self._tabs = QTabWidget()
        self._live_widget = LivePlotWidget()
        self._offline_widget = OfflinePlotWidget()
        self._tabs.addTab(self._live_widget, "Live")
        self._tabs.addTab(self._offline_widget, "Offline")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        root_layout.addWidget(self._tabs, stretch=1)

        self._status_label = QLabel("Not connected.")
        root_layout.addWidget(self._status_label)

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox("Connection")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Host:"))
        self._host_edit = QLineEdit(DEFAULT_HOST)
        self._host_edit.setFixedWidth(120)
        layout.addWidget(self._host_edit)

        layout.addWidget(QLabel("Port:"))
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(DEFAULT_PORT)
        layout.addWidget(self._port_spin)

        self._connect_button = QPushButton("Connect")
        self._connect_button.clicked.connect(self._on_connect_clicked)
        layout.addWidget(self._connect_button)

        self._disconnect_button = QPushButton("Disconnect")
        self._disconnect_button.setEnabled(False)
        self._disconnect_button.clicked.connect(self._vm.disconnect_requested)
        layout.addWidget(self._disconnect_button)

        layout.addStretch(1)
        return group

    def _build_display_group(self) -> QGroupBox:
        group = QGroupBox("Display")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Channel:"))
        self._channel_spin = QSpinBox()
        self._channel_spin.setRange(0, 31)
        self._channel_spin.valueChanged.connect(self._vm.channel_changed)
        layout.addWidget(self._channel_spin)

        layout.addWidget(QLabel("Signal mode:"))
        self._mode_combo = QComboBox()
        for mode in SignalMode:
            self._mode_combo.addItem(mode.value)
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        layout.addWidget(self._mode_combo)

        self._all_channels_button = QPushButton("Plot All Channels")
        self._all_channels_button.setCheckable(True)
        self._all_channels_button.toggled.connect(self._on_all_channels_toggled)
        layout.addWidget(self._all_channels_button)

        layout.addStretch(1)
        return group

    # --- ViewModel <-> View Bindings ---------------------------------------

    def _connect_view_model(self) -> None:
        self._vm.status_changed.connect(self._status_label.setText)
        self._vm.connection_state_changed.connect(self._on_connection_state_changed)
        self._vm.live_view_updated.connect(self._on_live_view_updated)
        self._vm.offline_data_available.connect(self._on_offline_data_available)

    # --- User Action Handlers ---------------------------------------------

    def _on_connect_clicked(self) -> None:
        host = self._host_edit.text().strip() or DEFAULT_HOST
        self._vm.connect_requested(host, self._port_spin.value())

    def _on_mode_changed(self, mode_text: str) -> None:
        self._vm.mode_changed(mode_text)
        self._refresh_offline_if_visible()

    def _on_all_channels_toggled(self, checked: bool) -> None:
        self._channel_spin.setEnabled(not checked)
        self._vm.show_all_channels_changed(checked)

    def _on_tab_changed(self, index: int) -> None:
        if self._tabs.widget(index) is self._offline_widget:
            self._refresh_offline_if_visible()

    # --- ViewModel Signal Handlers ----------------------------------------

    def _on_connection_state_changed(self, connected: bool) -> None:
        self._connect_button.setEnabled(not connected)
        self._disconnect_button.setEnabled(connected)
        self._host_edit.setEnabled(not connected)
        self._port_spin.setEnabled(not connected)

    def _on_live_view_updated(self, time_axis: np.ndarray, data: np.ndarray) -> None:
        if data.ndim == 1:
            self._live_widget.update_single_channel(time_axis, data)
        else:
            self._live_widget.update_all_channels(time_axis, data)

    def _on_offline_data_available(self, available: bool) -> None:
        if available:
            self._refresh_offline_if_visible(force=True)
        else:
            self._offline_widget.clear()

    def _refresh_offline_if_visible(self, force: bool = False) -> None:
        if not (force or self._tabs.currentWidget() is self._offline_widget):
            return
        time_axis, data = self._vm.get_offline_data()
        self._offline_widget.plot(time_axis, data, self._channel_spin.value(), self._mode_combo.currentText())

    # --- Resource Cleanup -------------------------------------------------

    def closeEvent(self, event) -> None:
        """Cleanly close the socket if the window is closed while still connected."""
        if self._vm.is_connected:
            self._vm.disconnect_requested()
        super().closeEvent(event)
