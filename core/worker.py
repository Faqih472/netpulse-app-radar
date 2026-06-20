"""
worker.py
=========
QThread worker yang menjalankan sampling tiap 1 detik di background,
lalu mengirim hasilnya ke main thread lewat Qt signal supaya UI tidak
pernah freeze/lag walau jumlah proses banyak.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
import time

from core.net_engine import CrossPlatformSampler, ProcNetSample


class SamplerWorker(QThread):
    sample_ready = pyqtSignal(list)   # List[ProcNetSample]
    error_occurred = pyqtSignal(str)

    def __init__(self, interval_sec: float = 1.0, parent=None):
        super().__init__(parent)
        self._interval = interval_sec
        self._running = False
        self._sampler = CrossPlatformSampler()

    @property
    def is_simulated(self) -> bool:
        return self._sampler.is_simulated

    def run(self):
        self._running = True
        while self._running:
            t0 = time.monotonic()
            try:
                data = self._sampler.sample()
                self.sample_ready.emit(data)
            except Exception as e:
                self.error_occurred.emit(str(e))

            elapsed = time.monotonic() - t0
            sleep_left = max(0.0, self._interval - elapsed)
            # sleep dalam potongan kecil supaya stop() responsif
            slept = 0.0
            step = 0.05
            while self._running and slept < sleep_left:
                self.msleep(int(step * 1000))
                slept += step

    def stop(self):
        self._running = False
        self.wait(2000)
