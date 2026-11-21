import os
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image
from PySide6.QtSvg import QSvgRenderer
from photo_tools.app_icons import ICONS


class AppIconTests(unittest.TestCase):
    def test_vector_sources_and_multiresolution_windows_icons(self):
        names = {'launcher', 'camera-import', 'yearbook', 'slideshow', 'radial-menu'}
        self.assertEqual({path.stem for path in ICONS.glob('*.svg')}, names)
        for name in names:
            self.assertTrue(QSvgRenderer(str(ICONS / (name + '.svg'))).isValid())
            with Image.open(ICONS / (name + '.ico')) as image:
                self.assertEqual(image.ico.sizes(), {(size, size) for size in (16,20,24,32,40,48,64,128,256)})
                self.assertEqual(image.convert('RGBA').getpixel((0, 0))[3], 0)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows taskbar metadata')
    def test_native_taskbar_identity_and_icon_properties(self):
        code = """
from PySide6.QtWidgets import QApplication, QMainWindow
from photo_tools.app_icons import set_window_identity, clear_window_identity
from photo_tools.registry import load_apps
from win32com.propsys import propsys, pscon
import win32gui, win32con
app = QApplication([])
windows = []
for definition in [*load_apps().values(), None]:
    window = QMainWindow()
    windows.append(window)
    set_window_identity(window, definition)
    store = propsys.SHGetPropertyStoreForWindow(int(window.winId()))
    suffix = definition.id if definition else 'launcher'
    assert store.GetValue(pscon.PKEY_AppUserModel_ID).GetValue() == 'MyUtils.' + suffix
    resource = store.GetValue(pscon.PKEY_AppUserModel_RelaunchIconResource).GetValue()
    assert resource.endswith(suffix + '.ico,0'), resource
    command = store.GetValue(pscon.PKEY_AppUserModel_RelaunchCommand).GetValue()
    assert 'pythonw.exe' in command and '.py' in command, command
    assert not window.windowIcon().isNull()
    hwnd = int(window.winId())
    assert win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0)
    assert win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
for window in windows:
    clear_window_identity(window)
    store = propsys.SHGetPropertyStoreForWindow(int(window.winId()))
    assert store.GetValue(pscon.PKEY_AppUserModel_ID).vt == 0
print('Native taskbar properties verified')
"""
        environment = dict(os.environ, QT_QPA_PLATFORM='windows')
        result = subprocess.run([sys.executable, '-c', code], env=environment,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Native taskbar properties verified', result.stdout)
