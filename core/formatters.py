"""
formatters.py
=============
Helper kecil untuk format angka bytes/speed agar konsisten di seluruh
UI dan tidak "loncat-loncat" lebar teksnya saat update tiap detik.
"""

from __future__ import annotations


def format_speed(bytes_per_sec: float) -> str:
    """0 B/s, 12.3 KB/s, 4.2 MB/s, 1.1 GB/s"""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:5.0f} B/s"
    elif bytes_per_sec < 1024 ** 2:
        return f"{bytes_per_sec / 1024:5.1f} KB/s"
    elif bytes_per_sec < 1024 ** 3:
        return f"{bytes_per_sec / 1024 ** 2:5.1f} MB/s"
    else:
        return f"{bytes_per_sec / 1024 ** 3:5.2f} GB/s"


def format_bytes(total_bytes: float) -> str:
    """0 B, 12.3 KB, 4.2 MB, 1.1 GB"""
    if total_bytes < 1024:
        return f"{total_bytes:.0f} B"
    elif total_bytes < 1024 ** 2:
        return f"{total_bytes / 1024:.1f} KB"
    elif total_bytes < 1024 ** 3:
        return f"{total_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{total_bytes / 1024 ** 3:.2f} GB"


def short_path(path: str, max_len: int = 60) -> str:
    if not path:
        return "(path tidak tersedia)"
    if len(path) <= max_len:
        return path
    return path[:max_len // 2 - 2] + "..." + path[-max_len // 2:]
