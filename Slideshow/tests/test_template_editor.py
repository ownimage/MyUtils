import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import copy
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from template_render import (ensure_fonts, default_template, missing_fonts,
    validate_template, text_path, render_image)
from template_editor import TemplateEditor


class TemplateEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        ensure_fonts()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.user_default = Path(self.temporary.name)/'template.json'
        self.defaults_patch = patch('template_render.USER_DEFAULT_PATH',self.user_default)
        self.defaults_patch.start()
        self.addCleanup(self.defaults_patch.stop)
        self.original = default_template()
        self.dialog = TemplateEditor(self.original,title='Title',date='2026 06 15')
        self.dialog.show()
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        self.app.processEvents()

    def screen_point(self, point):
        rect = self.dialog.canvas.image_rect()
        return QPoint(round(rect.x()+point.x()*rect.width()/1920),
                      round(rect.y()+point.y()*rect.height()/1080))

    def test_default_uses_system_title_font_and_expected_anchors(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(missing_fonts(self.original),[])
        self.assertEqual(self.original['title']['font_family'],'Segoe Script')
        self.assertEqual(self.original['title']['font_file'],'')
        self.assertEqual(self.original['title']['size_pt'],28.8)
        self.assertEqual(self.original['date']['size_pt'],11.2)
        self.assertEqual(self.original['title']['x'],1825.5)
        self.assertAlmostEqual(self.original['title']['y'],128.1,delta=.01)
        self.assertEqual(self.original['title']['align'],'right')
        self.assertFalse(list(root.glob('*LaSalle*')))
        self.assertFalse((root/'segoesc.ttf').exists())
        from photo_tools.fluent import QPushButton
        self.assertIn('Reset to default',[b.text() for b in self.dialog.findChildren(QPushButton)])

    def test_controls_change_actual_render_and_cancel_keeps_original(self):
        before = self.dialog.canvas.rendered.copy()
        self.dialog.size.setValue(18)
        self.dialog.x.setValue(1500)
        self.dialog.font.setCurrentIndex(self.dialog.font.findData('7-Segment'))
        QTest.qWait(50)
        self.assertEqual(self.dialog.value['title']['size_pt'],18)
        self.assertEqual(self.dialog.value['title']['font_family'],'7-Segment')
        self.assertNotEqual(before,self.dialog.canvas.rendered)
        self.dialog.reject()
        self.assertEqual(self.original,default_template())

    def test_drag_moves_title_and_updates_controls(self):
        canvas = self.dialog.canvas
        start = self.screen_point(canvas.bounds('title').center())
        original_x = canvas.template['title']['x']
        original_y = canvas.template['title']['y']
        QTest.mousePress(canvas,Qt.LeftButton,pos=start)
        QTest.mouseMove(canvas,start+QPoint(-50,45))
        QTest.mouseRelease(canvas,Qt.LeftButton,pos=start+QPoint(-50,45))
        self.assertLess(canvas.template['title']['x'],original_x-50)
        self.assertGreater(canvas.template['title']['y'],original_y+40)
        self.assertAlmostEqual(self.dialog.x.value(),canvas.template['title']['x'],delta=.1)

    def test_resize_handle_changes_font_size(self):
        canvas = self.dialog.canvas
        start = self.screen_point(canvas.handle_point('title'))
        QTest.mousePress(canvas,Qt.LeftButton,pos=start)
        QTest.mouseMove(canvas,start+QPoint(-60,20))
        QTest.mouseRelease(canvas,Qt.LeftButton,pos=start+QPoint(-60,20))
        self.assertGreater(canvas.template['title']['size_pt'],28.8)

    def test_numeric_controls_remain_visible_and_editable(self):
        self.assertGreater(self.dialog.size.lineEdit().width(),30)
        edit = self.dialog.size.lineEdit()
        edit.setFocus()
        edit.selectAll()
        QTest.keyClicks(edit,'20.5')
        QTest.keyClick(edit,Qt.Key_Return)
        self.assertAlmostEqual(self.dialog.value['title']['size_pt'],20.5)

    def test_date_selection_and_reset(self):
        self.dialog.select_layer('date')
        self.dialog.size.setValue(15)
        self.dialog.y.setValue(950)
        self.assertEqual(self.dialog.value['date']['size_pt'],15)
        self.assertEqual(self.dialog.value['title']['size_pt'],28.8)
        self.dialog.reset()
        self.assertEqual(self.dialog.value,default_template())

    def test_saved_and_editor_preview_use_same_renderer(self):
        canvas = self.dialog.canvas
        expected = render_image(None,'Title','2026 06 15',self.original)
        self.assertEqual(canvas.rendered,expected)

    def test_save_user_default_and_load_user_or_system(self):
        from template_render import SYSTEM_DEFAULT_PATH
        system_bytes = SYSTEM_DEFAULT_PATH.read_bytes()
        self.dialog.size.setValue(19)
        self.dialog.save_as_default()
        saved = json.loads(self.user_default.read_text())
        self.assertEqual(saved['title']['size_pt'],19)
        self.assertNotIn('images',saved)
        self.dialog.load_system_default()
        self.assertEqual(self.dialog.value,self.original)
        self.dialog.load_user_default()
        self.assertEqual(self.dialog.value['title']['size_pt'],19)
        self.assertEqual(SYSTEM_DEFAULT_PATH.read_bytes(),system_bytes)

    def test_missing_or_invalid_user_default_preserves_current_template(self):
        self.dialog.size.setValue(19)
        current = copy.deepcopy(self.dialog.value)
        self.dialog.load_user_default()
        self.assertIn('No user default',self.dialog.default_status.text())
        self.assertEqual(self.dialog.value,current)
        self.user_default.write_text('{broken',encoding='utf-8')
        self.dialog.load_user_default()
        self.assertIn('Could not load',self.dialog.default_status.text())
        self.assertEqual(self.dialog.value,current)

    def test_failed_default_save_preserves_previous_file(self):
        self.dialog.save_as_default()
        original = self.user_default.read_bytes()
        self.dialog.size.setValue(19)
        with patch('template_render.os.replace',side_effect=PermissionError('Read only')):
            self.dialog.save_as_default()
        self.assertEqual(self.user_default.read_bytes(),original)
        self.assertIn('Could not save',self.dialog.default_status.text())
        self.assertFalse(list(self.user_default.parent.glob('.template-*.tmp')))

    def test_font_typeahead_updates_the_render(self):
        picker = self.dialog.font
        picker.setCurrentIndex(0)
        self.dialog.canvas.refresh()
        before = self.dialog.canvas.rendered.copy()
        picker.setFocus()
        QTest.keyClicks(picker,'segoe u')
        QTest.qWait(60)
        self.assertEqual(picker.currentText(),'Segoe UI')
        self.assertEqual(self.dialog.value['title']['font_family'],'Segoe UI')
        self.assertNotEqual(before,self.dialog.canvas.rendered)

    def test_font_popup_arrows_preview_without_enter(self):
        picker = self.dialog.font
        picker.setCurrentIndex(0)
        self.dialog.canvas.refresh()
        before = self.dialog.canvas.rendered.copy()
        picker.showPopup()
        self.app.processEvents()
        QTest.keyClick(picker.view(),Qt.Key_Down)
        QTest.qWait(60)
        self.assertEqual(picker.currentIndex(),1)
        self.assertTrue(picker.view().isVisible())
        self.assertEqual(self.dialog.value['title']['font_family'],picker.itemData(1))
        self.assertNotEqual(before,self.dialog.canvas.rendered)
        picker.hidePopup()

    def test_font_popup_supports_multi_letter_search(self):
        picker = self.dialog.font
        picker.setCurrentIndex(0)
        picker.showPopup()
        self.app.processEvents()
        QTest.keyClicks(picker.view(),'segoe s')
        QTest.qWait(60)
        self.assertEqual(self.dialog.value['title']['font_family'],'Segoe Script')
        self.assertTrue(picker.view().isVisible())
        picker.hidePopup()

    def test_bad_template_rejected_instead_of_silent_reset(self):
        invalid = copy.deepcopy(self.original)
        invalid['title']['x'] = float('nan')
        with self.assertRaises(ValueError):
            validate_template(invalid)
        invalid = copy.deepcopy(self.original)
        invalid['date']['font_file'] = '../font.ttf'
        with self.assertRaises(ValueError):
            validate_template(invalid)


if __name__ == '__main__':
    unittest.main()
