"""
FFX Downgrader — PySide6 GUI
Recursively finds .ffx files in the input folder (including subfolders),
downgrades them to a chosen After Effects version, and writes them to the
output folder while preserving the original directory structure.
"""

import os
import sys
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QIcon, QColor, QPalette, QPixmap, QPainter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar,
    QTextEdit, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QSizePolicy, QMessageBox, QCheckBox,
)

# ── Version map (same as Main.py) ──────────────────────────────────────────
VERSION_MAP = {
    2025: 0x60,
    2024: 0x5F,
    2023: 0x5E,
    2022: 0x5D,
}
REVERSE_MAP = {v: k for k, v in VERSION_MAP.items()}


# ── Worker thread ──────────────────────────────────────────────────────────
class DowngradeWorker(QThread):
    """Runs the downgrade work off the main/UI thread."""
    log = Signal(str)           # text message
    progress = Signal(int)      # 0‥100
    finished_signal = Signal(int, int)   # (success_count, fail_count)

    def __init__(self, input_dir: str, output_dir: str, target_year: int, copy_folders: bool = True):
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.target_year = target_year
        self.copy_folders = copy_folders
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    # ── core logic ────────────────────────────────────────────────────────
    def run(self):
        input_path = Path(self.input_dir)
        output_path = Path(self.output_dir)
        target_byte = VERSION_MAP[self.target_year]

        # Collect every .ffx under input_path
        ffx_files = list(input_path.rglob("*.ffx"))
        total = len(ffx_files)

        if total == 0:
            self.log.emit("⚠  No .ffx files found in the input folder.")
            self.finished_signal.emit(0, 0)
            return

        self.log.emit(f"Found {total} .ffx file(s).  Target → AE {self.target_year}\n")

        success = 0
        failed = 0

        for idx, ffx in enumerate(ffx_files, start=1):
            if self._cancelled:
                self.log.emit("\n⛔  Cancelled by user.")
                break

            relative = ffx.relative_to(input_path)
            if self.copy_folders:
                dest = output_path / relative
            else:
                # Flat mode: all files go directly into output root
                dest = output_path / ffx.name
                # Handle name collisions by appending a counter
                if dest.exists() and dest != ffx:
                    stem = ffx.stem
                    suffix = ffx.suffix
                    counter = 1
                    while dest.exists():
                        dest = output_path / f"{stem}_{counter}{suffix}"
                        counter += 1

            try:
                # Read
                data = bytearray(ffx.read_bytes())

                # Validate header
                if data[0:4] != b"RIFX":
                    self.log.emit(f"  ✗  {relative}  — not a valid FFX (bad header)")
                    failed += 1
                    self.progress.emit(int(idx / total * 100))
                    continue

                # Find & patch version byte
                patched = False
                for i in range(len(data)):
                    if data[i] in REVERSE_MAP:
                        current_year = REVERSE_MAP[data[i]]
                        if current_year > self.target_year:
                            data[i] = target_byte
                            patched = True
                            break

                if not patched:
                    # Already at or below target — just copy as-is
                    self.log.emit(f"  ↳  {relative}  — already ≤ AE {self.target_year}, copied as-is")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(ffx), str(dest))
                    success += 1
                    self.progress.emit(int(idx / total * 100))
                    continue

                # Write patched file
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)

                self.log.emit(f"  ✓  {relative}  → downgraded to AE {self.target_year}")
                success += 1

            except Exception as exc:
                self.log.emit(f"  ✗  {relative}  — {exc}")
                failed += 1

            self.progress.emit(int(idx / total * 100))

        self.log.emit(f"\n✅  Done — {success} succeeded, {failed} failed.")
        self.finished_signal.emit(success, failed)


