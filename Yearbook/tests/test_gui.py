import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

import yearbook
from yearbook_gui import YearbookWindow


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        cls.settings_temp = tempfile.TemporaryDirectory()
        cls.old_shared_settings = os.environ.get('PHOTO_TOOLS_SETTINGS')
        os.environ['PHOTO_TOOLS_SETTINGS'] = str(Path(cls.settings_temp.name) / 'shared.ini')
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                          cls.settings_temp.name)
        # The organization/application constructor uses the Windows registry,
        # even after setDefaultFormat. Keep test preferences in temporary files.
        cls.settings_patch = patch(
            'yearbook_gui.QSettings',
            side_effect=lambda organization, application: QSettings(
                QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                organization, application),
        )
        cls.settings_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.settings_patch.stop()
        from photo_tools.shell import get_context
        get_context().preferences.timer.stop()
        if hasattr(cls.app, '_photo_tools_context'):
            del cls.app._photo_tools_context
        if cls.old_shared_settings is None:
            os.environ.pop('PHOTO_TOOLS_SETTINGS', None)
        else:
            os.environ['PHOTO_TOOLS_SETTINGS'] = cls.old_shared_settings
        cls.settings_temp.cleanup()

    def setUp(self):
        from photo_tools.shell import get_context
        get_context().preferences.update(appearance='system', accent='#246b53')
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                  'Yearbook', 'Create').clear()
        self.window = YearbookWindow(str(self.root))
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.wait_for(lambda: not self.window.busy)
        self.app.processEvents()
        self.window.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def make_photo(self):
        source = self.root / '20260615 Holiday' / 'slideshow' / '001.jpg'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b'test photo')
        return source

    def wait_for(self, predicate):
        deadline = time.monotonic() + 10
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(predicate(), 'GUI operation did not complete')

    def preview(self):
        QTest.mouseClick(self.window.preview, Qt.MouseButton.LeftButton)
        self.wait_for(lambda: not self.window.busy)

    def test_preview_and_create(self):
        source = self.make_photo()
        self.assertFalse(self.window.create.isEnabled())
        self.preview()
        self.assertEqual(self.window.table.rowCount(), 1)
        self.assertEqual(self.window.table.item(0, 2).text(), '20260615_001.jpg')
        self.assertEqual(self.window.table.item(0, 3).text(), 'Ready')
        self.assertTrue(self.window.create.isEnabled())
        self.assertFalse((self.root / 'yearbook').exists())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            QTest.mouseClick(self.window.create, Qt.MouseButton.LeftButton)
        self.wait_for(lambda: not self.window.busy)
        self.assertIn('1 copied', self.window.status.text())
        self.assertEqual(self.window.table.item(0, 3).text(), 'Copied')
        self.assertTrue(source.exists())
        self.assertTrue((self.root / 'yearbook' / '20260615_001.jpg').exists())
        self.assertTrue(self.window.open_folder.isEnabled())
        self.assertFalse(self.window.create.isEnabled())
        self.preview()
        self.assertEqual(self.window.table.item(0, 3).text(), 'Skipped')
        self.assertFalse(self.window.create.isEnabled())

    def test_folder_edit_invalidates_preview(self):
        self.make_photo()
        self.preview()
        self.window.folder.setText(str(self.root / 'other'))
        self.assertIsNone(self.window.plan)
        self.assertFalse(self.window.create.isEnabled())
        self.assertEqual(self.window.table.rowCount(), 0)

    def test_empty_folder_has_no_copies(self):
        self.preview()
        self.assertIn('No JPG photos', self.window.status.text())
        self.assertFalse(self.window.create.isEnabled())

    def test_invalid_folder_displays_warning(self):
        self.window.folder.setText(str(self.root / 'missing'))
        with patch.object(QMessageBox, 'warning') as warning:
            self.window.start_preview()
        warning.assert_called_once()
        self.assertFalse(self.window.busy)

    def test_cancelled_preview_stays_disabled(self):
        self.make_photo()
        started, release = Event(), Event()

        def blocked_scan(directory, **options):
            started.set()
            release.wait(5)
            return yearbook.scan_directory(directory, **options)

        with patch('yearbook_gui.scan_directory', side_effect=blocked_scan):
            self.window.start_preview()
            self.wait_for(started.is_set)
            self.assertFalse(self.window.browse.isEnabled())
            self.assertFalse(self.window.folder.isEnabled())
            QTest.mouseClick(self.window.cancel, Qt.MouseButton.LeftButton)
            release.set()
            self.wait_for(lambda: not self.window.busy)
        self.assertIn('cancelled', self.window.status.text())
        self.assertFalse(self.window.create.isEnabled())
        self.assertFalse((self.root / 'yearbook').exists())

    def test_close_waits_for_worker(self):
        started, release = Event(), Event()

        def blocked_scan(directory, **options):
            started.set()
            release.wait(5)
            return yearbook.scan_directory(directory, **options)

        with patch('yearbook_gui.scan_directory', side_effect=blocked_scan):
            self.window.start_preview()
            self.wait_for(started.is_set)
            self.window.close()
            self.assertTrue(self.window.isVisible())
            self.assertTrue(self.window.worker.isInterruptionRequested())
            release.set()
            self.wait_for(lambda: not self.window.isVisible())
        self.assertFalse(self.window.busy)

    def test_theme_switch_preserves_preview_and_restores_setting(self):
        self.make_photo()
        self.preview()
        plan = self.window.plan
        self.window.appearance.setCurrentIndex(self.window.appearance.findData('dark'))
        self.assertTrue(self.window.is_dark)
        self.assertEqual(self.window.table.item(0, 3).foreground().color().name(), '#83d5b1')
        other = YearbookWindow(str(self.root))
        try:
            self.assertEqual(other.appearance.currentData(), 'dark')
            self.assertTrue(other.is_dark)
        finally:
            other.close()
            other.deleteLater()
        self.window.appearance.setCurrentIndex(self.window.appearance.findData('light'))
        self.assertFalse(self.window.is_dark)
        self.assertIs(self.window.plan, plan)
        self.assertTrue(self.window.create.isEnabled())

    def test_follow_windows_reacts_to_theme_change(self):
        self.assertEqual(self.window.appearance.currentData(), 'system')
        with patch.object(YearbookWindow, '_system_is_dark', return_value=True):
            QApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
            self.assertTrue(self.window.is_dark)
        with patch.object(YearbookWindow, '_system_is_dark', return_value=False):
            QApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
            self.assertFalse(self.window.is_dark)


if __name__ == '__main__':
    unittest.main()
