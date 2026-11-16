"""Shared Fluent controls with the suite's Qt-compatible combo API."""
from qfluentwidgets import (
    PushButton as QPushButton, PrimaryPushButton, LineEdit,
    PlainTextEdit as QPlainTextEdit, ProgressBar as QProgressBar,
    TableWidget, ListWidget as QListWidget,
    ComboBox, CheckBox as QCheckBox,
)
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QDialogButtonBox as QtDialogButtonBox

class QComboBox(ComboBox):
    def addItem(self, text, userData=None):
        super().addItem(text, userData=userData)

class QTableWidget(TableWidget):
    def __init__(self, rows=0, columns=0, parent=None):
        super().__init__(parent)
        self.setRowCount(rows)
        self.setColumnCount(columns)

class QLineEdit(LineEdit):
    def __init__(self, text='', parent=None):
        if not isinstance(text, str):
            parent, text = text, ''
        super().__init__(parent)
        self.setText(text)


class QDialogButtonBox(QWidget):
    """Fluent Save/Cancel buttons with the existing settings dialog API."""
    StandardButton = QtDialogButtonBox.StandardButton
    accepted = Signal()
    rejected = Signal()

    def __init__(self, buttons, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch()
        self._buttons = {}
        for key, text, control, signal in (
                (self.StandardButton.Save, 'Save', PrimaryPushButton, self.accepted),
                (self.StandardButton.Cancel, 'Cancel', QPushButton, self.rejected)):
            if buttons & key:
                button = control(text)
                button.clicked.connect(lambda _checked=False, output=signal: output.emit())
                self._buttons[key] = button
                row.addWidget(button)

    def button(self, key):
        return self._buttons[key]
