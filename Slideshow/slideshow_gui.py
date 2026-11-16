"""Fluent desktop view for preparing an event slideshow."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Launch'))
from photo_tools import apply_theme, bind_window, run_app
from photo_tools.fluent import (QComboBox, QLineEdit, QPushButton, PrimaryPushButton,
                               QTableWidget, QPlainTextEdit, QProgressBar)
from PySide6.QtCore import QSettings, QThread, QUrl, Qt, Signal, QSize
from PySide6.QtGui import QDesktopServices, QImageReader, QPixmap
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QFileDialog, QMessageBox, QTableWidgetItem, QHeaderView, QSplitter, QSizePolicy)
from slideshow_jobs import Slide, event_folder, load_slides, save_slides, render_slides, defaults


class PhotoPreview(QLabel):
    """A bounded, orientation-aware image that fits without stretching."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_path = None
        self.source_pixmap = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setMinimumSize(220, 160)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setAccessibleName('Selected highlight image preview')
        self.set_image(None)

    def sizeHint(self):
        return QSize(360, 260)

    def set_image(self, path):
        if path is not None and path == self.image_path:
            return
        self.image_path = path
        self.source_pixmap = QPixmap()
        self.clear()
        if path is None:
            self.setText('Select a photo to preview it.')
            return
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid() and (size.width() > 1600 or size.height() > 1200):
            reader.setScaledSize(size.scaled(QSize(1600, 1200), Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        if image.isNull():
            self.setText('Preview unavailable.\nThe image is missing or could not be read.')
            return
        self.source_pixmap = QPixmap.fromImage(image)
        self._fit()

    def _fit(self):
        if not self.source_pixmap.isNull():
            available = self.contentsRect().size() - QSize(12, 12)
            self.setPixmap(self.source_pixmap.scaled(available,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()


class RenderWorker(QThread):
    progress = Signal(int, int, str)
    result = Signal(int)
    failed = Signal(str)

    def __init__(self, folder, slides, parent=None):
        super().__init__(parent)
        self.folder, self.slides = folder, slides

    def run(self):
        try:
            count = render_slides(self.folder, self.slides, cancelled=self.isInterruptionRequested,
                                  progress=self.progress.emit)
            self.result.emit(count)
        except Exception as error:
            self.failed.emit(str(error))


class SlideshowWindow(QMainWindow):
    def __init__(self, directory='', *, suite=None):
        super().__init__()
        self.settings = QSettings('Slideshow', 'Create')
        self.busy = False
        self.worker = None
        self.loaded_folder = None
        self.dirty = False
        self.setWindowTitle('Slideshow · Create titled slides')
        self.resize(1080, 840)
        self.setMinimumSize(900, 760)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(14)
        heading = QHBoxLayout()
        label = QLabel('SLIDESHOW')
        label.setObjectName('eyebrow')
        heading.addWidget(label)
        heading.addStretch()
        heading.addWidget(QLabel('Appearance'))
        self.appearance = QComboBox()
        for name, value in (('Follow Windows', 'system'), ('Light', 'light'), ('Dark', 'dark')):
            self.appearance.addItem(name, value)
        heading.addWidget(self.appearance)
        layout.addLayout(heading)
        title = QLabel('Give every photo its story')
        title.setObjectName('title')
        layout.addWidget(title)
        subtitle = QLabel('Create slides from an event’s highlight photos, with dates and titles from your Photoshop template.')
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addWidget(QLabel('Event folder (contains highlight)'))
        row = QHBoxLayout()
        self.folder = QLineEdit(directory or self.settings.value('lastFolder', '', type=str))
        self.folder.setPlaceholderText('Choose an event folder…')
        self.folder.setAccessibleName('Event folder')
        self.folder.returnPressed.connect(self.load)
        self.folder.textChanged.connect(self._folder_changed)
        row.addWidget(self.folder, 1)
        self.browse = QPushButton('Browse…')
        self.browse.clicked.connect(self.choose_folder)
        row.addWidget(self.browse)
        self.preview = QPushButton('Load photos')
        self.preview.clicked.connect(self.load)
        row.addWidget(self.preview)
        layout.addLayout(row)
        self.default_label = QLabel('Blank cells use the date and title from the event folder name.')
        self.default_label.setWordWrap(True)
        layout.addWidget(self.default_label)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Highlight image', 'Date override', 'Title override'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.itemChanged.connect(self._edited)
        self.table.currentCellChanged.connect(self._update_preview)
        editor = QSplitter(Qt.Orientation.Horizontal)
        editor.setChildrenCollapsible(False)
        editor.addWidget(self.table)
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 0, 0, 0)
        preview_heading = QLabel('Selected photo')
        preview_heading.setObjectName('eyebrow')
        preview_layout.addWidget(preview_heading)
        self.image_preview = PhotoPreview()
        preview_layout.addWidget(self.image_preview, 1)
        self.preview_filename = QLabel('')
        self.preview_filename.setWordWrap(True)
        self.preview_filename.setTextFormat(Qt.TextFormat.PlainText)
        preview_layout.addWidget(self.preview_filename)
        preview_hint = QLabel('Original highlight image')
        preview_hint.setObjectName('muted')
        preview_layout.addWidget(preview_hint)
        editor.addWidget(preview_panel)
        editor.setStretchFactor(0, 3)
        editor.setStretchFactor(1, 2)
        editor.setSizes([650, 380])
        layout.addWidget(editor, 1)
        self.status = QLabel('Load an event to edit dates and titles. Photoshop is required to create slides.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setFixedHeight(90)
        layout.addWidget(self.log)
        row = QHBoxLayout()
        self.open_folder = QPushButton('Open slideshow')
        self.open_folder.clicked.connect(self.show_folder)
        row.addWidget(self.open_folder)
        self.template = QPushButton('Open Photoshop template')
        self.template.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(__file__).with_name('template.psd')))))
        row.addWidget(self.template)
        row.addStretch()
        self.save = QPushButton('Save dates and titles')
        self.save.clicked.connect(self.save_data)
        row.addWidget(self.save)
        self.cancel = QPushButton('Cancel')
        self.cancel.clicked.connect(self.cancel_work)
        row.addWidget(self.cancel)
        self.create = PrimaryPushButton('Create slideshow')
        self.create.clicked.connect(self.create_slides)
        row.addWidget(self.create)
        layout.addLayout(row)
        self._actions()
        self.suite_binding = bind_window(self, 'slideshow', suite)

    def _appearance_changed(self):
        try:
            self.suite_context.preferences.update(appearance=self.appearance.currentData())
        except OSError as error:
            self.suite_binding.refresh()
            QMessageBox.warning(self, 'Could not save display settings', str(error))

    def _apply_theme(self):
        self.is_dark = apply_theme(self, self.appearance.currentData(), self.suite_context.preferences.state['accent'])

    def _actions(self):
        for widget in (self.folder, self.browse, self.preview, self.table, self.template):
            widget.setEnabled(not self.busy)
        ready = self.loaded_folder is not None and self.table.rowCount() > 0
        self.save.setEnabled(not self.busy and ready)
        self.create.setEnabled(not self.busy and ready)
        self.open_folder.setEnabled(not self.busy and self.loaded_folder is not None)
        self.cancel.setVisible(self.busy)

    def _edited(self, *_):
        self.dirty = True

    def _folder_changed(self, text):
        if self.loaded_folder is not None and text != str(self.loaded_folder):
            self.loaded_folder = None
            self._update_preview()
            self.status.setText('Load this event before saving or creating slides.')
            self._actions()

    def _update_preview(self, *_):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        if self.loaded_folder is None or item is None:
            self.image_preview.set_image(None)
            self.preview_filename.setText('')
            return
        filename = item.text()
        self.preview_filename.setText(filename)
        self.image_preview.set_image(self.loaded_folder / 'highlight' / filename)

    def _discard(self):
        return not self.dirty or QMessageBox.question(self, 'Unsaved edits',
            'Discard unsaved date and title edits?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Choose event folder', self.folder.text())
        if folder:
            self.load(folder)

    def load(self, folder=None):
        if self.busy or not self._discard():
            return
        try:
            event = event_folder(folder if isinstance(folder, str) else self.folder.text())
            slides = load_slides(event)
            self.table.blockSignals(True)
            self.table.setRowCount(len(slides))
            for row, slide in enumerate(slides):
                for column, value in enumerate((slide.image, slide.date, slide.title)):
                    item = QTableWidgetItem(value)
                    if column == 0:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, column, item)
            self.table.blockSignals(False)
            self.loaded_folder = event
            self.image_preview.set_image(None)
            if slides:
                self.table.setCurrentCell(0, 0)
            else:
                self.table.setCurrentItem(None)
            self._update_preview()
            self.folder.setText(str(event))
            self.settings.setValue('lastFolder', str(event))
            date, title = defaults(event)
            self.default_label.setText(f'Blank cells use: Date: {date or "(empty)"}  ·  Title: {title}')
            self.status.setText(f'{len(slides)} highlight photos loaded. Edit any date or title, then save or create.')
            self.dirty = False
            self._actions()
        except Exception as error:
            QMessageBox.warning(self, 'Could not load event', str(error))

    def slides(self):
        return [Slide(*(self.table.item(row, col).text() for col in range(3)))
                for row in range(self.table.rowCount())]

    def save_data(self):
        try:
            save_slides(self.loaded_folder, self.slides())
            self.dirty = False
            self.status.setText('Saved dates and titles to slideshow/data.txt.')
            return True
        except Exception as error:
            QMessageBox.warning(self, 'Could not save data', str(error))
            return False

    def create_slides(self):
        if self.busy or self.loaded_folder is None:
            return
        answer = QMessageBox.question(self, 'Create slideshow?',
            'Create slides from the highlight originals? Existing slides with matching filenames will be replaced. '
            'Highlight originals stay unchanged. Photoshop will open as needed.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes or not self.save_data():
            return
        self.busy = True
        self._actions()
        self.progress.setRange(0, self.table.rowCount())
        self.progress.setValue(0)
        self.log.clear()
        self.status.setText('Creating slides in Photoshop…')
        self.worker = RenderWorker(self.loaded_folder, self.slides(), self)
        self.worker.progress.connect(self._progress)
        self.worker.result.connect(self._result)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _progress(self, current, total, image):
        self.progress.setValue(current)
        self.log.appendPlainText(f'Created {image} ({current}/{total})')

    def _result(self, count):
        state = 'Cancelled' if self.worker.isInterruptionRequested() else 'Finished'
        self.status.setText(f'{state}: {count} slides created. Completed slides are kept.')

    def _failed(self, message):
        self.status.setText('Could not finish. Completed slides are kept; see the details below.')
        self.log.appendPlainText(message)

    def _finished(self):
        self.busy = False
        self.worker.deleteLater()
        self.worker = None
        self._actions()

    def cancel_work(self):
        if self.worker:
            self.worker.requestInterruption()
            self.status.setText('Stopping after the current Photoshop image finishes…')

    def show_folder(self):
        if self.loaded_folder:
            folder = self.loaded_folder / 'slideshow'
            if not folder.is_dir():
                QMessageBox.information(self, 'Slideshow folder', 'Save dates and titles or create slides first.')
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event):
        if self.busy:
            self.cancel_work()
            event.ignore()
        elif self._discard():
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    raise SystemExit(run_app('slideshow', sys.argv[1] if len(sys.argv) > 1 else '', SlideshowWindow))
