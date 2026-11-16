import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, QSettings, QSize, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox

from photo_tools.preferences import Preferences
from photo_tools.settings_dialog import SettingsDialog
from photo_tools.shell import SuiteContext, SuiteWindow, offset_window_position


class SuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.settings = self.root / 'shared.ini'
        self.context = SuiteContext(self.app, settings_path=self.settings)
        self.app._photo_tools_context = self.context
        # Also isolate the child apps' remembered folders from real user settings.
        from photo_tools.registry import load_window_class
        self.local_settings_patches = []
        for definition in self.context.apps.values():
            load_window_class(definition)
            settings_patch = patch(
                definition.module + '.QSettings',
                side_effect=lambda organization, application: QSettings(
                    str(self.root / (organization + '-' + application + '.ini')),
                    QSettings.Format.IniFormat),
            )
            settings_patch.start()
            self.local_settings_patches.append(settings_patch)
        self.window = SuiteWindow(self.context)
        self.window.show()
        self.app.processEvents()
        self.direct = []

    def tearDown(self):
        for window in list(self.context.windows):
            window.close()
        for window in self.direct:
            window.close()
            window.deleteLater()
        self.wait_for(lambda: not self.context.windows)
        self.context.preferences.timer.stop()
        for settings_patch in self.local_settings_patches:
            settings_patch.stop()
        self.app.processEvents()
        del self.app._photo_tools_context
        self.context.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 10
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(predicate(), 'Operation did not finish')

    def test_tiles_open_in_window_and_preserve_app_state(self):
        QTest.mouseClick(self.window.tiles['camera-import'], Qt.MouseButton.LeftButton)
        camera = self.window.pages['camera-import']
        camera.folder.setText(str(self.root))
        self.window.navigation.launch_actions['yearbook'].trigger()
        self.assertEqual(self.window.current_app, 'yearbook')
        self.assertEqual(len(self.context.windows), 1)
        self.window.show_home()
        self.assertIs(self.window.stack.currentWidget(), self.window.home)
        QTest.mouseClick(self.window.tiles['camera-import'], Qt.MouseButton.LeftButton)
        self.assertIs(self.window.pages['camera-import'], camera)
        self.assertEqual(camera.folder.text(), str(self.root))
        self.assertEqual(self.window.current_app, 'camera-import')

    def test_settings_tabs_reorder_and_new_window_preference_persist(self):
        dialog = SettingsDialog(self.context, self.window)
        self.assertEqual([dialog.tabs.tabText(index) for index in range(2)], ['Display', 'Apps'])
        dialog.apps.setCurrentRow(1)
        dialog.move_item(-1)
        dialog.apps.item(0).setCheckState(Qt.CheckState.Checked)
        dialog.accent.setText('#a34dce')
        dialog.appearance.setCurrentIndex(dialog.appearance.findData('dark'))
        dialog.save()
        state = self.context.preferences.state
        self.assertEqual(state['order'], ['yearbook', 'camera-import', 'slideshow'])
        self.assertTrue(state['new_windows']['yearbook'])
        self.assertFalse(state['new_windows']['camera-import'])
        self.assertEqual(state['accent'], '#a34dce')
        self.assertEqual(state['appearance'], 'dark')
        self.assertEqual(list(self.window.tiles), state['order'])
        self.assertEqual(list(self.window.navigation.launch_actions), state['order'])
        second = Preferences(self.context.apps, path=self.settings)
        self.assertEqual(second.state, state)
        second.timer.stop()
        dialog.deleteLater()

    def test_checkbox_opens_new_window_from_tile_and_child_menu(self):
        self.context.preferences.update(new_windows={'yearbook': True, 'camera-import': False})
        QTest.mouseClick(self.window.tiles['yearbook'], Qt.MouseButton.LeftButton)
        self.assertEqual(len(self.context.windows), 2)
        self.assertIsNone(self.window.current_app)
        child = next(window for window in self.context.windows if window is not self.window)
        self.assertEqual(child.current_app, 'yearbook')
        self.assertNotEqual(child.frameGeometry().topLeft(), self.window.frameGeometry().topLeft())
        child.navigation.launch_actions['camera-import'].trigger()
        self.assertEqual(child.current_app, 'camera-import')
        self.assertEqual(len(self.context.windows), 2)
        child.navigation.launch_actions['yearbook'].trigger()
        self.assertEqual(len(self.context.windows), 3)
        grandchild = next(window for window in self.context.windows
                          if window is not self.window and window is not child)
        self.assertNotEqual(grandchild.frameGeometry().topLeft(), child.frameGeometry().topLeft())

    def test_reordering_reuses_tiles_and_does_not_restyle_open_apps(self):
        self.window.open_app('camera-import')
        self.window.open_app('yearbook')
        self.window.show_home()
        original_tiles = dict(self.window.tiles)
        camera, yearbook = self.window.pages.values()
        with patch.object(camera, '_apply_theme') as camera_theme, \
                patch.object(yearbook, '_apply_theme') as yearbook_theme, \
                patch('photo_tools.shell.apply_theme') as shell_theme:
            dialog = SettingsDialog(self.context, self.window)
            dialog.apps.setCurrentRow(1)
            dialog.move_item(-1)
            dialog.save()
            self.assertIs(self.window.stack.currentWidget(), self.window.home)
            self.assertEqual(list(self.window.tiles), ['yearbook', 'camera-import', 'slideshow'])
            self.assertIs(self.window.tiles_layout.itemAtPosition(0, 0).widget(), original_tiles['yearbook'])
            self.assertIs(self.window.tiles_layout.itemAtPosition(0, 1).widget(), original_tiles['camera-import'])
            camera_theme.assert_not_called()
            yearbook_theme.assert_not_called()
            shell_theme.assert_not_called()
            dialog.deleteLater()

    def test_offset_stays_on_screen_and_reverses_at_bottom_right(self):
        available = QRect(0, 0, 1920, 1040)
        size = QSize(1160, 940)
        self.assertEqual(offset_window_position(QRect(100, 20, 1160, 940), size, available),
                         QPoint(136, 56))
        position = offset_window_position(QRect(760, 100, 1160, 940), size, available)
        self.assertEqual(position, QPoint(724, 64))
        self.assertTrue(available.contains(QRect(position, size)))
        # Screen coordinates can be negative on a monitor to the left of the primary.
        second_monitor = QRect(-1920, 0, 1920, 1040)
        position = offset_window_position(QRect(-1800, 20, 1160, 940), size, second_monitor)
        self.assertEqual(position, QPoint(-1764, 56))

    def test_shared_menu_is_present_in_direct_child_apps(self):
        from photo_tools.registry import load_window_class
        for app_id in self.context.apps:
            page = load_window_class(self.context.apps[app_id])()
            self.direct.append(page)
            self.assertEqual([action.text() for action in page.menuBar().actions()], ['Settings', 'Launch'])
            self.assertEqual(list(page.suite_binding.navigation.launch_actions),
                             ['camera-import', 'yearbook', 'slideshow'])
        self.context.preferences.update(order=['yearbook', 'camera-import', 'slideshow'])
        for page in self.direct:
            self.assertEqual(list(page.suite_binding.navigation.launch_actions),
                             ['yearbook', 'camera-import', 'slideshow'])

    def test_cross_process_settings_update_every_open_app(self):
        self.window.open_app('camera-import')
        self.window.open_app('yearbook')
        script = ('from PySide6.QtCore import QCoreApplication; app=QCoreApplication([]); '
                  'from photo_tools.preferences import Preferences; '
                  f'p=Preferences(["camera-import","yearbook"],path={str(self.settings)!r}); '
                  'p.update(accent="#ae395a",appearance="dark",order=["yearbook","camera-import"])')
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.context.preferences.refresh()
        self.assertIn('#ae395a', self.window.styleSheet())
        self.assertEqual(list(self.window.navigation.launch_actions), ['yearbook', 'camera-import', 'slideshow'])
        for page in self.window.pages.values():
            self.assertIn('#ae395a', page.styleSheet())
            self.assertTrue(page.is_dark)
            self.assertEqual(page.appearance.currentData(), 'dark')

    def test_app_appearance_control_changes_other_app_and_shared_setting(self):
        self.window.open_app('camera-import')
        self.window.open_app('yearbook')
        camera, yearbook = self.window.pages.values()
        camera.appearance.setCurrentIndex(camera.appearance.findData('dark'))
        self.assertEqual(self.context.preferences.state['appearance'], 'dark')
        self.assertTrue(yearbook.is_dark)
        self.assertEqual(yearbook.appearance.currentData(), 'dark')

    def test_accent_tints_background_wash_in_launcher_and_both_apps(self):
        self.window.open_app('camera-import')
        self.window.open_app('yearbook')
        accent = QColor('#7755cc')
        for appearance in ('light', 'dark'):
            self.context.preferences.update(accent=accent.name(), appearance=appearance)
            for window in [self.window, *self.window.pages.values()]:
                for role in (QPalette.ColorRole.Window, QPalette.ColorRole.AlternateBase):
                    color = window.palette().color(role)
                    hue_difference = abs(color.hslHue() - accent.hslHue())
                    # Near-white RGB shades have only a few channel steps, so
                    # rounding makes their hue less precise than darker surfaces.
                    self.assertLess(min(hue_difference, 360 - hue_difference), 25)
                if appearance == 'dark':
                    card = window.palette().color(QPalette.ColorRole.Base)
                    self.assertLess(abs(card.hslHue() - accent.hslHue()), 5)

    def test_drag_uses_painted_row_size_and_preserves_checkbox_when_dropped(self):
        dialog = SettingsDialog(self.context, self.window)
        dialog.tabs.setCurrentIndex(1)
        dialog.show()
        self.app.processEvents()
        apps = dialog.apps
        first = apps.item(0)
        first.setCheckState(Qt.CheckState.Checked)
        rect = apps.visualItemRect(first)
        start = QPoint(rect.left() + 100, rect.center().y())
        target_rect = apps.visualItemRect(apps.item(1))
        end = QPoint(start.x(), target_rect.bottom() - 2)
        QTest.mousePress(apps.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(apps.viewport(), end)
        overlay = apps._drag_overlay
        self.assertIsNotNone(overlay)
        self.assertTrue(overlay.isVisible())
        self.assertEqual(overlay.size(), rect.size())
        self.assertTrue(overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput)
        self.assertAlmostEqual(overlay.pixmap().deviceIndependentSize().height(), rect.height(), delta=1)
        QTest.mouseRelease(apps.viewport(), Qt.MouseButton.LeftButton, pos=end)
        self.assertEqual(apps.item(1).data(Qt.ItemDataRole.UserRole), 'camera-import')
        self.assertEqual(apps.item(1).checkState(), Qt.CheckState.Checked)
        self.assertIsNone(apps._drag_item)
        self.assertIsNone(apps._drag_overlay)
        dialog.save()
        self.assertEqual(self.context.preferences.state['order'], ['yearbook', 'camera-import', 'slideshow'])
        self.assertTrue(self.context.preferences.state['new_windows']['camera-import'])
        dialog.deleteLater()

    def test_escape_cancels_row_drag_without_closing_settings(self):
        dialog = SettingsDialog(self.context, self.window)
        dialog.tabs.setCurrentIndex(1)
        dialog.show()
        self.app.processEvents()
        apps = dialog.apps
        rect = apps.visualItemRect(apps.item(0))
        start = QPoint(rect.left() + 100, rect.center().y())
        end = QPoint(start.x(), apps.visualItemRect(apps.item(1)).bottom() - 2)
        QTest.mousePress(apps.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(apps.viewport(), end)
        self.assertIsNotNone(apps._drag_overlay)
        QTest.keyClick(apps, Qt.Key.Key_Escape)
        QTest.mouseRelease(apps.viewport(), Qt.MouseButton.LeftButton, pos=end)
        self.assertIsNone(apps._drag_overlay)
        self.assertEqual(apps.item(0).data(Qt.ItemDataRole.UserRole), 'camera-import')
        self.assertTrue(dialog.isVisible())
        dialog.close()
        dialog.deleteLater()

    def test_releasing_outside_list_cancels_and_next_drag_still_works(self):
        dialog = SettingsDialog(self.context, self.window)
        dialog.tabs.setCurrentIndex(1)
        dialog.show()
        self.app.processEvents()
        apps = dialog.apps
        rect = apps.visualItemRect(apps.item(0))
        start = QPoint(rect.left() + 100, rect.center().y())
        outside = QPoint(-10, rect.center().y() + 55)
        QTest.mousePress(apps.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(apps.viewport(), outside)
        self.assertIsNotNone(apps._drag_overlay)
        QTest.mouseRelease(apps.viewport(), Qt.MouseButton.LeftButton, pos=outside)
        self.assertIsNone(apps._drag_overlay)
        self.assertEqual(apps.item(0).data(Qt.ItemDataRole.UserRole), 'camera-import')
        for source_row, target_row in ((0, 1), (1, 0)):
            rect = apps.visualItemRect(apps.item(source_row))
            target = apps.visualItemRect(apps.item(target_row))
            start = QPoint(rect.left() + 100, rect.center().y())
            end = QPoint(start.x(), target.bottom() - 2 if target_row > source_row else target.top() + 2)
            QTest.mousePress(apps.viewport(), Qt.MouseButton.LeftButton, pos=start)
            QTest.mouseMove(apps.viewport(), end)
            QTest.mouseRelease(apps.viewport(), Qt.MouseButton.LeftButton, pos=end)
            self.assertEqual(apps.item(target_row).data(Qt.ItemDataRole.UserRole), 'camera-import')
        dialog.close()
        dialog.deleteLater()

    def test_drag_preview_matches_row_at_different_display_scales(self):
        script = '''
import json, sys
from PySide6.QtWidgets import QApplication
from photo_tools.shell import SuiteContext
from photo_tools.settings_dialog import SettingsDialog
from photo_tools.app_list import RowDragPreview
from PySide6.QtCore import QPoint
app = QApplication([])
context = SuiteContext(app, settings_path=sys.argv[1])
dialog = SettingsDialog(context)
dialog.tabs.setCurrentIndex(1)
dialog.show()
app.processEvents()
pixmap, rect = dialog.apps.drag_preview(dialog.apps.item(0))
size = pixmap.deviceIndependentSize()
overlay = RowDragPreview(dialog.apps, pixmap, rect.size(), QPoint())
overlay.begin()
app.processEvents()
print(json.dumps(dict(row=[rect.width(), rect.height()],
                      preview=[size.width(), size.height()], dpr=pixmap.devicePixelRatio(),
                      overlay=[overlay.width(), overlay.height()])))
overlay.finish()
dialog.close()
'''
        for scale in ('1', '1.5', '2'):
            environment = dict(os.environ, QT_SCALE_FACTOR=scale)
            result = subprocess.run([sys.executable, '-c', script, str(self.settings)],
                                    capture_output=True, text=True, env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            metrics = json.loads(result.stdout.strip().splitlines()[-1])
            for actual, expected in zip(metrics['preview'], metrics['row']):
                self.assertAlmostEqual(actual, expected, delta=1)
            self.assertEqual(metrics['overlay'], metrics['row'])
            self.assertAlmostEqual(metrics['dpr'], float(scale), delta=.01)

    def test_cancel_settings_leaves_shared_state_unchanged(self):
        before = self.context.preferences.state
        dialog = SettingsDialog(self.context, self.window)
        dialog.accent.setText('#88ccff')
        dialog.move_item(1)
        dialog.reject()
        self.assertEqual(self.context.preferences.state, before)
        dialog.deleteLater()

    def test_invalid_accent_cannot_be_saved(self):
        dialog = SettingsDialog(self.context, self.window)
        dialog.accent.setText('invalid-colour')
        self.assertFalse(dialog.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled())
        dialog.save()
        self.assertEqual(self.context.preferences.state['accent'], '#246b53')
        dialog.accent.setText('#ffcc00')
        self.assertTrue(dialog.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled())
        dialog.deleteLater()

    def test_unavailable_app_reports_error_without_losing_home(self):
        with patch('photo_tools.shell.load_window_class', side_effect=FileNotFoundError('Unavailable')):
            with patch.object(QMessageBox, 'warning') as warning:
                self.assertFalse(self.window.open_app('yearbook'))
        warning.assert_called_once()
        self.assertIsNone(self.window.current_app)
        self.assertIs(self.window.stack.currentWidget(), self.window.home)

    def test_hidden_worker_is_cancelled_and_finished_before_host_closes(self):
        self.window.open_app('camera-import', directory=str(self.root))
        camera = self.window.pages['camera-import']
        import reorg
        started, release = Event(), Event()

        def blocked_scan(directory, **options):
            started.set()
            release.wait(5)
            return reorg.scan_directory(directory, **options)

        with patch('reorg_gui.scan_directory', side_effect=blocked_scan):
            camera.start_preview()
            self.wait_for(started.is_set)
            self.window.open_app('yearbook')
            self.assertTrue(camera.busy)
            self.window.close()
            self.assertIn(self.window, self.context.windows)
            self.assertTrue(camera.worker.isInterruptionRequested())
            release.set()
            self.wait_for(lambda: self.window not in self.context.windows)

    def test_malformed_preferences_fall_back_and_new_apps_get_added(self):
        self.context.preferences.settings.setValue('suite/state', '{broken')
        self.context.preferences.refresh()
        self.assertEqual(self.context.preferences.state['accent'], '#246b53')
        self.context.preferences.settings.setValue('suite/state', json.dumps({
            'order': ['yearbook', 'missing-app', 'yearbook'], 'accent': 32, 'new_windows': []}))
        self.context.preferences.refresh()
        self.assertEqual(self.context.preferences.state['order'], ['yearbook', 'camera-import', 'slideshow'])
        self.assertEqual(self.context.preferences.state['accent'], '#246b53')


if __name__ == '__main__':
    unittest.main()
