"""Offline Tabler Design icon selection; no network access at runtime."""
from functools import lru_cache
import json
from pathlib import Path
from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidgetItem, QLabel, QListWidget
from photo_tools.fluent import QLineEdit, QPushButton

ROOT = Path(__file__).resolve().parent/'assets'/'tabler'

@lru_cache(maxsize=1)
def entries():
    return json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))['icons']

@lru_cache(maxsize=1024)
def button_icon(reference, dark=False):
    if not reference.startswith('tabler:'):
        return QIcon(reference) if reference else QIcon()
    relative = reference[len('tabler:'):]
    allowed = {entry['path'] for entry in entries()}
    if relative not in allowed:
        return QIcon()
    svg = (ROOT/relative).read_bytes().replace(b'currentColor', b'#ffffff' if dark else b'#172d24')
    renderer = QSvgRenderer(QByteArray(svg))
    if not renderer.isValid():
        return QIcon()
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

class IconPicker(QDialog):
    def __init__(self, parent=None, *, dark=False):
        super().__init__(parent)
        self.reference = ''
        self.setWindowTitle('Tabler Design icons — offline library')
        self.resize(760, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Choose a Tabler Design icon'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search icons by name or keyword…')
        self.search.setAccessibleName('Search offline icons')
        layout.addWidget(self.search)
        self.grid = QListWidget()
        self.grid.setViewMode(self.grid.ViewMode.IconMode)
        self.grid.setResizeMode(self.grid.ResizeMode.Adjust)
        self.grid.setIconSize(QSize(32, 32))
        self.grid.setGridSize(QSize(124, 86))
        self.grid.setWordWrap(True)
        self.grid.setAccessibleName('Offline Tabler icons')
        for entry in entries():
            reference = 'tabler:'+entry['path']
            item = QListWidgetItem(button_icon(reference, dark), entry['name']+'\n'+entry['style'])
            item.setData(Qt.ItemDataRole.UserRole, reference)
            item.setData(Qt.ItemDataRole.UserRole+1, ' '.join(str(value) for value in [entry['name'], entry['style'], *entry['tags']]).lower())
            item.setToolTip(entry['name']+' ('+entry['style']+')')
            self.grid.addItem(item)
        layout.addWidget(self.grid, 1)
        self.search.textChanged.connect(self.filter)
        self.grid.itemDoubleClicked.connect(self.choose)
        actions = QHBoxLayout()
        actions.addWidget(QLabel('Tabler Icons 3.52.0 · MIT license · available offline'))
        actions.addStretch()
        select = QPushButton('Use Icon')
        select.clicked.connect(self.choose)
        actions.addWidget(select)
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        layout.addLayout(actions)

    def filter(self, query):
        words = query.lower().split()
        for index in range(self.grid.count()):
            item = self.grid.item(index)
            item.setHidden(not all(word in item.data(Qt.ItemDataRole.UserRole+1) for word in words))

    def choose(self, *_):
        item = self.grid.currentItem()
        if item is not None and not item.isHidden():
            self.reference = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
