<div align="center">

# 🔴 NetPulse

### Real-Time Per-App Bandwidth Monitor untuk Windows

Pantau pemakaian internet tiap aplikasi secara live — siapa yang lagi download, siapa yang diam-diam pakai kuota di background, semuanya kelihatan per detik.

[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)](#)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](#)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41CD52?logo=qt&logoColor=white)](#)
[![License](https://img.shields.io/badge/license-MIT-red.svg)](#-lisensi)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#)

</div>

---

## 📖 Daftar Isi

- [Tentang Proyek](#-tentang-proyek)
- [Fitur](#-fitur)
- [Screenshot](#-screenshot)
- [Cara Kerja](#-cara-kerja)
- [Instalasi](#-instalasi)
  - [1. Install Npcap](#1-install-npcap-wajib-untuk-akurasi-penuh)
  - [2. Install Python](#2-install-python-310)
  - [3. Clone & Install Dependencies](#3-clone--install-dependencies)
  - [4. Jalankan](#4-jalankan)
- [Struktur Proyek](#-struktur-proyek)
- [Konfigurasi & Kustomisasi](#-konfigurasi--kustomisasi)
- [Build ke .exe](#-build-ke-exe)
- [Troubleshooting](#-troubleshooting)
- [Batasan & Catatan Teknis](#-batasan--catatan-teknis)
- [Roadmap](#-roadmap)
- [Kontribusi](#-kontribusi)
- [Lisensi](#-lisensi)

---

## 🎯 Tentang Proyek

**NetPulse** adalah aplikasi desktop untuk Windows yang menampilkan
pemakaian bandwidth tiap aplikasi yang berjalan, **per detik, secara
real-time**. Dibuat untuk menjawab pertanyaan sederhana yang sering
sulit dijawab oleh Task Manager bawaan Windows:

> *"Aplikasi apa yang sekarang ini paling banyak makan kuota saya?"*
> *"Ada proses aneh di background yang diam-diam pakai internet, gak ya?"*

NetPulse membaca trafik jaringan langsung dari network interface card
(NIC) lewat packet capture (Npcap), memetakannya ke proses yang
bersangkutan, dan menyajikannya dalam tampilan dark-theme dengan accent
merah yang terinspirasi command-center ala Steam.

---

## ✨ Fitur

| Fitur | Deskripsi |
|---|---|
| 🔴 **Live monitoring per detik** | Update bandwidth tiap aplikasi setiap 1 detik, tanpa delay |
| 📊 **Akurasi byte-level** | Pakai packet capture (Npcap), bukan estimasi — angka MB/s benar-benar dari NIC |
| 🗂 **Kategori otomatis** | Aplikasi otomatis dikelompokkan: Browser, Game & Launcher, Chat, Streaming, Cloud, Sistem, dll |
| 📌 **List yang tidak loncat-loncat** | Posisi aplikasi di tab utama stabil (diurutkan nama), memudahkan pencarian manual |
| 🏆 **Top Ranking terpisah** | Tab khusus dengan dropdown rentang (1–10, 11–20, dst) berdasarkan Download / Upload / Total tertinggi |
| ⚠️ **Deteksi aplikasi mencurigakan** | Badge otomatis untuk proses tanpa path jelas atau di folder temp/unknown |
| 📈 **Grafik history 2 menit** | Panel detail dengan line chart penuh untuk aplikasi yang dipilih |
| 🔍 **Sparkline inline** | Mini grafik tren 30 detik langsung di setiap baris tabel |
| 🔎 **Search & filter kategori** | Cari aplikasi spesifik atau filter per kategori |
| 🌐 **Info koneksi** | Lihat berapa koneksi aktif dan IP remote yang terhubung |
| 🎨 **Desain custom** | Dark theme + accent merah, pulse indicator yang berdenyut saat ada traffic aktif |

---

## 📸 Screenshot

> Ganti placeholder di bawah ini dengan screenshot asli aplikasi kamu
> setelah dijalankan di Windows. Simpan di folder `docs/screenshots/`
> lalu update path-nya di sini.

```
docs/screenshots/tab-semua-aplikasi.png
docs/screenshots/tab-top-ranking.png
docs/screenshots/detail-panel.png
```

<!--
![Tab Semua Aplikasi](docs/screenshots/tab-semua-aplikasi.png)
![Tab Top Ranking](docs/screenshots/tab-top-ranking.png)
-->

---

## ⚙️ Cara Kerja

Windows tidak menyediakan API publik yang langsung memberi "berapa
byte network per proses per detik". NetPulse mengatasi ini dengan
pipeline berikut:

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│   Network NIC    │ --> │  Packet Capture   │ --> │  Mapping ke PID    │
│ (semua trafik IP) │     │  (Npcap + scapy)  │     │ (psutil.net_       │
└─────────────────┘     └──────────────────┘     │  connections)      │
                                                    └───────────────────┘
                                                              │
                                                              ▼
                                                  ┌───────────────────────┐
                                                  │  Akumulasi byte/detik   │
                                                  │  per proses, di-flush   │
                                                  │  tiap 1 detik           │
                                                  └───────────────────────┘
                                                              │
                                                              ▼
                                                  ┌───────────────────────┐
                                                  │   UI (PyQt6) — table,   │
                                                  │   grafik, ranking       │
                                                  └───────────────────────┘
```

1. **Sniffing** — semua paket TCP/UDP yang lewat NIC ditangkap secara
   pasif (tidak mengubah/memblokir trafik apa pun).
2. **Pemetaan** — tiap paket dicocokkan ke proses pemiliknya lewat port
   lokal yang sedang terbuka (`psutil.net_connections()`).
3. **Agregasi** — byte dikumpulkan per proses dalam jendela 1 detik,
   lalu ditampilkan sebagai MB/s di UI.
4. **Fallback otomatis** — jika Npcap belum terinstall, sistem otomatis
   beralih ke mode estimasi berbasis `psutil.io_counters()` (kurang
   akurat untuk download besar, tapi tetap menunjukkan tren aktivitas).

---

## 🚀 Instalasi

### 1. Install Npcap (wajib untuk akurasi penuh)

NetPulse menggunakan [Npcap](https://npcap.com/#download) — driver
packet capture gratis & resmi dari tim Nmap, yang juga dipakai oleh
Wireshark.

1. Download installer dari **[npcap.com/#download](https://npcap.com/#download)**
2. Jalankan installer
3. Pastikan opsi **"Install Npcap in WinPcap API-compatible Mode"**
   tercentang (biasanya default)
4. Selesai — tidak perlu restart

> Tanpa Npcap, aplikasi tetap bisa dijalankan (mode fallback), tapi
> angka bandwidth untuk download besar (Steam, game update, dll) tidak
> akan akurat.

### 2. Install Python 3.10+

Download dari [python.org/downloads](https://www.python.org/downloads/).

⚠️ Saat instalasi, **centang "Add Python to PATH"**.

Verifikasi instalasi:

```bash
python --version
```

### 3. Clone & Install Dependencies

```bash
git clone https://github.com/USERNAME/netpulse.git
cd netpulse
```

Disarankan pakai virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

Install semua dependency:

```bash
pip install -r requirements.txt
```

### 4. Jalankan

Packet capture butuh hak admin di Windows. **Jalankan Command Prompt /
PowerShell sebagai Administrator**, lalu:

```bash
cd path\ke\netpulse
python main.py
```

Cek status di footer bawah aplikasi:

| Status footer | Artinya |
|---|---|
| ✅ `Sumber data: packet capture (Npcap) — akurat byte-level` | Semua benar, siap dipakai |
| ⚠️ `Mode fallback (Npcap tidak terdeteksi)` | Npcap belum terinstall, atau app tidak dijalankan sebagai admin |

---

## 📁 Struktur Proyek

```
netpulse/
├── main.py                  # Entry point — jalankan ini untuk start app
├── requirements.txt          # Daftar dependency Python
├── README.md
│
├── core/                      # Logika inti (non-UI)
│   ├── net_engine.py          # Packet capture engine + klasifikasi kategori aplikasi
│   ├── worker.py               # QThread background sampler (jalan tiap 1 detik)
│   ├── app_model.py            # State & history per aplikasi (untuk grafik)
│   └── formatters.py           # Helper format angka (B/s, KB/s, MB/s)
│
└── ui/                         # Komponen tampilan (PyQt6)
    ├── main_window.py          # Jendela utama — tab "Semua Aplikasi" & "Top Ranking"
    ├── theme.py                  # Palet warna & stylesheet (QSS)
    └── widgets.py                 # Widget custom: pulse dot indicator & sparkline chart
```

### Modul-modul utama

| Modul | Tanggung Jawab |
|---|---|
| `net_engine.py` | Sniffing paket, klasifikasi kategori aplikasi, fallback otomatis |
| `worker.py` | Menjalankan sampling di thread terpisah agar UI tidak freeze |
| `app_model.py` | Menyimpan history bandwidth, total sesi, peak speed per aplikasi |
| `main_window.py` | Layout UI, tabel, grafik, interaksi pengguna |
| `theme.py` | Semua definisi warna & style terpusat di satu tempat |
| `widgets.py` | Komponen visual kecil yang dipakai berulang (pulse dot, sparkline) |

---

## 🛠 Konfigurasi & Kustomisasi

### Mengubah interval refresh

Default 1 detik. Untuk mengubah, edit `core/worker.py` saat instansiasi
di `ui/main_window.py`:

```python
self.worker = SamplerWorker(interval_sec=1.0)  # ubah ke 2.0, 0.5, dst
```

### Menambah kategori aplikasi baru

Edit `CATEGORY_RULES` di `core/net_engine.py`:

```python
CATEGORY_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("Browser", (
        "chrome", "msedge", "firefox", "opera", # ...
    )),
    # tambahkan kategori baru di sini, atau tambah keyword
    # ke kategori yang sudah ada
]
```

Nama proses dicocokkan secara *substring match* (lowercase), jadi
`"steam"` akan cocok dengan `steam.exe`, `steamwebhelper.exe`, dst.

### Mengubah ambang batas "aktif"

Default: aplikasi dianggap "aktif" (pulse dot menyala) jika bandwidth
> 2 KB/s. Ubah di `ui/main_window.py`:

```python
ACTIVITY_THRESHOLD_BPS = 2048  # ubah sesuai kebutuhan
```

### Mengubah jumlah item per halaman ranking

```python
RANK_PAGE_SIZE = 10  # ubah ke 20, 25, dst
```

---

## 📦 Build ke .exe

Untuk mendistribusikan tanpa perlu install Python di komputer lain:

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name NetPulse main.py
```

Hasil ada di folder `dist/NetPulse.exe`.

Karena butuh hak admin untuk packet capture, set executable agar
selalu minta elevasi:

> Klik kanan `NetPulse.exe` → **Properties** → tab **Compatibility** →
> centang **"Run this program as an administrator"**.

Untuk menambahkan ikon custom:

```bash
pyinstaller --noconsole --onefile --name NetPulse --icon=assets/icon.ico main.py
```

---

## 🔧 Troubleshooting

| Masalah | Solusi |
|---|---|
| Footer menunjukkan "Mode fallback" | Pastikan Npcap sudah terinstall **dan** aplikasi dijalankan sebagai Administrator |
| `ModuleNotFoundError: No module named 'scapy'` | Jalankan `pip install -r requirements.txt` di environment yang sama dengan yang dipakai untuk `python main.py` |
| `ModuleNotFoundError: No module named 'PyQt6'` | Sama seperti di atas — pastikan venv aktif sebelum install/run |
| Tidak ada aplikasi muncul sama sekali | Pastikan ada aktivitas internet aktif (buka browser apa pun), tunggu 1–2 detik untuk tick pertama |
| Angka download besar (Steam dll) masih kecil | Cek footer — kalau "Mode fallback", install Npcap dan jalankan sebagai admin |
| Aplikasi lag saat banyak proses aktif | Wajar bila 100+ koneksi aktif tersampling tiap detik. Naikkan `interval_sec` di `worker.py` |
| Kategori "Lainnya" terlalu penuh | Tambahkan keyword nama proses ke `CATEGORY_RULES` di `core/net_engine.py` |
| Banyak proses sistem tidak terbaca | Jalankan sebagai Administrator agar `psutil.net_connections()` bisa membaca semua proses |

---

## ⚠️ Batasan & Catatan Teknis

- **Butuh Npcap** untuk akurasi penuh. Tanpa Npcap, aplikasi tetap
  berjalan tapi memakai estimasi `io_counters()` yang kurang presisi
  untuk transfer besar.
- **Butuh hak Administrator** untuk packet capture berfungsi dan untuk
  membaca seluruh daftar koneksi proses sistem.
- Paket loopback (komunikasi antar proses lokal, mis. `127.0.0.1`)
  sengaja tidak dihitung sebagai upload/download untuk menghindari
  duplikasi penghitungan.
- Aplikasi yang tidak memiliki koneksi socket terbuka tidak akan
  muncul di daftar (karena memang sedang tidak memakai jaringan).
- Saat ini hanya mendukung **Windows**. Di sistem non-Windows, aplikasi
  berjalan dalam mode simulasi (data demo) untuk keperluan pengembangan
  UI.

---

## 🗺 Roadmap

- [ ] Mode dark/light toggle
- [ ] Export laporan pemakaian harian/bulanan ke CSV
- [ ] Notifikasi saat aplikasi tertentu melebihi batas pemakaian data
- [ ] Dukungan multi-NIC (pilih interface mana yang disniff)
- [ ] Grafik perbandingan antar aplikasi dalam satu tampilan
- [ ] Mode "data saver alert" untuk koneksi tethering/terbatas

Punya ide fitur lain? Buka [issue](../../issues) baru.

---

## 🤝 Kontribusi

Kontribusi terbuka untuk siapa saja!

1. Fork repository ini
2. Buat branch baru (`git checkout -b fitur/nama-fitur`)
3. Commit perubahan (`git commit -m "Tambah fitur X"`)
4. Push ke branch (`git push origin fitur/nama-fitur`)
5. Buka Pull Request

Pastikan kode tetap mengikuti struktur modular yang sudah ada (logika
di `core/`, tampilan di `ui/`) dan diuji di Windows sebelum membuat PR.

---

## 📄 Lisensi

Didistribusikan di bawah lisensi **MIT**. Lihat file `LICENSE` untuk
detail lengkap.

```
MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

---

<div align="center">

Dibuat dengan 🔴 menggunakan Python & PyQt6

</div>
