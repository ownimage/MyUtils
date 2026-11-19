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
        self.assertEqual(len(entries()), 15166)
        self.assertTrue((ROOT/'LICENSE').is_file())
        for entry in entries():
            for dark in (False, True):
                self.assertFalse(button_icon(entry['reference'], dark).isNull(), entry['path'])
        picker = IconPicker()
        picker.search.setText('palette')
        visible = [picker.grid.item(i) for i in range(picker.grid.count()) if not picker.grid.item(i).isHidden()]
        self.assertTrue(visible)
        picker.grid.setCurrentItem(visible[0])
        picker.choose()
        self.assertIn(picker.reference, {entry['reference'] for entry in entries()})
        picker.library.setCurrentIndex(picker.library.findData('tabler'))
        picker.style.setCurrentIndex(picker.style.findData('outline'))
        visible = [picker.grid.item(i) for i in range(picker.grid.count()) if not picker.grid.item(i).isHidden()]
        self.assertTrue(visible)
        self.assertTrue(all(item.data(Qt.ItemDataRole.UserRole).startswith('tabler:outline/') for item in visible))
        self.assertFalse(button_icon('tabler:outline/palette.svg').isNull())
        self.assertFalse(button_icon('phosphor:regular/palette.svg').isNull())
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

    def test_libraries_keep_colliding_names_and_unique_references(self):
        from icon_library import libraries
        self.assertEqual(set(libraries()), {'tabler','phosphor','lucide','remix'})
        self.assertEqual(len({e['reference'] for e in entries()}), len(entries()))
        tabler = {e['name'] for e in entries() if e['library']=='tabler'}
        phosphor = {e['name'] for e in entries() if e['library']=='phosphor'}
        self.assertTrue(tabler & phosphor)
        self.assertIn('palette', tabler & phosphor)

    def test_importer_updates_stable_ids_and_retains_removed_icons(self):
        import io, json, tarfile
        from pathlib import Path
        from import_icon_set import install
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h1v1"/></svg>'
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)/'icons.tgz'
            def package(version,names):
                with tarfile.open(archive,'w:gz') as output:
                    files = {'package/package.json':json.dumps({'version':version}).encode(),
                             'package/LICENSE':b'MIT test license'}
                    files.update({'package/assets/regular/'+name+'.svg':svg for name in names})
                    for name,data in files.items():
                        member = tarfile.TarInfo(name)
                        member.size = len(data)
                        output.addfile(member,io.BytesIO(data))
            package('1.0',['palette','old'])
            first = install(archive,'future-set','Future Set','test',assets_root=Path(tmp)/'assets')
            package('2.0',['palette','new'])
            second = install(archive,'future-set','Future Set','test',assets_root=Path(tmp)/'assets')
            self.assertEqual(first['icons'][1]['path'], 'regular/palette.svg')
            self.assertEqual(second['version'],'2.0')
            old = next(e for e in second['icons'] if e['name']=='old')
            self.assertTrue(old['retired'])
            self.assertTrue((Path(tmp)/'assets/future-set'/old['path']).exists())
            self.assertEqual((Path(tmp)/'assets/future-set/regular/palette.svg').read_bytes(),svg)

    def test_about_page_contains_every_exact_bundled_license(self):
        from html import escape
        from about_page import credits_html
        from icon_library import libraries, ASSETS
        html = credits_html()
        for slug, manifest in libraries().items():
            self.assertIn(escape(manifest['label']),html)
            self.assertIn(escape(manifest['attribution']),html)
            license_text = (ASSETS/slug/'LICENSE').read_text(encoding='utf-8')
            self.assertIn(escape(license_text),html)
        self.assertIn('Cole Bemis',html)
        self.assertIn('Remix Icon License v1.0',html)
        self.assertIn('ISC License',html)

    def test_importer_supports_flat_and_categorised_icon_archives(self):
        import io, json, tarfile
        from pathlib import Path
        from import_icon_set import install
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
        with tempfile.TemporaryDirectory() as tmp:
            for slug, layout, icon_paths, license_name, expected in (
                    ('lucide','flat',['package/icons/palette.svg'],'LICENSE',{'outline/palette.svg'}),
                    ('remix','remix',['package/icons/Design/palette-line.svg','package/icons/Design/palette-fill.svg','package/icons/Editor/a-b.svg'],'License',{'line/palette.svg','fill/palette.svg','regular/a-b.svg'})):
                archive = Path(tmp)/(slug+'.tgz')
                with tarfile.open(archive,'w:gz') as tar:
                    files = {'package/package.json':json.dumps({'version':'1.0'}).encode(),
                             'package/'+license_name:b'Full upstream copyright and license'}
                    files.update({path:svg for path in icon_paths})
                    for name,data in files.items():
                        item = tarfile.TarInfo(name)
                        item.size=len(data)
                        tar.addfile(item,io.BytesIO(data))
                manifest=install(archive,slug,slug.title(),'test','package/icons/',
                    layout=layout,license_name=license_name,assets_root=Path(tmp)/'assets')
                self.assertEqual({item['path'] for item in manifest['icons']},expected)
                self.assertEqual((Path(tmp)/'assets'/slug/'LICENSE').read_bytes(),b'Full upstream copyright and license')

    def test_about_page_is_reachable_from_configuration(self):
        from PySide6.QtTest import QTest
        with tempfile.TemporaryDirectory() as tmp, patch.object(RadialService,'start'), patch.object(RadialService,'install_tray'):
            context = SuiteContext(self.app,settings_path=tmp+'/settings.ini')
            host = SuiteWindow(context)
            self.assertTrue(host.open_app('radial-menu',force_new=False))
            host.show()
            page = host.pages['radial-menu']
            try:
                QTest.mouseClick(page.about_button,Qt.MouseButton.LeftButton)
                self.assertIs(page.pages.currentWidget(),page.about)
                self.assertIn('Remix Icon License v1.0',page.about.browser.toPlainText())
                self.assertIn('Cole Bemis',page.about.browser.toPlainText())
            finally:
                page.service.stop()
                self.app.aboutToQuit.disconnect(page.service.stop)
                host.close()
