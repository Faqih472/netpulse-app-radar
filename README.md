  # NetPulse — Real-Time Per-App Bandwidth Monitor

Aplikasi desktop Windows untuk memantau pemakaian bandwidth tiap aplikasi
secara real-time (update setiap 1 detik), dikelompokkan per kategori,
dengan fitur ranking terpisah. Desain dark theme dengan accent merah,
terinspirasi command-center seperti Steam.

![status](https://img.shields.io/badge/platform-Windows-blue)

---
## Fitur

- **Live per-app bandwidth**: lihat MB/s naik-turun tiap aplikasi
  (Chrome, Discord, game, dll) setiap 1 detik.
- **Deteksi aplikasi mencurigakan**: aplikasi tanpa path jelas atau di
  folder temp ditandai dengan badge ⚠ kuning, supaya kamu sadar ada
  proses background yang diam-diam pakai data.
- **Sparkline tren 30 detik** langsung di tabel, tanpa perlu klik apa-apa.
- **Panel detail** dengan grafik history penuh 2 menit terakhir, total
  data terpakai sesi ini, peak speed, dan daftar IP remote yang
  terhubung.
- **Search, sort, dan filter** (semua aplikasi / hanya yang aktif /
  hanya yang mencurigakan).
- **Total bandwidth sistem** real-time di bagian atas.

---


## Instalasi (Windows)

### Langkah 1 — Install Npcap (PENTING, untuk akurasi penuh)

1. Download Npcap dari situs resminya:
   **[https://npcap.com/#download](https://npcap.com/#download)**
   (gratis, dibuat oleh tim Nmap, juga dipakai Wireshark).
2. Jalankan installer-nya.
3. Saat instalasi, **centang opsi "Install Npcap in WinPcap API-compatible
   Mode"** (biasanya sudah tercentang default).
4. Selesai, tidak perlu restart komputer.

> Tanpa Npcap, aplikasi tetap bisa jalan (mode fallback), tapi angka
> bandwidth untuk download besar (Steam, dll) tidak akan akurat — ini
> persis masalah yang kamu laporkan di poin #2.

### Langkah 2 — Install Python 3.10+

Download dari [python.org](https://www.python.org/downloads/). Saat
instalasi, centang **"Add Python to PATH"**.

### Langkah 3 — Install dependencies Python

```bash
cd path\ke\netmonitor
pip install -r requirements.txt
```

### Langkah 4 — Jalankan sebagai Administrator (WAJIB untuk packet capture)

Packet capture butuh hak admin di Windows. Tanpa ini, sniffing gagal
start dan otomatis jatuh ke mode fallback.

1. Buka **Command Prompt** atau **PowerShell** → klik kanan →
   **Run as Administrator**.
2. Jalankan:
   ```bash
   cd path\ke\netmonitor
   python main.py
   ```

Cek footer di bagian bawah aplikasi:
- ✅ **"Sumber data: packet capture (Npcap) — akurat byte-level"** →
  semua sudah benar, angka MB/s sekarang akurat.
- ⚠ **"Mode fallback (Npcap tidak terdeteksi)"** → Npcap belum
  terinstall, atau aplikasi tidak dijalankan sebagai Administrator.

---

## Fitur Lengkap

- **Live per-app bandwidth** akurat byte-level (lewat Npcap), update
  tiap 1 detik.
- **Kategori otomatis** untuk semua aplikasi yang terdeteksi.
- **List statis** (tab Semua Aplikasi) supaya mudah scanning/mencari,
  tidak loncat-loncat posisi.
- **Top Ranking terpisah** (tab 🏆) dengan dropdown metrik & rentang
  1-10/11-20/dst.
- **Deteksi aplikasi mencurigakan**: badge ⚠ untuk app tanpa path jelas
  atau di folder temp/unknown.
- **Sparkline tren 30 detik** langsung di tabel.
- **Panel detail** dengan grafik history 2 menit, peak speed, total
  data sesi ini, dan daftar IP remote yang terhubung.
- **Search & filter kategori** di tab Semua Aplikasi.
- **Total bandwidth sistem real-time** di bagian atas.

---

## Struktur Project

```
netmonitor/
├── main.py                 # entry point — jalankan ini
├── requirements.txt
├── core/
│   ├── net_engine.py       # packet capture engine + kategori aplikasi
│   ├── worker.py           # QThread background sampler (1x/detik)
│   ├── app_model.py        # state & history per aplikasi
│   └── formatters.py       # format angka (B/s, KB/s, MB/s, dst)
└── ui/
    ├── main_window.py      # jendela utama (2 tab: Semua Aplikasi & Top Ranking)
    ├── theme.py             # palet warna & stylesheet (QSS)
    └── widgets.py           # pulse dot & sparkline custom widget
```

---

## Build jadi .exe (opsional)

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name NetPulse main.py
```

Hasilnya ada di `dist/NetPulse.exe`. Karena butuh hak admin untuk
packet capture, sebaiknya set executable supaya selalu minta elevasi:
klik kanan `.exe` → Properties → Compatibility → centang **"Run this
program as an administrator"**.

---

## Troubleshooting

| Masalah | Solusi |
|---|---|
| Footer menunjukkan "Mode fallback" | Pastikan Npcap sudah terinstall DAN aplikasi dijalankan sebagai Administrator |
| Angka Steam/download masih kecil padahal sedang download besar | Cek footer dulu — kalau masih "Mode fallback", itu sebabnya. Install Npcap + run as admin |
| `ModuleNotFoundError: No module named 'scapy'` | `pip install -r requirements.txt` belum dijalankan / environment salah |
| Tidak ada aplikasi muncul sama sekali | Pastikan ada aktivitas internet aktif (buka browser/app apa pun yang konek internet), tunggu 1-2 detik untuk tick pertama |
| App lag dengan banyak proses aktif | Wajar bila ada 100+ koneksi aktif tersampling tiap detik; bisa naikkan interval di `main.py` → cari `SamplerWorker(interval_sec=1.0)` ubah ke `2.0` |
| Kategori "Lainnya" terlalu banyak isinya | Edit `CATEGORY_RULES` di `core/net_engine.py`, tambahkan nama proses aplikasi yang sering kamu pakai ke kategori yang sesuai |
