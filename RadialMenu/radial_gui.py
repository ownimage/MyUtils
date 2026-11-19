"""Launcher settings page and an independent, transparent radial popup."""
import ctypes
from ctypes import wintypes
import math
import ntpath
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Launch'))
from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QPoint, QRectF, QSettings, Qt, QTimer, Signal, QFileInfo
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget, QSystemTrayIcon, QMenu, QStackedWidget, QHBoxLayout, QFileDialog, QFileIconProvider
from photo_tools import apply_theme, bind_window, run_app
from windows_input import WindowsInput
from application_icons import ApplicationIcons
from icon_library import IconPicker, button_icon
from button_profiles import ButtonProfiles, default_button, parse_sequence, app_key
from photo_tools.fluent import QComboBox, QPushButton, QLineEdit
from qfluentwidgets import ToolButton, FluentIcon


def popup_geometry(cursor, available, diameter=360):
    size = min(diameter, available.width(), available.height())
    return (max(available.left(), min(cursor.x() - size // 2, available.right() - size + 1)),
            max(available.top(), min(cursor.y() - size // 2, available.bottom() - size + 1)), size)


class RadialPopup(QWidget):
    selected = Signal(int)
    settings_requested = Signal()

    def __init__(self, parent=None, *, embedded=False):
        super().__init__(parent, Qt.WindowType.Widget if embedded else (Qt.WindowType.Tool |
                         Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setMouseTracking(True)
        self.embedded = embedded
        self.active_button = -1
        self.buttons = [default_button(i) for i in range(26)]
        self.count = 12
        self.hover = -1
        self.accent = QColor('#246b53')
        self.dark = False
        self.settings_button = ToolButton(FluentIcon.SETTING, self)
        self.settings_button.setFixedSize(32, 32)
        self.settings_button.setToolTip('RadialMenu settings')
        self.settings_button.setAccessibleName('RadialMenu settings')
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.clicked.connect(self.request_settings)
        self.settings_button.setVisible(not embedded)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.settings_button.move(max(0, self.width() - 36), 4)

    def request_settings(self):
        self.hide()
        self.settings_requested.emit()

    def refresh_settings_button(self):
        foreground = '#ffffff' if self.dark else '#172d24'
        background = '#28322f' if self.dark else '#f2f6f4'
        self.settings_button.setIcon(FluentIcon.SETTING.icon(color=QColor(foreground)))
        self.settings_button.setStyleSheet(
            f'ToolButton {{ background: {background}; border: 1px solid {self.accent.name()}; '
            'border-radius: 8px; }'
            f'ToolButton:hover {{ border: 2px solid {self.accent.name()}; }}')

    def show_at_cursor(self):
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        x, y, size = popup_geometry(cursor, screen.availableGeometry())
        self.setGeometry(x, y, size, size)
        self.hover = -1
        self.refresh_settings_button()
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.update()

    def segment_at(self, point):
        dx, dy = point.x() - self.width()/2, point.y() - self.height()/2
        radius = math.hypot(dx, dy)
        if not self.width() * .17 <= radius <= self.width()/2 - 4:
            return -1
        angle = (math.degrees(math.atan2(dy, dx)) + 90 + 180/self.count) % 360
        return int(angle // (360/self.count))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c, outer, inner = self.width()/2, self.width()/2 - 4, self.width()*.17
        outer_rect = QRectF(c-outer, c-outer, outer*2, outer*2)
        inner_rect = QRectF(c-inner, c-inner, inner*2, inner*2)
        span = 360/self.count
        for index in range(self.count):
            start = 90 + span/2 - index*span - 1
            path = QPainterPath()
            path.arcMoveTo(outer_rect, start)
            path.arcTo(outer_rect, start, -(span-2))
            end = math.radians(start-span+2)
            path.lineTo(c+inner*math.cos(end), c-inner*math.sin(end))
            path.arcTo(inner_rect, start-span+2, span-2)
            path.closeSubpath()
            color = self.accent if index in (self.hover, self.active_button) else QColor('#28322f' if self.dark else '#f2f6f4')
            painter.setBrush(color)
            painter.setPen(QPen(self.accent, 1))
            painter.drawPath(path)
            painter.setPen(QColor('white' if self.dark or index in (self.hover, self.active_button) else '#172d24'))
            angle = math.radians(-90+index*span)
            radius = (outer+inner)/2
            x, y = c+radius*math.cos(angle), c+radius*math.sin(angle)
            button = self.buttons[index]
            icon_path = button['hover_icon'] if index == self.hover and button['hover_icon'] else button['icon']
            icon = button_icon(icon_path, self.dark or index in (self.hover, self.active_button))
            if not icon.isNull():
                icon.paint(painter, round(x-10), round(y-20), 20, 20)
            width = min(74, max(30, radius * span * math.pi / 180 - 6))
            label = painter.fontMetrics().elidedText(button['name'], Qt.TextElideMode.ElideRight, int(width))
            painter.drawText(QRectF(x-width/2, y if not icon.isNull() else y-14, width, 28),
                             Qt.AlignmentFlag.AlignCenter, label)

    def mouseMoveEvent(self, event):
        self.hover = self.segment_at(event.position())
        self.update()

    def mouseReleaseEvent(self, event):
        index = self.segment_at(event.position())
        if not self.embedded:
            self.hide()
        if event.button() == Qt.MouseButton.LeftButton and index >= 0:
            self.active_button = index if self.embedded else -1
            self.update()
            self.selected.emit(index+1)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()

    def event(self, event):
        from PySide6.QtCore import QEvent
        if not getattr(self, 'embedded', False) and event.type() == QEvent.Type.WindowDeactivate:
            self.hide()
        return super().event(event)


class HotkeyFilter(QAbstractNativeEventFilter):
    """Receive thread WM_HOTKEY messages before Qt consumes them."""
    def __init__(self, service):
        super().__init__()
        self.service = service

    def nativeEventFilter(self, event_type, message):
        if event_type in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            native = wintypes.MSG.from_address(int(message))
            if (self.service.registered and native.message == 0x312 and
                    native.wParam == self.service.HOTKEY_ID):
                self.service.toggle_popup()
                return True, 0
        return False, 0


class RadialService(QObject):
    changed = Signal()
    HOTKEY_ID = 0x524D

    def __init__(self, context):
        super().__init__(context)
        self.popup = RadialPopup()
        self.input = WindowsInput() if sys.platform == 'win32' else None
        self.target = None
        self.application = ''
        self.pending = None
        self.send_timer = QTimer(self)
        self.send_timer.setInterval(20)
        self.send_timer.timeout.connect(self.deliver_letter)
        self.popup.selected.connect(self.select_letter)
        self.popup.settings_requested.connect(self.open_settings)
        self.tray = None
        self.registered = False
        self.status = 'Waiting to start'
        self.hotkey_filter = HotkeyFilter(self)
        self.filter_installed = False
        self.settings = context.preferences.settings
        self.profiles = ButtonProfiles(self.settings)
        self.popup.count = max(2, min(26, self.settings.value('radial/count', 12, type=int)))
        self.key = self.settings.value('radial/key', 'Ctrl+Alt+Space', type=str)
        self.context = context
        context.preferences.changed.connect(self.refresh_theme)
        QApplication.styleHints().colorSchemeChanged.connect(self.refresh_theme)
        QApplication.instance().aboutToQuit.connect(self.stop)
        # QApplication.aboutToQuit releases the process-owned registration.
        self.refresh_theme()
        self.start(self.key)
        self.install_tray()

    def install_tray(self):
        if self.tray is not None or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        image = QPixmap(32, 32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#246b53'), 7))
        painter.drawEllipse(5, 5, 22, 22)
        painter.end()
        self.tray = QSystemTrayIcon(QIcon(image), self)
        self.tray.setToolTip('RadialMenu - ' + self.status)
        self.tray_menu = QMenu()
        self.tray_menu.addAction('Open RadialMenu settings', self.open_settings)
        self.tray_menu.addAction('Preview radial menu', self.preview)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction('Exit RadialMenu', self.exit_background)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        QApplication.instance().setQuitOnLastWindowClosed(False)

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()

    def open_settings(self):
        self.cancel_delivery()
        self.popup.hide()
        for window in self.context.windows:
            if not window.closing:
                window.open_app('radial-menu', force_new=False)
                if self.application:
                    window.pages['radial-menu'].choose_application(self.application)
                window.showNormal()
                window.raise_()
                window.activateWindow()
                return
        window = self.context.create_window('radial-menu')
        if window and self.application:
            window.pages['radial-menu'].choose_application(self.application)

    def exit_background(self):
        self.stop()
        if self.tray is not None:
            self.tray.hide()
        self.status = 'Stopped. Choose an activation key to restart.'
        self.changed.emit()
        app = QApplication.instance()
        app.setQuitOnLastWindowClosed(True)
        if not any(window.isVisible() for window in self.context.windows):
            app.quit()

    def run_in_background(self, window):
        self.install_tray()
        if self.tray is not None:
            self.tray.show()
            QApplication.instance().setQuitOnLastWindowClosed(False)
            window.hide()
        else:
            window.showMinimized()

    def refresh_theme(self, *_):
        state = self.context.preferences.state
        self.popup.accent = QColor(state['accent'])
        self.popup.dark = state['appearance'] == 'dark' or (state['appearance'] == 'system' and
            QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
        self.popup.refresh_settings_button()
        self.popup.update()

    def stop(self, *_):
        self.cancel_delivery()
        if self.filter_installed:
            QApplication.instance().removeNativeEventFilter(self.hotkey_filter)
            self.filter_installed = False
        if self.registered:
            ctypes.windll.user32.UnregisterHotKey(None, self.HOTKEY_ID)
        self.registered = False
        self.popup.hide()

    def start(self, key):
        self.stop()
        keys = {'Ctrl+Alt+Space': (3, 0x20), 'Ctrl+Alt+R': (3, 0x52), 'F8': (0, 0x77)}
        self.key = key if key in keys else 'Ctrl+Alt+Space'
        if sys.platform == 'win32':
            modifiers, vk = keys[self.key]
            self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, self.HOTKEY_ID, modifiers | 0x4000, vk))
        self.status = f'Listening for {self.key}' if self.registered else 'Activation key unavailable. Choose another key; Preview still works.'
        if self.registered:
            QApplication.instance().installNativeEventFilter(self.hotkey_filter)
            self.filter_installed = True
            self.settings.setValue('radial/key', self.key)
        if self.tray is not None:
            self.tray.setToolTip('RadialMenu - ' + self.status)
            self.tray.show()
            QApplication.instance().setQuitOnLastWindowClosed(False)
        self.changed.emit()

    def cancel_delivery(self):
        self.send_timer.stop()
        self.pending = None
        self.target = None

    def preview(self):
        self.cancel_delivery()
        self.popup.show_at_cursor()

    def toggle_popup(self):
        self.cancel_delivery()
        if self.popup.isVisible():
            self.popup.hide()
        else:
            # Capture before showing/activating our own popup.
            self.target = self.input.capture() if self.input else None
            application = self.input.application(self.target) if self.target and self.input else ''
            self.application = application if isinstance(application, str) else ''
            try:
                self.popup.buttons = self.profiles.buttons(self.application)
            except (ValueError, OSError) as error:
                self.status = str(error)
                self.changed.emit()
                self.target = None
                return
            self.popup.show_at_cursor()

    def select_letter(self, number):
        if not self.target or not 1 <= number <= 26:
            return
        letter = self.popup.buttons[number-1]['sequence']
        if not letter.strip():
            self.cancel_delivery()
            return
        self.pending = (self.target, letter, time.monotonic() + 5)
        self.status = f'Waiting for the original app to receive {letter}'
        self.changed.emit()
        self.input.restore(self.target)
        self.send_timer.start()

    def deliver_letter(self):
        if self.pending is None:
            return
        target, letter, deadline = self.pending
        if not self.input.valid(target) or time.monotonic() >= deadline:
            self.cancel_delivery()
            self.status = 'Letter cancelled: original app unavailable or focus timed out.'
            self.changed.emit()
            return
        if not self.input.focused(target) or not self.input.keys_released():
            return
        self.cancel_delivery()  # Exactly one attempt, including failure.
        sent = (self.input.send_letter(target, letter) if len(letter) == 1 and letter.isalpha()
                else self.input.send_sequence(target, letter))
        self.status = f'Sent {letter}' if sent else 'Could not send letter to the original app.'
        self.changed.emit()


class ButtonEditor(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.current = 0
        self.loading = False
        self.application = ''
        self.buttons = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        self.heading = QLabel()
        self.heading.setObjectName('title')
        layout.addWidget(self.heading)
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)
        body = QHBoxLayout()
        self.ring = RadialPopup(embedded=True)
        self.ring.setFixedSize(360, 360)
        self.ring.selected.connect(self.select_button)
        body.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignTop)
        form = QVBoxLayout()
        self.button_heading = QLabel()
        form.addWidget(self.button_heading)
        form.addWidget(QLabel('Name'))
        self.name = QLineEdit()
        self.name.setMaxLength(40)
        self.name.setAccessibleName('Button name')
        form.addWidget(self.name)
        self.icons = []
        for title in ('Normal icon', 'Hover icon'):
            form.addWidget(QLabel(title))
            row = QHBoxLayout()
            field = QLineEdit()
            field.setAccessibleName(title)
            field.setPlaceholderText('Choose an image, or leave blank')
            row.addWidget(field, 1)
            library = QPushButton('Icons…')
            library.clicked.connect(lambda _=False, edit=field: self.choose_library_icon(edit))
            row.addWidget(library)
            choose = QPushButton('File…')
            choose.clicked.connect(lambda _=False, edit=field: self.choose_icon(edit))
            row.addWidget(choose)
            clear = QPushButton('Clear')
            clear.clicked.connect(field.clear)
            row.addWidget(clear)
            form.addLayout(row)
            self.icons.append(field)
        form.addWidget(QLabel('Button sequence'))
        self.sequence = QLineEdit()
        self.sequence.setAccessibleName('Button sequence')
        self.sequence.setPlaceholderText('Ctrl+C, Ctrl+V')
        form.addWidget(self.sequence)
        hint = QLabel('Separate keys or shortcuts with commas. Example: Ctrl+A, Delete. Blank disables the action.')
        hint.setWordWrap(True)
        form.addWidget(hint)
        self.message = QLabel()
        self.message.setWordWrap(True)
        form.addWidget(self.message)
        actions = QHBoxLayout()
        save = QPushButton('Save Buttons')
        save.clicked.connect(self.save)
        actions.addWidget(save)
        back = QPushButton('Save and Back')
        back.clicked.connect(self.go_back)
        actions.addWidget(back)
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(lambda: self.owner.pages.setCurrentIndex(0))
        actions.addWidget(cancel)
        form.addLayout(actions)
        form.addStretch()
        body.addLayout(form, 1)
        layout.addLayout(body)
        layout.addStretch()
        for field in [self.name, *self.icons, self.sequence]:
            field.textChanged.connect(self.update_draft)

    def choose_library_icon(self, field):
        picker = IconPicker(self, dark=self.ring.dark)
        if picker.exec():
            field.setText(picker.reference)

    def choose_icon(self, field):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose button icon', '', 'Images (*.png *.svg *.ico *.jpg *.jpeg *.bmp)')
        if path:
            field.setText(path)

    def load_application(self, application):
        self.application = application
        self.buttons = self.owner.service.profiles.buttons(application)
        self.heading.setText(f'Edit Buttons — {ntpath.basename(application)}')
        self.path_label.setText(application)
        self.ring.buttons = self.buttons
        self.ring.count = self.owner.service.popup.count
        self.ring.accent = self.owner.service.popup.accent
        self.ring.dark = self.owner.service.popup.dark
        self.message.clear()
        self.select_button(1)

    def select_button(self, number):
        self.loading = True
        self.current = number-1
        button = self.buttons[self.current]
        self.button_heading.setText(f'Button {number}')
        self.name.setText(button['name'])
        self.icons[0].setText(button['icon'])
        self.icons[1].setText(button['hover_icon'])
        self.sequence.setText(button['sequence'])
        self.ring.active_button = self.current
        self.ring.update()
        self.loading = False

    def update_draft(self):
        if self.loading or not self.buttons:
            return
        self.buttons[self.current] = dict(name=self.name.text(), icon=self.icons[0].text(),
            hover_icon=self.icons[1].text(), sequence=self.sequence.text())
        self.ring.update()
        self.message.setText('Unsaved changes')

    def save(self):
        try:
            for number, button in enumerate(self.buttons, 1):
                try:
                    parse_sequence(button['sequence'])
                    for path in (button['icon'], button['hover_icon']):
                        if path and button_icon(path).isNull():
                            raise ValueError('Choose a readable icon image or clear the icon.')
                except ValueError as error:
                    raise ValueError(f'Button {number}: {error}') from error
            self.owner.service.profiles.save(self.application, self.buttons)
        except (ValueError, OSError) as error:
            self.message.setText(str(error))
            return False
        self.message.setText('Buttons saved')
        return True

    def go_back(self):
        if self.save():
            self.owner.pages.setCurrentIndex(0)


class ApplicationPicker(QComboBox):
    refreshing = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentIndexChanged.connect(self.sync_icon)

    def sync_icon(self, *_):
        index = self.currentIndex()
        self.setIcon(self.items[index].icon if 0 <= index < len(self.items) else QIcon())

    def clear(self):
        super().clear()
        self.sync_icon()

    def _showComboMenu(self):
        self.refreshing.emit()
        super()._showComboMenu()

    def add_application(self, text, path, icon):
        # Shared combo's adapter keeps the second positional argument as userData.
        from qfluentwidgets import ComboBox
        ComboBox.addItem(self, text, icon=icon, userData=path)


class RadialMenuWindow(QMainWindow):
    def __init__(self, directory='', *, suite=None):
        super().__init__()
        self.setWindowTitle('RadialMenu')
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(QLabel('RADIAL MENU'))
        self.appearance = QComboBox()
        for label, data in [('Follow Windows', 'system'), ('Light', 'light'), ('Dark', 'dark')]:
            self.appearance.addItem(label, data)
        layout.addWidget(self.appearance)
        layout.addWidget(QLabel('Activation key'))
        self.key = QComboBox()
        self.key.addItems(['Ctrl+Alt+Space', 'Ctrl+Alt+R', 'F8'])
        layout.addWidget(self.key)
        layout.addWidget(QLabel('Segments'))
        self.segments = QComboBox()
        for count in range(2, 27):
            self.segments.addItem(str(count), count)
        layout.addWidget(self.segments)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(QLabel('Application'))
        self.application_picker = ApplicationPicker()
        self.application_picker.setAccessibleName('Application to configure')
        layout.addWidget(self.application_picker)
        browse_app = QPushButton('Choose application…')
        layout.addWidget(browse_app)
        self.edit_buttons = QPushButton('Edit Buttons')
        layout.addWidget(self.edit_buttons)
        self.profile_message = QLabel('Choose a running application, or browse for another executable.')
        self.profile_message.setWordWrap(True)
        layout.addWidget(self.profile_message)
        self.background_button = QPushButton('Run in background')
        layout.addWidget(self.background_button)
        layout.addWidget(QLabel('The activation key works while you use other apps. Restore settings from the system tray.'))
        layout.addWidget(QLabel('Click a segment to select it. Escape, right-click or focus loss dismisses the menu.'))
        self.selection = QLabel('Select a letter to send its keypress to the original application.')
        layout.addWidget(self.selection)
        layout.addStretch()
        self.pages = QStackedWidget()
        self.pages.addWidget(root)
        self.setCentralWidget(self.pages)
        self.suite_binding = bind_window(self, 'radial-menu', suite)
        context = self.suite_context
        if not hasattr(context, 'radial_service'):
            context.radial_service = RadialService(context)
        self.service = context.radial_service
        self.app_icons = ApplicationIcons(context.preferences.settings)
        self.key.setCurrentText(self.service.key)
        self.segments.setCurrentIndex(self.segments.findData(self.service.popup.count))
        self.status.setText(self.service.status)
        self.key.currentTextChanged.connect(self.service.start)
        self.segments.currentIndexChanged.connect(self.change_count)
        self.service.changed.connect(self.refresh_status)
        self.service.popup.selected.connect(self.selected_button)
        self.editor = ButtonEditor(self)
        self.pages.addWidget(self.editor)
        self.edit_buttons.clicked.connect(self.begin_edit)
        browse_app.clicked.connect(self.browse_application)
        self.application_picker.refreshing.connect(self.refresh_applications)
        self.refresh_applications()
        if self.service.application:
            self.choose_application(self.service.application)
        self.background_button.clicked.connect(lambda: self.service.run_in_background(self.window()))

    def refresh_status(self):
        self.status.setText(self.service.status)

    def selected_button(self, number):
        self.selection.setText(f"Selected {self.service.popup.buttons[number-1]['name']}")

    def refresh_applications(self):
        selected = self.application_picker.currentData()
        self.application_picker.clear()
        provider = QFileIconProvider()
        known = set()
        running = self.service.input.running_applications() if self.service.input else []
        for item in running:
            path = app_key(item['path'])
            icon = self.service.input.window_icon(item['hwnd'])
            if icon.isNull():
                icon = provider.icon(QFileInfo(path))
            if icon.isNull():
                icon = self.app_icons.cached(path)
            self.cache_application_icon(path, icon)
            label = f"{ntpath.basename(path)} — {item['title']}"
            self.application_picker.add_application(label, path, icon)
            known.add(path)
        for path in self.service.profiles.applications():
            if path not in known:
                icon = self.app_icons.cached(path)
                if icon.isNull():
                    icon = provider.icon(QFileInfo(path))
                    self.cache_application_icon(path, icon)
                self.application_picker.add_application(f'{ntpath.basename(path)} (configured)', path, icon)
        if selected:
            index = self.application_picker.findData(selected)
            if index >= 0:
                self.application_picker.setCurrentIndex(index)

    def cache_application_icon(self, application, icon):
        try:
            self.app_icons.remember(application, icon)
        except OSError as error:
            self.profile_message.setText(f'Could not cache application icon: {error}')

    def choose_application(self, application):
        application = app_key(application)
        index = self.application_picker.findData(application)
        if index < 0:
            icon = self.app_icons.cached(application)
            if icon.isNull():
                icon = QFileIconProvider().icon(QFileInfo(application))
                self.cache_application_icon(application, icon)
            self.application_picker.add_application(f'{ntpath.basename(application)} — {application}', application, icon)
            index = self.application_picker.count()-1
        self.application_picker.setCurrentIndex(index)

    def browse_application(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose application', '', 'Applications (*.exe)')
        if path:
            self.choose_application(path)

    def begin_edit(self):
        application = self.application_picker.currentData()
        if not application:
            self.profile_message.setText('Choose an application first.')
            return
        self.service.cancel_delivery()
        self.service.popup.hide()
        try:
            self.editor.load_application(application)
        except (ValueError, OSError) as error:
            self.profile_message.setText(str(error))
            return
        self.pages.setCurrentWidget(self.editor)

    def change_count(self):
        self.service.popup.count = self.segments.currentData()
        self.service.settings.setValue('radial/count', self.service.popup.count)
        self.service.popup.update()

    def _appearance_changed(self):
        self.suite_context.preferences.update(appearance=self.appearance.currentData())

    def _apply_theme(self):
        dark = apply_theme(self, self.appearance.currentData(), self.suite_context.preferences.state['accent'])
        if hasattr(self, 'editor'):
            self.editor.ring.dark = dark
            self.editor.ring.accent = QColor(self.suite_context.preferences.state['accent'])
            self.editor.ring.update()


if __name__ == '__main__':
    raise SystemExit(run_app('radial-menu', factory=RadialMenuWindow))
