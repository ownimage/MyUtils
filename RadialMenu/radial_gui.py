"""Launcher settings page and an independent, transparent radial popup."""
import ctypes
from ctypes import wintypes
import math
import ntpath
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Launch'))
from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QPoint, QRectF, QSettings, Qt, QTimer, Signal, QFileInfo, QRegularExpression
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QIcon, QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget, QSystemTrayIcon, QMenu, QHBoxLayout, QFileDialog, QFileIconProvider, QFrame, QScrollArea
from photo_tools import apply_theme, bind_window, run_app
from photo_tools.shell import CurrentPageStack
from windows_input import WindowsInput
from activation_monitor import parse_hotkey
from about_page import AboutPage
from application_icons import ApplicationIcons
from icon_library import IconPicker, button_icon
from button_profiles import ButtonProfiles, default_button, parse_sequence, app_key, normalise_sequence, normalise_button, BEHAVIOURS
from photo_tools.fluent import QComboBox, QPushButton, QLineEdit, QCheckBox
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
            width = min(74, max(30, radius * span * math.pi / 180 - 6))
            icons = [button_icon(reference, self.dark or index in (self.hover, self.active_button))
                     for reference in (button['icon'], button['secondary_icon']) if reference]
            icons = [icon for icon in icons if not icon.isNull()]
            size = min(20, int((width-4)/max(1,len(icons))))
            total_width = len(icons)*size + max(0,len(icons)-1)*4
            for offset, icon in enumerate(icons):
                icon.paint(painter, round(x-total_width/2+offset*(size+4)), round(y-20), size, size)
            label = painter.fontMetrics().elidedText(button['name'], Qt.TextElideMode.ElideRight, int(width))
            painter.drawText(QRectF(x-width/2, y if icons else y-14, width, 28),
                             Qt.AlignmentFlag.AlignCenter, label)
            marker = BEHAVIOURS[button.get('behaviour', 'normal')]
            # Keep the mode separate from names and both icon slots.
            marker_radius = outer - 12
            mx, my = c+marker_radius*math.cos(angle), c+marker_radius*math.sin(angle)
            painter.drawText(QRectF(mx-12, my-10, 24, 20),
                             Qt.AlignmentFlag.AlignCenter, marker)

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
        self.armed = None
        self.gesture_registration = False
        self.gesture_cleanup_needed = False
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
        try:
            parse_hotkey(self.key)
        except ValueError:
            self.key = 'Ctrl+Alt+Space'
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
        self.cancel_delivery(resume=False)
        if self.filter_installed:
            QApplication.instance().removeNativeEventFilter(self.hotkey_filter)
            self.filter_installed = False
        if self.registered:
            ctypes.windll.user32.UnregisterHotKey(None, self.HOTKEY_ID)
        self.registered = False
        self.popup.hide()

    def start(self, key):
        try:
            modifiers, vk = parse_hotkey(key)
        except ValueError as error:
            self.status = str(error)
            self.changed.emit()
            return False
        previous, was_registered = self.key, self.registered or self.gesture_registration
        self.stop()
        if sys.platform == 'win32':
            self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, self.HOTKEY_ID, modifiers | 0x4000, vk))
        success = self.registered
        if success:
            self.key = key
            self.settings.setValue('radial/key', self.key)
            self.settings.sync()
            self.status = f'Listening for {self.key}'
        else:
            self.status = 'Activation key unavailable. Choose another shortcut.'
            if was_registered:
                modifiers, vk = parse_hotkey(previous)
                self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, self.HOTKEY_ID, modifiers | 0x4000, vk))
                self.status += (f' Still listening for {previous}.' if self.registered
                                else ' Previous hotkey could not be restored.')
        if self.registered:
            QApplication.instance().installNativeEventFilter(self.hotkey_filter)
            self.filter_installed = True
        if self.tray is not None:
            self.tray.setToolTip('RadialMenu - ' + self.status)
            self.tray.show()
            QApplication.instance().setQuitOnLastWindowClosed(False)
        self.changed.emit()
        return success

    def cancel_delivery(self, *, resume=True):
        self.send_timer.stop()
        self.pending = None
        self.target = None
        cleaned = True
        if self.armed is not None or self.gesture_cleanup_needed:
            self.armed = None
            cleaned = self.input.end_gesture()
            self.gesture_cleanup_needed = not cleaned
        if self.gesture_registration:
            self.gesture_registration = False
            if resume:
                modifiers, vk = parse_hotkey(self.key)
                self.registered = bool(ctypes.windll.user32.RegisterHotKey(
                    None, self.HOTKEY_ID, modifiers | 0x4000, vk))
                cleaned = self.registered and cleaned
        return cleaned

    def finish_gesture(self, message):
        cleaned = self.cancel_delivery()
        self.status = message if cleaned else message + ' Input cleanup or hotkey restart failed; restart RadialMenu.'
        if self.tray is not None:
            self.tray.setToolTip('RadialMenu - ' + self.status)
        self.changed.emit()

    def arm_gesture(self, target, button):
        if not self.input.begin_gesture(self.key):
            self.status = 'Could not capture the hotkey for Hold / Repeat.'
            self.target = None
            self.changed.emit()
            return
        self.armed = dict(target=target, sequence=button['sequence'],
                          behaviour=button['behaviour'], phase='focus',
                          deadline=time.monotonic()+5, active=False, next_repeat=0,
                          presses=self.input.gesture_presses())
        # Suspend RegisterHotKey while the temporary hook owns activation, so
        # injected sequences cannot create WM_HOTKEY messages of their own.
        if self.registered:
            if not ctypes.windll.user32.UnregisterHotKey(None, self.HOTKEY_ID):
                self.finish_gesture('Could not transfer activation to Hold / Repeat.')
                return
            self.registered = False
            self.gesture_registration = True
        instruction = 'press to start, press again to stop'
        self.status = f"Armed {button['behaviour'].title()}: {self.key} — {instruction}. Escape cancels."
        self.changed.emit()
        self.input.restore(target)
        self.send_timer.start()

    def deliver_gesture(self):
        action = self.armed
        target, sequence = action['target'], action['sequence']
        now = time.monotonic()
        state = self.input.gesture_state()
        if state == 'cancelled' or not self.input.valid(target):
            self.finish_gesture('Action cancelled.')
            return
        if action['phase'] == 'focus':
            if now >= action['deadline']:
                self.finish_gesture('Action cancelled: focus timed out.')
                return
            if state == 'waiting' or not self.input.focused(target) or not self.input.gesture_safe(target):
                return
            action['phase'] = 'ready'
        allow_mouse = action['active']
        if not self.input.focused(target) or not self.input.gesture_safe(target, allow_mouse=allow_mouse):
            self.finish_gesture('Action cancelled: original app lost focus or another modifier was pressed.')
            return
        presses = self.input.gesture_presses()
        fresh_press = presses > action['presses']
        if fresh_press and (action['active'] or presses - action['presses'] > 1):
            self.finish_gesture('Action stopped. The next hotkey press opens the menu.')
            return
        if not action['active'] and not fresh_press:
            return
        if action['behaviour'] == 'hold':
            if not action['active']:
                if not self.input.begin_hold(target, sequence, toggle=True):
                    self.finish_gesture('Could not hold the configured key.')
                    return
                action['active'] = True
                action['presses'] = presses
                self.status = f'Holding {sequence}. Press {self.key} again to release. Escape cancels.'
                if self.tray is not None:
                    self.tray.setToolTip('RadialMenu - ' + self.status)
                self.changed.emit()
            return
        if not action['active'] or now >= action['next_repeat']:
            if not self.input.repeat_sequence(target, sequence, toggle=True):
                self.finish_gesture('Could not repeat the configured sequence.')
                return
            first = not action['active']
            action['active'] = True
            action['presses'] = presses
            action['next_repeat'] = now + 0.1
            if first:
                self.status = f'Repeating {sequence}. Press {self.key} again to stop. The following press opens the menu. Escape cancels.'
                if self.tray is not None:
                    self.tray.setToolTip('RadialMenu - ' + self.status)
                self.changed.emit()

    def preview(self):
        self.cancel_delivery()
        self.popup.show_at_cursor()

    def toggle_popup(self):
        if self.armed is not None:
            return  # The physical-key monitor owns the next press.
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
        self.popup.hide()
        button = self.popup.buttons[number-1]
        letter = button['sequence']
        if not letter.strip():
            self.cancel_delivery()
            return
        if button.get('behaviour', 'normal') != 'normal':
            self.arm_gesture(self.target, button)
            return
        self.pending = (self.target, letter, time.monotonic() + 5)
        self.status = f'Waiting for the original app to receive {letter}'
        self.changed.emit()
        self.input.restore(self.target)
        self.send_timer.start()

    def deliver_letter(self):
        if self.armed is not None:
            self.deliver_gesture()
            return
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


