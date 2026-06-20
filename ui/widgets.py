"""
widgets.py
==========
Widget custom kecil yang jadi signature visual aplikasi:
  - PulseDot: titik indikator yang berdenyut (animasi opacity) saat
    sebuah app punya traffic aktif, redup saat idle. Ini elemen
    pembeda utama dari tabel monitor biasa.
  - Sparkline: grafik mini di dalam baris tabel yang menunjukkan tren
    20 detik terakhir, dirender langsung via QPainter (ringan, tanpa
    overhead pyqtgraph per-row).
"""

from __future__ import annotations

from collections import deque
from typing import Deque

from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QPainterPath
from PyQt6.QtWidgets import QWidget

from ui.theme import COLORS


class PulseDot(QWidget):
    """Titik kecil yang berdenyut (radius & opacity berubah) ketika
    aplikasi terkait sedang aktif mengirim/menerima data.

    Animasi didorong oleh fase global yang di-set dari luar (lihat
    `advance_global_phase` / `set_active`), BUKAN oleh QTimer per
    instance. Ini sengaja dihindari karena membuat puluhan QTimer per
    baris tabel yang sering dibuat-ulang (setCellWidget) rawan memicu
    crash low-level Qt saat widget lama dihapus sebelum timer-nya
    sempat di-stop dengan bersih."""

    _global_phase = 0.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self._active = False

    @classmethod
    def advance_global_phase(cls):
        cls._global_phase = (cls._global_phase + 0.5) % (2 * 3.14159)

    def set_active(self, active: bool):
        if active != self._active:
            self._active = active
            self.update()

    def refresh(self):
        if self._active:
            self.update()

    def paintEvent(self, event):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2

        if self._active:
            pulse = (math.sin(PulseDot._global_phase) + 1) / 2  # 0..1
            glow_r = 4 + pulse * 3
            glow_color = QColor(COLORS["red_signal"])
            glow_color.setAlphaF(0.25 + pulse * 0.25)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(glow_color))
            p.drawEllipse(QRectF(cx - glow_r - 3, cy - glow_r - 3, (glow_r + 3) * 2, (glow_r + 3) * 2))

            core_color = QColor(COLORS["red_glow"])
            p.setBrush(QBrush(core_color))
            p.drawEllipse(QRectF(cx - 3.5, cy - 3.5, 7, 7))
        else:
            dim = QColor(COLORS["text_faint"])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(dim))
            p.drawEllipse(QRectF(cx - 2.5, cy - 2.5, 5, 5))


class Sparkline(QWidget):
    """Mini line-chart ringan untuk menunjukkan tren bandwidth dalam
    satu baris tabel, dirender manual via QPainter (download = merah,
    upload = hijau, ditumpuk semi-transparan)."""

    def __init__(self, parent=None, max_points: int = 30):
        super().__init__(parent)
        self.setMinimumHeight(28)
        self.setMinimumWidth(80)
        self._down: Deque[float] = deque([0.0] * max_points, maxlen=max_points)
        self._up: Deque[float] = deque([0.0] * max_points, maxlen=max_points)

    def push(self, down: float, up: float):
        self._down.append(down)
        self._up.append(up)
        self.update()

    def _build_path(self, values, w, h, vmax):
        path = QPainterPath()
        n = len(values)
        if n < 2 or vmax <= 0:
            path.moveTo(0, h)
            path.lineTo(w, h)
            return path
        step = w / (n - 1)
        path.moveTo(0, h - (values[0] / vmax) * h)
        for i, v in enumerate(values):
            x = i * step
            y = h - (v / vmax) * h
            path.lineTo(x, y)
        return path

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        vmax = max(max(self._down, default=0), max(self._up, default=0), 1.0)

        # garis baseline halus
        p.setPen(QPen(QColor(COLORS["border_soft"]), 1))
        p.drawLine(0, h - 1, w, h - 1)

        down_path = self._build_path(list(self._down), w, h, vmax)
        up_path = self._build_path(list(self._up), w, h, vmax)

        pen_down = QPen(QColor(COLORS["red_signal"]), 1.6)
        pen_down.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen_down)
        p.drawPath(down_path)

        pen_up = QPen(QColor(COLORS["green_up"]), 1.2)
        pen_up.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen_up)
        p.drawPath(up_path)
