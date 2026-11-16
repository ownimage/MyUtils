"""A single Settings dialog, used from every app's shared menu."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QColorDialog, QComboBox, QDialog,
    QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidgetItem,
    QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from .fluent import QPushButton, QLineEdit, QPlainTextEdit, QProgressBar, QTableWidget, QComboBox, PrimaryPushButton, QDialogButtonBox

from .preferences import DEFAULT_ACCENT
from .app_list import AppList
from .theme import apply_theme


class SettingsDialog(QDialog):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.setWindowTitle('Settings Â· Photo Tools')
        self.resize(640, 510)
        self.setMinimumSize(580, 460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._display_tab()
        self._apps_tab()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                       QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName('primary')
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.appearance.currentIndexChanged.connect(self.preview_theme)
        self.accent.textChanged.connect(self.preview_theme)
        self.preview_theme()

    def _display_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(15)
        heading = QLabel('Make it yours')
        heading.setObjectName('tileTitle')
        layout.addWidget(heading)
        explanation = QLabel('These display settings are shared by the launcher and every app.')
        explanation.setWordWrap(True)
        explanation.setObjectName('muted')
        layout.addWidget(explanation)
        layout.addWidget(QLabel('Appearance'))
        self.appearance = QComboBox()
        self.appearance.setAccessibleName('Shared appearance')
        for label, value in (('Follow Windows', 'system'), ('Light', 'light'), ('Dark', 'dark')):
            self.appearance.addItem(label, value)
        self.appearance.setCurrentIndex(self.appearance.findData(self.context.preferences.state['appearance']))
        layout.addWidget(self.appearance)
        layout.addWidget(QLabel('Accent colour'))
        row = QHBoxLayout()
        self.accent = QLineEdit(self.context.preferences.state['accent'])
        self.accent.setAccessibleName('Accent colour')
        self.accent.setMaxLength(40)
        row.addWidget(self.accent)
        self.choose_color = QPushButton('Choose colour…')
        self.choose_color.clicked.connect(self.pick_color)
        row.addWidget(self.choose_color)
        reset = QPushButton('Reset')
        reset.clicked.connect(lambda: self.accent.setText(DEFAULT_ACCENT))
        row.addWidget(reset)
        layout.addLayout(row)
        self.sample = PrimaryPushButton('Accent preview')
        self.sample.setObjectName('primary')
        self.sample.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.sample, alignment=Qt.AlignmentFlag.AlignLeft)
        self.color_error = QLabel('Enter a colour name or a hex value such as #246b53.')
        self.color_error.setWordWrap(True)
        self.color_error.setObjectName('muted')
        layout.addWidget(self.color_error)
        layout.addStretch()
        self.tabs.addTab(tab, 'Display')

    def _apps_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)
        explanation = QLabel('Drag apps to change their order, or use Move up / Move down.\n'
                             'Unchecked apps open in this window.')
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.apps_heading = QLabel('Open in a new window')
        heading_font = self.apps_heading.font()
        heading_font.setBold(True)
        self.apps_heading.setFont(heading_font)
        layout.addWidget(self.apps_heading)
        self.apps = AppList()
        self.apps_heading.setBuddy(self.apps)
        self.apps.setAccessibleName('App order and new-window preferences')
        self.apps.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.apps.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        state = self.context.preferences.state
        for app_id in state['order']:
            item = QListWidgetItem(self.context.apps[app_id].name, self.apps)
            item.setData(Qt.ItemDataRole.UserRole, app_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if state['new_windows'][app_id]
                               else Qt.CheckState.Unchecked)
            item.setToolTip('Checked: new window. Unchecked: this window.')
        layout.addWidget(self.apps, 1)
        row = QHBoxLayout()
        self.move_up = QPushButton('Move up')
        self.move_down = QPushButton('Move down')
        self.move_up.clicked.connect(lambda: self.move_item(-1))
        self.move_down.clicked.connect(lambda: self.move_item(1))
        row.addWidget(self.move_up)
        row.addWidget(self.move_down)
        row.addStretch()
        layout.addLayout(row)
        self.apps.currentRowChanged.connect(self._update_move_buttons)
        self.apps.model().rowsMoved.connect(self._update_move_buttons)
        self.apps.setCurrentRow(0)
        self.tabs.addTab(tab, 'Apps')

    def _update_move_buttons(self, *_args):
        index = self.apps.currentRow()
        self.move_up.setEnabled(index > 0)
        self.move_down.setEnabled(0 <= index < self.apps.count() - 1)

    def move_item(self, step):
        index = self.apps.currentRow()
        destination = index + step
        if 0 <= index < self.apps.count() and 0 <= destination < self.apps.count():
            self.apps.insertItem(destination, self.apps.takeItem(index))
            self.apps.setCurrentRow(destination)

    def pick_color(self):
        initial = QColor(self.accent.text())
        color = QColorDialog.getColor(initial if initial.isValid() else QColor(DEFAULT_ACCENT),
                                      self, 'Choose a shared accent colour')
        if color.isValid():
            self.accent.setText(color.name())

    def preview_theme(self):
        color = QColor(self.accent.text().strip())
        valid = color.isValid() and color.alpha() == 255
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(valid)
        self.color_error.setText('Enter a colour name or a hex value such as #246b53.' if valid
                                 else 'Enter a valid, fully opaque colour before saving.')
        apply_theme(self, self.appearance.currentData(), color.name() if valid else DEFAULT_ACCENT)

    def done(self, result):
        # Fluent's theme is process-wide: discard an unsaved colour preview.
        state = self.context.preferences.state
        apply_theme(self, state['appearance'], state['accent'])
        super().done(result)

    def save(self):
        color = QColor(self.accent.text().strip())
        if not color.isValid() or color.alpha() != 255:
            return
        order, windows = [], {}
        for index in range(self.apps.count()):
            item = self.apps.item(index)
            app_id = item.data(Qt.ItemDataRole.UserRole)
            order.append(app_id)
            windows[app_id] = item.checkState() == Qt.CheckState.Checked
        try:
            self.context.preferences.update(accent=color.name(), appearance=self.appearance.currentData(),
                                            order=order, new_windows=windows)
        except OSError as error:
            QMessageBox.warning(self, 'Could not save settings', str(error))
            return
        self.accept()
