import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PySide6.QtCore import QSettings, QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel
from button_profiles import ButtonProfiles, parse_sequence, app_key, normalise_sequence
from radial_gui import RadialService, ButtonEditor
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
            self.assertEqual(again.buttons('C:/Apps/Two.exe')[0]['sequence'], 'A')
            buttons[0]['sequence'] = 'Ctrl+NoSuchKey'
            with self.assertRaises(ValueError):
                profiles.save('C:/Apps/One.exe', buttons)
            self.assertEqual(again.buttons('C:/Apps/One.exe')[0]['sequence'], 'Ctrl+C')

    def test_letter_key_spelling_is_normalised_without_adding_shift(self):
        source = 'Ctrl+Alt+a, Shift+b, z, F24, Return'
        canonical = 'Ctrl+Alt+A, Shift+B, Z, F24, Return'
        self.assertEqual(normalise_sequence(source), canonical)
        self.assertEqual(parse_sequence(source), parse_sequence(canonical))
        self.assertEqual(normalise_sequence('Ctrl+'), 'Ctrl+')
        with tempfile.TemporaryDirectory() as tmp:
            import json
            settings = QSettings(tmp+'/settings.ini', QSettings.Format.IniFormat)
            profiles = ButtonProfiles(settings)
            buttons = profiles.buttons('C:/Test.exe')
            buttons[0]['sequence'] = source
            # Existing profiles normalise on read, and persist canonical text on save.
            settings.setValue('radial/profiles', json.dumps({app_key('C:/Test.exe'): {'0': buttons[0]}}))
            self.assertEqual(profiles.buttons('C:/Test.exe')[0]['sequence'], canonical)
            profiles.save('C:/Test.exe', buttons)
            self.assertEqual(profiles.read()[app_key('C:/Test.exe')]['0']['sequence'], canonical)

    def test_key_entry_overtypes_and_special_keys_remain_single_choices(self):
        editor = ButtonEditor(Mock())
        editor.show()
        try:
            field = editor.key
            field.setFocus()
            QTest.keyClicks(field, 'abc')
            self.assertEqual(field.text(), 'C')
            field.setCursorPosition(0)
            QTest.keyClicks(field, '7')
            self.assertEqual(field.text(), '7')
            editor.special_key.setCurrentIndex(editor.special_key.findData('F24'))
            self.assertEqual(field.text(), 'F24')
            QTest.keyClicks(field, 'z')
            self.assertEqual(field.text(), 'Z')
            self.assertEqual(editor.special_key.currentText(), 'Special keys…')
            # Selecting the same special key again must work after typing.
            editor.special_key.setCurrentIndex(editor.special_key.findData('F24'))
            self.assertEqual(field.text(), 'F24')
            self.app.clipboard().setText('hello')
            QTest.keyClick(field, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(field.text(), 'O')
            editor.special_key.setCurrentIndex(editor.special_key.findData('Backspace'))
            self.assertEqual(field.text(), 'Backspace')
            QTest.keyClick(field, Qt.Key.Key_Backspace)
            self.assertEqual(field.text(), '')
            self.assertEqual(editor.special_key.currentText(), 'Special keys…')
            # The sequence field continues to allow multiple chords.
            QTest.keyClicks(editor.sequence, 'Ctrl+A, Tab')
            self.assertEqual(editor.sequence.text(), 'Ctrl+A, Tab')
        finally:
            editor.close()

    def test_behaviour_migration_validation_and_editor_round_trip(self):
        import json
        with tempfile.TemporaryDirectory() as tmp, patch.object(RadialService, 'start'), patch.object(RadialService, 'install_tray'):
            context = SuiteContext(self.app, settings_path=tmp+'/settings.ini')
            service = RadialService(context)
            owner = Mock(service=service)
            editor = ButtonEditor(owner)
            try:
                old = dict(name='Old', icon='', secondary_icon='', sequence='A')
                service.settings.setValue('radial/profiles', json.dumps({app_key('C:/Test.exe'): {'0': old}}))
                self.assertEqual(service.profiles.buttons('C:/Test.exe')[0]['behaviour'], 'normal')
                editor.load_application('C:/Test.exe')
                for mode in ('hold', 'repeat', 'normal'):
                    editor.behaviour.setCurrentIndex(editor.behaviour.findData(mode))
                    self.assertEqual(editor.buttons[0]['behaviour'], mode)
                    editor.select_button(2)
                    editor.select_button(1)
                    self.assertEqual(editor.behaviour.currentData(), mode)
                    self.assertTrue(editor.save())
                    self.assertEqual(service.profiles.buttons('C:/Test.exe')[0]['behaviour'], mode)
                editor.sequence.setText('Ctrl+A, B')
                editor.behaviour.setCurrentIndex(editor.behaviour.findData('hold'))
                self.assertTrue(editor.append_key.isHidden())
                self.assertEqual(editor.sequence.text(), 'Ctrl+A')
                self.assertIn('first entry', editor.message.text())
                editor.sequence.setText('Ctrl+A, B')
                self.assertEqual(editor.sequence.text(), 'Ctrl+A')
                editor.sequence.setCursorPosition(len(editor.sequence.text()))
                QTest.keyClicks(editor.sequence, ',')
                self.assertEqual(editor.sequence.text(), 'Ctrl+A')
                editor.key.setText('Z')
                editor.apply_key(append=True)
                self.assertEqual(editor.sequence.text(), 'Z')
                self.assertTrue(editor.save())
                self.assertEqual(service.profiles.buttons('C:/Test.exe')[0]['behaviour'], 'hold')
                for mode in ('repeat', 'normal'):
                    editor.behaviour.setCurrentIndex(editor.behaviour.findData(mode))
                    self.assertFalse(editor.append_key.isHidden())
                    editor.sequence.setText('A')
                    editor.key.setText('B')
                    editor.apply_key(append=True)
                    self.assertEqual(editor.sequence.text(), 'A, B')
                buttons = service.profiles.buttons('C:/Test.exe')
                buttons[0]['behaviour'] = 'invalid'
                with self.assertRaises(ValueError):
                    service.profiles.save('C:/Test.exe', buttons)
            finally:
                editor.close()
                service.stop()
                self.app.aboutToQuit.disconnect(service.stop)

    def test_modifier_only_builder_round_trip_and_short_screen_layout(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(RadialService, 'start'), patch.object(RadialService, 'install_tray'):
            context = SuiteContext(self.app, settings_path=tmp+'/settings.ini')
            host = SuiteWindow(context)
            try:
                host.open_app('radial-menu', force_new=False)
                page = host.pages['radial-menu']
                page.choose_application('C:/Apps/One.exe')
                with patch.object(host, 'screen') as screen:
                    screen.return_value.availableGeometry.return_value = QRect(0, 0, 1024, 700)
                    host.resize(1160, 940)
                    host.open_app('radial-menu', force_new=False)
                    self.assertLessEqual(host.width(), 1024)
                    self.assertLessEqual(host.height(), 660)
                page.begin_edit()
                host.resize(900, 620)
                host.show()
                self.app.processEvents()
                editor = page.editor
                self.assertEqual(host.windowTitle(), 'Edit Buttons — one.exe')
                self.assertFalse(any(label.isVisible() and label.text().startswith('Edit Buttons')
                                     for label in editor.findChildren(QLabel)))
                self.assertLessEqual(host.height(), 620)
                self.assertLessEqual(host.width(), 900)
                self.assertLess(editor.name.mapTo(editor, QPoint()).y(), 32)
                self.assertTrue(editor.rect().contains(editor.actions.geometry()))
                key_y = editor.key.mapTo(editor, editor.key.rect().center()).y()
                for button in (editor.use_key, editor.append_key):
                    self.assertLessEqual(abs(key_y - button.mapTo(editor, button.rect().center()).y()), 1)
                editor.modifiers_only.setChecked(True)
                editor.apply_key(append=False)
                self.assertIn('at least one modifier', editor.message.text())
                editor.modifiers['Ctrl'].setChecked(True)
                editor.modifiers['Alt'].setChecked(True)
                self.assertFalse(editor.key.isEnabled())
                self.assertFalse(editor.special_key.isEnabled())
                editor.apply_key(append=False)
                self.assertEqual(editor.sequence.text(), 'Ctrl+Alt')
                self.assertTrue(editor.save())
                editor.select_button(2)
                editor.select_button(1)
                self.assertTrue(editor.modifiers_only.isChecked())
                self.assertTrue(editor.modifiers['Ctrl'].isChecked())
                self.assertTrue(editor.modifiers['Alt'].isChecked())
                self.assertEqual(editor.key.text(), '')
                self.assertEqual(page.service.profiles.buttons('C:/Apps/One.exe')[0]['sequence'], 'Ctrl+Alt')
                editor.go_back()
                self.assertEqual(host.windowTitle(), 'RadialMenu')
            finally:
                page.service.stop()
                self.app.aboutToQuit.disconnect(page.service.stop)
                host.close()

    def test_modifier_only_sequences_validate_without_duplicate_modifiers(self):
        self.assertEqual(parse_sequence('Ctrl'), [([17], None)])
        self.assertEqual(parse_sequence('Ctrl+Alt+Shift+Win'), [([17,18,16,91], None)])
        self.assertEqual(parse_sequence('Shift, Ctrl+A'), [([16],None),([17],65)])
        for invalid in ('Ctrl+Ctrl', 'Alt+Shift+Alt', 'Ctrl+', '+Shift'):
            with self.assertRaises(ValueError):
                parse_sequence(invalid)

    def test_sequence_validation(self):
        self.assertEqual(parse_sequence('Ctrl+C, Ctrl+V, Enter'), [([17],67),([17],86),([],13)])
        self.assertEqual(parse_sequence('Shift+F12, Win+Left'), [([16],123),([91],37)])
        self.assertEqual(parse_sequence(''), [])
        for invalid in ('Ctrl+', 'Ctrl+Ctrl+C', 'Unknown', 'a,', ',a'):
            with self.assertRaises(ValueError):
                parse_sequence(invalid)

    def test_cog_opens_editor_and_configuration_round_trip_preserves_drafts(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(RadialService, 'start'), patch.object(RadialService, 'install_tray'):
            context = SuiteContext(self.app, settings_path=tmp+'/settings.ini')
            host = SuiteWindow(context)
            host.open_app('radial-menu', force_new=False)
            page = host.pages['radial-menu']
            service = page.service
            try:
                service.application = 'C:/Apps/One.exe'
                host.show()
                service.popup.show_at_cursor()
                QTest.mouseClick(service.popup.settings_button, Qt.MouseButton.LeftButton)
                self.assertIs(page.pages.currentWidget(), page.editor)
                self.assertEqual(app_key(page.editor.application), app_key(service.application))
                self.assertFalse(service.popup.isVisible())
                page.editor.select_button(3)
                page.editor.name.setText('Pending edit')
                QTest.mouseClick(page.editor.configuration_button, Qt.MouseButton.LeftButton)
                self.assertEqual(page.pages.currentIndex(), 0)
                self.assertEqual(host.windowTitle(), 'RadialMenu')
                QTest.mouseClick(page.edit_buttons, Qt.MouseButton.LeftButton)
                self.assertIs(page.pages.currentWidget(), page.editor)
                self.assertEqual(page.editor.current, 2)
                self.assertEqual(page.editor.name.text(), 'Pending edit')
                self.assertEqual(service.profiles.buttons(service.application)[2]['name'], 'c')
                page.segments.setCurrentIndex(page.segments.findData(8))
                page.editor.configuration_button.click()
                page.edit_buttons.click()
                self.assertEqual(page.editor.ring.count, 8)
                page.cancel_edit()
                page.edit_buttons.click()
                self.assertEqual(page.editor.name.text(), 'a')
                page.choose_application('C:/Apps/Two.exe')
                page.begin_edit()
                self.assertEqual(page.editor.application, app_key('C:/Apps/Two.exe'))
            finally:
                service.stop()
                self.app.aboutToQuit.disconnect(service.stop)
                host.close()

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
                self.assertIn('one.exe', host.windowTitle())
                # The builder combines every modifier with typed and special keys,
                # persists sequences, and does not overwrite drafts on bad input.
                editor.sequence.setText('Ctrl+Alt+a')
                self.assertEqual(editor.sequence.text(), 'Ctrl+Alt+A')
                self.assertEqual(editor.buttons[0]['sequence'], 'Ctrl+Alt+A')
                editor.key.setText('k')
                self.assertEqual(editor.key.text(), 'K')
                for check in editor.modifiers.values():
                    check.setChecked(True)
                QTest.mouseClick(editor.use_key, Qt.MouseButton.LeftButton)
                self.assertEqual(editor.sequence.text(), 'Ctrl+Alt+Shift+Win+K')
                for check in editor.modifiers.values():
                    check.setChecked(False)
                for key in [f'F{i}' for i in range(1, 25)] + [
                        'Tab', 'Space', 'Backspace', 'Return', 'Enter', 'Escape',
                        'Delete', 'Insert', 'Home', 'End', 'PageUp', 'PageDown',
                        'Left', 'Right', 'Up', 'Down', 'Plus', 'Comma']:
                    editor.special_key.setCurrentIndex(editor.special_key.findData(key))
                    editor.modifiers['Shift'].setChecked(True)
                    QTest.mouseClick(editor.use_key, Qt.MouseButton.LeftButton)
                    self.assertEqual(editor.sequence.text(), 'Shift+' + key)
                    self.assertTrue(parse_sequence(editor.sequence.text()))
                editor.special_key.setCurrentIndex(editor.special_key.findData('Tab'))
                QTest.mouseClick(editor.append_key, Qt.MouseButton.LeftButton)
                self.assertEqual(editor.sequence.text(), 'Shift+Comma, Shift+Tab')
                self.assertTrue(editor.save())
                self.assertEqual(service.profiles.buttons('C:/Apps/One.exe')[0]['sequence'],
                                 'Shift+Comma, Shift+Tab')
                editor.key.clear()
                QTest.mouseClick(editor.use_key, Qt.MouseButton.LeftButton)
                self.assertEqual(editor.sequence.text(), 'Shift+Comma, Shift+Tab')
                editor.select_button(2)
                self.assertFalse(any(check.isChecked() for check in editor.modifiers.values()))
                self.assertEqual(editor.key.text(), 'B')
                editor.select_button(1)
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
                editor.icons[0].set_reference(normal)
                editor.icons[1].set_reference(hover)
                self.assertFalse(editor.icons[0].pixmap().isNull())
                self.assertFalse(editor.icons[1].pixmap().isNull())
                QTest.mouseClick(editor.ring, Qt.MouseButton.LeftButton, pos=QPoint(editor.ring.width()//2, round(editor.ring.height()*.86)))
                self.assertTrue(editor.ring.isVisible())
                self.assertEqual(editor.current, 6)
                for preview in editor.icons:
                    self.assertEqual(preview.reference, '')
                    self.assertTrue(preview.pixmap().isNull())
                    self.assertEqual(preview.text(), '')
                    self.assertEqual(preview.toolTip(), 'No icon selected')
                editor.name.setText('Paste')
                editor.sequence.setText('Ctrl+V')
                editor.select_button(1)
                self.assertEqual(editor.name.text(), 'Copy')
                self.assertEqual(editor.icons[0].reference, normal)
                self.assertEqual(editor.icons[1].reference, hover)
                for preview, reference in zip(editor.icons, (normal, hover)):
                    self.assertFalse(preview.pixmap().isNull())
                    preview.clear()
                    self.assertTrue(preview.pixmap().isNull())
                    self.assertEqual(preview.reference, '')
                    self.assertEqual(preview.text(), '')
                    preview.set_reference(reference)
                    self.assertFalse(preview.pixmap().isNull())
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
