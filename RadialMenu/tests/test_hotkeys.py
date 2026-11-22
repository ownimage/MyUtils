import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from activation_monitor import ActivationMonitor, parse_hotkey
from photo_tools.shell import SuiteContext, SuiteWindow
from radial_gui import RadialService


class HotkeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_custom_shortcut_and_capture_modifiers(self):
        self.assertEqual(parse_hotkey('Ctrl+Alt+Space'), (3, 32))
        self.assertEqual(parse_hotkey('Shift+Win+F12'), (12, 123))
        monitor = ActivationMonitor('Shift+Win+F12')
        self.assertIn({16, 160, 161}, monitor.groups)
        self.assertIn({91, 92}, monitor.groups)
        for value in ('', 'Ctrl', 'A, B', 'Escape', 'Ctrl+Ctrl+A', 'BadKey'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_hotkey(value)

    def test_editor_navigation_save_cancel_conflict_and_reload(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(RadialService, 'install_tray'), \
                patch('radial_gui.ctypes.windll.user32.RegisterHotKey', return_value=1) as register, \
                patch('radial_gui.ctypes.windll.user32.UnregisterHotKey', return_value=1):
            context = SuiteContext(self.app, settings_path=folder+'/settings.ini')
            host = SuiteWindow(context)
            self.assertTrue(host.open_app('radial-menu', force_new=False))
            page = host.pages['radial-menu']
            service = page.service
            try:
                layout = page.edit_buttons.parentWidget().layout()
                hotkey_row = layout.itemAt(1).layout()
                self.assertEqual(hotkey_row.indexOf(page.hotkey_summary), 1)
                self.assertEqual(hotkey_row.indexOf(page.edit_hotkey), 2)
                self.assertEqual(layout.itemAt(0).layout().indexOf(page.appearance), 1)
                self.assertEqual(layout.itemAt(2).layout().indexOf(page.segments), 1)
                app_row = layout.itemAt(4).layout()
                self.assertEqual(app_row.indexOf(page.application_picker), 1)
                self.assertEqual(app_row.indexOf(page.application_help), 2)
                self.assertTrue(page.profile_message.isHidden())
                page.edit_hotkey.click()
                editor = page.hotkey_editor
                self.assertIs(page.pages.currentWidget(), editor)
                editor.modifiers['Ctrl'].setChecked(False)
                editor.modifiers['Alt'].setChecked(False)
                editor.modifiers['Shift'].setChecked(True)
                editor.special_key.setCurrentIndex(editor.special_key.findData('F12'))
                editor.cancel_button.click()
                self.assertEqual(service.key, 'Ctrl+Alt+Space')
                page.edit_hotkey.click()
                self.assertEqual(editor.candidate, service.key)
                editor.modifiers['Ctrl'].setChecked(False)
                editor.modifiers['Alt'].setChecked(False)
                editor.modifiers['Shift'].setChecked(True)
                editor.modifiers['Win'].setChecked(True)
                editor.special_key.setCurrentIndex(editor.special_key.findData('F12'))
                self.assertIn('Valid shortcut', editor.message.text())
                self.assertTrue(editor.save_button.isEnabled())
                editor.save_button.click()
                self.assertEqual(service.key, 'Shift+Win+F12')
                register.assert_called_with(None, service.HOTKEY_ID, 12 | 0x4000, 123)
                self.assertEqual(service.settings.value('radial/key'), service.key)
                self.assertEqual(page.pages.currentIndex(), 0)
                page.edit_hotkey.click()
                editor.key.clear()
                editor.save_button.click()
                self.assertTrue(service.registered)
                self.assertIs(page.pages.currentWidget(), editor)
                self.assertFalse(editor.save_button.isEnabled())
                self.assertIn('Invalid shortcut', editor.message.text())
                editor.key.setText('F9')
                register.side_effect = [0, 1]
                editor.save_button.click()
                self.assertEqual(service.key, 'Shift+Win+F12')
                self.assertTrue(service.registered)
                self.assertIn('unavailable', editor.message.text())
                self.assertEqual(service.settings.value('radial/key'), 'Shift+Win+F12')
                register.side_effect = None
                register.return_value = 0
                editor.key.setText('F10')
                self.assertFalse(editor.save_button.isEnabled())
                self.assertIn('unavailable', editor.message.text())
                self.assertTrue(service.registered)
                self.assertEqual(service.key, 'Shift+Win+F12')
                register.return_value = 1
                editor.key.setText('a')
                self.assertEqual(editor.key.text(), 'A')
                self.assertEqual(editor.special_key.currentIndex(), 0)
                self.assertTrue(editor.save_button.isEnabled())
                editor.key.setText('Escape')
                self.assertFalse(editor.save_button.isEnabled())
                service.stop()
                restored = RadialService(context)
                self.assertEqual(restored.key, 'Shift+Win+F12')
                restored.stop()
                self.app.aboutToQuit.disconnect(restored.stop)
            finally:
                service.stop()
                self.app.aboutToQuit.disconnect(service.stop)
                host.close()

    def test_typing_dropdown_sync_and_availability_probe_preserves_listener(self):
        from unittest.mock import Mock
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from radial_gui import HotkeyEditor
        from PySide6.QtWidgets import QWidget
        owner = QWidget()
        owner.service = Mock(key='Ctrl+Alt+Space', registered=True, HOTKEY_ID=0x524D)
        owner.pages = Mock()
        with patch('radial_gui.ctypes.windll.user32.RegisterHotKey', return_value=1) as register, \
                patch('radial_gui.ctypes.windll.user32.UnregisterHotKey', return_value=1) as unregister:
            editor = HotkeyEditor(owner)
            editor.resize(760, 460)
            editor.show()
            try:
                editor.load()
                self.assertIn('currently active', editor.message.text())
                register.assert_not_called()
                editor.special_key.setCurrentIndex(editor.special_key.findData('F24'))
                self.assertEqual(editor.candidate, 'Ctrl+Alt+F24')
                register.assert_called_with(None, 0x524E, 3 | 0x4000, 135)
                unregister.assert_called_with(None, 0x524E)
                editor.key.setFocus()
                QTest.keyClicks(editor.key, 'abc')
                self.assertEqual(editor.key.text(), 'C')
                self.assertEqual(editor.special_key.currentIndex(), 0)
                QTest.keyClick(editor.key, Qt.Key.Key_Backspace)
                self.assertFalse(editor.save_button.isEnabled())
                editor.save_button.click()
                owner.service.start.assert_not_called()
                self.app.processEvents()
                self.assertTrue(editor.rect().contains(editor.save_button.geometry().topLeft()))
                self.assertTrue(editor.rect().contains(editor.save_button.geometry().bottomRight()))
            finally:
                editor.close()
                owner.close()