# ── Stylesheet ─────────────────────────────────────────────────────────────
STYLESHEET = """
* {
    font-family: 'Segoe UI', 'Inter', sans-serif;
}

QMainWindow {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #0d0d1a, stop:1 #1a1a2e
    );
}

QLabel {
    color: #d0d0e0;
    font-size: 13px;
}

QLabel#title {
    font-size: 22px;
    font-weight: 700;
    color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #a78bfa, stop:1 #6ee7b7
    );
    /* gradient on text doesn't work in stylesheets — we set it via palette */
    color: #c4b5fd;
}

QLabel#subtitle {
    font-size: 12px;
    color: #777794;
    margin-bottom: 6px;
}

QLineEdit {
    background: #1e1e30;
    border: 1px solid #3a3a5c;
    border-radius: 8px;
    color: #e0e0f0;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #7c3aed;
}
QLineEdit:focus {
    border: 1px solid #7c3aed;
}

QPushButton {
    background: #2a2a44;
    color: #d0d0e0;
    border: 1px solid #3a3a5c;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background: #3a3a5c;
    border: 1px solid #7c3aed;
}
QPushButton:pressed {
    background: #7c3aed;
}
QPushButton:disabled {
    background: #1a1a2e;
    color: #555570;
    border: 1px solid #2a2a44;
}

QPushButton#startBtn {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #7c3aed, stop:1 #6d28d9
    );
    color: #ffffff;
    border: none;
    padding: 10px 32px;
    font-size: 14px;
    border-radius: 10px;
}
QPushButton#startBtn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #8b5cf6, stop:1 #7c3aed
    );
}
QPushButton#startBtn:pressed {
    background: #5b21b6;
}
QPushButton#startBtn:disabled {
    background: #2a2a44;
    color: #555570;
}

QPushButton#cancelBtn {
    background: #7f1d1d;
    color: #fca5a5;
    border: none;
    padding: 10px 24px;
    font-size: 14px;
    border-radius: 10px;
}
QPushButton#cancelBtn:hover {
    background: #991b1b;
}

QComboBox {
    background: #1e1e30;
    border: 1px solid #3a3a5c;
    border-radius: 8px;
    color: #e0e0f0;
    padding: 7px 12px;
    font-size: 13px;
    min-width: 140px;
}
QComboBox:focus {
    border: 1px solid #7c3aed;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #7c3aed;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background: #1e1e30;
    border: 1px solid #3a3a5c;
    color: #e0e0f0;
    selection-background-color: #7c3aed;
    outline: none;
}

QProgressBar {
    background: #1e1e30;
    border: 1px solid #3a3a5c;
    border-radius: 8px;
    text-align: center;
    color: #c4b5fd;
    font-size: 12px;
    height: 22px;
}
QProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #7c3aed, stop:1 #6ee7b7
    );
    border-radius: 7px;
}

QTextEdit {
    background: #12121f;
    border: 1px solid #2a2a44;
    border-radius: 10px;
    color: #a0a0c0;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
    padding: 10px;
    selection-background-color: #7c3aed;
}

QFrame#card {
    background: rgba(26, 26, 46, 200);
    border: 1px solid #2a2a44;
    border-radius: 14px;
}

QCheckBox {
    color: #d0d0e0;
    font-size: 13px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #3a3a5c;
    background: #1e1e30;
}
QCheckBox::indicator:hover {
    border: 2px solid #7c3aed;
}
QCheckBox::indicator:checked {
    background: #7c3aed;
    border: 2px solid #7c3aed;
    image: none;
}
"""


