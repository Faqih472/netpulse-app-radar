"""
main.py
=======
Entry point. Jalankan dengan:  python main.py

Di Windows, untuk akurasi terbaik (agar bisa membaca koneksi/IO milik
proses lain), jalankan terminal sebagai Administrator sebelum
menjalankan script ini. Tanpa admin, app tetap berjalan tapi beberapa
proses sistem mungkin tidak terbaca (AccessDenied akan otomatis
di-skip, bukan error fatal).
"""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
