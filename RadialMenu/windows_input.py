"""Windows foreground-window capture and keyboard input."""
import ctypes
from ctypes import wintypes as w
import os
from activation_monitor import INPUT_TAG

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', w.LONG), ('dy', w.LONG), ('mouseData', w.DWORD),
                ('dwFlags', w.DWORD), ('time', w.DWORD), ('dwExtraInfo', ctypes.c_size_t)]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', w.WORD), ('wScan', w.WORD), ('dwFlags', w.DWORD),
                ('time', w.DWORD), ('dwExtraInfo', ctypes.c_size_t)]

class INPUTUNION(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _anonymous_ = ('value',)
    _fields_ = [('type', w.DWORD), ('value', INPUTUNION)]

class WindowsInput:
    def __init__(self):
        self.api = ctypes.WinDLL('user32', use_last_error=True)
        self.api.GetForegroundWindow.restype = w.HWND
        self.api.IsWindow.argtypes = [w.HWND]
        self.api.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        self.api.SetForegroundWindow.argtypes = [w.HWND]
        self.api.SendInput.argtypes = [w.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        self.api.SendInput.restype = w.UINT

    def identity(self, hwnd):
        if not hwnd or not self.api.IsWindow(hwnd):
            return None
        pid = w.DWORD()
        thread = self.api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return (hwnd, pid.value, thread) if thread else None

    def capture(self):
        target = self.identity(self.api.GetForegroundWindow())
        return target if target and target[1] != os.getpid() else None

    def valid(self, target):
        return target is not None and self.identity(target[0]) == target

    def focused(self, target):
        return self.valid(target) and self.api.GetForegroundWindow() == target[0]

    def restore(self, target):
        if self.valid(target):
            self.api.SetForegroundWindow(target[0])

    def keys_released(self):
        return not any(self.api.GetAsyncKeyState(key) & 0x8000
                       for key in (0x10, 0x11, 0x12, 0x5b, 0x5c, 0x01, 0x02))

    def send_letter(self, target, letter):
        if not self.focused(target) or not self.keys_released():
            return False
        events = (INPUT * 2)()
        for index, flags in enumerate((0, 2)):
            events[index].type = 1
            events[index].ki = KEYBDINPUT(ord(letter.upper()), 0, flags, 0, INPUT_TAG)
        return self.api.SendInput(2, events, ctypes.sizeof(INPUT)) == 2

    def application(self, target):
        if not self.valid(target):
            return ''
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        kernel.OpenProcess.restype = w.HANDLE
        kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
        kernel.CloseHandle.argtypes = [w.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, target[1])
        if not handle:
            return ''
        try:
            size = w.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            return buffer.value if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)) else ''
        finally:
            kernel.CloseHandle(handle)

    def send_sequence(self, target, sequence):
        from button_profiles import parse_sequence
        chords = parse_sequence(sequence)
        if not self.focused(target) or not self.keys_released():
            return False
        pairs = []
        extended = {33, 34, 35, 36, 37, 38, 39, 40, 45, 46, 91}
        for modifiers, key in chords:
            pairs.extend((vk, 1 if vk in extended else 0) for vk in modifiers)
            if key is not None:
                flag = 1 if key in extended else 0
                pairs.extend(((key, flag), (key, flag | 2)))
            pairs.extend((vk, (1 if vk in extended else 0) | 2) for vk in reversed(modifiers))
        if not pairs:
            return True
        events = (INPUT * len(pairs))()
        for index, (key, flags) in enumerate(pairs):
            events[index].type = 1
            events[index].ki = KEYBDINPUT(key, 0, flags, 0, INPUT_TAG)
        return self.api.SendInput(len(events), events, ctypes.sizeof(INPUT)) == len(events)

    def begin_gesture(self, hotkey):
        from activation_monitor import ActivationMonitor
        if not self.end_gesture():
            return False
        self.gesture_held = []
        self.monitor = ActivationMonitor(hotkey)
        if not self.monitor.start():
            self.monitor = None
            return False
        # Activation modifiers may still be physically held when a button is
        # selected. Clear their logical downs, while the monitor retains physical
        # state, so the first subsequent main-key press injects only our combo.
        release = []
        for generic, sides in ((17, (162, 163)), (18, (164, 165)), (16, (160, 161)), (91, (91, 92))):
            if generic in self.monitor.trigger_keys:
                held = [vk for vk in sides if vk in self.monitor.physical]
                if not held and generic in self.monitor.physical:
                    held = [generic]
                release.extend((vk, self._key_flag(vk) | 2) for vk in held)
        if release and self._gesture_send(list(reversed(release))) != len(release):
            self.end_gesture()
            return False
        return True

    def gesture_state(self):
        return self.monitor.state() if self.monitor else 'cancelled'

    def gesture_presses(self):
        return self.monitor.press_count if self.monitor else 0

    def gesture_safe(self, target, *, allow_mouse=False):
        return (self.focused(target) and self.monitor is not None and
                self.monitor.safe() and (allow_mouse or not any(self.api.GetAsyncKeyState(vk) & 0x8000
                                                               for vk in (1, 2, 4, 5, 6))))

    def _gesture_send(self, pairs):
        events = (INPUT * len(pairs))()
        for index, (key, flags) in enumerate(pairs):
            events[index].type = 1
            events[index].ki = KEYBDINPUT(key, 0, flags, 0, INPUT_TAG)
        return int(self.api.SendInput(len(events), events, ctypes.sizeof(INPUT)))

    def _gesture_batch(self, pairs):
        # Account for partial SendInput delivery so cleanup releases only keys
        # whose downs were actually inserted, including a failed repeat batch.
        count = self._gesture_send(pairs)
        for vk, flags in pairs[:count]:
            if flags & 2:
                if vk in self.gesture_held:
                    self.gesture_held.remove(vk)
            elif vk not in self.gesture_held:
                self.gesture_held.append(vk)
        return count == len(pairs)

    @staticmethod
    def _key_flag(vk):
        return 1 if vk in {33, 34, 35, 36, 37, 38, 39, 40, 45, 46, 91, 92, 163, 165} else 0

    def begin_hold(self, target, sequence, *, toggle=False):
        from button_profiles import parse_sequence
        chords = parse_sequence(sequence)
        state = self.gesture_state()
        if (len(chords) != 1 or not self.gesture_safe(target) or
                (state not in ('down', 'ready') if toggle else state != 'down')):
            return False
        modifiers, key = chords[0]
        return self._gesture_batch([(vk, self._key_flag(vk)) for vk in modifiers + ([key] if key is not None else [])])

    def repeat_sequence(self, target, sequence, *, toggle=False):
        from button_profiles import parse_sequence
        chords = parse_sequence(sequence)
        state = self.gesture_state()
        if (not self.gesture_safe(target, allow_mouse=toggle) or
                (state not in ('down', 'ready') if toggle else state != 'down')):
            return False
        pairs = []
        for modifiers, key in chords:
            pairs.extend((vk, self._key_flag(vk)) for vk in modifiers)
            if key is not None:
                pairs.extend(((key, self._key_flag(key)), (key, self._key_flag(key) | 2)))
            pairs.extend((vk, self._key_flag(vk) | 2) for vk in reversed(modifiers))
        return self._gesture_batch(pairs)

    def end_gesture(self):
        released = True
        for _ in range(2):
            if not getattr(self, 'gesture_held', None):
                released = True
                break
            pairs = [(vk, self._key_flag(vk) | 2) for vk in reversed(self.gesture_held)]
            released = self._gesture_batch(pairs)
            if released:
                break
        monitor = getattr(self, 'monitor', None)
        unhooked = monitor.stop() if monitor else True
        if unhooked:
            self.monitor = None
        return released and unhooked

    def running_applications(self):
        """Visible taskbar-style windows, one entry per executable."""
        callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        self.api.EnumWindows.argtypes = [callback_type, w.LPARAM]
        self.api.IsWindowVisible.argtypes = [w.HWND]
        self.api.GetWindow.argtypes = [w.HWND, w.UINT]
        self.api.GetWindow.restype = w.HWND
        self.api.GetWindowTextLengthW.argtypes = [w.HWND]
        self.api.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
        self.api.GetWindowLongW.argtypes = [w.HWND, ctypes.c_int]
        results = {}
        def visit(hwnd, _):
            if not self.api.IsWindowVisible(hwnd):
                return True
            style = self.api.GetWindowLongW(hwnd, -20)
            if style & 0x80 or (self.api.GetWindow(hwnd, 4) and not style & 0x40000):
                return True
            length = self.api.GetWindowTextLengthW(hwnd)
            if not length:
                return True
            cloaked = w.DWORD()
            dwm = ctypes.windll.dwmapi.DwmGetWindowAttribute
            dwm.argtypes = [w.HWND, w.DWORD, w.LPVOID, w.DWORD]
            if dwm(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)) == 0 and cloaked.value:
                return True
            identity = self.identity(hwnd)
            path = self.application(identity) if identity else ''
            if not path:
                return True
            title = ctypes.create_unicode_buffer(length+1)
            self.api.GetWindowTextW(hwnd, title, length+1)
            from button_profiles import app_key
            results.setdefault(app_key(path), dict(path=path, title=title.value, hwnd=hwnd))
            return True
        self.api.EnumWindows(callback_type(visit), 0)
        return sorted(results.values(), key=lambda item: item['title'].casefold())

    def window_icon(self, hwnd):
        """Copy a window's own icon without blocking on an unresponsive app."""
        from PySide6.QtGui import QIcon, QImage, QPixmap
        self.api.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, ctypes.c_size_t,
            ctypes.c_ssize_t, w.UINT, w.UINT, ctypes.POINTER(ctypes.c_size_t)]
        self.api.SendMessageTimeoutW.restype = ctypes.c_ssize_t
        self.api.GetClassLongPtrW.argtypes = [w.HWND, ctypes.c_int]
        self.api.GetClassLongPtrW.restype = ctypes.c_size_t
        for kind in (1, 2, 0):
            icon = ctypes.c_size_t()
            self.api.SendMessageTimeoutW(hwnd, 0x7f, kind, 0, 2, 50, ctypes.byref(icon))
            if icon.value:
                image = QImage.fromHICON(icon.value)
                if not image.isNull():
                    return QIcon(QPixmap.fromImage(image))
        for index in (-14, -34):
            handle = self.api.GetClassLongPtrW(hwnd, index)
            if handle:
                image = QImage.fromHICON(handle)
                if not image.isNull():
                    return QIcon(QPixmap.fromImage(image))
        return QIcon()