# ── Main window ────────────────────────────────────────────────────────────
class FFXDowngraderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FFX Downgrader")
        self.setMinimumSize(680, 620)
        self.resize(740, 680)
        self.setStyleSheet(STYLESHEET)

        self.worker: DowngradeWorker | None = None

        # ── Central widget ────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(16)

        # ── Title ─────────────────────────────────────────────────────────
        title = QLabel("FFX Downgrader")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        root_layout.addWidget(title)

        subtitle = QLabel("Batch-downgrade After Effects .ffx presets to an older version")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        root_layout.addWidget(subtitle)

        # ── Card frame ────────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(14)

        # ── Input folder ──────────────────────────────────────────────────
        card_layout.addWidget(self._section_label("Input Folder"))
        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Path to folder containing .ffx files…")
        input_browse = QPushButton("Browse")
        input_browse.clicked.connect(self._browse_input)
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(input_browse)
        card_layout.addLayout(input_row)

        # ── Output folder ─────────────────────────────────────────────────
        card_layout.addWidget(self._section_label("Output Folder"))
        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Path where downgraded files will be saved…")
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self._browse_output)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(output_browse)
        card_layout.addLayout(output_row)

        # ── Target version ────────────────────────────────────────────────
        version_row = QHBoxLayout()
        version_row.addWidget(self._section_label("Target Version"))
        version_row.addStretch()
        self.version_combo = QComboBox()
        for year in sorted(VERSION_MAP.keys()):
            self.version_combo.addItem(f"After Effects {year}", year)
        self.version_combo.setCurrentIndex(1)  # default AE 2023
        version_row.addWidget(self.version_combo)
        card_layout.addLayout(version_row)

        # ── Copy folders toggle ───────────────────────────────────────────
        self.copy_folders_cb = QCheckBox("Copy folder structure into output")
        self.copy_folders_cb.setChecked(True)
        self.copy_folders_cb.setToolTip(
            "ON — subfolders are recreated inside the output folder.\n"
            "OFF — all .ffx files are placed flat in the output root."
        )
        card_layout.addWidget(self.copy_folders_cb)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(self.cancel_btn)

        self.start_btn = QPushButton("⚡  Start Downgrade")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.clicked.connect(self._start)
        btn_row.addWidget(self.start_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        # ── Progress ──────────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        card_layout.addWidget(self.progress_bar)

        root_layout.addWidget(card)

        # ── Log ───────────────────────────────────────────────────────────
        log_label = self._section_label("Log")
        root_layout.addWidget(log_label)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root_layout.addWidget(self.log_view, 1)

        # ── Drop shadow on card ───────────────────────────────────────────
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

    # ── Helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: 600; color: #a78bfa; font-size: 13px; margin-top: 2px;")
        return lbl

    def _browse_input(self):
        path = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if path:
            self.input_edit.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.output_edit.setText(path)

    def _log(self, msg: str):
        self.log_view.append(msg)

    # ── Start / Cancel ────────────────────────────────────────────────────
    def _start(self):
        input_dir = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()

        if not input_dir or not os.path.isdir(input_dir):
            QMessageBox.warning(self, "Invalid Input", "Please select a valid input folder.")
            return
        if not output_dir:
            QMessageBox.warning(self, "Invalid Output", "Please select an output folder.")
            return

        os.makedirs(output_dir, exist_ok=True)

        target_year = self.version_combo.currentData()
        self.progress_bar.setValue(0)
        self.log_view.clear()
        self._log(f"🔄  Scanning  {input_dir} …\n")

        self.start_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)

        copy_folders = self.copy_folders_cb.isChecked()
        self.worker = DowngradeWorker(input_dir, output_dir, target_year, copy_folders)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()

    def _on_finished(self, success: int, failed: int):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.worker = None


# ── Entry point ────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette base (Fusion adapts nicely)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0d0d1a"))
    palette.setColor(QPalette.WindowText, QColor("#d0d0e0"))
    palette.setColor(QPalette.Base, QColor("#12121f"))
    palette.setColor(QPalette.AlternateBase, QColor("#1a1a2e"))
    palette.setColor(QPalette.ToolTipBase, QColor("#1e1e30"))
    palette.setColor(QPalette.ToolTipText, QColor("#d0d0e0"))
    palette.setColor(QPalette.Text, QColor("#e0e0f0"))
    palette.setColor(QPalette.Button, QColor("#2a2a44"))
    palette.setColor(QPalette.ButtonText, QColor("#d0d0e0"))
    palette.setColor(QPalette.Highlight, QColor("#7c3aed"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    win = FFXDowngraderWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
