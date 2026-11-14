"""Application theme stylesheets."""

from __future__ import annotations
from pathlib import Path
import sys


LIGHT_THEME = """
QWidget {
    color: #17202a;
    font-family: "Segoe UI";
    font-size: 10.5pt;
}
QMainWindow, QStackedWidget {
    background: #f5f7fb;
}
QFrame#card, QGroupBox#card {
    background: #ffffff;
    border: 1px solid #d9dee8;
    border-radius: 8px;
}
QFrame#selectedCard {
    background: #eef4ff;
    border: 2px solid #2563eb;
    border-radius: 8px;
}
QFrame#warningPanel {
    background: #fff7ed;
    border: 1px solid #fb923c;
    border-radius: 8px;
}
QLabel#heroTitle {
    font-size: 26pt;
    font-weight: 700;
    color: #111827;
}
QLabel#sectionTitle {
    font-size: 16pt;
    font-weight: 650;
    color: #111827;
}
QLabel#mutedLabel {
    color: #5f6c7b;
}
QLabel#statusLabel {
    background: #eef4ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    color: #1e3a8a;
    padding: 10px 12px;
}
QLabel#recommendedLabel {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    border-radius: 6px;
    color: #065f46;
    padding: 8px;
}
QLabel#metricValue {
    font-weight: 650;
    color: #111827;
}
QFrame#thumbnailFrame {
    background: #ffffff;
    border: 1px solid #d9dee8;
    border-radius: 8px;
}
QLabel#thumbnailLabel {
    background: #eef1f6;
    border: 1px solid #d9dee8;
    border-radius: 6px;
    color: #5f6c7b;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #cfd7e6;
    border-radius: 7px;
    padding: 9px 14px;
}
QPushButton:hover {
    background: #edf2fb;
}
QToolButton, QMenu {
    background: #ffffff;
    border: 1px solid #cfd7e6;
    border-radius: 6px;
    padding: 6px;
}
QMenu::item:selected { background: #dbeafe; color: #17202a; }
QPushButton:disabled {
    color: #8a94a6;
    background: #eef1f6;
}
QPushButton#primaryButton {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
    font-weight: 650;
}
QPushButton#primaryButton:hover {
    background: #1d4ed8;
}
QPushButton#dangerButton {
    background: #dc2626;
    border-color: #dc2626;
    color: #ffffff;
    font-weight: 650;
}
QPushButton#dangerButton:hover {
    background: #b91c1c;
}
QPushButton#primaryButton:disabled, QPushButton#dangerButton:disabled {
    background: #eef1f6;
    border-color: #cfd7e6;
    color: #697586;
}
QCheckBox {
    spacing: 10px;
    padding: 8px 4px;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #64748b;
    border-radius: 4px;
    background: #ffffff;
}
QCheckBox::indicator:hover {
    border-color: #2563eb;
}
QCheckBox::indicator:checked {
    image: url("__CHECKMARK__");
    background: #2563eb;
    border-color: #1d4ed8;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget, QListWidget {
    background: #ffffff;
    border: 1px solid #cfd7e6;
    border-radius: 6px;
    padding: 6px;
}
QTableWidget {
    gridline-color: #e5e9f2;
    selection-background-color: #dbeafe;
    selection-color: #17202a;
    alternate-background-color: #f7f9fc;
}
QTableCornerButton::section { background: #eef1f6; border: 0; }
QScrollArea {
    border: 0;
    background: transparent;
}
QHeaderView::section {
    background: #eef1f6;
    border: 0;
    border-bottom: 1px solid #d9dee8;
    padding: 7px;
    font-weight: 650;
}
QProgressBar {
    border: 1px solid #cfd7e6;
    border-radius: 7px;
    height: 20px;
    text-align: center;
    background: #ffffff;
}
QProgressBar::chunk {
    border-radius: 6px;
    background: #2563eb;
}
"""


