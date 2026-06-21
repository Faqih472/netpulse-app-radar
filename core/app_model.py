"""
app_model.py
============
Menyimpan state per-aplikasi across tick: history bandwidth (untuk
grafik line chart), total terpakai sejak app dibuka, peak speed, dsb.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Tuple

from core.net_engine import ProcNetSample

HISTORY_LEN = 120  # 120 detik terakhir (2 menit) untuk grafik


@dataclass
class AppState:
    pid: int
    name: str
    exe_path: str
    category: str = "Lainnya"
    icon_key: str = ""               # dipakai utk pilih warna/icon di UI
    download_history: Deque[float] = field(default_factory=lambda: deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN))
    upload_history: Deque[float] = field(default_factory=lambda: deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN))
    current_down: float = 0.0
    current_up: float = 0.0
    peak_down: float = 0.0
    peak_up: float = 0.0
    session_total_down: int = 0
    session_total_up: int = 0
    connections: int = 0
    remote_hosts: Tuple[str, ...] = ()
    last_seen_tick: int = 0
    is_unknown_publisher: bool = False

    def push(self, sample: ProcNetSample, tick: int):
        self.category = sample.category
        self.current_down = sample.download_bps
        self.current_up = sample.upload_bps
        self.download_history.append(sample.download_bps)
        self.upload_history.append(sample.upload_bps)
        self.peak_down = max(self.peak_down, sample.download_bps)
        self.peak_up = max(self.peak_up, sample.upload_bps)
        self.connections = sample.connections
        self.remote_hosts = sample.remote_hosts
        self.last_seen_tick = tick


class AppRegistry:
    """
    Registry semua aplikasi yang pernah terdeteksi pada sesi ini.
    Menghitung delta total bytes (untuk akumulasi 'data terpakai sesi
    ini') secara independen dari io_counters mentah, karena io_counters
    proses bisa direset psutil tiap kali proses baru terdeteksi.
    """

    def __init__(self):
        self._apps: Dict[int, AppState] = {}
        self._tick = 0
        self._first_seen_total: Dict[int, Tuple[int, int]] = {}

    def update(self, samples: List[ProcNetSample]) -> List[AppState]:
        self._tick += 1
        seen_pids = set()

        for s in samples:
            seen_pids.add(s.pid)
            if s.pid not in self._apps:
                self._apps[s.pid] = AppState(
                    pid=s.pid, name=s.name, exe_path=s.exe_path,
                    category=s.category,
                )
                self._first_seen_total[s.pid] = (s.total_down, s.total_up)

            state = self._apps[s.pid]
            state.push(s, self._tick)

            base_down, base_up = self._first_seen_total.get(s.pid, (0, 0))
            state.session_total_down = max(0, s.total_down - base_down)
            state.session_total_up = max(0, s.total_up - base_up)

        # Untuk app yang tidak terlihat di tick ini, decay ke 0 secara
        # halus (bukan langsung hilang) supaya grafik tidak patah² kalau
        # cuma miss satu tick.
        for pid, state in self._apps.items():
            if pid not in seen_pids:
                state.current_down = 0.0
                state.current_up = 0.0
                state.download_history.append(0.0)
                state.upload_history.append(0.0)

        return list(self._apps.values())

    def get_active(self, stale_after_ticks: int = 5) -> List[AppState]:
        """App yang masih dianggap aktif (terlihat dlm N tick terakhir)."""
        return [
            a for a in self._apps.values()
            if self._tick - a.last_seen_tick <= stale_after_ticks
        ]

    def get_all(self) -> List[AppState]:
        return list(self._apps.values())

    @property
    def tick(self) -> int:
        return self._tick
