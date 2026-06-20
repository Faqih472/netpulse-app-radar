"""
net_engine.py
=============
Inti pengambilan data bandwidth per-proses.

CATATAN PENTING SOAL AKURASI (baca supaya ekspektasi tepat):
------------------------------------------------------------------
Windows TIDAK menyediakan API publik yang langsung memberi "bytes
network per proses per detik" tanpa salah satu dari:
  (a) packet capture driver (Npcap/WinDivert) -- instalasi terpisah
      dari Python, butuh admin, dan lebih berat, atau
  (b) ETW (Event Tracing for Windows) session khusus network -- jauh
      lebih kompleks untuk disetup & didistribusikan.

Supaya aplikasi ini ringan & langsung jalan tanpa instalasi driver
tambahan, engine memakai pendekatan yang sama dengan banyak tool
monitoring ringan: psutil.Process.io_counters() (read_bytes/write_bytes
kumulatif) sebagai proxy aktivitas I/O, TAPI hanya untuk proses yang
terbukti punya koneksi socket aktif (psutil.net_connections). Ini
representatif untuk tujuan "lihat aplikasi mana yang sedang pakai
data / deteksi aplikasi mencurigakan di background", namun di Windows
io_counters() menggabungkan I/O disk + network, jadi bila sebuah app
kebetulan menulis file besar ke disk di waktu yang sama dengan idle
network, angkanya bisa sedikit bias.

Upgrade opsional ke depan: integrasi Npcap + scapy untuk packet
sniffing murni byte-level NIC per proses, jika dibutuhkan akurasi lebih
tinggi.
"""

from __future__ import annotations

import sys
import time
import threading
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import psutil

IS_WINDOWS = sys.platform == "win32"


@dataclass
class ProcNetSample:
    """Satu snapshot bandwidth untuk satu proses pada satu tick."""
    pid: int
    name: str
    exe_path: str
    download_bps: float = 0.0
    upload_bps: float = 0.0
    total_down: int = 0
    total_up: int = 0
    connections: int = 0
    remote_hosts: Tuple[str, ...] = ()


class RateTracker:
    """Menghitung delta bytes/detik dari counter kumulatif per PID."""

    def __init__(self):
        self._last_values: Dict[int, Tuple[float, int, int]] = {}

    def update(self, pid: int, in_bytes: int, out_bytes: int) -> Tuple[float, float]:
        now = time.monotonic()
        prev = self._last_values.get(pid)
        self._last_values[pid] = (now, in_bytes, out_bytes)
        if prev is None:
            return 0.0, 0.0
        prev_t, prev_in, prev_out = prev
        dt = max(now - prev_t, 0.001)
        d_in = max(in_bytes - prev_in, 0)
        d_out = max(out_bytes - prev_out, 0)
        return d_in / dt, d_out / dt

    def purge_missing(self, alive_pids: set):
        for pid in list(self._last_values.keys()):
            if pid not in alive_pids:
                del self._last_values[pid]


class WindowsNetworkSampler:
    """
    Sampler real untuk Windows berbasis psutil:
      1. Petakan pid -> jumlah koneksi inet aktif (TCP/UDP).
      2. Untuk tiap proses dengan >=1 koneksi aktif, ambil io_counters().
      3. Hitung delta terhadap tick sebelumnya -> bytes/detik in & out.
    """

    def __init__(self):
        self._tracker = RateTracker()
        self._lock = threading.Lock()

    def sample(self) -> List[ProcNetSample]:
        with self._lock:
            return self._sample_impl()

    def _sample_impl(self) -> List[ProcNetSample]:
        results: List[ProcNetSample] = []
        alive_pids = set()

        pid_conn_count: Dict[int, int] = {}
        pid_remote_hosts: Dict[int, set] = {}
        try:
            for c in psutil.net_connections(kind="inet"):
                if not c.pid:
                    continue
                pid_conn_count[c.pid] = pid_conn_count.get(c.pid, 0) + 1
                if c.raddr:
                    pid_remote_hosts.setdefault(c.pid, set()).add(c.raddr.ip)
        except (psutil.AccessDenied, PermissionError):
            pid_conn_count = {}

        for proc in psutil.process_iter(["pid", "name", "exe"]):
            pid = proc.info["pid"]
            if pid not in pid_conn_count:
                continue
            try:
                io = proc.io_counters()
            except (psutil.AccessDenied, psutil.NoSuchProcess, PermissionError):
                continue
            except Exception:
                continue

            alive_pids.add(pid)
            down_bps, up_bps = self._tracker.update(pid, io.read_bytes, io.write_bytes)

            results.append(ProcNetSample(
                pid=pid,
                name=proc.info.get("name") or f"PID {pid}",
                exe_path=proc.info.get("exe") or "",
                download_bps=down_bps,
                upload_bps=up_bps,
                total_down=io.read_bytes,
                total_up=io.write_bytes,
                connections=pid_conn_count.get(pid, 0),
                remote_hosts=tuple(sorted(pid_remote_hosts.get(pid, []))),
            ))

        self._tracker.purge_missing(alive_pids)
        return results