DARK_THEME = """
QWidget {
    color: #f9fafb;
    font-family: "Segoe UI";
    font-size: 10.5pt;
}
QMainWindow, QStackedWidget {
    background: #111827;
}
QFrame#card, QGroupBox#card {
    background: #1f2937;
    border: 1px solid #374151;
    border-radius: 8px;
}
QFrame#selectedCard {
    background: #1e3a5f;
    border: 2px solid #60a5fa;
    border-radius: 8px;
}
QFrame#warningPanel {
    background: #3b2415;
    border: 1px solid #fb923c;
    border-radius: 8px;
}
QLabel#heroTitle {
    font-size: 26pt;
    font-weight: 700;
    color: #ffffff;
}
QLabel#sectionTitle {
    font-size: 16pt;
    font-weight: 650;
    color: #ffffff;
}
QLabel#mutedLabel {
    color: #9ca3af;
}
QLabel#statusLabel {
    background: #172554;
    border: 1px solid #1d4ed8;
    border-radius: 8px;
    color: #dbeafe;
    padding: 10px 12px;
}
QLabel#recommendedLabel {
    background: #063c2b;
    border: 1px solid #047857;
    border-radius: 6px;
    color: #bbf7d0;
    padding: 8px;
}
QLabel#metricValue {
    font-weight: 650;
    color: #ffffff;
}
QFrame#thumbnailFrame {
    background: #1f2937;
    border: 1px solid #374151;
    border-radius: 8px;
}
QLabel#thumbnailLabel {
    background: #111827;
    border: 1px solid #374151;
    border-radius: 6px;
    color: #9ca3af;
}
QPushButton {
    background: #1f2937;
    border: 1px solid #4b5563;
    border-radius: 7px;
    padding: 9px 14px;
}
QPushButton:hover {
    background: #263244;
}
QToolButton, QMenu {
    background: #1f2937;
    border: 1px solid #4b5563;
    border-radius: 6px;
    padding: 6px;
}
QMenu::item:selected { background: #1e40af; color: #f9fafb; }
QPushButton:disabled {
    color: #6b7280;
    background: #1b2330;
}
QPushButton#primaryButton {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
    font-weight: 650;
}
QPushButton#primaryButton:hover {
    background: #1d4ed8;
}
QPushButton#dangerButton {
    background: #dc2626;
    border-color: #dc2626;
    color: #ffffff;
    font-weight: 650;
}
QPushButton#dangerButton:hover {
    background: #b91c1c;
}
QPushButton#primaryButton:disabled, QPushButton#dangerButton:disabled {
    background: #1b2330;
    border-color: #374151;
    color: #9ca3af;
}
QCheckBox {
    spacing: 10px;
    padding: 8px 4px;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #94a3b8;
    border-radius: 4px;
    background: #111827;
}
QCheckBox::indicator:hover {
    border-color: #60a5fa;
}
QCheckBox::indicator:checked {
    image: url("__CHECKMARK__");
    background: #60a5fa;
    border-color: #93c5fd;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget, QListWidget {
    background: #1f2937;
    border: 1px solid #4b5563;
    border-radius: 6px;
    padding: 6px;
    color: #f9fafb;
}
QTableWidget {
    gridline-color: #374151;
    selection-background-color: #1e40af;
    selection-color: #f9fafb;
    alternate-background-color: #263244;
}
QTableCornerButton::section { background: #263244; border: 0; }
QScrollArea {
    border: 0;
    background: transparent;
}
QHeaderView::section {
    background: #263244;
    border: 0;
    border-bottom: 1px solid #374151;
    padding: 7px;
    font-weight: 650;
}
QProgressBar {
    border: 1px solid #4b5563;
    border-radius: 7px;
    height: 20px;
    text-align: center;
    background: #1f2937;
}
QProgressBar::chunk {
    border-radius: 6px;
    background: #60a5fa;
}
"""


def stylesheet_for_theme(theme_name: str | None) -> str:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    checkmark = (root / "assets" / "checkmark.svg").as_posix()
    theme = DARK_THEME if (theme_name or "").lower() == "dark" else LIGHT_THEME
    return theme.replace("__CHECKMARK__", checkmark)
