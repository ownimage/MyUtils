"""Suite icon assets and per-window Windows taskbar identity."""
from pathlib import Path
import logging
import subprocess
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

ICONS = Path(__file__).resolve().parents[1] / 'assets' / 'icons'


def app_icon(name='launcher'):
    return QIcon(str(ICONS / (name + '.ico')))


def set_process_identity(app_id=None):
    if sys.platform == 'win32':
        import ctypes
        function = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        function.argtypes = [ctypes.c_wchar_p]
        function.restype = ctypes.c_long
        result = function('MyUtils.' + (app_id or 'launcher'))
        if result < 0:
            logging.getLogger(__name__).warning('Could not set taskbar process identity: %s', result)


def set_window_identity(window, definition=None):
    name = definition.icon if definition else 'launcher'
    window.setWindowIcon(app_icon(name))
    if sys.platform != 'win32' or QApplication.platformName() != 'windows':
        return
    from win32com.propsys import propsys, pscon
    # Window-level IDs keep different suite apps distinct on the taskbar even
    # when their windows share a Python process. Set relaunch details first.
    script = (definition.folder / (definition.module + '.py') if definition else
              Path(__file__).resolve().parents[1] / 'launcher.py')
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    command = subprocess.list2cmdline([str(pythonw), '-X', 'utf8', str(script)])
    store = propsys.SHGetPropertyStoreForWindow(int(window.winId()))
    for key, value in (
        (pscon.PKEY_AppUserModel_RelaunchCommand, command),
        (pscon.PKEY_AppUserModel_RelaunchDisplayNameResource, definition.name if definition else 'MyUtils Launcher'),
        (pscon.PKEY_AppUserModel_RelaunchIconResource, str(ICONS / (name + '.ico')) + ',0'),
        (pscon.PKEY_AppUserModel_ID, 'MyUtils.' + (definition.id if definition else 'launcher')),
    ):
        store.SetValue(key, propsys.PROPVARIANTType(value))
    window._suite_taskbar_properties = True


def clear_window_identity(window):
    if not getattr(window, '_suite_taskbar_properties', False):
        return
    from win32com.propsys import propsys, pscon
    store = propsys.SHGetPropertyStoreForWindow(int(window.winId()))
    for key in (pscon.PKEY_AppUserModel_ID, pscon.PKEY_AppUserModel_RelaunchCommand,
                pscon.PKEY_AppUserModel_RelaunchDisplayNameResource,
                pscon.PKEY_AppUserModel_RelaunchIconResource):
        store.SetValue(key, propsys.PROPVARIANTType(None))
    window._suite_taskbar_properties = False