class SingleKeyEdit(QLineEdit):
    """One typed key, or a named key supplied by the special-key selector."""
    def __init__(self):
        super().__init__()
        self.textEdited.connect(self.replace_typed_key)

    def replace_typed_key(self, text):
        if not text:
            return
        # Also handles paste: retain the last inserted character, wherever the
        # cursor was placed, rather than accumulating a string of keys.
        character = text[max(0, self.cursorPosition() - 1)]
        if character.isascii() and character.isalnum():
            key = character.upper()
        else:
            key = {' ': 'Space', '+': 'Plus', ',': 'Comma'}.get(character, '')
        self.setText(key)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.clear()
            event.accept()
            return
        if event.text() and not (event.modifiers() & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            self.selectAll()
        super().keyPressEvent(event)


class ButtonEditor(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.current = 0
        self.loading = False
        self.application = ''
        self.buttons = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(16)
        self.selector_column = QWidget()
        self.selector_column.setFixedWidth(360)
        left = QVBoxLayout(self.selector_column)
        left.setContentsMargins(0, 0, 0, 0)
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        left.addWidget(self.path_label)
        self.ring = RadialPopup(embedded=True)
        self.ring.setFixedSize(360, 360)
        self.ring.selected.connect(self.select_button)
        left.addWidget(self.ring)
        left.addStretch()
        layout.addWidget(self.selector_column)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_widget = QWidget()
        form = QVBoxLayout(form_widget)
        form.setContentsMargins(0, 0, 14, 0)
        form.setSpacing(4)
        self.button_heading = QLabel()
        form.addWidget(self.button_heading)
        form.addWidget(QLabel('Name'))
        self.name = QLineEdit()
        self.name.setMaxLength(40)
        self.name.setAccessibleName('Button name')
        form.addWidget(self.name)
        self.icons = []
        for title in ('Icon 1', 'Icon 2'):
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
        form.addWidget(QLabel('Behaviour'))
        self.behaviour = QComboBox()
        self.behaviour.setAccessibleName('Button behaviour')
        for mode, marker in BEHAVIOURS.items():
            self.behaviour.addItem(f'{mode.title()} ({marker})', mode)
        form.addWidget(self.behaviour)
        behaviour_hint = QLabel('Press the hotkey to start Hold / Repeat; press again to stop. The following press opens the menu.')
        behaviour_hint.setWordWrap(True)
        form.addWidget(behaviour_hint)
        form.addWidget(QLabel('Build a key or shortcut'))
        modifiers = QHBoxLayout()
        self.modifiers = {}
        for name in ('Ctrl', 'Alt', 'Shift', 'Win'):
            check = QCheckBox(name)
            check.setAccessibleName(f'{name} modifier')
            self.modifiers[name] = check
            modifiers.addWidget(check)
        modifiers.addStretch()
        self.modifiers_only = QCheckBox('Modifiers only')
        self.modifiers_only.toggled.connect(self.modifier_only_changed)
        modifiers.addWidget(self.modifiers_only)
        form.addLayout(modifiers)
        keys = QHBoxLayout()
        self.key = SingleKeyEdit()
        self.key.setAccessibleName('Shortcut key')
        self.key.setPlaceholderText('Type one key, or choose a special key')
        keys.addWidget(self.key, 1)
        self.special_key = QComboBox()
        self.special_key.setAccessibleName('Special key')
        self.special_key.addItem('Special keys…', '')
        for name in ([f'F{i}' for i in range(1, 25)] + [
                'Tab', 'Space', 'Backspace', 'Return', 'Enter', 'Escape',
                'Delete', 'Insert', 'Home', 'End', 'PageUp', 'PageDown',
                'Left', 'Right', 'Up', 'Down', 'Plus', 'Comma']):
            self.special_key.addItem(name, name)
        self.special_key.currentIndexChanged.connect(self.choose_special_key)
        keys.addWidget(self.special_key, 1)
        form.addLayout(keys)
        key_actions = QHBoxLayout()
        self.use_key = QPushButton('Use key')
        self.use_key.clicked.connect(lambda: self.apply_key(append=False))
        key_actions.addWidget(self.use_key)
        self.append_key = QPushButton('Append key')
        self.append_key.clicked.connect(lambda: self.apply_key(append=True))
        key_actions.addWidget(self.append_key)
        key_actions.addStretch()
        form.addLayout(key_actions)
        form.addWidget(QLabel('Button sequence'))
        self.sequence = QLineEdit()
        self.sequence.setAccessibleName('Button sequence')
        self.sequence.setPlaceholderText('Ctrl+C, Ctrl+V')
        form.addWidget(self.sequence)
        self.sequence_hint = QLabel()
        self.sequence_hint.setWordWrap(True)
        form.addWidget(self.sequence_hint)
        self.hold_validator = QRegularExpressionValidator(QRegularExpression('[^,]*'), self.sequence)
        self.message = QLabel()
        self.message.setWordWrap(True)
        right.addWidget(self.message)
        self.actions = QWidget()
        actions = QHBoxLayout(self.actions)
        actions.setContentsMargins(0, 0, 0, 0)
        save = QPushButton('Save Buttons')
        save.clicked.connect(self.save)
        actions.addWidget(save)
        back = QPushButton('Save and Back')
        back.clicked.connect(self.go_back)
        actions.addWidget(back)
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(lambda: self.owner.pages.setCurrentIndex(0))
        actions.addWidget(cancel)
        form.addStretch()
        self.form_scroll.setWidget(form_widget)
        self.form_scroll.setStyleSheet("""QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 10px; }
            QScrollBar::handle:vertical { background: #888888; min-height: 20px; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }""")
        self.form_scroll.viewport().setAutoFillBackground(False)
        form_widget.setAutoFillBackground(False)
        right.insertWidget(0, self.form_scroll, 1)
        right.addWidget(self.actions)
        layout.addLayout(right, 1)
        self.behaviour.currentIndexChanged.connect(self.behaviour_changed)
        for field in (self.key, self.sequence):
            field.textChanged.connect(lambda _text, edit=field: self.normalise_key_field(edit))
        for field in [self.name, *self.icons, self.sequence]:
            field.textChanged.connect(self.update_draft)
        self.behaviour_changed()

    def behaviour_changed(self, *_):
        hold = self.behaviour.currentData() == 'hold'
        self.append_key.setVisible(not hold)
        self.sequence.setValidator(self.hold_validator if hold else None)
        self.sequence.setPlaceholderText('Ctrl+C' if hold else 'Ctrl+C, Ctrl+V')
        self.sequence_hint.setText(
            'Hold accepts one key or shortcut. Blank disables the action.' if hold else
            'Separate keys or shortcuts with commas. Example: Ctrl+A, Delete. Blank disables the action.')
        shortened = hold and ',' in self.sequence.text()
        if shortened:
            self.sequence.setText(self.sequence.text().split(',', 1)[0].strip())
        self.update_draft()
        if shortened and not self.loading:
            self.message.setText('Hold accepts one shortcut; kept the first entry. Unsaved changes.')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        size = min(360, max(240, int(self.width() * .34)))
        self.selector_column.setFixedWidth(size)
        self.ring.setFixedSize(size, size)

    def modifier_only_changed(self, checked):
        self.key.setEnabled(not checked)
        self.special_key.setEnabled(not checked)

    def normalise_key_field(self, field):
        text = normalise_sequence(field.text())
        if field is self.sequence and self.behaviour.currentData() == 'hold':
            text = text.split(',', 1)[0].strip()
        if text != field.text():
            cursor = field.cursorPosition()
            blocked = field.blockSignals(True)
            try:
                field.setText(text)
                field.setCursorPosition(cursor)
            finally:
                field.blockSignals(blocked)
        if field is self.key:
            index = self.special_key.findData(field.text())
            blocked = self.special_key.blockSignals(True)
            try:
                self.special_key.setCurrentIndex(max(0, index))
            finally:
                self.special_key.blockSignals(blocked)

    def choose_special_key(self, index):
        key = self.special_key.itemData(index)
        if key:
            self.key.setText(key)

    def apply_key(self, *, append):
        parts = [name for name, check in self.modifiers.items() if check.isChecked()]
        if not self.modifiers_only.isChecked():
            parts.append(self.key.text().strip())
        chord = '+'.join(parts)
        sequence = self.sequence.text().strip()
        append = append and self.behaviour.currentData() != 'hold'
        candidate = f'{sequence}, {chord}' if append and sequence else chord
        try:
            if self.modifiers_only.isChecked():
                if not parts:
                    raise ValueError('Choose at least one modifier.')
            elif not self.key.text().strip():
                raise ValueError('Enter a key or choose a special key first.')
            parse_sequence(candidate)
        except ValueError as error:
            self.message.setText(str(error))
            return
        self.sequence.setText(candidate)

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
        self.path_label.setText(ntpath.basename(application))
        self.path_label.setToolTip(application)
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
        self.icons[1].setText(button['secondary_icon'])
        self.sequence.setText(button['sequence'])
        self.behaviour.setCurrentIndex(self.behaviour.findData(button.get('behaviour', 'normal')))
        for check in self.modifiers.values():
            check.setChecked(False)
        self.special_key.setCurrentIndex(0)
        self.modifiers_only.setChecked(False)
        self.key.clear()
        # Reflect an existing single shortcut without rewriting its stored text.
        if button['sequence'].strip() and ',' not in button['sequence']:
            parts = [part.strip() for part in button['sequence'].split('+')]
            modifiers, key = parse_sequence(button['sequence'])[0]
            for name, vk in (('Ctrl', 17), ('Alt', 18), ('Shift', 16), ('Win', 91)):
                self.modifiers[name].setChecked(vk in modifiers)
            self.modifiers_only.setChecked(key is None)
            if key is not None:
                self.key.setText(parts[-1])

        self.ring.active_button = self.current
        self.ring.update()
        self.loading = False

    def update_draft(self):
        if self.loading or not self.buttons:
            return
        self.buttons[self.current] = dict(name=self.name.text(), icon=self.icons[0].text(),
            secondary_icon=self.icons[1].text(), sequence=self.sequence.text(),
            behaviour=self.behaviour.currentData())
        self.ring.update()
        self.message.setText('Unsaved changes')

    def save(self):
        try:
            for number, button in enumerate(self.buttons, 1):
                try:
                    normalise_button(button)
                    for path in (button['icon'], button['secondary_icon']):
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


class HotkeyEditor(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(QLabel('Activation hotkey'))
        hint = QLabel('Choose modifiers, then type one letter or digit, or choose a special key. '
                      'Escape is reserved for cancelling actions.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        modifiers = QHBoxLayout()
        self.modifiers = {}
        for name, label in [('Ctrl', 'Ctrl'), ('Shift', 'Shift'), ('Alt', 'Alt'), ('Win', 'Windows')]:
            check = QCheckBox(label)
            check.setAccessibleName(f'{label} hotkey modifier')
            self.modifiers[name] = check
            modifiers.addWidget(check)
            check.toggled.connect(self.update_shortcut)
        modifiers.addStretch()
        layout.addLayout(modifiers)
        keys = QHBoxLayout()
        self.key = SingleKeyEdit()
        self.key.setAccessibleName('Hotkey key')
        self.key.setPlaceholderText('Type one letter or digit')
        keys.addWidget(self.key, 1)
        self.special_key = QComboBox()
        self.special_key.setAccessibleName('Hotkey special key')
        self.special_key.addItem('Special keys…', '')
        for name in ([f'F{i}' for i in range(1, 25)] + [
                'Tab', 'Space', 'Backspace', 'Return', 'Enter',
                'Delete', 'Insert', 'Home', 'End', 'PageUp', 'PageDown',
                'Left', 'Right', 'Up', 'Down', 'Plus', 'Comma']):
            self.special_key.addItem(name, name)
        keys.addWidget(self.special_key, 1)
        layout.addLayout(keys)
        self.shortcut = QLabel()
        self.shortcut.setAccessibleName('Activation hotkey preview')
        self.shortcut.setWordWrap(True)
        layout.addWidget(self.shortcut)
        self.message = QLabel()
        self.message.setAccessibleName('Hotkey validation')
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        layout.addStretch()
        buttons = QHBoxLayout()
        self.save_button = QPushButton('Save Hotkey')
        self.cancel_button = QPushButton('Cancel')
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        self.key.textChanged.connect(self.update_shortcut)
        self.special_key.currentIndexChanged.connect(self.choose_special_key)
        self.save_button.clicked.connect(self.save)
        self.cancel_button.clicked.connect(lambda: owner.pages.setCurrentIndex(0))

    def choose_special_key(self, index):
        key = self.special_key.itemData(index)
        if key:
            self.key.setText(key)

    def load(self):
        self.loading = True
        try:
            parts = self.owner.service.key.split('+')
            selected = {part.strip().lower() for part in parts[:-1]}
            for name, check in self.modifiers.items():
                check.setChecked(name.lower() in selected)
            self.key.setText(parts[-1].strip())
        finally:
            self.loading = False
        self.update_shortcut()

    def update_shortcut(self, *_):
        if self.loading:
            return
        key = normalise_sequence(self.key.text().strip())
        if key != self.key.text():
            self.key.setText(key)
            return
        # Reflect typed keys too, so the dropdown never shows a stale selection.
        index = self.special_key.findData(key)
        blocked = self.special_key.blockSignals(True)
        self.special_key.setCurrentIndex(max(0, index))
        self.special_key.blockSignals(blocked)
        parts = [name for name in ('Ctrl', 'Alt', 'Shift', 'Win') if self.modifiers[name].isChecked()]
        parts.append(key)
        self.candidate = '+'.join(parts)
        self.shortcut.setText('Shortcut: ' + (self.candidate or 'Choose a key'))
        valid, message = self.validate_shortcut()
        self.message.setText(message)
        self.save_button.setEnabled(valid)

    def validate_shortcut(self):
        try:
            modifiers, vk = parse_hotkey(self.candidate)
        except ValueError as error:
            return False, 'Invalid shortcut: ' + str(error)
        service = self.owner.service
        if service.registered and parse_hotkey(service.key) == (modifiers, vk):
            return True, 'Valid shortcut — currently active.'
        if sys.platform != 'win32':
            return False, 'Global hotkeys require Windows.'
        # Probe a separate ID and release it immediately; retain the active listener.
        probe_id = service.HOTKEY_ID + 1
        api = ctypes.windll.user32
        if not api.RegisterHotKey(None, probe_id, modifiers | 0x4000, vk):
            return False, 'Shortcut unavailable — already in use or reserved by Windows.'
        api.UnregisterHotKey(None, probe_id)
        return True, 'Valid shortcut — available. Save Hotkey to apply.'

    def save(self):
        # Registration checks availability again in case another app acquired it.
        if self.owner.service.start(self.candidate):
            self.owner.pages.setCurrentIndex(0)
        else:
            self.message.setText(self.owner.service.status)


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
        self.hotkey_summary = QLabel()
        layout.addWidget(self.hotkey_summary)
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
        self.edit_hotkey = QPushButton('Edit Hotkey')
        layout.addWidget(self.edit_hotkey)
        self.profile_message = QLabel('Choose a running application, or browse for another executable.')
        self.profile_message.setWordWrap(True)
        layout.addWidget(self.profile_message)
        self.about_button = QPushButton('About & Licenses')
        layout.addWidget(self.about_button)
        self.background_button = QPushButton('Run in background')
        layout.addWidget(self.background_button)
        layout.addWidget(QLabel('The activation key works while you use other apps. Restore settings from the system tray.'))
        layout.addWidget(QLabel('Click a segment to select it. Escape, right-click or focus loss dismisses the menu.'))
        self.selection = QLabel('Select a letter to send its keypress to the original application.')
        layout.addWidget(self.selection)
        layout.addStretch()
        self.pages = CurrentPageStack()
        config_scroll = QScrollArea()
        config_scroll.setWidgetResizable(True)
        config_scroll.setFrameShape(QFrame.Shape.NoFrame)
        config_scroll.setWidget(root)
        config_scroll.setStyleSheet("""QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 10px; }
            QScrollBar::handle:vertical { background: #888888; min-height: 20px; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }""")
        config_scroll.viewport().setAutoFillBackground(False)
        root.setAutoFillBackground(False)
        self.pages.addWidget(config_scroll)
        self.setCentralWidget(self.pages)
        self.suite_binding = bind_window(self, 'radial-menu', suite)
        context = self.suite_context
        if not hasattr(context, 'radial_service'):
            context.radial_service = RadialService(context)
        self.service = context.radial_service
        self.app_icons = ApplicationIcons(context.preferences.settings)
        self.hotkey_summary.setText(f'Activation hotkey: {self.service.key}')
        self.segments.setCurrentIndex(self.segments.findData(self.service.popup.count))
        self.status.setText(self.service.status)
        self.segments.currentIndexChanged.connect(self.change_count)
        self.service.changed.connect(self.refresh_status)
        self.service.popup.selected.connect(self.selected_button)
        self.editor = ButtonEditor(self)
        self.pages.addWidget(self.editor)
        self.hotkey_editor = HotkeyEditor(self)
        self.pages.addWidget(self.hotkey_editor)
        self.edit_hotkey.clicked.connect(self.begin_hotkey_edit)
        self.about = AboutPage(lambda: self.pages.setCurrentIndex(0),self)
        self.pages.addWidget(self.about)
        self.pages.currentChanged.connect(self.update_page_title)
        self.about_button.clicked.connect(lambda: self.pages.setCurrentWidget(self.about))
        self.edit_buttons.clicked.connect(self.begin_edit)
        browse_app.clicked.connect(self.browse_application)
        self.application_picker.refreshing.connect(self.refresh_applications)
        self.refresh_applications()
        if self.service.application:
            self.choose_application(self.service.application)
        self.background_button.clicked.connect(lambda: self.service.run_in_background(self.window()))

    def update_page_title(self, *_):
        title = (f'Edit Buttons — {ntpath.basename(self.editor.application)}'
                 if self.pages.currentWidget() is self.editor else
                 'Edit Hotkey' if self.pages.currentWidget() is self.hotkey_editor else 'RadialMenu')
        self.setWindowTitle(title)
        host = self.window()
        if host is self or getattr(host, 'current_app', None) == 'radial-menu':
            host.setWindowTitle(title)

    def begin_hotkey_edit(self):
        self.service.cancel_delivery()
        self.service.popup.hide()
        self.hotkey_editor.load()
        self.pages.setCurrentWidget(self.hotkey_editor)

    def refresh_status(self):
        self.hotkey_summary.setText(f'Activation hotkey: {self.service.key}')
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
