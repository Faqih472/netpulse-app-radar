# NetPulse — Real-Time Per-App Bandwidth Monitor

Aplikasi desktop Windows untuk memantau pemakaian bandwidth tiap aplikasi
yang berjalan, secara real-time (update setiap 1 detik). Desain dark
theme dengan accent merah, terinspirasi tampilan command-center seperti
Steam, dengan signature elemen "pulse dot" yang berdenyut saat aplikasi
sedang aktif mengirim/menerima data.

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

## ⚠️ Catatan Penting Soal Akurasi Data

Windows **tidak punya API publik** yang langsung memberi "berapa byte
network per proses per detik" tanpa salah satu dari:

1. **Packet capture driver** (Npcap/WinDivert) — butuh instalasi
   terpisah, perlu admin, lebih berat di sistem.
2. **ETW (Event Tracing for Windows)** session khusus network — jauh
   lebih kompleks untuk disetup & didistribusikan ke orang lain.

Supaya aplikasi ini **ringan, tidak perlu install driver tambahan, dan
langsung jalan**, NetPulse memakai pendekatan yang sama dengan banyak
tool monitoring ringan lainnya:

> `psutil.Process.io_counters()` (read_bytes/write_bytes) sebagai proxy
> aktivitas I/O, **hanya untuk proses yang terbukti punya koneksi
> jaringan aktif** (dicek lewat `psutil.net_connections()`).

Artinya:
- Untuk aplikasi yang memang aktif network (browser sedang download,
  game online, app streaming), angka yang ditampilkan **sangat
  representatif** dan mengikuti pola asli naik-turun bandwidth-nya.
- `io_counters()` di Windows menggabungkan I/O disk + network dalam satu
  angka. Jadi kalau sebuah app **kebetulan** menulis file besar ke disk
  di waktu yang sama saat network-nya idle, angkanya bisa sedikit bias
  (keliatan seperti pakai network padahal itu disk write).
- Aplikasi yang tidak punya koneksi socket terbuka sama sekali tidak
  akan muncul di daftar (karena memang tidak pakai internet).

**Kalau nanti kamu butuh akurasi byte-level murni dari NIC per
proses** (misal untuk keperluan yang lebih serius/profesional), upgrade
yang bisa dilakukan adalah mengintegrasikan **Npcap + scapy** untuk
packet sniffing sungguhan. Versi ini sengaja tidak memakai itu supaya
instalasinya simpel — tinggal `pip install` dan jalan, tanpa driver
eksternal.

---

## Instalasi (Windows)

1. **Install Python 3.10+** kalau belum ada — download dari
   [python.org](https://www.python.org/downloads/). Saat instalasi,
   centang "Add Python to PATH".

2. **Buka folder project ini** di Command Prompt / PowerShell:
   ```bash
   cd path\ke\netmonitor
   ```

3. **(Opsional tapi disarankan)** buat virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Jalankan aplikasi:**
   ```bash
   python main.py
   ```

### Untuk hasil terbaik: jalankan sebagai Administrator

Tanpa hak admin, Windows membatasi `psutil.net_connections()` sehingga
sebagian proses (terutama proses sistem) mungkin tidak terbaca dan
tidak akan muncul di daftar. Aplikasi tetap berjalan normal, hanya
datanya jadi kurang lengkap.

Cara jalankan sebagai admin:
- Buka **Command Prompt** atau **PowerShell**, klik kanan → **Run as
  Administrator**.
- Lalu jalankan langkah 2–5 di atas seperti biasa dari situ.

---

## Struktur Project

```
netmonitor/
├── main.py                 # entry point — jalankan ini
├── requirements.txt
├── core/
│   ├── net_engine.py       # pengambilan data bandwidth per-proses
│   ├── worker.py           # QThread background sampler (1x/detik)
│   ├── app_model.py        # state & history per aplikasi
│   └── formatters.py       # format angka (B/s, KB/s, MB/s, dst)
└── ui/
    ├── main_window.py      # jendela utama
    ├── theme.py            # palet warna & stylesheet (QSS)
    └── widgets.py          # pulse dot & sparkline custom widget
```

---

## Build jadi .exe (opsional)

Kalau mau dijadikan file `.exe` standalone supaya tidak perlu install
Python di komputer lain:

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name NetPulse main.py
```

Hasilnya ada di folder `dist/NetPulse.exe`. Untuk ikon custom, tambahkan
flag `--icon=assets/icon.ico`.

---

## Troubleshooting

| Masalah | Solusi |
|---|---|
| Banyak aplikasi tidak muncul di daftar | Jalankan sebagai Administrator |
| Angka terasa "kasar"/tidak presisi untuk app tertentu | Lihat bagian "Catatan Penting Soal Akurasi Data" di atas — ini batasan `io_counters()`, bukan bug |
| App lag / CPU tinggi saat banyak proses | Wajar bila ada 100+ proses aktif tersampling tiap detik; bisa naikkan interval di `main.py` → `SamplerWorker(interval_sec=2.0)` |
| `ModuleNotFoundError` saat run | Pastikan sudah `pip install -r requirements.txt` di environment yang sama dengan yang dipakai `python main.py` |
