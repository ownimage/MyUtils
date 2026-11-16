"""App reordering with a drag image captured at the row's actual size."""

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QCursor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QAbstractItemView, QLabel, QListWidget

from .fluent import QListWidget

class RowDragPreview(QLabel):
    """Paint in a Qt window, avoiding Windows' native drag-cursor magnification."""
    def __init__(self, parent, pixmap, size, hotspot):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.NoDropShadowWindowHint | Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet('background: transparent; border: none; padding: 0; margin: 0;')
        self.setMargin(0)
        self.setPixmap(pixmap)
        self.setFixedSize(size)
        self.setWindowOpacity(.86)
        self.hotspot = hotspot
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.follow_cursor)

    def follow_cursor(self):
        self.move(QCursor.pos() - self.hotspot)

    def begin(self):
        self.follow_cursor()
        self.show()
        self.timer.start()

    def finish(self):
        self.timer.stop()
        self.hide()
        self.deleteLater()


class AppList(QListWidget):
    """Reorder locally: the row image never becomes a Windows drag cursor."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_item = None
        self._drag_overlay = None
        self._press_position = None
        self._pressed_item = None
        self._drop_slot = None
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def drag_preview(self, item):
        rect = self.visualItemRect(item).intersected(self.viewport().rect())
        if rect.isEmpty():
            return QPixmap(), rect
        return self.viewport().grab(rect), rect

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
            self._pressed_item = self.itemAt(self._press_position)

    def mouseMoveEvent(self, event):
        position = event.position().toPoint()
        if event.buttons() & Qt.MouseButton.LeftButton:
            if (self._drag_item is None and self._press_position is not None and
                    self._pressed_item is not None and
                    (position - self._press_position).manhattanLength() >= QApplication.startDragDistance()):
                self._begin_row_drag(position)
            if self._drag_item is not None:
                self._track_drag(position)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def _begin_row_drag(self, position):
        pixmap, rect = self.drag_preview(self._pressed_item)
        if rect.isEmpty():
            return
        cursor = self._press_position - rect.topLeft()
        hotspot = QPoint(max(0, min(cursor.x(), rect.width() - 1)),
                         max(0, min(cursor.y(), rect.height() - 1)))
        self._drag_item = self._pressed_item
        self._drag_overlay = RowDragPreview(self, pixmap, rect.size(), hotspot)
        self._drag_overlay.timer.timeout.connect(self._track_drag)
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        self._drag_overlay.begin()
        self._track_drag(position)

    def _slot_at(self, position):
        if self.count() and position.y() < self.visualItemRect(self.item(0)).top():
            return 0
        target = self.indexAt(QPoint(self.viewport().width() // 2, position.y()))
        if target.isValid():
            return target.row() + (position.y() >= self.visualRect(target).center().y())
        return self.count()

    def _track_drag(self, position=None):
        if self._drag_item is None:
            return
        if position is None:
            position = self.viewport().mapFromGlobal(QCursor.pos())
        slot = None
        if self.viewport().rect().contains(position):
            scrollbar = self.verticalScrollBar()
            if position.y() < 16:
                scrollbar.setValue(scrollbar.value() - 4)
            elif position.y() > self.viewport().height() - 16:
                scrollbar.setValue(scrollbar.value() + 4)
            slot = self._slot_at(position)
        if slot != self._drop_slot:
            self._drop_slot = slot
            self.viewport().update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_item is not None:
            try:
                position = event.position().toPoint()
                if self.viewport().rect().contains(position):
                    source = self.row(self._drag_item)
                    slot = self._slot_at(position)
                    destination = slot - (1 if slot > source else 0)
                    if source >= 0 and destination != source:
                        self.insertItem(destination, self.takeItem(source))
                    self.setCurrentRow(destination)
            finally:
                self._finish_row_drag()
            event.accept()
            return
        self._press_position = None
        self._pressed_item = None
        super().mouseReleaseEvent(event)

    def _finish_row_drag(self):
        if self._drag_overlay is not None:
            self._drag_overlay.finish()
        self._drag_overlay = None
        self._drag_item = None
        self._press_position = None
        self._pressed_item = None
        self._drop_slot = None
        self.viewport().unsetCursor()
        self.viewport().update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self._drag_item is not None:
            self._finish_row_drag()
            event.accept()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event):
        self._finish_row_drag()
        super().hideEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drag_item is None or self._drop_slot is None:
            return
        if self._drop_slot < self.count():
            y = self.visualItemRect(self.item(self._drop_slot)).top()
        else:
            y = self.visualItemRect(self.item(self.count() - 1)).bottom() + 1
        y = max(1, min(y, self.viewport().height() - 2))
        painter = QPainter(self.viewport())
        painter.setPen(QPen(self.palette().link().color(), 2))
        painter.drawLine(5, y, self.viewport().width() - 6, y)
