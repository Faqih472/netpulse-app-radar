"""
net_engine.py
=============
Inti pengambilan data bandwidth per-proses.

VERSI 2 — PACKET CAPTURE (akurat byte-level, bukan estimasi)
------------------------------------------------------------------
Versi sebelumnya pakai psutil.io_counters() sebagai proxy, yang
TERBUKTI tidak akurat untuk app seperti Steam (Steam sering punya
proses launcher yang ringan, sementara download sebenarnya lewat
banyak koneksi paralel ke content-server, dan io_counters() proses
punya lag/buffering di OS yang membuat angka MB/s besar tidak
ter-capture tepat per detik).

Versi ini ganti total pendekatannya jadi PACKET CAPTURE SUNGGUHAN:
  1. Sniff semua paket IP yang lewat NIC aktif via scapy (butuh driver
     Npcap terinstall di Windows -- lihat README untuk link & cara
     install, ini SEKALI saja di awal, bukan tiap run).
  2. Tiap paket TCP/UDP, hitung panjang payload-nya dan tandai sebagai
     "in" (download) jika alamat tujuan adalah IP lokal mesin ini, atau
     "out" (upload) jika alamat asal adalah IP lokal.
  3. Map paket itu ke proses yang memiliki socket dengan local
     port yang sama, lewat psutil.net_connections() (di-refresh tiap
     tick, port lokal adalah kunci paling stabil untuk pemetaan ini
     karena 1 port lokal = 1 proses pada satu waktu).
  4. Akumulasikan byte per PID dalam jendela 1 detik, lalu inilah yang
     jadi angka MB/s yang ditampilkan -- ini BYTE ASLI yang lewat NIC,
     bukan proxy/estimasi, sehingga akurat untuk download besar sekelas
     Steam, browser, game, dll.

Sniffing berjalan di thread terpisah secara terus-menerus (non-blocking
terhadap UI), mengumpulkan byte ke counter in-memory yang di-flush
("dibaca lalu di-reset ke 0") setiap 1 detik oleh worker utama.

FALLBACK: jika Npcap belum terinstall atau scapy gagal sniffing (mis.
permission, atau dijalankan bukan di Windows), engine otomatis jatuh
ke FallbackIOCounterSampler (pendekatan versi 1 / io_counters proxy)
supaya app TETAP BISA JALAN, dengan peringatan jelas di footer UI bahwa
sedang memakai mode kurang akurat.
"""

from __future__ import annotations

import sys
import time
import threading
import math
import random
import socket
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import psutil

IS_WINDOWS = sys.platform == "win32"


# ======================================================================
# KATEGORI APLIKASI
# ======================================================================
# Dipakai untuk mengelompokkan aplikasi di UI (poin permintaan #1).
# Pencocokan berbasis nama proses (lowercase, tanpa .exe) dan/atau
# fragment path. Daftar ini sengaja luas mencakup aplikasi populer di
# Indonesia/umum; apa pun yang tidak cocok kategori manual masuk ke
# "Lainnya", dan proses sistem inti Windows masuk ke "Sistem Windows".

