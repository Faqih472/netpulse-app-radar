"""
main_window.py
==============
Jendela utama. Struktur baru (revisi atas permintaan user):

1. TAB "Semua Aplikasi" — daftar LENGKAP semua aplikasi, dikelompokkan
   per KATEGORI (Browser, Game & Launcher, Chat, dst) dengan header
   kategori yang bisa expand/collapse. Urutan baris di dalam tiap
   kategori STABIL (diurutkan berdasarkan nama, BUKAN berdasarkan
   bandwidth) supaya tidak loncat-loncat posisi tiap detik — angka
   download/upload tetap update live, tapi baris tidak pindah tempat.
   ini memudahkan kamu scanning/mencari aplikasi tertentu karena
   posisinya konsisten.

2. TAB "Top Ranking" — fitur TAMBAHAN terpisah (bukan pengganti list
   utama). Di sini kamu pilih:
     - Metrik: Download tercepat / Upload tercepat / Total terbesar
     - Rentang: 1-10 / 11-20 / 21-30 / dst (dropdown, otomatis
       menyesuaikan jumlah halaman dengan jumlah aplikasi yang
       terdeteksi)
   List di tab ini SECARA SENGAJA boleh berubah urutan (karena memang
   tujuannya ranking live), beda dengan tab "Semua Aplikasi" yang sengaja
   dibuat diam agar mudah dicari.

Detail panel di sisi kanan tetap ada di kedua tab, menampilkan grafik
history penuh untuk aplikasi yang dipilih.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QComboBox,
    QFrame, QAbstractItemView, QGridLayout, QTabWidget, QScrollArea,
    QToolButton, QSizePolicy,
)
import pyqtgraph as pg

from core.net_engine import ProcNetSample, CATEGORY_RULES
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
RANK_PAGE_SIZE = 10             # ukuran tiap halaman ranking (1-10, 11-20, ...)

# Urutan tampilan kategori di UI (kategori yang tidak ada di sini akan
# ditambahkan otomatis di akhir, jadi tetap aman kalau ada kategori baru)
CATEGORY_ORDER = [name for name, _ in CATEGORY_RULES] + ["Lainnya"]

CATEGORY_ICONS = {
    "Browser": "🌐",
    "Game & Launcher": "🎮",
    "Chat & Komunikasi": "💬",
    "Musik & Video Streaming": "🎵",
    "Cloud & Sinkronisasi File": "☁",
    "Update & Background Service": "🔄",
    "Sistem Windows": "🖥",
    "Pengembangan & Produktivitas": "🛠",
    "Lainnya": "📦",
}


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


class CategoryHeader(QFrame):
    """Header baris untuk satu kategori di dalam tabel utama, bisa
    diklik untuk expand/collapse. Dirender sebagai full-width row di
    QTableWidget (lewat setSpan)."""

    def __init__(self, category: str, count: int, on_toggle, parent=None):
        super().__init__(parent)
        self.setObjectName("CategoryHeaderRow")
        self._expanded = True
        self._on_toggle = on_toggle
        self._category = category

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 0, 14, 0)
        h.setSpacing(8)

        self.toggle_btn = QToolButton()
        self.toggle_btn.setText("▾")
        self.toggle_btn.setObjectName("CategoryToggleBtn")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle)

        icon = CATEGORY_ICONS.get(category, "📦")
        self.label = QLabel(f"{icon}  {category}")
        self.label.setObjectName("CategoryHeaderLabel")

        self.count_label = QLabel(f"{count} aplikasi")
        self.count_label.setObjectName("CategoryCountLabel")

        h.addWidget(self.toggle_btn)
        h.addWidget(self.label)
        h.addStretch()
        h.addWidget(self.count_label)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self._toggle()
        super().mousePressEvent(event)

    def _toggle(self):
        self._expanded = not self._expanded
        self.toggle_btn.setText("▾" if self._expanded else "▸")
        self._on_toggle(self._category, self._expanded)

    def set_count(self, count: int):
        self.count_label.setText(f"{count} aplikasi")

    @property
    def expanded(self) -> bool:
        return self._expanded


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NetPulse — Real-Time App Bandwidth Monitor")
        self.resize(1400, 820)
        self.setStyleSheet(QSS)

        self.registry = AppRegistry()
        self.row_widgets: Dict[int, Dict] = {}
        self.search_text = ""
        self.collapsed_categories: set = set()
        self.rank_metric = "download"
        self.rank_page = 0

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

        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        self.tabs.addTab(self._build_all_apps_tab(), "Semua Aplikasi")
        self.tabs.addTab(self._build_ranking_tab(), "🏆 Top Ranking")
        left.addWidget(self.tabs, stretch=1)

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

    # ---------------- TAB 1: SEMUA APLIKASI (statis, per kategori) ----
    def _build_all_apps_tab(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setContentsMargins(0, 12, 0, 0)
        v.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText("Cari aplikasi di semua kategori...")
        self.search_box.textChanged.connect(self._on_search_changed)

        self.category_filter_combo = QComboBox()
        self.category_filter_combo.addItem("Semua kategori")
        for cat in CATEGORY_ORDER:
            self.category_filter_combo.addItem(f"{CATEGORY_ICONS.get(cat, '📦')} {cat}")
        self.category_filter_combo.currentIndexChanged.connect(lambda _: self._refresh_all_apps_table())

        filter_row.addWidget(self.search_box, stretch=2)
        filter_row.addWidget(self.category_filter_combo, stretch=1)
        v.addLayout(filter_row)

        hint = QLabel(
            "Posisi aplikasi di list ini TETAP (tidak loncat-loncat), "
            "dikelompokkan per kategori lalu diurutkan nama — supaya mudah "
            "dicari. Untuk lihat siapa pemakai data terbesar, buka tab 🏆 Top Ranking."
        )
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.table = self._build_table()
        v.addWidget(self.table)

        return tab

    # ---------------- TAB 2: TOP RANKING (dropdown 1-10/11-20/dst) ----
    def _build_ranking_tab(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setContentsMargins(0, 12, 0, 0)
        v.setSpacing(10)

        control_row = QHBoxLayout()
        control_row.setSpacing(10)

        metric_label = QLabel("Urutkan berdasarkan:")
        metric_label.setObjectName("HintLabel")
        self.rank_metric_combo = QComboBox()
        self.rank_metric_combo.addItems([
            "⬇ Download tercepat", "⬆ Upload tercepat", "Σ Total terbesar (sesi ini)",
        ])
        self.rank_metric_combo.currentIndexChanged.connect(self._on_rank_metric_changed)

        range_label = QLabel("Tampilkan rentang:")
        range_label.setObjectName("HintLabel")
        self.rank_range_combo = QComboBox()
        self.rank_range_combo.addItem("1 - 10")
        self.rank_range_combo.currentIndexChanged.connect(self._on_rank_range_changed)

        control_row.addWidget(metric_label)
        control_row.addWidget(self.rank_metric_combo)
        control_row.addSpacing(16)
        control_row.addWidget(range_label)
        control_row.addWidget(self.rank_range_combo)
        control_row.addStretch()
        v.addLayout(control_row)

        hint = QLabel(
            "List ini SENGAJA bisa berubah urutan tiap detik karena memang "
            "fitur ranking live — beda dengan tab Semua Aplikasi yang posisinya diam."
        )
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.rank_table = self._build_table(with_rank_col=True)
        v.addWidget(self.rank_table)

        return tab

    def _build_table(self, with_rank_col: bool = False) -> QTableWidget:
        cols = 8 if with_rank_col else 7
        table = QTableWidget(0, cols)
        if with_rank_col:
            headers = ["#", "", "Aplikasi", "Download", "Upload", "Tren (30s)", "Koneksi", "Total Sesi"]
        else:
            headers = ["", "Aplikasi", "Download", "Upload", "Tren (30s)", "Koneksi", "Total Sesi"]
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.verticalHeader().setDefaultSectionSize(44)

        offset = 1 if with_rank_col else 0
        header = table.horizontalHeader()

        if with_rank_col:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(0, 36)

        header.setSectionResizeMode(COL_PULSE + offset, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_PULSE + offset, 32)
        header.setSectionResizeMode(COL_NAME + offset, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DOWN + offset, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_DOWN + offset, 110)
        header.setSectionResizeMode(COL_UP + offset, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_UP + offset, 110)
        header.setSectionResizeMode(COL_TREND + offset, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_TREND + offset, 110)
        header.setSectionResizeMode(COL_CONN + offset, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_CONN + offset, 80)
        header.setSectionResizeMode(COL_TOTAL + offset, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(COL_TOTAL + offset, 110)

        table.itemSelectionChanged.connect(lambda t=table: self._on_row_selected(t))
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

    # ------------------------------------------------------------------
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
        self.worker.mode_ready.connect(self._on_mode_ready)
        self.worker.start()

    def _on_mode_ready(self, mode: str, warning: str):
        if mode == "packet_capture":
            self.footer_mode_label.setText("Sumber data: packet capture (Npcap) — akurat byte-level")
        elif mode == "fallback":
            self.footer_mode_label.setText(
                f"⚠ Mode fallback (Npcap tidak terdeteksi) — angka kurang akurat untuk download besar. {warning}"
            )
        elif mode == "simulated":
            self.footer_mode_label.setText(
                "⚠ Mode simulasi (bukan Windows) — data demo untuk preview UI"
            )

    # ------------------------------------------------------------------
    def _on_search_changed(self, text: str):
        self.search_text = text.lower().strip()
        self._refresh_all_apps_table()

    def _on_rank_metric_changed(self, idx: int):
        self.rank_metric = {0: "download", 1: "upload", 2: "total"}.get(idx, "download")
        self._refresh_ranking_table()

    def _on_rank_range_changed(self, idx: int):
        self.rank_page = max(0, idx)
        self._refresh_ranking_table()

    def _on_worker_error(self, msg: str):
        self.footer_label.setText(f"Error sampling: {msg}")

    def _on_row_selected(self, table: QTableWidget):
        rows = table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        name_col = COL_NAME + (1 if table.columnCount() == 8 else 0)
        pid_item = table.item(row, name_col)
        if pid_item is None:
            return
        pid = pid_item.data(Qt.ItemDataRole.UserRole)
        if pid is None:
            return  # baris header kategori
        states = {s.pid: s for s in self.registry.get_all()}
        if pid in states:
            self.detail_panel.show_app(states[pid])
            self.detail_panel.setVisible(True)

    # ------------------------------------------------------------------
    def _on_sample_ready(self, samples: List[ProcNetSample]):
        states = self.registry.update(samples)
        self._update_summary(states)
        self._refresh_all_apps_table(states)
        self._refresh_ranking_table(states)
        self._update_range_dropdown(states)
        self.footer_label.setText("Update terakhir: baru saja • interval 1 detik")

        if self.detail_panel.isVisible():
            current = next((s for s in states if s.pid == self.detail_panel._current_pid), None)
            if current:
                self.detail_panel.show_app(current)

    def _update_summary(self, states: List[AppState]):
        total_down = sum(s.current_down for s in states)
        total_up = sum(s.current_up for s in states)
        active_count = sum(1 for s in states if s.current_down + s.current_up > ACTIVITY_THRESHOLD_BPS)
        session_total = sum(s.session_total_down + s.session_total_up for s in states)

        self.card_total_down.set_value(format_speed(total_down))
        self.card_total_up.set_value(format_speed(total_up))
        self.card_apps_active.set_value(str(active_count))
        self.card_session_total.set_value(format_bytes(session_total))

    def _update_range_dropdown(self, states: List[AppState]):
        """Sesuaikan jumlah opsi dropdown rentang (1-10, 11-20, ...)
        dengan jumlah aplikasi yang terdeteksi saat ini."""
        n = len(states)
        n_pages = max(1, (n + RANK_PAGE_SIZE - 1) // RANK_PAGE_SIZE)
        current_n = self.rank_range_combo.count()
        if current_n == n_pages:
            return
        current_idx = self.rank_range_combo.currentIndex()
        self.rank_range_combo.blockSignals(True)
        self.rank_range_combo.clear()
        for i in range(n_pages):
            start = i * RANK_PAGE_SIZE + 1
            end = min((i + 1) * RANK_PAGE_SIZE, n)
            self.rank_range_combo.addItem(f"{start} - {end}")
        new_idx = min(current_idx, n_pages - 1) if current_idx >= 0 else 0
        self.rank_range_combo.setCurrentIndex(new_idx)
        self.rank_range_combo.blockSignals(False)
        self.rank_page = new_idx

    # ---------------- TAB 1 rendering: per kategori, STATIS ----------
    def _filtered_states_for_all_tab(self, states: Optional[List[AppState]] = None) -> List[AppState]:
        if states is None:
            states = self.registry.get_all()

        if self.search_text:
            states = [s for s in states if self.search_text in s.name.lower()]

        cat_idx = self.category_filter_combo.currentIndex()
        if cat_idx > 0:
            selected_category = CATEGORY_ORDER[cat_idx - 1]
            states = [s for s in states if s.category == selected_category]

        return states

    def _refresh_all_apps_table(self, states: Optional[List[AppState]] = None):
        states = self._filtered_states_for_all_tab(states)

        by_category: Dict[str, List[AppState]] = defaultdict(list)
        for s in states:
            by_category[s.category].append(s)

        ordered_categories = [c for c in CATEGORY_ORDER if c in by_category]
        for c in by_category:
            if c not in ordered_categories:
                ordered_categories.append(c)

        # PENTING: dalam tiap kategori, urutkan berdasarkan NAMA (stabil),
        # BUKAN berdasarkan bandwidth -- ini yang membuat list tidak
        # loncat-loncat posisi tiap detik.
        for c in ordered_categories:
            by_category[c].sort(key=lambda s: s.name.lower())

        selected_pid = self.detail_panel._current_pid if self.detail_panel.isVisible() else None

        total_rows = sum(len(by_category[c]) + 1 for c in ordered_categories)
        self.table.setRowCount(0)
        self.table.setRowCount(total_rows)

        new_select_row = -1
        new_row_widgets: Dict[int, Dict] = {}
        row = 0

        for category in ordered_categories:
            apps = by_category[category]
            is_collapsed = category in self.collapsed_categories

            header_widget = CategoryHeader(category, len(apps), self._on_category_toggle)
            if is_collapsed:
                header_widget.toggle_btn.setText("▸")
                header_widget._expanded = False
            self.table.setCellWidget(row, 0, header_widget)
            self.table.setSpan(row, 0, 1, self.table.columnCount())
            self.table.setRowHeight(row, 38)
            row += 1

            if is_collapsed:
                for s in apps:
                    self.table.setRowHidden(row, True)
                    row += 1
                continue

            for state in apps:
                self._populate_row(self.table, row, state, new_row_widgets)
                if selected_pid == state.pid:
                    new_select_row = row
                row += 1

        if new_select_row >= 0:
            self.table.selectRow(new_select_row)

        self._merge_row_widgets(new_row_widgets)

    def _on_category_toggle(self, category: str, expanded: bool):
        if expanded:
            self.collapsed_categories.discard(category)
        else:
            self.collapsed_categories.add(category)
        self._refresh_all_apps_table()

    # ---------------- TAB 2 rendering: ranking, dinamis ---------------
    def _refresh_ranking_table(self, states: Optional[List[AppState]] = None):
        if states is None:
            states = self.registry.get_all()

        if self.rank_metric == "download":
            states = sorted(states, key=lambda s: s.current_down, reverse=True)
        elif self.rank_metric == "upload":
            states = sorted(states, key=lambda s: s.current_up, reverse=True)
        else:
            states = sorted(states, key=lambda s: s.session_total_down + s.session_total_up, reverse=True)

        start = self.rank_page * RANK_PAGE_SIZE
        end = start + RANK_PAGE_SIZE
        page_states = states[start:end]

        selected_pid = self.detail_panel._current_pid if self.detail_panel.isVisible() else None

        self.rank_table.setRowCount(len(page_states))
        new_select_row = -1
        new_row_widgets: Dict[int, Dict] = {}

        for i, state in enumerate(page_states):
            rank_item = QTableWidgetItem(str(start + i + 1))
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            rank_item.setForeground(QColor(COLORS["text_muted"]))
            self.rank_table.setItem(i, 0, rank_item)

            self._populate_row(self.rank_table, i, state, new_row_widgets, col_offset=1)
            if selected_pid == state.pid:
                new_select_row = i

        if new_select_row >= 0:
            self.rank_table.selectRow(new_select_row)

        self._merge_row_widgets(new_row_widgets)

    def _merge_row_widgets(self, new_entries: Dict[int, Dict]):
        for pid, entry in new_entries.items():
            self.row_widgets.setdefault(pid, {}).update(entry)
        # buang entri lama yang sudah tidak relevan sama sekali (pid
        # tidak ada lagi di entries baru manapun) -- dibersihkan saat
        # registry sample berikutnya berjalan; cukup batasi ukuran dict
        # agar tidak tumbuh tanpa batas pada sesi yang sangat lama.
        if len(self.row_widgets) > 500:
            self.row_widgets = dict(new_entries)

    # ---------------- shared row population ---------------------------
    def _populate_row(self, table: QTableWidget, row: int, state: AppState,
                       widget_store: Dict[int, Dict], col_offset: int = 0):
        is_active = (state.current_down + state.current_up) > ACTIVITY_THRESHOLD_BPS

        pulse = PulseDot()
        pulse.set_active(is_active)
        table.setCellWidget(row, COL_PULSE + col_offset, self._center_wrap(pulse))
        widget_store.setdefault(state.pid, {})["pulse"] = pulse

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
        table.setItem(row, COL_NAME + col_offset, name_item)

        down_item = QTableWidgetItem(format_speed(state.current_down))
        down_item.setForeground(QColor(COLORS["red_glow"] if state.current_down > ACTIVITY_THRESHOLD_BPS else COLORS["text_secondary"]))
        down_item.setFont(self._mono_font())
        table.setItem(row, COL_DOWN + col_offset, down_item)

        up_item = QTableWidgetItem(format_speed(state.current_up))
        up_item.setForeground(QColor(COLORS["green_up"] if state.current_up > ACTIVITY_THRESHOLD_BPS else COLORS["text_secondary"]))
        up_item.setFont(self._mono_font())
        table.setItem(row, COL_UP + col_offset, up_item)

        spark = Sparkline()
        for d, u in zip(list(state.download_history)[-30:], list(state.upload_history)[-30:]):
            spark.push(d, u)
        table.setCellWidget(row, COL_TREND + col_offset, spark)
        widget_store.setdefault(state.pid, {})["spark"] = spark

        conn_item = QTableWidgetItem(str(state.connections))
        conn_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        conn_item.setForeground(QColor(COLORS["text_muted"]))
        table.setItem(row, COL_CONN + col_offset, conn_item)

        total_item = QTableWidgetItem(format_bytes(state.session_total_down + state.session_total_up))
        total_item.setForeground(QColor(COLORS["text_secondary"]))
        total_item.setFont(self._mono_font())
        table.setItem(row, COL_TOTAL + col_offset, total_item)

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

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        if hasattr(self, "worker"):
            self.worker.stop()
        event.accept()
