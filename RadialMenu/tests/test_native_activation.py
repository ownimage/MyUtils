"""Opt-in native SendInput/hook/receiver integration (own focused window only)."""
import ctypes
import os
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from photo_tools.shell import SuiteContext
from radial_gui import RadialService
from windows_input import INPUT, KEYBDINPUT


@unittest.skipUnless(os.environ.get('RADIALMENU_NATIVE_INPUT_TEST') == '1', 'Opt-in focused native receiver')
class NativeActivationTests(unittest.TestCase):
    def test_remapped_repeat_and_toggled_hold_into_native_receiver(self):
        app = QApplication.instance() or QApplication([])
        class Receiver(QWidget):
            def __init__(self):
                super().__init__()
                self.events = []
            def keyPressEvent(self, event):
                if event.key() == Qt.Key.Key_F24:
                    self.events.append(('down', event.modifiers()))
                event.accept()
            def keyReleaseEvent(self, event):
                if event.key() == Qt.Key.Key_F24:
                    self.events.append(('up', event.modifiers()))
                event.accept()
        receiver = Receiver()
        receiver.setWindowTitle('RadialMenu isolated input test')
        receiver.resize(320, 100)
        receiver.show()
        receiver.raise_()
        receiver.activateWindow()
        receiver.setFocus()
        with tempfile.TemporaryDirectory() as tmp, patch.object(RadialService, 'start'), patch.object(RadialService, 'install_tray'):
            service = RadialService(SuiteContext(app, settings_path=tmp+'/settings.ini'))
            backend = service.input
            target = backend.identity(int(receiver.winId()))
            backend.restore(target)
            for _ in range(5):
                receiver.raise_()
                receiver.activateWindow()
                backend.restore(target)
                QTest.qWait(100)
                if backend.focused(target):
                    break
            if not backend.focused(target):
                # A background test runner may need to join the foreground input
                # queue briefly to activate its own receiver. Always detach before
                # input, and still refuse injection unless the receiver is focused.
                foreground = backend.identity(backend.api.GetForegroundWindow())
                current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
                if foreground and foreground[2] != current_thread:
                    attached = backend.api.AttachThreadInput(current_thread, foreground[2], True)
                    try:
                        backend.restore(target)
                    finally:
                        if attached:
                            backend.api.AttachThreadInput(current_thread, foreground[2], False)
                    QTest.qWait(100)
            try:
                if not backend.focused(target):
                    self.skipTest('Windows did not grant foreground focus to the isolated receiver')
                def trigger(down, keys=None):
                    self.assertTrue(backend.focused(target), 'Refuse injection outside isolated receiver')
                    keys = keys if keys is not None else ((162, 164, 32) if down else (32, 164, 162))
                    events = (INPUT * len(keys))()
                    for i, vk in enumerate(keys):
                        events[i].type = 1
                        # Tag zero models input from a mouse/remapper, not our output.
                        events[i].ki = KEYBDINPUT(vk, 0, 0 if down else 2, 0, 0)
                    self.assertEqual(backend.api.SendInput(len(events), events, ctypes.sizeof(INPUT)), len(events))
                def arm(mode):
                    service.target = target
                    service.popup.buttons[0].update(sequence='F24', behaviour=mode)
                    service.select_letter(1)
                    QTest.qWait(40)
                arm('repeat')
                trigger(True)
                trigger(False)
                QTest.qWait(260)
                self.assertGreaterEqual(sum(kind == 'down' for kind, _ in receiver.events), 2)
                self.assertEqual(sum(kind == 'down' for kind, _ in receiver.events),
                                 sum(kind == 'up' for kind, _ in receiver.events))
                self.assertTrue(all(mods == Qt.KeyboardModifier.NoModifier for _, mods in receiver.events))
                self.assertIsNotNone(service.armed)
                trigger(True)
                trigger(False)
                QTest.qWait(60)
                self.assertFalse(service.popup.isVisible())
                count = len(receiver.events)
                QTest.qWait(120)
                self.assertEqual(len(receiver.events), count)
                self.assertIsNone(service.armed)
                receiver.events.clear()
                # Keep Ctrl+Alt held across selecting Hold, then tap only Space.
                trigger(True)
                trigger(False, (32,))
                QTest.qWait(40)
                arm('hold')
                self.assertEqual(receiver.events, [], 'Selection must not start Hold')
                trigger(True, (32,))
                trigger(False, (32,))
                QTest.qWait(80)
                self.assertEqual([kind for kind, _ in receiver.events], ['down'])
                self.assertEqual(receiver.events[0][1], Qt.KeyboardModifier.NoModifier)
                QTest.qWait(120)
                self.assertEqual([kind for kind, _ in receiver.events], ['down'])
                trigger(True, (32,))
                trigger(False, (32,))
                QTest.qWait(80)
                trigger(False, (164,162))
                self.assertEqual([kind for kind, _ in receiver.events], ['down', 'up'])
                self.assertIsNone(service.armed)
            finally:
                service.stop()
                # Balance only activation modifiers inserted by this test,
                # including failure paths before the monitor is installed.
                releases = (INPUT * 2)()
                for i, vk in enumerate((164, 162)):
                    releases[i].type = 1
                    releases[i].ki = KEYBDINPUT(vk, 0, 2, 0, 0)
                backend.api.SendInput(2, releases, ctypes.sizeof(INPUT))
                app.aboutToQuit.disconnect(service.stop)
                receiver.close()