CATEGORY_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("Browser", (
        "chrome", "msedge", "firefox", "opera", "opera_gx", "brave",
        "vivaldi", "iexplore", "browser",
    )),
    ("Game & Launcher", (
        "steam", "steamwebhelper", "steamservice", "valorant", "riot",
        "leagueclient", "league of legends", "epicgameslauncher",
        "epicwebhelper", "battle.net", "battlenet", "origin", "eadesktop",
        "ubisoftconnect", "uplay", "gog galaxy", "galaxyclient",
        "minecraft", "javaw", "rockstarservice", "rockstarerrorhandler",
        "playstationapp", "xboxapp", "wgc", "wargaming", "robloxplayer",
        "robloxplayerbeta", "fivem", "ragemp", "dota2", "csgo", "cs2",
        "overwatch", "apex", "genshinimpact", "honkai", "wuwa", "wutheringwaves",
    )),
    ("Chat & Komunikasi", (
        "discord", "telegram", "whatsapp", "slack", "teams", "skype",
        "zoom", "line", "messenger", "signal", "viber", "googlemeet",
        "webex",
    )),
    ("Musik & Video Streaming", (
        "spotify", "applemusic", "tidal", "deezer", "vlc", "netflix",
        "youtube", "primevideo", "disneyplus", "iqiyi", "viu", "wetv",
        "joox", "soundcloud",
    )),
    ("Cloud & Sinkronisasi File", (
        "onedrive", "googledrivesync", "dropbox", "icloud", "mega",
        "syncthing", "backblaze", "idrive",
    )),
    ("Update & Background Service", (
        "svchost", "wuauclt", "usoclient", "msmpeng", "searchindexer",
        "windowsupdatebox", "updater", "crashpad", "backgroundtransferhost",
        "delivery optimization", "doplaybackagent",
    )),
    ("Sistem Windows", (
        "explorer", "dwm", "csrss", "winlogon", "wininit", "services",
        "lsass", "smss", "fontdrvhost", "sihost", "taskhostw", "dllhost",
        "runtimebroker", "registry", "system", "system idle process",
        "conhost", "ctfmon",
    )),
    ("Pengembangan & Produktivitas", (
        "code", "pycharm", "idea", "webstorm", "node", "python",
        "docker", "postman", "git", "github", "outlook", "excel",
        "word", "powerpoint", "onenote", "notion", "obsidian",
    )),
]


def classify_app(process_name: str, exe_path: str = "") -> str:
    """Tentukan kategori aplikasi dari nama proses (& path bila perlu)."""
    name = (process_name or "").lower().replace(".exe", "").strip()
    path = (exe_path or "").lower()

    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in name or kw in path:
                return category
    return "Lainnya"


# ======================================================================
# DATA STRUCTURES
# ======================================================================

@dataclass
class ProcNetSample:
    """Satu snapshot bandwidth untuk satu proses pada satu tick."""
    pid: int
    name: str
    exe_path: str
    category: str = "Lainnya"
    download_bps: float = 0.0
    upload_bps: float = 0.0
    total_down: int = 0
    total_up: int = 0
    connections: int = 0
    remote_hosts: Tuple[str, ...] = ()


class RateAccumulator:
    """Counter byte kumulatif per PID, di-flush tiap 1 detik."""

    def __init__(self):
        self._lock = threading.Lock()
        self._in_bytes: Dict[int, int] = {}
        self._out_bytes: Dict[int, int] = {}
        self._total_in: Dict[int, int] = {}
        self._total_out: Dict[int, int] = {}

    def add(self, pid: int, in_bytes: int = 0, out_bytes: int = 0):
        with self._lock:
            if in_bytes:
                self._in_bytes[pid] = self._in_bytes.get(pid, 0) + in_bytes
                self._total_in[pid] = self._total_in.get(pid, 0) + in_bytes
            if out_bytes:
                self._out_bytes[pid] = self._out_bytes.get(pid, 0) + out_bytes
                self._total_out[pid] = self._total_out.get(pid, 0) + out_bytes

    def flush(self) -> Dict[int, Tuple[int, int]]:
        """Ambil & reset counter per-detik. Total kumulatif TIDAK direset."""
        with self._lock:
            pids = set(self._in_bytes) | set(self._out_bytes)
            result = {
                pid: (self._in_bytes.get(pid, 0), self._out_bytes.get(pid, 0))
                for pid in pids
            }
            self._in_bytes.clear()
            self._out_bytes.clear()
            return result

    def get_totals(self, pid: int) -> Tuple[int, int]:
        with self._lock:
            return self._total_in.get(pid, 0), self._total_out.get(pid, 0)


# ======================================================================
# PACKET CAPTURE SAMPLER (akurat, butuh Npcap)
# ======================================================================

