  # NetPulse — Real-Time Per-App Bandwidth Monitor

Aplikasi desktop Windows untuk memantau pemakaian bandwidth tiap aplikasi
secara real-time (update setiap 1 detik), dikelompokkan per kategori,
dengan fitur ranking terpisah. Desain dark theme dengan accent merah,
terinspirasi command-center seperti Steam.

---

## 🆕 Apa yang Berubah di Versi Ini (jawaban poin #1, #2, #3)

### 1. Kategori aplikasi + list statis + Top Ranking terpisah

- **Tab "Semua Aplikasi"** sekarang mengelompokkan semua aplikasi ke
  dalam kategori (Browser, Game & Launcher, Chat & Komunikasi, Musik &
  Video Streaming, Cloud & Sinkronisasi, Update & Background Service,
  Sistem Windows, Pengembangan, Lainnya). Tiap kategori punya header
  yang bisa diklik untuk **expand/collapse**.
- Di dalam tiap kategori, aplikasi diurutkan **berdasarkan nama**
  (bukan bandwidth), jadi **posisinya tidak loncat-loncat** tiap detik
  — hanya angka MB/s-nya yang update live. Ini memudahkan kamu mencari
  aplikasi tertentu karena tahu persis di mana posisinya.
- **Tab "🏆 Top Ranking"** adalah fitur tambahan terpisah (bukan
  pengganti list utama). Di sini ada 2 dropdown:
  - **Urutkan berdasarkan**: Download tercepat / Upload tercepat /
    Total terbesar sesi ini.
  - **Tampilkan rentang**: 1-10 / 11-20 / 21-30 / dst — otomatis
    menyesuaikan jumlah halaman dengan jumlah aplikasi yang terdeteksi.
  - List di tab ini SENGAJA berubah urutan tiap detik (karena memang
    tujuannya ranking live).

### 2. Akurasi bandwidth diperbaiki total — sekarang pakai Packet Capture

Versi sebelumnya pakai `psutil.io_counters()` sebagai proxy, yang
**tidak akurat** untuk aplikasi seperti Steam (download besar tidak
ter-capture dengan benar). Versi ini diganti total ke pendekatan
**packet capture sungguhan** lewat **Npcap + scapy**:

- Setiap paket yang lewat network card di-sniff langsung.
- Byte asli dihitung per koneksi, lalu dipetakan ke proses pemilik
  lewat port lokal (`psutil.net_connections()`).
- Hasilnya: angka MB/s yang kamu lihat adalah **byte sungguhan dari
  NIC**, sama akurasinya dengan Task Manager / GlassWire / NetLimiter.

**Ini butuh instalasi Npcap satu kali** — lihat langkah instalasi di
bawah. Jika Npcap belum terinstall, aplikasi otomatis jatuh ke mode
fallback (kurang akurat, ada peringatan ⚠ di footer) supaya tetap bisa
dipakai sambil kamu install Npcap.

### 3. Arahan: file apa saja yang diubah

Kalau kamu pernah copy project versi sebelumnya secara manual dan ingin
tahu bagian mana yang perlu diganti, ini daftarnya:

| File | Status | Apa yang berubah |
|---|---|---|
| `core/net_engine.py` | **Ganti total** | Engine diganti dari proxy `io_counters()` ke packet capture (scapy+Npcap), plus ditambah sistem kategori aplikasi (`classify_app`, `CATEGORY_RULES`) |
| `core/worker.py` | **Diubah** | `CrossPlatformSampler` sekarang dibuat di dalam thread worker (bukan main thread) supaya sniffing tidak mengganggu UI; tambah signal `mode_ready` |
| `core/app_model.py` | **Diubah kecil** | `AppState` punya field `category` baru, di-set dari sample |
| `ui/main_window.py` | **Ganti total** | Struktur UI diubah dari 1 tabel dinamis menjadi 2 tab: "Semua Aplikasi" (statis per kategori) dan "🏆 Top Ranking" (dinamis dengan dropdown) |
| `ui/theme.py` | **Ditambah** | Style baru untuk tab widget, header kategori, dan hint text |
| `requirements.txt` | **Ditambah 1 baris** | Tambah `scapy>=2.5.0` |
| `core/formatters.py` | Tidak berubah | — |
| `ui/widgets.py` | Tidak berubah | — |
| `main.py` | Tidak berubah | — |

**Kalau kamu mulai dari nol** (extract ulang folder ini), tidak perlu
peduli tabel di atas — tinggal pakai semua file yang ada di sini, semua
sudah saling kompatibel.

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
