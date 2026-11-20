"""Temporary physical-key capture for one armed Hold/Repeat action."""
import ctypes
import os
from button_profiles import parse_sequence
from ctypes import wintypes as w

INPUT_TAG = 0x524D0000 | (os.getpid() & 0xffff)



def parse_hotkey(text):
    chords = parse_sequence(text)
    if len(chords) != 1 or chords[0][1] is None:
        raise ValueError('Choose one key with optional Ctrl, Alt, Shift or Win modifiers.')
    mods, vk = chords[0]
    if vk == 27:
        raise ValueError('Escape is reserved for cancelling actions.')
    flags = {17: 2, 18: 1, 16: 4, 91: 8}
    return sum(flags[mod] for mod in mods), vk


MODIFIER_KEYS = {16, 17, 18, 91, 92, 160, 161, 162, 163, 164, 165}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [('vkCode', w.DWORD), ('scanCode', w.DWORD), ('flags', w.DWORD),
                ('time', w.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class ActivationMonitor:
    def __init__(self, key):
        modifiers, vk = parse_hotkey(key)
        self.primary_key = vk
        self.groups = [{vk}]
        if modifiers & 2:
            self.groups.append({17, 162, 163})
        if modifiers & 1:
            self.groups.append({18, 164, 165})
        if modifiers & 4:
            self.groups.append({16, 160, 161})
        if modifiers & 8:
            self.groups.append({91, 92})
        self.trigger_keys = set().union(*self.groups)
        self.physical = set()
        self.ready = False
        self.cancelled = False
        self.press_count = 0
        self.handle = None
        self.callback = None

    def start(self):
        self.api = ctypes.WinDLL('user32', use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, w.WPARAM, w.LPARAM)
        self.api.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, w.HINSTANCE, w.DWORD]
        self.api.SetWindowsHookExW.restype = w.HHOOK
        self.api.CallNextHookEx.argtypes = [w.HHOOK, ctypes.c_int, w.WPARAM, w.LPARAM]
        self.api.CallNextHookEx.restype = ctypes.c_ssize_t
        self.api.UnhookWindowsHookEx.argtypes = [w.HHOOK]
        self.physical = {vk for vk in self.trigger_keys | MODIFIER_KEYS
                         if self.api.GetAsyncKeyState(vk) & 0x8000}
        self.ready = self.primary_key not in self.physical
        self.callback = callback_type(self.key_event)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
        kernel.GetModuleHandleW.restype = w.HMODULE
        self.handle = self.api.SetWindowsHookExW(13, self.callback, kernel.GetModuleHandleW(None), 0)
        return bool(self.handle)

    def key_event(self, code, message, address):
        if code >= 0:
            event = KBDLLHOOKSTRUCT.from_address(address)
            # Ignore our own output, but accept hotkeys from mouse software and
            # remappers which also use injected input.
            own_output = event.flags & 0x10 and event.dwExtraInfo == INPUT_TAG
            if not own_output and message in (0x100, 0x101, 0x104, 0x105):
                was_ready = self.ready
                was_down = all(self.physical & group for group in self.groups)
                down = message in (0x100, 0x104)
                if down:
                    self.physical.add(event.vkCode)
                else:
                    self.physical.discard(event.vkCode)
                    # GetAsyncKeyState seeds generic aliases; LL events use sides.
                    generic = {160: 16, 161: 16, 162: 17, 163: 17, 164: 18, 165: 18}.get(event.vkCode)
                    if generic:
                        self.physical.discard(generic)
                if event.vkCode == 27:
                    self.cancelled = True
                    return 1
                if self.primary_key not in self.physical:
                    self.ready = True
                if was_ready and not was_down and all(self.physical & group for group in self.groups):
                    self.press_count += 1
                # Only the opening main key must release. Ctrl/Alt may stay
                # held across selection and the next Space/R press must count.
                # Thereafter swallow activation keys, including their modifiers.
                if was_ready and event.vkCode in self.trigger_keys:
                    return 1
        return self.api.CallNextHookEx(self.handle, code, message, address)

    def state(self):
        if self.cancelled:
            return 'cancelled'
        if not self.ready:
            return 'waiting'
        return 'down' if all(self.physical & group for group in self.groups) else 'ready'

    def safe(self):
        return not bool(self.physical & (MODIFIER_KEYS - self.trigger_keys))

    def stop(self):
        if self.handle:
            if not self.api.UnhookWindowsHookEx(self.handle):
                return False
            self.handle = None
        return True
