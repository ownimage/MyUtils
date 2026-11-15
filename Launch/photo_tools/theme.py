"""The palette and accent styles used by every window and dialog."""

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


BASE_STYLE = Path(__file__).with_name('base.qss').read_text(encoding='utf-8')
EXTRA_STYLE = '''
    QMenuBar { background: #f4f6f5; padding: 5px 18px; }
    QMenuBar::item { padding: 6px 12px; border-radius: 4px; }
    QMenuBar::item:selected, QMenu::item:selected { background: #d4eae1; color: #163e32; }
    QMenu { background: white; border: 1px solid #d4dfd9; padding: 5px; }
    QMenu::item { padding: 7px 32px 7px 14px; }
    QStackedWidget, QWidget#home { background: #f4f6f5; }
    QPushButton#tile { text-align: left; border-radius: 12px; background: white; }
    QPushButton#tile:hover { background: #e8f1eb; border-color: #24745d; }
    QPushButton#tile:focus { border: 2px solid #24745d; }
    QLabel#tileTitle { font-size: 19pt; font-weight: 600; }
    QLabel#tileNumber { font-size: 11pt; font-weight: 600; color: #24745d; }
    QLabel#tileLaunch { color: #24745d; font-weight: 600; }
    QLabel#subtitle { font-size: 11pt; color: #64756f; }
    QLabel#chip { padding: 5px 10px; background: #e8f1eb; border-radius: 5px; color: #24745d; }
    QTabWidget::pane { border: 1px solid #d4dfd9; background: white; border-radius: 6px; }
    QTabBar::tab { padding: 10px 22px; background: #eaf0ec; }
    QTabBar::tab:selected { background: white; border-bottom: 2px solid #24745d; }
    QListWidget { background: white; border: 1px solid #d4dfd9; border-radius: 5px; padding: 5px; }
    QListWidget::item { padding: 13px 10px; }
    QListWidget::item:selected { background: #d4eae1; color: #163e32; }
    QCheckBox { spacing: 9px; }
    QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #94a29b; border-radius: 3px; background: white; }
    QCheckBox::indicator:checked { background: #246b53; border: 2px solid #246b53; image: none; }
    QScrollBar:vertical { background: #edf1ee; width: 12px; }
    QScrollBar::handle:vertical { background: #94a29b; min-height: 22px; border-radius: 4px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
'''


def _mix(first, second, amount):
    a, b = QColor(first), QColor(second)
    return QColor(*(round(x * (1 - amount) + y * amount) for x, y in
                    zip((a.red(), a.green(), a.blue()), (b.red(), b.green(), b.blue())))).name()


def _foreground(background):
    color = QColor(background)
    channels = [channel / 255 for channel in (color.red(), color.green(), color.blue())]
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
              for value in channels]
    luminance = sum(x * weight for x, weight in zip(linear, (.2126, .7152, .0722)))
    return '#ffffff' if (luminance + .05) / .05 < 1.05 / (luminance + .05) else '#111111'


def _wash_color(base, accent):
    """Give the whole neutral palette the chosen hue, preserving its lightness."""
    base, accent = QColor(base), QColor(accent)
    saturation_scale = accent.hslSaturationF() / QColor('#246b53').hslSaturationF()
    saturation = min(.65, base.hslSaturationF() * saturation_scale)
    hue = max(0., accent.hslHueF())
    return QColor.fromHslF(hue, saturation, base.lightnessF()).name()


def apply_theme(window, appearance='system', accent='#246b53'):
    system_dark = getattr(window, '_system_is_dark', lambda:
        QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
    dark = appearance == 'dark' or (appearance == 'system' and system_dark())
    dark_colors = {
        '#f4f6f5': '#151d19', '#233a35': '#e2eee7', '#507269': '#9cbcad',
        '#64756f': '#a6b9ae', 'white': '#202a25', '#dce5e0': '#38483e',
        '#d4dfd9': '#43554a', '#d4eae1': '#365c49', '#163e32': '#f1fff7',
        '#24745d': '#83d5b1', '#f6f9f7': '#253129', '#edf1ef': '#334238',
        '#eaf0ec': '#2c3b31', '#cbd9d1': '#4b5f51', '#e8f1eb': '#304337',
        '#d5e8dd': '#3c5444', '#94a29b': '#82958a', '#edf1ee': '#27342b',
        '#dfe6e1': '#394b3f', '#8da899': '#8da899', '#dce7df': '#2c4033',
        '#dfe8e2': '#34483b', '#328267': '#66bd96',
    }
    accent = QColor(accent).name()
    # All the original green-tinted surfaces, borders, text, and disabled states
    # use the accent's hue. Lightness stays stable so changing hue keeps contrast.
    source_colors = set(re.findall(r'#[0-9a-fA-F]{6}', BASE_STYLE + EXTRA_STYLE)) | {'white'}
    colors = {source: _wash_color(dark_colors.get(source, source) if dark else source, accent)
              for source in source_colors}
    active = _wash_color('#83d5b1' if dark else '#24745d', accent)
    selection = _mix(accent, colors['#f4f6f5'], .74 if dark else .86)
    colors.update({'#246b53': accent, '#19553f': _mix(accent, '#000000', .2),
                   '#24745d': active, '#328267': active,
                   '#d4eae1': selection, '#163e32': colors['#233a35']})
    palette = QPalette(window.palette())
    for role, value in {
        QPalette.ColorRole.Window: '#f4f6f5', QPalette.ColorRole.WindowText: '#233a35',
        QPalette.ColorRole.Base: 'white', QPalette.ColorRole.AlternateBase: '#f6f9f7',
        QPalette.ColorRole.Text: '#233a35', QPalette.ColorRole.Button: 'white',
        QPalette.ColorRole.ButtonText: '#233a35', QPalette.ColorRole.Highlight: '#d4eae1',
        QPalette.ColorRole.HighlightedText: '#163e32', QPalette.ColorRole.Link: '#24745d',
        QPalette.ColorRole.PlaceholderText: '#64756f',
        QPalette.ColorRole.ToolTipBase: 'white', QPalette.ColorRole.ToolTipText: '#233a35',
    }.items():
        palette.setColor(role, QColor(colors.get(value, value)))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors.get('#94a29b', '#94a29b')))
    stylesheet = re.sub(r'#[0-9a-fA-F]{6}|(?<=background: )white',
                        lambda match: colors.get(match[0], match[0]), BASE_STYLE + EXTRA_STYLE)
    # Use the more readable text color for any accent, including pale custom colors.
    stylesheet += f'\nQPushButton#primary {{ color: {_foreground(accent)}; }}'
    window.setStyleSheet(stylesheet)
    window.setPalette(palette)
    return dark
