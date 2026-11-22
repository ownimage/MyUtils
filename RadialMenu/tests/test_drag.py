import tempfile
import unittest
from unittest.mock import patch, Mock
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from photo_tools.shell import SuiteContext
from radial_gui import RadialService, ButtonEditor


class DragTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.context = SuiteContext(self.app, settings_path=self.tmp.name+'/settings.ini')
        with patch.object(RadialService, 'start'), patch.object(RadialService, 'install_tray'):
            self.service = RadialService(self.context)
        self.service.input = Mock()
        self.editor = ButtonEditor(Mock(service=self.service))
        self.editor.load_application('C:/Test.exe')
        self.editor.resize(760, 460)
        self.editor.show()
        self.app.processEvents()
        self.ring = self.editor.ring
        self.top = QPoint(self.ring.width()//2, 35)
        self.bottom = QPoint(self.ring.width()//2, self.ring.height()-35)

    def tearDown(self):
        self.editor.close()
        self.service.stop()
        self.app.aboutToQuit.disconnect(self.service.stop)
        self.tmp.cleanup()

    def drag(self, destination):
        QTest.mousePress(self.ring, Qt.MouseButton.LeftButton, pos=self.top)
        QTest.mouseMove(self.ring, destination)
        self.app.processEvents()

    def test_drag_previews_without_mutation_then_swaps_complete_draft_and_saves(self):
        self.editor.name.setText('First')
        self.editor.buttons[0].update(icon='tabler:outline/palette.svg', secondary_icon='phosphor:regular/palette.svg',
                                      sequence='Ctrl+A', behaviour='hold', style='hotkey')
        first, second = dict(self.editor.buttons[0]), dict(self.editor.buttons[6])
        saved = self.service.profiles.buttons('C:/Test.exe')
        self.drag(self.bottom)
        self.assertTrue(self.ring.dragging)
        self.assertEqual((self.ring.drag_source, self.ring.drag_target), (0, 6))
        self.assertEqual(self.editor.buttons[0], first)
        self.assertEqual(self.editor.buttons[6], second)
        self.assertEqual(self.service.profiles.buttons('C:/Test.exe'), saved)
        # Both source and target differ from the unhighlighted ring in both themes.
        for dark in (False, True):
            self.ring.dark = dark
            image = self.ring.grab().toImage()
            self.assertEqual(image.pixelColor(self.ring.width()//2, 55).name(), self.ring.accent.name())
        QTest.mouseRelease(self.ring, Qt.MouseButton.LeftButton, pos=self.bottom)
        self.assertEqual(self.editor.buttons[6], first)
        self.assertEqual(self.editor.buttons[0], second)
        self.assertEqual(self.editor.current, 6)
        self.assertEqual(self.editor.name.text(), 'First')
        self.assertFalse(self.ring.dragging)
        self.assertEqual(self.service.profiles.buttons('C:/Test.exe'), saved)
        self.assertTrue(self.editor.save())
        self.assertEqual(self.service.profiles.buttons('C:/Test.exe')[6], first)
        self.service.input.begin_gesture.assert_not_called()

    def test_invalid_drop_and_escape_cancel_without_selecting_or_swapping(self):
        original = [dict(b) for b in self.editor.buttons]
        for destination in (QPoint(-20, -20), self.ring.rect().center(), self.bottom):
            with self.subTest(destination=destination):
                self.drag(destination)
                if destination == self.bottom:
                    QTest.keyClick(self.ring, Qt.Key.Key_Escape)
                QTest.mouseRelease(self.ring, Qt.MouseButton.LeftButton, pos=destination)
                self.assertEqual(self.editor.buttons, original)
                self.assertEqual(self.editor.current, 0)
                self.assertFalse(self.ring.dragging)
                self.assertTrue(self.ring.isVisible())

    def test_click_without_drag_keeps_normal_selection_and_hide_cancels_preview(self):
        QTest.mouseClick(self.ring, Qt.MouseButton.LeftButton, pos=self.bottom)
        self.assertEqual(self.editor.current, 6)
        self.drag(self.bottom)
        self.editor.hide()
        self.assertFalse(self.ring.dragging)
        self.assertEqual(self.ring.drag_source, -1)
        self.assertEqual(self.editor.buttons[0]['name'], 'a')