class PacketCaptureSampler:
    """
    Sniff paket NIC secara terus-menerus di thread terpisah, map ke PID
    lewat port lokal, akumulasikan byte per detik.
    """

    def __init__(self):
        self._accumulator = RateAccumulator()
        self._port_to_pid: Dict[Tuple[str, int], int] = {}  # (proto, local_port) -> pid
        self._pid_info: Dict[int, dict] = {}  # pid -> {name, exe, remote_hosts, connections}
        self._local_ips: set = set()
        self._sniff_thread: Optional[threading.Thread] = None
        self._running = False
        self._available = False
        self._init_error: str = ""
        self._lock = threading.Lock()

        self._refresh_local_ips()
        self._available = self._try_start_sniffing()

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> str:
        return self._init_error

    def _refresh_local_ips(self):
        ips = set()
        try:
            for iface, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if a.family == socket.AF_INET:
                        ips.add(a.address)
        except Exception:
            pass
        ips.add("127.0.0.1")
        self._local_ips = ips

    def _try_start_sniffing(self) -> bool:
        try:
            from scapy.all import sniff, IP, TCP, UDP  # noqa: F401
        except Exception as e:
            self._init_error = f"scapy tidak tersedia: {e}"
            return False

        try:
            self._running = True
            self._sniff_thread = threading.Thread(
                target=self._sniff_loop, daemon=True
            )
            self._sniff_thread.start()
            # beri waktu sebentar utk tahu apakah sniffing berhasil start
            # (gagal biasanya karena Npcap belum terinstall -> exception
            # langsung muncul di thread, ditangkap di _sniff_loop)
            time.sleep(0.3)
            if self._init_error:
                return False
            return True
        except Exception as e:
            self._init_error = str(e)
            return False

    def _sniff_loop(self):
        try:
            from scapy.all import sniff
            sniff(prn=self._on_packet, store=False, stop_filter=lambda p: not self._running)
        except Exception as e:
            self._init_error = f"Gagal memulai packet capture (perlu Npcap + Run as Administrator): {e}"
            self._running = False

    def _on_packet(self, pkt):
        try:
            from scapy.all import IP, TCP, UDP
            if not pkt.haslayer(IP):
                return
            ip_layer = pkt[IP]
            length = len(pkt)

            proto = None
            sport = dport = None
            if pkt.haslayer(TCP):
                proto = "tcp"
                sport, dport = pkt[TCP].sport, pkt[TCP].dport
            elif pkt.haslayer(UDP):
                proto = "udp"
                sport, dport = pkt[UDP].sport, pkt[UDP].dport
            else:
                return

            src_is_local = ip_layer.src in self._local_ips
            dst_is_local = ip_layer.dst in self._local_ips

            if src_is_local and not dst_is_local:
                # paket keluar dari mesin ini -> upload, port lokal = sport
                pid = self._port_to_pid.get((proto, sport))
                if pid:
                    self._accumulator.add(pid, out_bytes=length)
            elif dst_is_local and not src_is_local:
                # paket masuk ke mesin ini -> download, port lokal = dport
                pid = self._port_to_pid.get((proto, dport))
                if pid:
                    self._accumulator.add(pid, in_bytes=length)
            # paket antara dua IP lokal (loopback/LAN ke diri sendiri)
            # diabaikan dari sisi "upload" ganda -- sengaja tidak dihitung
            # dua kali.
        except Exception:
            pass

    def refresh_port_mapping(self) -> Dict[int, dict]:
        """
        Refresh pemetaan (proto, local_port) -> pid, dan kumpulkan info
        proses (nama, exe, remote_hosts, jumlah koneksi). Dipanggil tiap
        tick SEBELUM flush accumulator, supaya paket yang datang di
        antara tick tetap ter-map ke proses yang benar.
        """
        new_mapping: Dict[Tuple[str, int], int] = {}
        pid_info: Dict[int, dict] = {}

        try:
            conns = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, PermissionError):
            conns = []

        for c in conns:
            if not c.pid or not c.laddr:
                continue
            proto = "tcp" if c.type == socket.SOCK_STREAM else "udp"
            new_mapping[(proto, c.laddr.port)] = c.pid

            info = pid_info.setdefault(c.pid, {"connections": 0, "remote_hosts": set()})
            info["connections"] += 1
            if c.raddr:
                info["remote_hosts"].add(c.raddr.ip)

        self._port_to_pid = new_mapping

        for pid in pid_info:
            try:
                p = psutil.Process(pid)
                pid_info[pid]["name"] = p.name()
                pid_info[pid]["exe"] = p.exe() if p else ""
            except (psutil.AccessDenied, psutil.NoSuchProcess, Exception):
                pid_info[pid]["name"] = f"PID {pid}"
                pid_info[pid]["exe"] = ""

        self._pid_info = pid_info
        return pid_info

    def sample(self) -> List[ProcNetSample]:
        pid_info = self.refresh_port_mapping()
        per_pid_bytes = self._accumulator.flush()

        results: List[ProcNetSample] = []
        all_pids = set(pid_info.keys()) | set(per_pid_bytes.keys())

        for pid in all_pids:
            in_b, out_b = per_pid_bytes.get(pid, (0, 0))
            info = pid_info.get(pid, {})
            name = info.get("name", f"PID {pid}")
            exe = info.get("exe", "")
            total_in, total_out = self._accumulator.get_totals(pid)

            results.append(ProcNetSample(
                pid=pid,
                name=name,
                exe_path=exe,
                category=classify_app(name, exe),
                download_bps=float(in_b),   # sudah per-1-detik karena flush tiap tick
                upload_bps=float(out_b),
                total_down=total_in,
                total_up=total_out,
                connections=info.get("connections", 0),
                remote_hosts=tuple(sorted(info.get("remote_hosts", []))),
            ))

        return results

    def stop(self):
        self._running = False


