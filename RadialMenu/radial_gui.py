"""Launcher settings page and an independent, transparent radial popup."""
import ctypes
from ctypes import wintypes
import math
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Launch'))
from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QPoint, QRectF, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget, QSystemTrayIcon, QMenu
from photo_tools import apply_theme, bind_window, run_app
from windows_input import WindowsInput
from photo_tools.fluent import QComboBox, QPushButton
from qfluentwidgets import ToolButton, FluentIcon


def popup_geometry(cursor, available, diameter=360):
    size = min(diameter, available.width(), available.height())
    return (max(available.left(), min(cursor.x() - size // 2, available.right() - size + 1)),
            max(available.top(), min(cursor.y() - size // 2, available.bottom() - size + 1)), size)


class RadialPopup(QWidget):
    selected = Signal(int)
    settings_requested = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setMouseTracking(True)
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
            color = self.accent if index == self.hover else QColor('#28322f' if self.dark else '#f2f6f4')
            painter.setBrush(color)
            painter.setPen(QPen(self.accent, 1))
            painter.drawPath(path)
            painter.setPen(QColor('white' if self.dark or index == self.hover else '#172d24'))
            angle = math.radians(-90+index*span)
            radius = (outer+inner)/2
            painter.drawText(QRectF(c+radius*math.cos(angle)-18, c+radius*math.sin(angle)-14, 36, 28),
                             Qt.AlignmentFlag.AlignCenter, chr(ord('a') + index))

    def mouseMoveEvent(self, event):
        self.hover = self.segment_at(event.position())
        self.update()

    def mouseReleaseEvent(self, event):
        index = self.segment_at(event.position())
        self.hide()
        if event.button() == Qt.MouseButton.LeftButton and index >= 0:
            self.selected.emit(index+1)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()

    def event(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowDeactivate:
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
                window.showNormal()
                window.raise_()
                window.activateWindow()
                return
        self.context.create_window('radial-menu')

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
            self.popup.show_at_cursor()

    def select_letter(self, number):
        if not self.target or not 1 <= number <= 26:
            return
        letter = chr(ord('a') + number - 1)
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
        sent = self.input.send_letter(target, letter)
        self.status = f'Sent {letter}' if sent else 'Could not send letter to the original app.'
        self.changed.emit()


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
        preview = QPushButton('Preview at mouse')
        layout.addWidget(preview)
        self.background_button = QPushButton('Run in background')
        layout.addWidget(self.background_button)
        layout.addWidget(QLabel('The activation key works while you use other apps. Restore settings from the system tray.'))
        layout.addWidget(QLabel('Click a segment to select it. Escape, right-click or focus loss dismisses the menu.'))
        self.selection = QLabel('Select a letter to send its keypress to the original application.')
        layout.addWidget(self.selection)
        layout.addStretch()
        self.setCentralWidget(root)
        self.suite_binding = bind_window(self, 'radial-menu', suite)
        context = self.suite_context
        if not hasattr(context, 'radial_service'):
            context.radial_service = RadialService(context)
        self.service = context.radial_service
        self.key.setCurrentText(self.service.key)
        self.segments.setCurrentIndex(self.segments.findData(self.service.popup.count))
        self.status.setText(self.service.status)
        self.key.currentTextChanged.connect(self.service.start)
        self.segments.currentIndexChanged.connect(self.change_count)
        self.service.changed.connect(lambda: self.status.setText(self.service.status))
        self.service.popup.selected.connect(lambda n: self.selection.setText(f'Selected {chr(96+n)}'))
        preview.clicked.connect(self.service.preview)
        self.background_button.clicked.connect(lambda: self.service.run_in_background(self.window()))

    def change_count(self):
        self.service.popup.count = self.segments.currentData()
        self.service.settings.setValue('radial/count', self.service.popup.count)
        self.service.popup.update()

    def _appearance_changed(self):
        self.suite_context.preferences.update(appearance=self.appearance.currentData())

    def _apply_theme(self):
        apply_theme(self, self.appearance.currentData(), self.suite_context.preferences.state['accent'])


if __name__ == '__main__':
    raise SystemExit(run_app('radial-menu', factory=RadialMenuWindow))
