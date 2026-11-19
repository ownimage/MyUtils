"""Manifest-discovered offline icon libraries; stable set/style/name references."""
from functools import lru_cache
import json
from pathlib import Path, PurePosixPath
from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidgetItem, QLabel, QListWidget, QStyledItemDelegate, QStyleOptionViewItem
from photo_tools.fluent import QLineEdit, QPushButton, QComboBox

ASSETS = Path(__file__).resolve().parent/'assets'
ROOT = ASSETS/'tabler'  # Compatibility for existing callers/tests.

@lru_cache(maxsize=1)
def libraries():
    result = {}
    for path in sorted(ASSETS.glob('*/manifest.json')):
        manifest = json.loads(path.read_text(encoding='utf-8'))
        slug = path.parent.name
        if manifest.get('id', slug) != slug:
            raise ValueError('Icon manifest ID does not match its directory.')
        result[slug] = dict(manifest, id=slug, label=manifest.get('label',slug.title()))
    return result

@lru_cache(maxsize=1)
def entries():
    result = []
    for slug, manifest in libraries().items():
        for entry in manifest['icons']:
            relative = entry['path']
            path = PurePosixPath(relative)
            if (path.is_absolute() or '..' in path.parts or ':' in relative
                    or chr(92) in relative or path.as_posix() != relative):
                raise ValueError('Icon manifest path escapes its library.')
            result.append(dict(entry, library=slug, library_label=manifest['label'],
                               reference=slug+':'+relative))
    if len({e['reference'] for e in result}) != len(result):
        raise ValueError('Duplicate icon IDs in library manifests.')
    return result

@lru_cache(maxsize=1)
def entry_index():
    return {entry['reference']:entry for entry in entries()}

@lru_cache(maxsize=1024)
def button_icon(reference, dark=False):
    entry = entry_index().get(reference)
    if entry is None:
        # Unknown namespaced references never become filesystem paths.
        if ':' in reference and not (len(reference)>2 and reference[1]==':'):
            return QIcon()
        return QIcon(reference) if reference else QIcon()
    path = ASSETS/entry['library']/entry['path']
    if not path.is_file():
        return QIcon()
    svg = path.read_bytes().replace(b'currentColor', b'#ffffff' if dark else b'#172d24')
    renderer = QSvgRenderer(QByteArray(svg))
    if not renderer.isValid():
        return QIcon()
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

class IconDelegate(QStyledItemDelegate):
    """Render only visible thumbnails; large sets do not render on opening."""
    def __init__(self, dark, parent=None):
        super().__init__(parent)
        self.dark = dark

    def initStyleOption(self, option, index):
        super().initStyleOption(option,index)
        option.icon = button_icon(index.data(Qt.ItemDataRole.UserRole), self.dark)
        option.features |= QStyleOptionViewItem.ViewItemFeature.HasDecoration
        option.decorationSize = QSize(32,32)

class IconPicker(QDialog):
    def __init__(self, parent=None, *, dark=False):
        super().__init__(parent)
        self.reference = ''
        self.setWindowTitle('Offline icon libraries')
        self.resize(760, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Choose an icon'))
        filters = QHBoxLayout()
        self.library = QComboBox()
        self.library.addItem('All libraries', '')
        for slug,manifest in libraries().items():
            self.library.addItem(manifest['label'],slug)
        self.style = QComboBox()
        self.style.addItem('All styles','')
        for style in sorted({e['style'] for e in entries()}):
            self.style.addItem(style.title(),style)
        filters.addWidget(self.library)
        filters.addWidget(self.style)
        layout.addLayout(filters)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search icons by name or keyword…')
        self.search.setAccessibleName('Search offline icons')
        layout.addWidget(self.search)
        self.grid = QListWidget()
        self.grid.setViewMode(self.grid.ViewMode.IconMode)
        self.grid.setResizeMode(self.grid.ResizeMode.Adjust)
        self.grid.setIconSize(QSize(32, 32))
        self.grid.setGridSize(QSize(166, 104))
        self.grid.setUniformItemSizes(True)
        self.grid.setItemDelegate(IconDelegate(dark,self.grid))
        self.grid.setWordWrap(True)
        self.grid.setAccessibleName('Offline icons')
        for entry in entries():
            if entry.get('retired'):
                continue
            reference = entry['reference']
            label = f"{entry['name']}\n{entry['library_label']} / {entry['style']}"
            item = QListWidgetItem(label)
            item.setSizeHint(QSize(166,104))
            item.setData(Qt.ItemDataRole.UserRole, reference)
            item.setData(Qt.ItemDataRole.UserRole+1, ' '.join(str(value) for value in
                [entry['name'],entry['library_label'],entry['style'],*entry.get('tags',[])]).lower())
            item.setData(Qt.ItemDataRole.UserRole+2, entry['library'])
            item.setData(Qt.ItemDataRole.UserRole+3, entry['style'])
            item.setToolTip(f"{entry['library_label']} / {entry['style']} / {entry['name']}")
            self.grid.addItem(item)
        layout.addWidget(self.grid, 1)
        self.search.textChanged.connect(self.filter)
        self.library.currentIndexChanged.connect(self.filter)
        self.style.currentIndexChanged.connect(self.filter)
        self.grid.itemDoubleClicked.connect(self.choose)
        actions = QHBoxLayout()
        actions.addWidget(QLabel('Available offline · names include library and style'))
        about = QPushButton('About & Licenses')
        about.clicked.connect(self.show_about)
        actions.addWidget(about)
        actions.addStretch()
        select = QPushButton('Use Icon')
        select.clicked.connect(self.choose)
        actions.addWidget(select)
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        layout.addLayout(actions)

    def show_about(self):
        from about_page import show_about_dialog
        show_about_dialog(self)

    def filter(self, *_):
        words = self.search.text().lower().split()
        library = self.library.currentData()
        style = self.style.currentData()
        for index in range(self.grid.count()):
            item = self.grid.item(index)
            item.setHidden(not (all(word in item.data(Qt.ItemDataRole.UserRole+1) for word in words)
                and (not library or item.data(Qt.ItemDataRole.UserRole+2)==library)
                and (not style or item.data(Qt.ItemDataRole.UserRole+3)==style)))

    def choose(self, *_):
        item = self.grid.currentItem()
        if item is not None and not item.isHidden():
            self.reference = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
