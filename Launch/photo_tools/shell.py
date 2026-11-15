"""Shared navigation and a persistent host for both existing photo apps."""

from __future__ import annotations

import sys
from PySide6.QtCore import QObject, QPoint, QSignalBlocker, QTimer, Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from .preferences import Preferences
from .registry import load_apps, load_window_class
from .settings_dialog import SettingsDialog
from .theme import apply_theme


class SuiteContext(QObject):
    def __init__(self, parent=None, *, settings_path=None, apps=None):
        super().__init__(parent)
        self.apps = apps if apps is not None else load_apps()
        self.preferences = Preferences(self.apps, self, path=settings_path)
        self.factories = {}
        self.windows = set()

    def create_window(self, app_id=None, directory='', *, source=None):
        window = SuiteWindow(self)
        if app_id is not None and not window.open_app(app_id, force_new=False, directory=directory):
            window.close()
            return None
        window.show()
        if source is not None:
            screen = source.screen()
            available = screen.availableGeometry()
            position = offset_window_position(source.frameGeometry(),
                                              window.frameGeometry().size(), available)
            window.move(position)
        return window


def offset_window_position(source_frame, new_size, available, distance=36):
    """Cascade from the source, reversing near edges and keeping the title visible."""
    coordinates = []
    for origin, extent, minimum, available_extent, title_extent in (
        (source_frame.left(), new_size.width(), available.left(), available.width(), 240),
        (source_frame.top(), new_size.height(), available.top(), available.height(), 80),
    ):
        visible_extent = extent if extent <= available_extent else min(title_extent, available_extent)
        maximum = minimum + available_extent - visible_extent
        desired = origin + distance
        if desired > maximum:
            desired = origin - distance
        coordinates.append(max(minimum, min(desired, maximum)))
    return QPoint(*coordinates)


def display_signature(state, window=None):
    """Only display changes require expensive widget restyling."""
    system_dark = None
    if state['appearance'] == 'system':
        system_dark = (window._system_is_dark() if hasattr(window, '_system_is_dark') else
                       QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
    return state['appearance'], state['accent'], system_dark


def get_context():
    app = QApplication.instance()
    if app is None:
        raise RuntimeError('Create QApplication before opening Photo Tools.')
    if not hasattr(app, '_photo_tools_context'):
        app._photo_tools_context = SuiteContext(app)
    return app._photo_tools_context


class SharedNavigation(QObject):
    """This is the only definition of the menu, used by launcher and child apps."""
    def __init__(self, window, context, host=None):
        super().__init__(window)
        self.window, self.context, self.host = window, context, host
        self.settings_action = QAction('Settings', self)
        self.settings_action.triggered.connect(self.show_settings)
        window.menuBar().addAction(self.settings_action)
        self.launch_menu = window.menuBar().addMenu('Launch')
        self.launch_actions = {}
        context.preferences.changed.connect(self.rebuild)
        self.launch_menu.aboutToShow.connect(context.preferences.refresh)
        self.rebuild()

    def rebuild(self):
        state = self.context.preferences.state
        signature = (tuple(state['order']), tuple(state['new_windows'].items()))
        if signature == getattr(self, '_menu_signature', None):
            return
        self._menu_signature = signature
        self.launch_menu.clear()
        home = self.launch_menu.addAction('Launcher home')
        home.triggered.connect(self.go_home)
        self.launch_menu.addSeparator()
        self.launch_actions = {}
        for app_id in state['order']:
            app = self.context.apps[app_id]
            action = self.launch_menu.addAction(app.name)
            new_window = state['new_windows'][app_id]
            action.setToolTip('Open in a new window' if new_window else 'Open in this window')
            action.triggered.connect(lambda _checked=False, key=app_id: self.launch(key))
            self.launch_actions[app_id] = action

    def _host(self):
        if self.host is None:
            # Directly constructed app views can also join the common shell.
            self.host = SuiteWindow(self.context)
            self.host.adopt(self.window, self.window.suite_binding.app_id)
            self.host.show()
        return self.host

    def launch(self, app_id):
        if self.context.preferences.state['new_windows'][app_id]:
            self.context.create_window(app_id, source=self.host or self.window)
        else:
            self._host().open_app(app_id, force_new=False)

    def go_home(self):
        self._host().show_home()

    def show_settings(self):
        self.context.preferences.refresh()
        dialog = SettingsDialog(self.context, self.host or self.window)
        dialog.exec()
        dialog.deleteLater()


class WindowBinding(QObject):
    def __init__(self, window, app_id, suite=None):
        super().__init__(window)
        self.window, self.app_id = window, app_id
        self.context = suite.context if suite is not None else get_context()
        window.suite_context = self.context
        self.navigation = None if suite is not None else SharedNavigation(window, self.context)
        self.context.preferences.changed.connect(self.refresh)
        QApplication.styleHints().colorSchemeChanged.connect(self.refresh)
        window.appearance.currentIndexChanged.connect(window._appearance_changed)
        self.refresh()

    def refresh(self, *_args):
        state = self.context.preferences.state
        signature = display_signature(state, self.window)
        if signature == getattr(self, '_display_signature', None):
            return
        self._display_signature = signature
        with QSignalBlocker(self.window.appearance):
            self.window.appearance.setCurrentIndex(self.window.appearance.findData(state['appearance']))
        self.window._apply_theme()


def bind_window(window, app_id, suite=None):
    return WindowBinding(window, app_id, suite)


class AppTile(QPushButton):
    def __init__(self, app, number, new_window, parent=None):
        super().__init__(parent)
        self.setObjectName('tile')
        self.setAccessibleName(f'Launch {app.name}')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(250)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 24, 25, 24)
        layout.setSpacing(13)
        self.number_label = QLabel(f'{number:02}  /  PHOTO TOOLS')
        self.number_label.setObjectName('tileNumber')
        layout.addWidget(self.number_label)
        title = QLabel(app.name)
        title.setObjectName('tileTitle')
        layout.addWidget(title)
        description = QLabel(app.description)
        description.setObjectName('subtitle')
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addStretch()
        self.launch_label = QLabel()
        self.launch_label.setObjectName('tileLaunch')
        layout.addWidget(self.launch_label)
        self.update_options(number, new_window)
        for label in self.findChildren(QLabel):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def update_options(self, number, new_window):
        self.number_label.setText(f'{number:02}  /  PHOTO TOOLS')
        self.launch_label.setText('Open in a new window  ↗' if new_window else 'Open in this window  →')


