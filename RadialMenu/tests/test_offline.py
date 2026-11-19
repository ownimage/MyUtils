import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QPixmap, QIcon, QColor
from PySide6.QtWidgets import QApplication
from icon_library import IconPicker, entries, button_icon, ROOT
from application_icons import ApplicationIcons
from button_profiles import default_button, app_key
from radial_gui import RadialService
from photo_tools.shell import SuiteContext, SuiteWindow

class OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_offline_icons_render_and_picker_searches(self):
        self.assertEqual(len(entries()), 461)
        self.assertTrue((ROOT/'LICENSE').is_file())
        for entry in entries():
            for dark in (False, True):
                self.assertFalse(button_icon('tabler:'+entry['path'], dark).isNull(), entry['path'])
        picker = IconPicker()
        picker.search.setText('palette')
        visible = [picker.grid.item(i) for i in range(picker.grid.count()) if not picker.grid.item(i).isHidden()]
        self.assertTrue(visible)
        picker.grid.setCurrentItem(visible[0])
        picker.choose()
        self.assertTrue(picker.reference.startswith('tabler:'))
        self.assertTrue(button_icon('tabler:../../bad.svg').isNull())
        picker.close()

    def test_running_and_configured_apps_keep_cached_icon(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(RadialService,'start'), patch.object(RadialService,'install_tray'):
            context = SuiteContext(self.app,settings_path=tmp+'/settings.ini')
            host = SuiteWindow(context)
            self.assertTrue(host.open_app('radial-menu',force_new=False))
            page = host.pages['radial-menu']
            service = page.service
            pixmap = QPixmap(32,32)
            pixmap.fill(QColor('blue'))
            icon = QIcon(pixmap)
            path = 'C:/Test/App.exe'
            service.profiles.save(path,[default_button(i) for i in range(26)])
            try:
                with patch.object(service.input,'running_applications', return_value=[dict(path=path,title='Test app',hwnd=123)]), patch.object(service.input,'window_icon',return_value=icon):
                    page.refresh_applications()
                page.choose_application(path)
                self.assertTrue(page.app_icons.path(path).is_file())
                self.assertFalse(page.app_icons.cached(path).isNull())
                self.assertEqual(page.app_icons.path(path), page.app_icons.path(path.upper()))
                with patch.object(service.input,'running_applications',return_value=[]):
                    page.refresh_applications()
                self.assertEqual(page.application_picker.currentData(),app_key(path))
                index = page.application_picker.findData(app_key(path))
                self.assertIn('configured',page.application_picker.itemText(index))
                self.assertFalse(page.application_picker.items[index].icon.isNull())
                self.assertEqual(page.application_picker.icon().cacheKey(), page.application_picker.items[index].icon.cacheKey())
                reloaded = ApplicationIcons(QSettings(tmp+'/settings.ini',QSettings.Format.IniFormat))
                self.assertFalse(reloaded.cached(path).isNull())
                self.assertEqual(sum(page.application_picker.itemData(i)==app_key(path) for i in range(page.application_picker.count())),1)
            finally:
                service.stop()
                self.app.aboutToQuit.disconnect(service.stop)
                host.close()