class CrossPlatformSampler:
    """
    Sampler yang dipakai UI.
    - Di Windows -> WindowsNetworkSampler (data asli dari sistem).
    - Di non-Windows (dev/preview) -> data simulasi agar UI tetap bisa
      didemokan tanpa mesin Windows asli.
    """

    def __init__(self):
        self._is_windows = IS_WINDOWS
        self._impl = WindowsNetworkSampler() if self._is_windows else None
        self._sim_state: Dict[int, Tuple[float, float]] = {}
        self._sim_t = 0.0

    @property
    def is_simulated(self) -> bool:
        return not self._is_windows

    def sample(self) -> List[ProcNetSample]:
        if self._is_windows:
            return self._impl.sample()
        return self._simulate()

    def _simulate(self) -> List[ProcNetSample]:
        self._sim_t += 1
        apps = [
            (1450, "chrome.exe", "C:/Program Files/Google/Chrome/Application/chrome.exe", "download"),
            (5132, "Discord.exe", "C:/Users/User/AppData/Local/Discord/app-1.0/Discord.exe", "chat"),
            (8841, "Spotify.exe", "C:/Users/User/AppData/Roaming/Spotify/Spotify.exe", "stream"),
            (2210, "steam.exe", "C:/Program Files (x86)/Steam/steam.exe", "idle"),
            (4012, "svchost.exe", "C:/Windows/System32/svchost.exe", "system"),
            (9920, "VALORANT-Win64-Shipping.exe", "C:/Riot Games/VALORANT/live/ShooterGame/Binaries/Win64/VALORANT-Win64-Shipping.exe", "game"),
            (3344, "Telegram.exe", "C:/Users/User/AppData/Roaming/Telegram Desktop/Telegram.exe", "chat"),
            (7781, "mysterious_bg_task.exe", "C:/Program Files/Unknown/mysterious_bg_task.exe", "unknown"),
        ]
        out: List[ProcNetSample] = []
        for pid_base, name, path, kind in apps:
            t = self._sim_t
            if kind == "download":
                base = 3_500_000 + 2_000_000 * math.sin(t / 6)
                down = max(0, base + random.gauss(0, 400_000))
                up = max(0, random.gauss(50_000, 20_000))
            elif kind == "stream":
                down = max(0, random.gauss(220_000, 60_000))
                up = max(0, random.gauss(8_000, 3_000))
            elif kind == "game":
                down = max(0, random.gauss(180_000, 90_000))
                up = max(0, random.gauss(150_000, 70_000))
            elif kind == "chat":
                down = max(0, random.gauss(15_000, 8_000))
                up = max(0, random.gauss(12_000, 6_000))
            elif kind == "unknown":
                down = max(0, random.gauss(45_000, 10_000))
                up = max(0, random.gauss(38_000, 9_000))
            else:
                down = max(0, random.gauss(2_000, 1_500))
                up = max(0, random.gauss(1_500, 1_000))

            prev = self._sim_state.get(pid_base, (0.0, 0.0))
            total_down = prev[0] + down
            total_up = prev[1] + up
            self._sim_state[pid_base] = (total_down, total_up)

            out.append(ProcNetSample(
                pid=pid_base, name=name, exe_path=path,
                download_bps=down, upload_bps=up,
                total_down=int(total_down), total_up=int(total_up),
                connections=random.randint(1, 8),
                remote_hosts=("203.0.113.5", "151.101.1.140") if kind != "system" else (),
            ))
        return out
