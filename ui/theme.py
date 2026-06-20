"""
theme.py
========
Token desain & stylesheet (QSS) terpusat untuk seluruh aplikasi.

KONSEP DESAIN: "PULSE"
-----------------------
Bukan sekadar dark+red generik. Identitas visual diturunkan dari subjek
aslinya: monitor jaringan = radar/pulse/sinyal yang hidup. Maka:
  - Warna dasar nyaris hitam dengan tone kebiruan gelap (bukan abu netral
    polos) supaya terasa seperti panel teknis/command-center, mengingatkan
    pada Steam tapi dengan karakter sendiri.
  - Merah bukan dipakai rata di semua tempat, tapi sebagai sinyal hidup:
    accent utama, live indicator berdenyut, dan highlight pada baris yang
    sedang aktif transfer data besar.
  - Signature element: setiap baris aplikasi punya "pulse dot" kecil di
    kiri nama yang mengindikasikan ada-tidaknya aktivitas network real-time
    (menyala/redup), seperti indikator sinyal radar.
  - Tipografi: Segoe UI Variable (native Windows 11) untuk UI umum,
    dan Consolas/JetBrains-style monospace KHUSUS untuk angka bandwidth,
    supaya angka tidak "loncat-loncat" lebarnya saat berubah tiap detik
    (penting untuk keterbacaan real-time).

PALET WARNA (named hex):
  bg_void      #0A0B0E   - latar utama, hitam-kebiruan pekat
  bg_panel     #14161B   - panel/card
  bg_panel_alt #1B1E25   - panel hover / row alternating
  border_soft  #262932   - garis pembatas halus
  red_signal   #E63946   - merah utama (accent, live indicator)
  red_glow     #FF4D5E   - merah lebih terang (hover/active state)
  red_dim      #5C1A22   - merah redup (background highlight halus)
  text_primary #F2F3F5   - teks utama
  text_muted   #8B8F99   - teks sekunder/caption
  green_up     #3DDC84   - indikator upload (kontras dgn merah download)
  amber_warn   #FFB020   - peringatan/unknown app
"""

COLORS = {
    "bg_void": "#0A0B0E",
    "bg_panel": "#14161B",
    "bg_panel_alt": "#1B1E25",
    "bg_panel_hover": "#20232B",
    "border_soft": "#262932",
    "border_strong": "#34384280".replace("80", ""),  # fallback safety
    "red_signal": "#E63946",
    "red_glow": "#FF4D5E",
    "red_dim": "#5C1A22",
    "red_dim_bg": "#2A1216",
    "text_primary": "#F2F3F5",
    "text_secondary": "#C4C7CE",
    "text_muted": "#8B8F99",
    "text_faint": "#5A5E68",
    "green_up": "#3DDC84",
    "amber_warn": "#FFB020",
}

FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"