# ======================================================================
# FALLBACK SAMPLER (io_counters proxy, dipakai bila Npcap tidak ada)
# ======================================================================

class FallbackIOCounterSampler:
    """Pendekatan versi 1: io_counters() sebagai proxy. Dipakai hanya
    jika packet capture (Npcap) tidak tersedia di mesin user."""

    def __init__(self):
        self._tracker_last: Dict[int, Tuple[float, int, int]] = {}

    def sample(self) -> List[ProcNetSample]:
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
            except Exception:
                continue

            alive_pids.add(pid)
            now = time.monotonic()
            prev = self._tracker_last.get(pid)
            self._tracker_last[pid] = (now, io.read_bytes, io.write_bytes)
            if prev is None:
                down_bps, up_bps = 0.0, 0.0
            else:
                dt = max(now - prev[0], 0.001)
                down_bps = max(io.read_bytes - prev[1], 0) / dt
                up_bps = max(io.write_bytes - prev[2], 0) / dt

            name = proc.info.get("name") or f"PID {pid}"
            exe = proc.info.get("exe") or ""

            results.append(ProcNetSample(
                pid=pid, name=name, exe_path=exe,
                category=classify_app(name, exe),
                download_bps=down_bps, upload_bps=up_bps,
                total_down=io.read_bytes, total_up=io.write_bytes,
                connections=pid_conn_count.get(pid, 0),
                remote_hosts=tuple(sorted(pid_remote_hosts.get(pid, []))),
            ))

        for pid in list(self._tracker_last.keys()):
            if pid not in alive_pids:
                del self._tracker_last[pid]

        return results


# ======================================================================
# CROSS-PLATFORM ENTRYPOINT
# ======================================================================

