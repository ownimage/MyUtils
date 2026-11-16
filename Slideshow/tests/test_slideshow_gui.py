import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
from photo_tools.shell import SuiteContext, SuiteWindow
from photo_tools.settings_dialog import SettingsDialog
from qfluentwidgets import PushButton, TableWidget


class SlideshowGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.event = self.root / '20260615 Holiday'
        (self.event / 'highlight').mkdir(parents=True)
        (self.event / 'highlight/001.jpg').write_bytes(b'original')
        self.context = SuiteContext(self.app, settings_path=self.root / 'suite.ini')
        self.app._photo_tools_context = self.context
        self.window = SuiteWindow(self.context)
        self.patch = patch('slideshow_gui.QSettings', side_effect=lambda *args:
                           QSettings(str(self.root / 'slideshow.ini'), QSettings.IniFormat))
        from photo_tools.registry import load_window_class
        load_window_class(self.context.apps['slideshow'])
        self.patch.start()
        self.window.open_app('slideshow', directory=str(self.event))
        self.page = self.window.pages['slideshow']

    def tearDown(self):
        self.page.dirty = False
        self.window.close()
        self.context.preferences.timer.stop()
        self.patch.stop()
        self.app.processEvents()
        self.temp.cleanup()

    def test_launcher_and_edit_save_reload(self):
        self.assertIn('slideshow', self.window.tiles)
        self.assertIn('slideshow', self.window.navigation.launch_actions)
        self.assertIsInstance(self.page.create, PushButton)
        self.assertIsInstance(self.page.table, TableWidget)
        self.page.load()
        self.assertEqual(self.page.table.rowCount(), 1)
        self.page.table.item(0, 2).setText('Café, Cornwall')
        self.assertTrue(self.page.save_data())
        self.page.load()
        self.assertEqual(self.page.table.item(0, 2).text(), 'Café, Cornwall')
        self.window.show_home()
        self.window.open_app('slideshow')
        self.assertIs(self.page, self.window.pages['slideshow'])

    def test_worker_failure_returns_to_editable_view(self):
        self.page.load()
        with patch('slideshow_gui.QMessageBox.question', return_value=QMessageBox.Yes), \
                patch('slideshow_gui.render_slides', side_effect=RuntimeError('Photoshop unavailable')):
            self.page.create_slides()
            for _ in range(100):
                QTest.qWait(10)
                if not self.page.busy:
                    break
        self.assertFalse(self.page.busy)
        self.assertTrue(self.page.create.isEnabled())
        self.assertIn('Photoshop unavailable', self.page.log.toPlainText())

    def test_cancel_theme_preview_restores_fluent_global_theme(self):
        from qfluentwidgets import qconfig, Theme
        self.context.preferences.update(appearance='light')
        dialog = SettingsDialog(self.context, self.window)
        dialog.appearance.setCurrentIndex(dialog.appearance.findData('dark'))
        self.assertEqual(qconfig.theme, Theme.DARK)
        dialog.reject()
        self.assertEqual(qconfig.theme, Theme.LIGHT)


if __name__ == '__main__':
    unittest.main()