QSS = f"""
* {{
    outline: none;
}}

QWidget {{
    background-color: {COLORS['bg_void']};
    color: {COLORS['text_primary']};
    font-family: "{FONT_UI}";
    font-size: 13px;
}}

QMainWindow {{
    background-color: {COLORS['bg_void']};
}}

/* ---------- Top bar ---------- */
#TopBar {{
    background-color: {COLORS['bg_panel']};
    border-bottom: 1px solid {COLORS['border_soft']};
}}

#AppTitle {{
    color: {COLORS['text_primary']};
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 1px;
}}

#AppSubtitle {{
    color: {COLORS['text_muted']};
    font-size: 11px;
}}

#LiveBadge {{
    background-color: {COLORS['red_dim_bg']};
    color: {COLORS['red_glow']};
    border: 1px solid {COLORS['red_signal']};
    border-radius: 9px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

/* ---------- Summary cards ---------- */
#SummaryCard {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border_soft']};
    border-radius: 10px;
}}

#SummaryCard:hover {{
    border: 1px solid {COLORS['red_dim']};
}}

#SummaryLabel {{
    color: {COLORS['text_muted']};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}}

#SummaryValue {{
    font-family: "{FONT_MONO}";
    font-size: 24px;
    font-weight: 700;
    color: {COLORS['text_primary']};
}}

#SummaryValueDown {{
    font-family: "{FONT_MONO}";
    font-size: 24px;
    font-weight: 700;
    color: {COLORS['red_glow']};
}}

#SummaryValueUp {{
    font-family: "{FONT_MONO}";
    font-size: 24px;
    font-weight: 700;
    color: {COLORS['green_up']};
}}

/* ---------- Search & filter ---------- */
#SearchBox {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border_soft']};
    border-radius: 8px;
    padding: 8px 14px;
    color: {COLORS['text_primary']};
    font-size: 13px;
}}

#SearchBox:focus {{
    border: 1px solid {COLORS['red_signal']};
}}

QComboBox {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border_soft']};
    border-radius: 8px;
    padding: 7px 12px;
    color: {COLORS['text_secondary']};
}}

QComboBox:hover {{
    border: 1px solid {COLORS['red_dim']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_panel_alt']};
    border: 1px solid {COLORS['border_soft']};
    selection-background-color: {COLORS['red_dim_bg']};
    selection-color: {COLORS['red_glow']};
    color: {COLORS['text_secondary']};
    outline: none;
}}

/* ---------- Table / app list ---------- */
QTableWidget {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border_soft']};
    border-radius: 10px;
    gridline-color: transparent;
    selection-background-color: {COLORS['red_dim_bg']};
}}

QTableWidget::item {{
    padding: 6px;
    border-bottom: 1px solid {COLORS['border_soft']};
}}

QTableWidget::item:selected {{
    background-color: {COLORS['red_dim_bg']};
    color: {COLORS['text_primary']};
}}

QHeaderView::section {{
    background-color: {COLORS['bg_panel']};
    color: {COLORS['text_muted']};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    padding: 10px 6px;
    border: none;
    border-bottom: 2px solid {COLORS['border_soft']};
}}

QTableWidget QScrollBar:vertical {{
    background: {COLORS['bg_panel']};
    width: 10px;
    border-radius: 5px;
}}

QTableWidget QScrollBar::handle:vertical {{
    background: {COLORS['border_soft']};
    border-radius: 5px;
    min-height: 24px;
}}

QTableWidget QScrollBar::handle:vertical:hover {{
    background: {COLORS['red_dim']};
}}

QTableWidget QScrollBar::add-line:vertical, QTableWidget QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* ---------- Detail panel ---------- */
#DetailPanel {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border_soft']};
    border-radius: 10px;
}}

#DetailAppName {{
    font-size: 16px;
    font-weight: 700;
    color: {COLORS['text_primary']};
}}

#DetailAppPath {{
    font-size: 10px;
    color: {COLORS['text_faint']};
}}

#StatChip {{
    background-color: {COLORS['bg_panel_alt']};
    border: 1px solid {COLORS['border_soft']};
    border-radius: 8px;
}}

#StatChipLabel {{
    color: {COLORS['text_muted']};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

#StatChipValue {{
    font-family: "{FONT_MONO}";
    color: {COLORS['text_primary']};
    font-size: 15px;
    font-weight: 700;
}}

/* ---------- Buttons ---------- */
QPushButton {{
    background-color: {COLORS['bg_panel_alt']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border_soft']};
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {COLORS['bg_panel_hover']};
    border: 1px solid {COLORS['red_dim']};
    color: {COLORS['text_primary']};
}}

QPushButton:pressed {{
    background-color: {COLORS['red_dim_bg']};
}}

#PrimaryButton {{
    background-color: {COLORS['red_signal']};
    color: #FFFFFF;
    border: none;
}}

#PrimaryButton:hover {{
    background-color: {COLORS['red_glow']};
}}

/* ---------- Tabs (sort/filter pills) ---------- */
#FilterPill {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border_soft']};
    border-radius: 14px;
    padding: 5px 14px;
    color: {COLORS['text_muted']};
    font-size: 12px;
    font-weight: 600;
}}

#FilterPillActive {{
    background-color: {COLORS['red_dim_bg']};
    border: 1px solid {COLORS['red_signal']};
    border-radius: 14px;
    padding: 5px 14px;
    color: {COLORS['red_glow']};
    font-size: 12px;
    font-weight: 600;
}}

QToolTip {{
    background-color: {COLORS['bg_panel_alt']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border_soft']};
    padding: 6px;
    border-radius: 6px;
}}

QSplitter::handle {{
    background-color: {COLORS['border_soft']};
}}

#StatusFooter {{
    background-color: {COLORS['bg_panel']};
    border-top: 1px solid {COLORS['border_soft']};
    color: {COLORS['text_faint']};
    font-size: 10.5px;
}}
"""
