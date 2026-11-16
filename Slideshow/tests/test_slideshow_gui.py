import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import Qt
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
        image = QImage(640, 320, QImage.Format.Format_RGB32)
        image.fill(QColor('red'))
        image.save(str(self.event / 'highlight/001.jpg'))
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

    def test_selected_photo_follows_date_and_title_cells(self):
        image = QImage(320, 640, QImage.Format.Format_RGB32)
        image.fill(QColor('blue'))
        image.save(str(self.event / 'highlight/002.jpg'))
        self.page.load()
        preview = self.page.image_preview
        self.assertEqual(preview.image_path.name, '001.jpg')
        self.assertFalse(preview.source_pixmap.isNull())
        self.assertEqual(preview.source_pixmap.size().width(), 640)
        self.page.table.setCurrentCell(1, 1)
        self.assertEqual(preview.image_path.name, '002.jpg')
        self.assertEqual(self.page.preview_filename.text(), '002.jpg')
        self.page.table.setCurrentCell(1, 2)
        self.page.table.item(1, 2).setText('Edited while previewing')
        self.assertEqual(preview.image_path.name, '002.jpg')
        self.page.table.setFocus()
        QTest.keyClick(self.page.table, Qt.Key.Key_Up)
        self.assertEqual(preview.image_path.name, '001.jpg')
        self.assertEqual(self.page.table.item(1, 2).text(), 'Edited while previewing')

    def test_preview_preserves_aspect_ratio_and_clears_on_folder_change(self):
        self.page.load()
        preview = self.page.image_preview
        preview.resize(300, 300)
        preview._fit()
        rendered = preview.pixmap()
        self.assertAlmostEqual(rendered.width() / rendered.height(), 16/9, delta=.02)
        self.page.folder.setText(str(self.root / 'other-event'))
        self.assertIsNone(preview.image_path)
        self.assertTrue(preview.pixmap().isNull())
        self.assertFalse(self.page.create.isEnabled())

    def test_unreadable_image_and_empty_event_clear_stale_preview(self):
        self.page.load()
        (self.event / 'highlight/002.jpg').write_bytes(b'invalid image')
        self.page.load()
        self.page.table.setCurrentCell(1, 0)
        self.assertTrue(self.page.image_preview.source_pixmap.isNull())
        self.assertIn('Preview unavailable', self.page.image_preview.text())
        for image in (self.event / 'highlight').iterdir():
            image.unlink()
        self.page.load()
        self.assertIsNone(self.page.image_preview.image_path)
        self.assertEqual(self.page.preview_filename.text(), '')
        self.assertFalse(self.page.create.isEnabled())

    def test_save_and_reload_template_in_highlight_folder(self):
        self.page.load()
        self.page.template_settings['title']['size_pt'] = 22
        self.page.template_settings['date']['x'] = 80
        self.page.table.item(0,2).setText('Saved title')
        self.assertTrue(self.page.save_data())
        import json
        project = json.loads((self.event/'highlight/slideshow.json').read_text())
        self.assertEqual(project['template']['title']['size_pt'],22)
        self.assertEqual(project['images'][0]['title'],'Saved title')
        self.page.template_settings['title']['size_pt'] = 15
        self.page.load()
        self.assertEqual(self.page.template_settings['title']['size_pt'],22)

    def test_native_worker_creates_jpeg_without_external_process(self):
        self.page.load()
        with patch('slideshow_gui.QMessageBox.question',return_value=QMessageBox.Yes):
            self.page.create_slides()
            for _ in range(300):
                QTest.qWait(10)
                if not self.page.busy:
                    break
        self.assertFalse(self.page.busy)
        image = QImage(str(self.event/'slideshow/001.jpg'))
        self.assertEqual((image.width(),image.height()),(1920,1080))
        self.assertIn('Finished',self.page.status.text())

    def test_worker_failure_returns_to_editable_view(self):
        self.page.load()
        with patch('slideshow_gui.QMessageBox.question', return_value=QMessageBox.Yes), \
                patch('slideshow_gui.render_slides', side_effect=RuntimeError('Image unavailable')):
            self.page.create_slides()
            for _ in range(100):
                QTest.qWait(10)
                if not self.page.busy:
                    break
        self.assertFalse(self.page.busy)
        self.assertTrue(self.page.create.isEnabled())
        self.assertIn('Image unavailable', self.page.log.toPlainText())

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
