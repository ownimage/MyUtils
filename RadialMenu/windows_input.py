"""Windows foreground-window capture and keyboard input."""
import ctypes
from ctypes import wintypes as w
import os

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
            events[index].ki = KEYBDINPUT(ord(letter.upper()), 0, flags, 0, 0)
        return self.api.SendInput(2, events, ctypes.sizeof(INPUT)) == 2
