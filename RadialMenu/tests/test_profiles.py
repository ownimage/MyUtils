import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PySide6.QtCore import QSettings, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from button_profiles import ButtonProfiles, parse_sequence, app_key
from radial_gui import RadialService
from photo_tools.shell import SuiteContext, SuiteWindow

class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_profiles_are_per_executable_and_survive_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = QSettings(tmp+'/settings.ini', QSettings.Format.IniFormat)
            profiles = ButtonProfiles(settings)
            buttons = profiles.buttons('C:/Apps/One.exe')
            buttons[0].update(name='Copy', icon='normal.png', secondary_icon='second.png', sequence='Ctrl+C')
            profiles.save('C:/Apps/One.exe', buttons)
            again = ButtonProfiles(QSettings(tmp+'/settings.ini', QSettings.Format.IniFormat))
            self.assertEqual(again.buttons('c:/apps/ONE.exe')[0], buttons[0])
            self.assertEqual(again.buttons('C:/Apps/Two.exe')[0]['sequence'], 'a')
            buttons[0]['sequence'] = 'Ctrl+NoSuchKey'
            with self.assertRaises(ValueError):
                profiles.save('C:/Apps/One.exe', buttons)
            self.assertEqual(again.buttons('C:/Apps/One.exe')[0]['sequence'], 'Ctrl+C')

    def test_sequence_validation(self):
        self.assertEqual(parse_sequence('Ctrl+C, Ctrl+V, Enter'), [([17],67),([17],86),([],13)])
        self.assertEqual(parse_sequence('Shift+F12, Win+Left'), [([16],123),([91],37)])
        self.assertEqual(parse_sequence(''), [])
        for invalid in ('Ctrl+', 'Ctrl+Ctrl+C', 'Unknown', 'a,', ',a'):
            with self.assertRaises(ValueError):
                parse_sequence(invalid)

    def test_editor_switches_segments_saves_and_never_sends_input(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(RadialService, 'start'), patch.object(RadialService, 'install_tray'):
            context = SuiteContext(self.app, settings_path=tmp+'/settings.ini')
            host = SuiteWindow(context)
            try:
                self.assertTrue(host.open_app('radial-menu', force_new=False))
                host.show()
                page = host.pages['radial-menu']
                service = page.service
                service.input = Mock()
                page.choose_application('C:/Apps/One.exe')
                QTest.mouseClick(page.edit_buttons, Qt.MouseButton.LeftButton)
                self.assertFalse(service.popup.isVisible())
                self.assertFalse(hasattr(page, 'edit_popup'))
                editor = page.editor
                self.assertIs(page.pages.currentWidget(), editor)
                self.assertIn('one.exe', editor.heading.text())
                editor.name.setText('Copy')
                editor.sequence.setText('Ctrl+C')
                from PySide6.QtGui import QImage, QColor
                image = QImage(24, 24, QImage.Format.Format_ARGB32)
                image.fill(QColor('blue'))
                normal = str(Path(tmp)/'normal.png')
                self.assertTrue(image.save(normal))
                image.fill(QColor('orange'))
                hover = str(Path(tmp)/'hover.png')
                self.assertTrue(image.save(hover))
                editor.icons[0].setText(normal)
                editor.icons[1].setText(hover)
                QTest.mouseClick(editor.ring, Qt.MouseButton.LeftButton, pos=QPoint(180,310))
                self.assertTrue(editor.ring.isVisible())
                self.assertEqual(editor.current, 6)
                editor.name.setText('Paste')
                editor.sequence.setText('Ctrl+V')
                editor.select_button(1)
                self.assertEqual(editor.name.text(), 'Copy')
                self.assertEqual(editor.icons[0].text(), normal)
                self.assertEqual(editor.icons[1].text(), hover)
                self.assertTrue(editor.save())
                self.assertEqual(service.profiles.buttons('C:/Apps/One.exe')[6]['sequence'], 'Ctrl+V')
                self.assertEqual(service.profiles.buttons('C:/Apps/Two.exe')[0]['name'], 'a')
                editor.sequence.setText('InvalidKey')
                self.assertFalse(editor.save())
                self.assertEqual(service.profiles.buttons('C:/Apps/One.exe')[0]['sequence'], 'Ctrl+C')
                service.input.send_letter.assert_not_called()
                service.input.send_sequence.assert_not_called()
                service.input.capture.return_value = (123,456,789)
                service.input.application.return_value = 'C:/Apps/One.exe'
                service.toggle_popup()
                self.assertEqual(service.popup.buttons[0]['name'], 'Copy')
                service.popup.hide()
                service.select_letter(1)
                service.send_timer.stop()
                service.input.valid.return_value = True
                service.input.focused.return_value = True
                service.input.keys_released.return_value = True
                service.deliver_letter()
                service.input.send_sequence.assert_called_once_with((123,456,789), 'Ctrl+C')
            finally:
                if hasattr(context, 'radial_service'):
                    service.stop()
                    self.app.aboutToQuit.disconnect(service.stop)
                host.close()

    def test_chord_input_releases_modifiers_between_shortcuts(self):
        from windows_input import WindowsInput
        backend = WindowsInput.__new__(WindowsInput)
        backend.api = Mock()
        backend.focused = Mock(return_value=True)
        backend.keys_released = Mock(return_value=True)
        events_seen = []
        def send(count, events, size):
            events_seen.extend((events[i].ki.wVk, events[i].ki.dwFlags) for i in range(count))
            return count
        backend.api.SendInput.side_effect = send
        self.assertTrue(backend.send_sequence((1,2,3), 'Ctrl+C, Ctrl+V'))
        self.assertEqual(events_seen, [(17,0),(67,0),(67,2),(17,2),(17,0),(86,0),(86,2),(17,2)])

    def test_legacy_hover_assignment_becomes_second_icon(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            settings = QSettings(tmp+'/settings.ini', QSettings.Format.IniFormat)
            old = dict(name='Both', icon='tabler:outline/palette.svg', hover_icon='phosphor:regular/palette.svg', sequence='a')
            settings.setValue('radial/profiles', json.dumps({app_key('C:/Test.exe'):{'0':old}}))
            profiles = ButtonProfiles(settings)
            buttons = profiles.buttons('C:/Test.exe')
            self.assertEqual(buttons[0]['secondary_icon'],old['hover_icon'])
            profiles.save('C:/Test.exe',buttons)
            saved = profiles.read()[app_key('C:/Test.exe')]['0']
            self.assertNotIn('hover_icon',saved)
            self.assertEqual(saved['secondary_icon'],old['hover_icon'])

    def test_both_icons_remain_visible_before_and_during_hover(self):
        from PySide6.QtGui import QPixmap,QIcon,QColor
        from radial_gui import RadialPopup
        red, blue = QPixmap(20,20), QPixmap(20,20)
        red.fill(QColor('red'))
        blue.fill(QColor('blue'))
        popup = RadialPopup()
        popup.resize(360,360)
        popup.buttons[0].update(icon='first',secondary_icon='second')
        try:
            with patch('radial_gui.button_icon',side_effect=lambda ref,dark: QIcon(red if ref=='first' else blue)):
                for hover in (-1,0):
                    popup.hover = hover
                    image = popup.grab().toImage()
                    self.assertEqual(image.pixelColor(168,50),QColor('red'))
                    self.assertEqual(image.pixelColor(192,50),QColor('blue'))
        finally:
            popup.close()
