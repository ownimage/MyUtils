import unittest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication
from radial_gui import RadialPopup, popup_geometry

class RadialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_edges_and_negative_monitor(self):
        screen = QRect(-1920, -200, 1920, 1080)
        for point in (screen.topLeft(), screen.bottomRight(), screen.center()):
            x, y, size = popup_geometry(point, screen)
            self.assertTrue(screen.contains(QRect(x, y, size, size)))
        self.assertEqual(popup_geometry(QPoint(50, 50), QRect(0, 0, 100, 80))[2], 80)

    def test_segment_hit_testing(self):
        popup = RadialPopup()
        popup.resize(360, 360)
        for count in (6, 12, 24):
            popup.count = count
            self.assertEqual(popup.segment_at(QPoint(180, 50)), 0)
            self.assertEqual(popup.segment_at(QPoint(180, 310)), count//2)
            self.assertEqual(popup.segment_at(QPoint(180, 180)), -1)
            self.assertEqual(popup.segment_at(QPoint(0, 0)), -1)
        self.assertTrue(popup.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertTrue(popup.windowFlags() & Qt.WindowType.FramelessWindowHint)
        popup.close()

    def test_background_survives_host_close_and_restores_settings(self):
        import tempfile
        from unittest.mock import patch
        from PySide6.QtWidgets import QSystemTrayIcon
        from photo_tools.shell import SuiteContext, SuiteWindow
        from radial_gui import RadialService
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(QSystemTrayIcon, 'isSystemTrayAvailable', return_value=True), \
                patch.object(RadialService, 'start'):
            context = SuiteContext(self.app, settings_path=folder+'/settings.ini')
            window = SuiteWindow(context)
            self.assertTrue(window.open_app('radial-menu', force_new=False))
            service = context.radial_service
            window.show()
            service.run_in_background(window)
            self.assertFalse(window.isVisible())
            self.assertFalse(self.app.quitOnLastWindowClosed())
            window.close()
            self.assertEqual(len(context.windows), 0)
            from PySide6.QtTest import QTest
            from unittest.mock import Mock
            service.input = Mock()
            service.input.running_applications.return_value = []
            service.target = (123, 456, 789)
            service.application = 'C:/Apps/Restored.exe'
            service.popup.show_at_cursor()
            QTest.mouseClick(service.popup.settings_button, Qt.MouseButton.LeftButton)
            self.assertFalse(service.popup.isVisible())
            self.assertIsNone(service.target)
            self.assertIsNone(service.pending)
            service.input.send_letter.assert_not_called()
            self.assertEqual(len(context.windows), 1)
            restored = next(iter(context.windows))
            self.assertTrue(restored.isVisible())
            page = restored.pages['radial-menu']
            self.assertIs(page.service, service)
            self.assertIs(page.pages.currentWidget(), page.editor)
            self.assertEqual(page.editor.application.lower().replace('\\', '/'), 'c:/apps/restored.exe')
            service.tray_menu.actions()[-1].trigger()
            self.assertFalse(service.tray.isVisible())
            self.assertTrue(self.app.quitOnLastWindowClosed())
            self.assertFalse(restored.isVisible())
            self.assertEqual(len(context.windows), 0)
            self.app.aboutToQuit.disconnect(service.stop)
            service.tray.hide()

    @unittest.skipUnless(__import__('sys').platform == 'win32', 'Windows hotkeys')
    def test_hidden_host_receives_hotkey_via_qt_dispatch(self):
        import ctypes
        import tempfile
        from unittest.mock import patch
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QSystemTrayIcon
        from photo_tools.shell import SuiteContext, SuiteWindow
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(QSystemTrayIcon, 'isSystemTrayAvailable', return_value=False), \
                patch('radial_gui.ctypes.windll.user32.RegisterHotKey', return_value=1), \
                patch('radial_gui.ctypes.windll.user32.UnregisterHotKey', return_value=1):
            context = SuiteContext(self.app, settings_path=folder+'/settings.ini')
            host = SuiteWindow(context)
            self.assertTrue(host.open_app('radial-menu', force_new=False))
            service = context.radial_service
            host.hide()
            thread = ctypes.windll.kernel32.GetCurrentThreadId()

            def post(identifier):
                self.assertTrue(ctypes.windll.user32.PostThreadMessageW(thread, 0x312, identifier, 0))
                QTest.qWait(80)

            try:
                post(service.HOTKEY_ID + 1)
                self.assertFalse(service.popup.isVisible())
                post(service.HOTKEY_ID)
                self.assertTrue(service.popup.isVisible())
                self.assertFalse(host.isVisible())
                post(service.HOTKEY_ID)
                self.assertFalse(service.popup.isVisible())
                service.stop()
                post(service.HOTKEY_ID)
                self.assertFalse(service.popup.isVisible())
            finally:
                service.stop()
                self.app.aboutToQuit.disconnect(service.stop)
                host.close()

    def test_letter_waits_for_original_focus_and_sends_once(self):
        import tempfile
        from unittest.mock import Mock, patch
        from photo_tools.shell import SuiteContext
        from radial_gui import RadialService
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(RadialService, 'start'), \
                patch.object(RadialService, 'install_tray'):
            context = SuiteContext(self.app, settings_path=folder+'/settings.ini')
            service = RadialService(context)
            backend = service.input = Mock()
            target = (123, 456, 789)
            backend.capture.return_value = target
            backend.valid.return_value = True
            backend.focused.return_value = False
            backend.keys_released.return_value = True
            backend.send_letter.return_value = True
            try:
                service.toggle_popup()
                self.assertEqual(service.target, target)
                service.popup.hide()
                service.select_letter(12)
                service.send_timer.stop()
                backend.restore.assert_called_once_with(target)
                service.deliver_letter()
                backend.send_letter.assert_not_called()
                backend.focused.return_value = True
                backend.keys_released.return_value = False
                service.deliver_letter()
                backend.send_letter.assert_not_called()
                backend.keys_released.return_value = True
                service.deliver_letter()
                service.deliver_letter()
                backend.send_letter.assert_called_once_with(target, 'L')
                service.preview()
                service.select_letter(1)
                self.assertIsNone(service.pending)
                service.popup.hide()
                service.target = target
                service.select_letter(1)
                backend.valid.return_value = False
                service.deliver_letter()
                self.assertIsNone(service.pending)
                self.assertEqual(backend.send_letter.call_count, 1)
                backend.valid.return_value = True
                service.pending = (target, 'a', 0)
                service.deliver_letter()
                self.assertIsNone(service.pending)
                self.assertEqual(backend.send_letter.call_count, 1)
            finally:
                service.stop()
                self.app.aboutToQuit.disconnect(service.stop)

    def test_windows_key_pair_has_correct_layout_and_focus_guard(self):
        import ctypes
        from unittest.mock import Mock
        from windows_input import WindowsInput, INPUT
        self.assertEqual(ctypes.sizeof(INPUT), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
        backend = WindowsInput.__new__(WindowsInput)
        backend.api = Mock()
        backend.focused = Mock(return_value=False)
        backend.keys_released = Mock(return_value=True)
        target = (12, 34, 56)
        self.assertFalse(backend.send_letter(target, 'l'))
        backend.api.SendInput.assert_not_called()
        backend.focused.return_value = True
        received = []
        def send(count, events, size):
            received.extend((events[i].type, events[i].ki.wVk, events[i].ki.dwFlags) for i in range(count))
            return count
        backend.api.SendInput.side_effect = send
        self.assertTrue(backend.send_letter(target, 'l'))
        self.assertEqual(received, [(1, ord('L'), 0), (1, ord('L'), 2)])

    def test_tray_exit_respects_cancelled_ui_close(self):
        import tempfile
        from unittest.mock import Mock, patch
        from photo_tools.shell import SuiteContext, SuiteWindow
        from radial_gui import RadialService
        with tempfile.TemporaryDirectory() as folder, patch.object(RadialService, 'start'), \
                patch.object(RadialService, 'install_tray'):
            context = SuiteContext(self.app, settings_path=folder+'/settings.ini')
            host = SuiteWindow(context)
            host.open_app('radial-menu', force_new=False)
            host.show()
            page = host.pages['radial-menu']
            service = page.service
            page.dirty = True
            page._discard = Mock(return_value=False)
            try:
                service.exit_background()
                page._discard.assert_called_once()
                self.assertIn(host, context.windows)
                self.assertTrue(host.isVisible())
                self.assertFalse(service.registered)
            finally:
                page.dirty = False
                host.close()
                service.stop()
                self.app.aboutToQuit.disconnect(service.stop)
