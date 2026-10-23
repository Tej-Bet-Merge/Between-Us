"""UI Theme styling and stylesheet for PySide6 desktop application."""
from __future__ import annotations

MAIN_STYLE_SHEET = """
QMainWindow, QWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #334155;
    background: #1e293b;
    border-radius: 8px;
    padding: 10px;
}

QTabBar::tab {
    background: #1e293b;
    color: #94a3b8;
    padding: 10px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #38bdf8;
    color: #0f172a;
}

QTabBar::tab:hover:!selected {
    background: #334155;
    color: #f8fafc;
}

QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3b82f6;
}

QPushButton:pressed {
    background-color: #1d4ed8;
}

QPushButton:disabled {
    background-color: #334155;
    color: #64748b;
}

QPushButton.secondary {
    background-color: #334155;
    color: #f8fafc;
}

QPushButton.secondary:hover {
    background-color: #475569;
}

QPushButton.danger {
    background-color: #dc2626;
}

QPushButton.danger:hover {
    background-color: #ef4444;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 12px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #38bdf8;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QProgressBar {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    text-align: center;
    color: #f8fafc;
    font-weight: 600;
    height: 20px;
}

QProgressBar::chunk {
    background-color: #38bdf8;
    border-radius: 5px;
}

QTableWidget {
    background-color: #1e293b;
    color: #f8fafc;
    gridline-color: #334155;
    border: 1px solid #334155;
    border-radius: 6px;
}

QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    font-weight: 600;
    padding: 8px;
    border: 1px solid #334155;
}

QTextEdit, QPlainTextEdit {
    background-color: #131c2e;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 12px;
}

QScrollBar:vertical {
    background: #0f172a;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 15px;
    padding-top: 15px;
    font-weight: 600;
    color: #38bdf8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #475569;
    background: #1e293b;
}

QCheckBox::indicator:checked {
    background: #38bdf8;
    border: 1px solid #38bdf8;
}
"""