class CrossPlatformSampler:
    """
    Sampler yang dipakai UI.
    - Windows + Npcap tersedia -> PacketCaptureSampler (akurat byte-level).
    - Windows tanpa Npcap       -> FallbackIOCounterSampler (proxy, kurang akurat).
    - Non-Windows (dev/preview) -> data simulasi.
    """

    def __init__(self):
        self._is_windows = IS_WINDOWS
        self._mode = "simulated"
        self._impl = None
        self._init_warning = ""

        if self._is_windows:
            pc = PacketCaptureSampler()
            if pc.is_available:
                self._impl = pc
                self._mode = "packet_capture"
            else:
                self._init_warning = pc.init_error
                self._impl = FallbackIOCounterSampler()
                self._mode = "fallback"

        self._sim_state: Dict[int, Tuple[float, float]] = {}
        self._sim_t = 0.0

    @property
    def mode(self) -> str:
        """'packet_capture' | 'fallback' | 'simulated'"""
        return self._mode

    @property
    def is_simulated(self) -> bool:
        return self._mode == "simulated"

    @property
    def init_warning(self) -> str:
        return self._init_warning

    def sample(self) -> List[ProcNetSample]:
        if self._mode in ("packet_capture", "fallback"):
            return self._impl.sample()
        return self._simulate()

    def stop(self):
        if self._mode == "packet_capture" and self._impl:
            self._impl.stop()

    # ---- simulasi untuk development/preview di non-Windows ----
    def _simulate(self) -> List[ProcNetSample]:
        self._sim_t += 1
        apps = [
            (1450, "chrome.exe", "C:/Program Files/Google/Chrome/Application/chrome.exe", "download"),
            (5132, "Discord.exe", "C:/Users/User/AppData/Local/Discord/app-1.0/Discord.exe", "chat"),
            (8841, "Spotify.exe", "C:/Users/User/AppData/Roaming/Spotify/Spotify.exe", "stream"),
            (2210, "steam.exe", "C:/Program Files (x86)/Steam/steam.exe", "steamdownload"),
            (4012, "svchost.exe", "C:/Windows/System32/svchost.exe", "system"),
            (9920, "VALORANT-Win64-Shipping.exe", "C:/Riot Games/VALORANT/live/ShooterGame/Binaries/Win64/VALORANT-Win64-Shipping.exe", "game"),
            (3344, "Telegram.exe", "C:/Users/User/AppData/Roaming/Telegram Desktop/Telegram.exe", "chat"),
            (7781, "mysterious_bg_task.exe", "C:/Program Files/Unknown/mysterious_bg_task.exe", "unknown"),
            (6601, "OneDrive.exe", "C:/Users/User/AppData/Local/Microsoft/OneDrive/OneDrive.exe", "cloud"),
            (2299, "Code.exe", "C:/Users/User/AppData/Local/Programs/Microsoft VS Code/Code.exe", "dev"),
        ]
        out: List[ProcNetSample] = []
        for pid_base, name, path, kind in apps:
            t = self._sim_t
            if kind == "download":
                base = 3_500_000 + 2_000_000 * math.sin(t / 6)
                down = max(0, base + random.gauss(0, 400_000))
                up = max(0, random.gauss(50_000, 20_000))
            elif kind == "steamdownload":
                # simulasikan Steam download besar & stabil (5-12 MB/s)
                base = 8_000_000 + 3_000_000 * math.sin(t / 9)
                down = max(0, base + random.gauss(0, 600_000))
                up = max(0, random.gauss(120_000, 40_000))
            elif kind == "stream":
                down = max(0, random.gauss(220_000, 60_000))
                up = max(0, random.gauss(8_000, 3_000))
            elif kind == "game":
                down = max(0, random.gauss(180_000, 90_000))
                up = max(0, random.gauss(150_000, 70_000))
            elif kind == "chat":
                down = max(0, random.gauss(15_000, 8_000))
                up = max(0, random.gauss(12_000, 6_000))
            elif kind == "cloud":
                down = max(0, random.gauss(60_000, 25_000))
                up = max(0, random.gauss(180_000, 70_000))
            elif kind == "dev":
                down = max(0, random.gauss(8_000, 4_000))
                up = max(0, random.gauss(3_000, 2_000))
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
                category=classify_app(name, path),
                download_bps=down, upload_bps=up,
                total_down=int(total_down), total_up=int(total_up),
                connections=random.randint(1, 8),
                remote_hosts=("203.0.113.5", "151.101.1.140") if kind != "system" else (),
            ))
        return out
