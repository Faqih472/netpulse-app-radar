"""
main_window.py
==============
Jendela utama: top bar, summary cards (total down/up real-time),
search + filter, tabel daftar aplikasi (live, sorted by usage), dan
panel detail di sisi kanan dengan grafik history penuh.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QComboBox,
    QSplitter, QFrame, QAbstractItemView, QSizePolicy, QGridLayout,
)
import pyqtgraph as pg

from core.net_engine import ProcNetSample
from core.app_model import AppRegistry, AppState
from core.worker import SamplerWorker
from core.formatters import format_speed, format_bytes, short_path
from ui.theme import QSS, COLORS
from ui.widgets import PulseDot, Sparkline

COL_PULSE = 0
COL_NAME = 1
COL_DOWN = 2
COL_UP = 3
COL_TREND = 4
COL_CONN = 5
COL_TOTAL = 6

ACTIVITY_THRESHOLD_BPS = 2048  # > 2KB/s dianggap "aktif" utk pulse dot


def app_kind_badge(state: AppState) -> Optional[str]:
    """Heuristik sederhana memberi label 'Unknown' utk app tanpa exe path
    jelas / berada di folder mencurigakan -- bantu user curiga app aneh."""
    path = (state.exe_path or "").lower()
    if not path:
        return "?"
    suspicious_markers = ["temp\\", "appdata\\local\\temp", "unknown"]
    if any(m in path for m in suspicious_markers):
        return "?"
    return None


class SummaryCard(QFrame):
    def __init__(self, label: str, value_object_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SummaryCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        self.label = QLabel(label)
        self.label.setObjectName("SummaryLabel")
        self.value = QLabel("0 B/s")
        self.value.setObjectName(value_object_name)

        layout.addWidget(self.label)
        layout.addWidget(self.value)

    def set_value(self, text: str):
        self.value.setText(text)


class DetailPanel(QFrame):
    """Panel kanan: detail aplikasi yang dipilih + grafik history penuh."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DetailPanel")
        self.setMinimumWidth(320)
        self._current_pid: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(2)
        self.name_label = QLabel("Pilih aplikasi")
        self.name_label.setObjectName("DetailAppName")
        self.path_label = QLabel("Klik salah satu baris di tabel kiri")
        self.path_label.setObjectName("DetailAppPath")
        self.path_label.setWordWrap(True)
        header.addWidget(self.name_label)
        header.addWidget(self.path_label)
        layout.addLayout(header)

        # Stat chips
        chips_grid = QGridLayout()
        chips_grid.setSpacing(8)
        self.chip_down = self._make_chip("DOWNLOAD SAAT INI")
        self.chip_up = self._make_chip("UPLOAD SAAT INI")
        self.chip_peak = self._make_chip("PEAK DOWNLOAD")
        self.chip_total = self._make_chip("TOTAL SESI INI")
        chips_grid.addWidget(self.chip_down[0], 0, 0)
        chips_grid.addWidget(self.chip_up[0], 0, 1)
        chips_grid.addWidget(self.chip_peak[0], 1, 0)
        chips_grid.addWidget(self.chip_total[0], 1, 1)
        layout.addLayout(chips_grid)

        # Grafik history
        graph_label = QLabel("RIWAYAT 2 MENIT TERAKHIR")
        graph_label.setObjectName("SummaryLabel")
        layout.addWidget(graph_label)

        self.plot = pg.PlotWidget()
        self.plot.setBackground(COLORS["bg_panel"])
        self.plot.showGrid(x=False, y=True, alpha=0.08)
        self.plot.getAxis("left").setTextPen(QColor(COLORS["text_muted"]))
        self.plot.getAxis("bottom").setTextPen(QColor(COLORS["text_muted"]))
        self.plot.getAxis("bottom").setStyle(showValues=False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        self.plot.setMinimumHeight(220)

        self.curve_down = self.plot.plot(pen=pg.mkPen(QColor(COLORS["red_signal"]), width=2))
        self.curve_up = self.plot.plot(pen=pg.mkPen(QColor(COLORS["green_up"]), width=2))
        layout.addWidget(self.plot)

        legend_row = QHBoxLayout()
        legend_row.addWidget(self._legend_dot(COLORS["red_signal"], "Download"))
        legend_row.addWidget(self._legend_dot(COLORS["green_up"], "Upload"))
        legend_row.addStretch()
        layout.addLayout(legend_row)

        # Info koneksi
        conn_label = QLabel("KONEKSI AKTIF")
        conn_label.setObjectName("SummaryLabel")
        layout.addWidget(conn_label)
        self.conn_info = QLabel("-")
        self.conn_info.setObjectName("DetailAppPath")
        self.conn_info.setWordWrap(True)
        layout.addWidget(self.conn_info)

        layout.addStretch()

    def _make_chip(self, label_text: str):
        chip = QFrame()
        chip.setObjectName("StatChip")
        v = QVBoxLayout(chip)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(2)
        lbl = QLabel(label_text)
        lbl.setObjectName("StatChipLabel")
        val = QLabel("-")
        val.setObjectName("StatChipValue")
        v.addWidget(lbl)
        v.addWidget(val)
        return chip, val

    def _legend_dot(self, color: str, text: str) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 11px;")
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        h.addWidget(dot)
        h.addWidget(lbl)
        return w

    def show_app(self, state: AppState):
        self._current_pid = state.pid
        self.name_label.setText(state.name)
        self.path_label.setText(short_path(state.exe_path, 70))
        self.chip_down[1].setText(format_speed(state.current_down))
        self.chip_up[1].setText(format_speed(state.current_up))
        self.chip_peak[1].setText(format_speed(state.peak_down))
        self.chip_total[1].setText(format_bytes(state.session_total_down + state.session_total_up))

        xs = list(range(len(state.download_history)))
        self.curve_down.setData(xs, list(state.download_history))
        self.curve_up.setData(xs, list(state.upload_history))

        if state.remote_hosts:
            self.conn_info.setText(
                f"{state.connections} koneksi aktif → " + ", ".join(state.remote_hosts[:5])
            )
        else:
            self.conn_info.setText(f"{state.connections} koneksi aktif")

    def refresh_if_current(self, state: AppState):
        if self._current_pid == state.pid:
            self.show_app(state)

    def clear(self):
        self._current_pid = None
        self.name_label.setText("Pilih aplikasi")
        self.path_label.setText("Klik salah satu baris di tabel kiri")
        for chip in (self.chip_down, self.chip_up, self.chip_peak, self.chip_total):
            chip[1].setText("-")
        self.curve_down.setData([], [])
        self.curve_up.setData([], [])
        self.conn_info.setText("-")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NetPulse — Real-Time App Bandwidth Monitor")
        self.resize(1320, 780)
        self.setStyleSheet(QSS)

        self.registry = AppRegistry()
        self.row_widgets: Dict[int, Dict] = {}  # pid -> {pulse, sparkline, name_item, ...}
        self.row_index: Dict[int, int] = {}     # pid -> current row number
        self.sort_mode = "download"
        self.search_text = ""

        self._build_ui()
        self._start_worker()
        self._start_pulse_animation()

    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_topbar())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 0)
        body_layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(14)
        left.addLayout(self._build_summary_row())
        left.addLayout(self._build_filter_row())
        left.addWidget(self._build_table())

        left_widget = QWidget()
        left_widget.setLayout(left)

        self.detail_panel = DetailPanel()
        self.detail_panel.setVisible(False)

        body_layout.addWidget(left_widget, stretch=3)
        body_layout.addWidget(self.detail_panel, stretch=1)

        root.addWidget(body, stretch=1)
        root.addWidget(self._build_footer())

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(64)
        h = QHBoxLayout(bar)
        h.setContentsMargins(24, 0, 24, 0)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("NetPulse")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Real-Time Per-App Bandwidth Monitor")
        subtitle.setObjectName("AppSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.live_badge = QLabel("● LIVE")
        self.live_badge.setObjectName("LiveBadge")

        h.addLayout(title_box)
        h.addStretch()
        h.addWidget(self.live_badge)
        return bar

    def _build_summary_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        self.card_total_down = SummaryCard("TOTAL DOWNLOAD / DETIK", "SummaryValueDown")
        self.card_total_up = SummaryCard("TOTAL UPLOAD / DETIK", "SummaryValueUp")
        self.card_apps_active = SummaryCard("APLIKASI AKTIF", "SummaryValue")
        self.card_session_total = SummaryCard("TOTAL TERPAKAI SESI INI", "SummaryValue")
        for c in (self.card_total_down, self.card_total_up, self.card_apps_active, self.card_session_total):
            row.addWidget(c)
        return row

    def _build_filter_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText("Cari aplikasi...")
        self.search_box.textChanged.connect(self._on_search_changed)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Sortir: Download tercepat",
            "Sortir: Upload tercepat",
            "Sortir: Total terbesar",
            "Sortir: Nama A-Z",
        ])
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "Semua aplikasi",
            "Hanya yang aktif sekarang",
            "Tandai mencurigakan",
        ])
        self.filter_combo.currentIndexChanged.connect(lambda _: self._refresh_table())

        row.addWidget(self.search_box, stretch=2)
        row.addWidget(self.sort_combo, stretch=1)
        row.addWidget(self.filter_combo, stretch=1)
        return row

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, 7)
        table.setObjectName("AppTable")
        table.setHorizontalHeaderLabels([
            "", "Aplikasi", "Download", "Upload", "Tren (30s)", "Koneksi", "Total Sesi"
        ])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.verticalHeader().setDefaultSectionSize(44)

        header = table.horizontalHeader()
        header.setSectionResizeMode(COL_PULSE, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_PULSE, 32)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DOWN, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_DOWN, 110)
        header.setSectionResizeMode(COL_UP, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_UP, 110)
        header.setSectionResizeMode(COL_TREND, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_TREND, 110)
        header.setSectionResizeMode(COL_CONN, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_CONN, 80)
        header.setSectionResizeMode(COL_TOTAL, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_TOTAL, 110)

        table.itemSelectionChanged.connect(self._on_row_selected)
        self.table = table
        return table

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setObjectName("StatusFooter")
        footer.setFixedHeight(28)
        h = QHBoxLayout(footer)
        h.setContentsMargins(20, 0, 20, 0)
        self.footer_label = QLabel("Menyiapkan engine monitoring...")
        h.addWidget(self.footer_label)
        h.addStretch()
        self.footer_mode_label = QLabel("")
        h.addWidget(self.footer_mode_label)
        return footer

    def _start_pulse_animation(self):
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._tick_pulse_animation)
        self._pulse_timer.start(80)

    def _tick_pulse_animation(self):
        PulseDot.advance_global_phase()
        for entry in self.row_widgets.values():
            dot = entry.get("pulse")
            if dot is not None:
                dot.refresh()

    # ------------------------------------------------------------------
    def _start_worker(self):
        self.worker = SamplerWorker(interval_sec=1.0)
        self.worker.sample_ready.connect(self._on_sample_ready)
        self.worker.error_occurred.connect(self._on_worker_error)
        self.worker.start()

        if self.worker.is_simulated:
            self.footer_mode_label.setText(
                "⚠ Mode simulasi (bukan Windows) — data demo untuk preview UI"
            )
        else:
            self.footer_mode_label.setText("Sumber data: psutil (io_counters + koneksi aktif)")

    # ------------------------------------------------------------------
    def _on_search_changed(self, text: str):
        self.search_text = text.lower().strip()
        self._refresh_table()

    def _on_sort_changed(self, _idx: int):
        mapping = {0: "download", 1: "upload", 2: "total", 3: "name"}
        self.sort_mode = mapping.get(self.sort_combo.currentIndex(), "download")
        self._refresh_table()

    def _on_worker_error(self, msg: str):
        self.footer_label.setText(f"Error sampling: {msg}")

    def _on_row_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.detail_panel.setVisible(False)
            return
        row = rows[0].row()
        pid_item = self.table.item(row, COL_NAME)
        if pid_item is None:
            return
        pid = pid_item.data(Qt.ItemDataRole.UserRole)
        states = {s.pid: s for s in self.registry.get_all()}
        if pid in states:
            self.detail_panel.show_app(states[pid])
            self.detail_panel.setVisible(True)

    # ------------------------------------------------------------------
    def _on_sample_ready(self, samples: List[ProcNetSample]):
        states = self.registry.update(samples)
        self._update_summary(states)
        self._refresh_table(states)
        self._pulse_live_badge()

    def _update_summary(self, states: List[AppState]):
        total_down = sum(s.current_down for s in states)
        total_up = sum(s.current_up for s in states)
        active_count = sum(1 for s in states if s.current_down + s.current_up > ACTIVITY_THRESHOLD_BPS)
        session_total = sum(s.session_total_down + s.session_total_up for s in states)

        self.card_total_down.set_value(format_speed(total_down))
        self.card_total_up.set_value(format_speed(total_up))
        self.card_apps_active.set_value(str(active_count))
        self.card_session_total.set_value(format_bytes(session_total))

    def _filtered_sorted_states(self, states: Optional[List[AppState]] = None) -> List[AppState]:
        if states is None:
            states = self.registry.get_all()

        if self.search_text:
            states = [s for s in states if self.search_text in s.name.lower()]

        filter_idx = self.filter_combo.currentIndex()
        if filter_idx == 1:  # hanya aktif sekarang
            states = [s for s in states if s.current_down + s.current_up > ACTIVITY_THRESHOLD_BPS]
        elif filter_idx == 2:  # mencurigakan
            states = [s for s in states if app_kind_badge(s) == "?"]

        if self.sort_mode == "download":
            states.sort(key=lambda s: s.current_down, reverse=True)
        elif self.sort_mode == "upload":
            states.sort(key=lambda s: s.current_up, reverse=True)
        elif self.sort_mode == "total":
            states.sort(key=lambda s: s.session_total_down + s.session_total_up, reverse=True)
        else:
            states.sort(key=lambda s: s.name.lower())

        return states

    def _refresh_table(self, states: Optional[List[AppState]] = None):
        states = self._filtered_sorted_states(states)

        selected_pid = None
        if self.detail_panel.isVisible() and self.detail_panel._current_pid is not None:
            selected_pid = self.detail_panel._current_pid

        # PENTING: row_widgets di sini menyimpan widget HIDUP yang sedang
        # ter-attach ke table di posisi row tertentu pada tick SEBELUMNYA.
        # Karena urutan baris berubah tiap tick (sorting by usage),
        # PID yang sama bisa pindah row. Untuk menghindari
        # "wrapped C/C++ object has been deleted" (Qt menghapus widget
        # lama saat setCellWidget dipanggil ulang di posisi yang sudah
        # terisi widget berbeda), kita SELALU buat widget baru per
        # render dan biarkan widget lama didelete otomatis oleh Qt --
        # TANPA menyimpan referensi Python jangka panjang ke widget
        # yang sudah dilepas dari table. State logis (history bandwidth)
        # tetap disimpan terpisah di AppState (core/app_model.py), jadi
        # tidak ada data yang hilang walau widget visualnya dibuat ulang.
        self.table.setRowCount(0)
        self.table.setRowCount(len(states))

        new_select_row = -1
        active_pids = set()
        new_row_widgets: Dict[int, Dict] = {}

        for row, state in enumerate(states):
            active_pids.add(state.pid)
            is_active = (state.current_down + state.current_up) > ACTIVITY_THRESHOLD_BPS

            # --- kolom pulse dot (widget baru tiap render, ringan) ---
            pulse = PulseDot()
            pulse.set_active(is_active)
            self.table.setCellWidget(row, COL_PULSE, self._center_wrap(pulse))
            new_row_widgets.setdefault(state.pid, {})["pulse"] = pulse

            # --- kolom nama ---
            badge = app_kind_badge(state)
            display_name = state.name
            if badge:
                display_name = f"{state.name}  ⚠"
            name_item = QTableWidgetItem(display_name)
            name_item.setData(Qt.ItemDataRole.UserRole, state.pid)
            if badge:
                name_item.setForeground(QColor(COLORS["amber_warn"]))
            font = QFont()
            font.setWeight(QFont.Weight.Medium)
            name_item.setFont(font)
            self.table.setItem(row, COL_NAME, name_item)

            # --- kolom download / upload ---
            down_item = QTableWidgetItem(format_speed(state.current_down))
            down_item.setForeground(QColor(COLORS["red_glow"] if state.current_down > ACTIVITY_THRESHOLD_BPS else COLORS["text_secondary"]))
            down_item.setFont(self._mono_font())
            self.table.setItem(row, COL_DOWN, down_item)

            up_item = QTableWidgetItem(format_speed(state.current_up))
            up_item.setForeground(QColor(COLORS["green_up"] if state.current_up > ACTIVITY_THRESHOLD_BPS else COLORS["text_secondary"]))
            up_item.setFont(self._mono_font())
            self.table.setItem(row, COL_UP, up_item)

            # --- kolom sparkline (widget baru tiap render) ---
            spark = Sparkline()
            # isi history sekaligus dari AppState supaya tidak mulai dari 0 tiap render
            for d, u in zip(list(state.download_history)[-30:], list(state.upload_history)[-30:]):
                spark.push(d, u)
            self.table.setCellWidget(row, COL_TREND, spark)
            new_row_widgets.setdefault(state.pid, {})["spark"] = spark

            # --- kolom koneksi ---
            conn_item = QTableWidgetItem(str(state.connections))
            conn_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            conn_item.setForeground(QColor(COLORS["text_muted"]))
            self.table.setItem(row, COL_CONN, conn_item)

            # --- kolom total sesi ---
            total_item = QTableWidgetItem(format_bytes(state.session_total_down + state.session_total_up))
            total_item.setForeground(QColor(COLORS["text_secondary"]))
            total_item.setFont(self._mono_font())
            self.table.setItem(row, COL_TOTAL, total_item)

            if selected_pid == state.pid:
                new_select_row = row

            if self.detail_panel.isVisible():
                self.detail_panel.refresh_if_current(state)

        if new_select_row >= 0:
            self.table.selectRow(new_select_row)

        self.row_widgets = new_row_widgets

    def _center_wrap(self, widget: QWidget) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(widget)
        return wrapper

    def _mono_font(self) -> QFont:
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        return f

    def _pulse_live_badge(self):
        self.footer_label.setText("Update terakhir: baru saja • interval 1 detik")

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        if hasattr(self, "worker"):
            self.worker.stop()
        event.accept()
