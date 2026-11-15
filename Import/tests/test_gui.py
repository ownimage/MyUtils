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

import reorg
from reorg_gui import ImportWindow
from test_reorg import make_image


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        cls.settings_temp = tempfile.TemporaryDirectory()
        cls.old_shared_settings = os.environ.get('PHOTO_TOOLS_SETTINGS')
        os.environ['PHOTO_TOOLS_SETTINGS'] = str(Path(cls.settings_temp.name) / 'shared.ini')
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, cls.settings_temp.name)
        cls.settings_patch = patch(
            'reorg_gui.QSettings',
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
                  'CameraImport', 'Reorganise').clear()
        self.window = ImportWindow(str(self.root))
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.wait_for(lambda: not self.window.busy)
        self.app.processEvents()
        self.window.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 10
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(predicate(), 'GUI operation did not complete')

    def preview(self):
        QTest.mouseClick(self.window.preview, Qt.MouseButton.LeftButton)
        self.wait_for(lambda: not self.window.busy)

    def test_preview_and_organise(self):
        source = self.root / 'photo.jpg'
        make_image(source)
        self.assertFalse(self.window.organise.isEnabled())
        self.preview()
        self.assertTrue(self.window.organise.isEnabled())
        self.assertEqual(self.window.table.rowCount(), 1)
        self.assertEqual(self.window.table.item(0, 3).text(), 'Ready')
        self.assertTrue(source.exists())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            QTest.mouseClick(self.window.organise, Qt.MouseButton.LeftButton)
        self.wait_for(lambda: not self.window.busy)
        self.assertEqual(self.window.table.item(0, 3).text(), 'Moved')
        self.assertIn('1 moved', self.window.status.text())
        self.assertFalse(self.window.organise.isEnabled())
        self.assertFalse(source.exists())
        self.assertTrue((self.root / '20250114' / 'origJPG' / 'photo.jpg').exists())

    def test_folder_edit_invalidates_preview(self):
        make_image(self.root / 'photo.jpg')
        self.preview()
        self.window.folder.setText(str(self.root / 'other'))
        self.assertIsNone(self.window.plan)
        self.assertFalse(self.window.organise.isEnabled())
        self.assertEqual(self.window.table.rowCount(), 0)

    def test_empty_folder_has_no_moves(self):
        self.preview()
        self.assertIn('No supported images', self.window.status.text())
        self.assertFalse(self.window.organise.isEnabled())

    def test_cancelled_preview_stays_disabled(self):
        make_image(self.root / 'photo.jpg')
        started, release = Event(), Event()

        def blocked_scan(directory, **options):
            started.set()
            release.wait(5)
            return reorg.scan_directory(directory, **options)

        with patch('reorg_gui.scan_directory', side_effect=blocked_scan):
            self.window.start_preview()
            self.wait_for(started.is_set)
            self.assertFalse(self.window.browse.isEnabled())
            self.assertFalse(self.window.folder.isEnabled())
            QTest.mouseClick(self.window.cancel, Qt.MouseButton.LeftButton)
            release.set()
            self.wait_for(lambda: not self.window.busy)
        self.assertIn('cancelled', self.window.status.text())
        self.assertFalse(self.window.organise.isEnabled())
        self.assertTrue((self.root / 'photo.jpg').exists())

    def test_close_waits_for_worker(self):
        started, release = Event(), Event()

        def blocked_scan(directory, **options):
            started.set()
            release.wait(5)
            return reorg.scan_directory(directory, **options)

        with patch('reorg_gui.scan_directory', side_effect=blocked_scan):
            self.window.start_preview()
            self.wait_for(started.is_set)
            self.window.close()
            self.assertTrue(self.window.isVisible())
            self.assertTrue(self.window.worker.isInterruptionRequested())
            release.set()
            self.wait_for(lambda: not self.window.isVisible())
        self.assertFalse(self.window.busy)

    def test_invalid_folder_displays_warning(self):
        self.window.folder.setText(str(self.root / 'missing'))
        with patch.object(QMessageBox, 'warning') as warning:
            self.window.start_preview()
        warning.assert_called_once()
        self.assertFalse(self.window.busy)

    def test_appearance_switch_preserves_preview_and_recolours_status(self):
        make_image(self.root / 'photo.jpg')
        self.preview()
        plan = self.window.plan
        self.window.appearance.setCurrentIndex(self.window.appearance.findData('dark'))
        self.assertTrue(self.window.is_dark)
        self.assertEqual(self.window.table.item(0, 3).foreground().color().name(), '#83d5b1')
        self.window.appearance.setCurrentIndex(self.window.appearance.findData('light'))
        self.assertFalse(self.window.is_dark)
        self.assertEqual(self.window.table.item(0, 3).foreground().color().name(), '#246b53')
        self.assertIs(self.window.plan, plan)
        self.assertTrue(self.window.organise.isEnabled())
        self.assertTrue((self.root / 'photo.jpg').exists())

    def test_appearance_is_restored_on_reopening(self):
        self.window.appearance.setCurrentIndex(self.window.appearance.findData('dark'))
        other = ImportWindow(str(self.root))
        try:
            self.assertEqual(other.appearance.currentData(), 'dark')
            self.assertTrue(other.is_dark)
        finally:
            other.close()
            other.deleteLater()

    def test_follow_windows_reacts_to_system_changes(self):
        self.assertEqual(self.window.appearance.currentData(), 'system')
        hints = QApplication.styleHints()
        with patch.object(ImportWindow, '_system_is_dark', return_value=True):
            hints.colorSchemeChanged.emit(Qt.ColorScheme.Dark)
            self.assertTrue(self.window.is_dark)
        with patch.object(ImportWindow, '_system_is_dark', return_value=False):
            hints.colorSchemeChanged.emit(Qt.ColorScheme.Light)
            self.assertFalse(self.window.is_dark)
        self.window.appearance.setCurrentIndex(self.window.appearance.findData('dark'))
        with patch.object(ImportWindow, '_system_is_dark', return_value=False):
            hints.colorSchemeChanged.emit(Qt.ColorScheme.Light)
            self.assertTrue(self.window.is_dark)


if __name__ == '__main__':
    unittest.main()