class SuiteWindow(QMainWindow):
    def __init__(self, context=None):
        super().__init__()
        self.context = context or get_context()
        self.context.windows.add(self)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle('Photo Tools · Launcher')
        self.resize(1160, 940)
        self.setMinimumSize(980, 860)
        self.pages = {}
        self.current_app = None
        self.closing = False
        self.close_timer = QTimer(self)
        self.close_timer.setInterval(50)
        self.close_timer.timeout.connect(self._close_when_idle)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.breadcrumb = QFrame()
        bar = QHBoxLayout(self.breadcrumb)
        bar.setContentsMargins(28, 8, 28, 4)
        self.home_button = QPushButton('← All apps')
        self.home_button.clicked.connect(self.show_home)
        bar.addWidget(self.home_button)
        self.page_name = QLabel()
        bar.addWidget(self.page_name)
        bar.addStretch()
        hint = QLabel('Shared display settings')
        hint.setObjectName('muted')
        bar.addWidget(hint)
        layout.addWidget(self.breadcrumb)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.home = QWidget()
        self.home.setObjectName('home')
        home_layout = QVBoxLayout(self.home)
        home_layout.setContentsMargins(36, 32, 36, 30)
        home_layout.setSpacing(18)
        eyebrow = QLabel('PHOTO TOOLS')
        eyebrow.setObjectName('eyebrow')
        home_layout.addWidget(eyebrow)
        title = QLabel('Your photos. One starting point.')
        title.setObjectName('title')
        home_layout.addWidget(title)
        subtitle = QLabel('Choose a tool to get started. Your work stays here when you switch apps.')
        subtitle.setObjectName('subtitle')
        subtitle.setWordWrap(True)
        home_layout.addWidget(subtitle)
        self.tiles_layout = QGridLayout()
        self.tiles = {}
        self._tile_order = ()
        self.tiles_layout.setSpacing(20)
        home_layout.addSpacing(16)
        home_layout.addLayout(self.tiles_layout)
        home_layout.addStretch(1)
        note = QLabel('A workspace that fits your workflow')
        note.setObjectName('tileTitle')
        home_layout.addWidget(note)
        self.home_note = QLabel('Use Settings to choose your accent colour, reorder tools, '
                               'and decide which apps open in a new window.')
        self.home_note.setObjectName('muted')
        self.home_note.setWordWrap(True)
        home_layout.addWidget(self.home_note)
        home_layout.addStretch(1)
        self.stack.addWidget(self.home)
        self.navigation = SharedNavigation(self, self.context, self)
        self.context.preferences.changed.connect(self.refresh)
        QApplication.styleHints().colorSchemeChanged.connect(self.refresh_theme)
        self.refresh()
        self.show_home()

    def refresh_theme(self, *_args):
        state = self.context.preferences.state
        signature = display_signature(state)
        if signature == getattr(self, '_display_signature', None):
            return
        self._display_signature = signature
        apply_theme(self, state['appearance'], state['accent'])

    def refresh(self):
        self.refresh_theme()
        state = self.context.preferences.state
        order = tuple(state['order'])
        reordered = order != self._tile_order
        if reordered:
            while self.tiles_layout.count():
                self.tiles_layout.takeAt(0)
        for removed in set(self.tiles) - set(order):
            self.tiles.pop(removed).deleteLater()
        for index, app_id in enumerate(state['order']):
            tile = self.tiles.get(app_id)
            if tile is None:
                tile = AppTile(self.context.apps[app_id], index + 1, state['new_windows'][app_id])
                tile.clicked.connect(lambda _checked=False, key=app_id: self.open_app(key))
                self.tiles[app_id] = tile
            else:
                tile.update_options(index + 1, state['new_windows'][app_id])
            if reordered:
                self.tiles_layout.addWidget(tile, index // 2, index % 2)
        self.tiles = {app_id: self.tiles[app_id] for app_id in order}
        self._tile_order = order

    def adopt(self, page, app_id):
        if app_id in self.pages:
            raise ValueError(f'{app_id} is already open in this window.')
        page.hide()
        page.setParent(self.stack)
        page.setWindowFlags(Qt.WindowType.Widget)
        page.menuBar().hide()
        self.stack.addWidget(page)
        self.pages[app_id] = page
        self._select_app(app_id)

    def _select_app(self, app_id):
        self.current_app = app_id
        self.stack.setCurrentWidget(self.pages[app_id])
        self.breadcrumb.show()
        self.page_name.setText(self.context.apps[app_id].name)
        self.setWindowTitle(self.pages[app_id].windowTitle())

    def open_app(self, app_id, *, force_new=None, directory=''):
        if self.closing:
            return False
        self.context.preferences.refresh()
        if force_new is None:
            force_new = self.context.preferences.state['new_windows'][app_id]
        if force_new:
            return self.context.create_window(app_id, directory, source=self) is not None
        if app_id not in self.pages:
            try:
                factory = self.context.factories.get(app_id)
                if factory is None:
                    factory = load_window_class(self.context.apps[app_id])
                    self.context.factories[app_id] = factory
                page = factory(directory, suite=self)
                self.adopt(page, app_id)
            except Exception as error:
                QMessageBox.warning(self, 'Could not open app', str(error) or type(error).__name__)
                return False
        else:
            self._select_app(app_id)
        return True

    def show_home(self):
        if self.closing:
            return
        self.current_app = None
        self.stack.setCurrentWidget(self.home)
        self.breadcrumb.hide()
        self.setWindowTitle('Photo Tools · Launcher')

    def _close_when_idle(self):
        if not any(getattr(page, 'busy', False) for page in self.pages.values()):
            self.close_timer.stop()
            self.close()

    def closeEvent(self, event):
        busy = [page for page in self.pages.values() if getattr(page, 'busy', False)]
        if busy:
            self.closing = True
            self.menuBar().setEnabled(False)
            self.breadcrumb.setEnabled(False)
            for page in busy:
                page.cancel_work()
            self.close_timer.start()
            event.ignore()
            return
        self.context.windows.discard(self)
        for page in self.pages.values():
            page.close()
        event.accept()


def run_app(initial_app=None, directory='', factory=None):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Photo Tools')
    app.setOrganizationName('PhotoToolsPrototype')
    app.setStyle('Fusion')
    app.setFont(QFont('Segoe UI', 10))
    context = get_context()
    if factory is not None:
        context.factories[initial_app] = factory
    window = context.create_window(initial_app, directory)
    if window is None:
        return 1
    return app.exec()
