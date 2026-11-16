"""Fluent desktop view for preparing an event slideshow."""
from __future__ import annotations
import sys
import copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Launch'))
from photo_tools import apply_theme, bind_window, run_app
from photo_tools.fluent import (QComboBox, QLineEdit, QPushButton, PrimaryPushButton,
                               QTableWidget, QPlainTextEdit, QProgressBar)
from PySide6.QtCore import QSettings, QThread, QUrl, Qt, Signal, QSize
from PySide6.QtGui import QDesktopServices, QImageReader, QPixmap
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QFileDialog, QMessageBox, QTableWidgetItem, QHeaderView, QSplitter, QSizePolicy, QStackedWidget)
from slideshow_jobs import Slide, event_folder, load_slides, save_slides, render_slides, defaults, load_project, save_template, render_worker_count

from template_render import ensure_fonts, default_template, render_image
from template_editor import TemplateEditor


class PhotoPreview(QLabel):
    """A bounded, orientation-aware image that fits without stretching."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_path = None
        self.source_pixmap = QPixmap()
        self.rendered_pixmap = QPixmap()
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
        self.rendered_pixmap = QPixmap()
        self.clear()
        if path is None:
            self.setText('Select a photo to preview it.')
            return
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid() and (size.width() > 1920 or size.height() > 1080):
            reader.setScaledSize(size.scaled(QSize(1920, 1080), Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        if image.isNull():
            self.setText('Preview unavailable.\nThe image is missing or could not be read.')
            return
        self.source_pixmap = QPixmap.fromImage(image)
        self._fit()

    def set_slide(self, path, title, date, template):
        self.set_image(path)
        if not self.source_pixmap.isNull():
            image = render_image(self.source_pixmap.toImage(), title, date, template)
            self.rendered_pixmap = QPixmap.fromImage(image)
            self._fit()

    def _fit(self):
        pixmap = self.rendered_pixmap if not self.rendered_pixmap.isNull() else self.source_pixmap
        if not pixmap.isNull():
            available = self.contentsRect().size() - QSize(12, 12)
            self.setPixmap(pixmap.scaled(available,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()


class RenderWorker(QThread):
    progress = Signal(int, int, str)
    result = Signal(int)
    failed = Signal(str)

    def __init__(self, folder, slides, parent=None, *, template=None):
        super().__init__(parent)
        self.folder, self.slides = folder, slides
        self.template = copy.deepcopy(template)

    def run(self):
        try:
            count = render_slides(self.folder, self.slides, cancelled=self.isInterruptionRequested,
                                  progress=self.progress.emit, template=self.template)
            self.result.emit(count)
        except Exception as error:
            self.failed.emit(str(error))


class SlideshowWindow(QMainWindow):
    def __init__(self, directory='', *, suite=None):
        super().__init__()
        ensure_fonts()
        self.template_settings = default_template()
        self.settings = QSettings('Slideshow', 'Create')
        self.busy = False
        self.worker = None
        self.loaded_folder = None
        self.template_editor = None
        self.dirty = False
        self.setWindowTitle('Slideshow · Create titled slides')
        self.resize(1080, 840)
        self.setMinimumSize(900, 760)
        root = QWidget()
        self.main_page = root
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(root)
        self.setCentralWidget(self.content_stack)
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
        subtitle = QLabel('Create slides from an event’s highlight photos, with dates and titles you can style and position visually.')
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
        preview_hint = QLabel('Rendered slide preview · 1920 × 1080')
        preview_hint.setObjectName('muted')
        preview_layout.addWidget(preview_hint)
        editor.addWidget(preview_panel)
        editor.setStretchFactor(0, 3)
        editor.setStretchFactor(1, 2)
        editor.setSizes([650, 380])
        layout.addWidget(editor, 1)
        self.status = QLabel('Load an event to edit dates and titles. Edit the template to change fonts and move the text.')
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
        self.template = QPushButton('Edit template…')
        self.template.clicked.connect(self.edit_template)
        row.addWidget(self.template)
        row.addStretch()
        self.save = QPushButton('Save data')
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

    @property
    def dirty(self):
        editor = getattr(self,'template_editor',None)
        return getattr(self,'_dirty',False) or (editor is not None and editor.is_dirty())

    @dirty.setter
    def dirty(self, value):
        self._dirty = bool(value)
        editor = getattr(self,'template_editor',None)
        if not value and editor is not None:
            editor.mark_clean()

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
        self.template.setEnabled(not self.busy and ready)
        self.open_folder.setEnabled(not self.busy and self.loaded_folder is not None)
        self.cancel.setVisible(self.busy)

    def _edited(self, *_):
        self.dirty = True
        self._update_preview()

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
        default_date, default_title = defaults(self.loaded_folder)
        date = self.table.item(row, 1).text() or default_date
        title = self.table.item(row, 2).text() or default_title
        self.image_preview.set_slide(self.loaded_folder / 'highlight' / filename, title, date, self.template_settings)

    def _discard(self):
        return not self.dirty or QMessageBox.question(self, 'Unsaved edits',
            'Discard unsaved slideshow edits, including template changes?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
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
            project = load_project(event)
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
            self.template_settings = project['template']
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
            save_slides(self.loaded_folder, self.slides(), self.template_settings)
            self.dirty = False
            self.status.setText('Saved dates/titles to highlight/data.txt and layout to highlight/template.json.')
            return True
        except Exception as error:
            QMessageBox.warning(self, 'Could not save data', str(error))
            return False

    def edit_template(self):
        if self.loaded_folder is None or self.busy:
            return
        if self.template_editor is not None:
            self.content_stack.setCurrentWidget(self.template_editor)
            return
        row = self.table.currentRow()
        date, title = defaults(self.loaded_folder)
        path = None
        if row >= 0:
            path = self.loaded_folder / 'highlight' / self.table.item(row,0).text()
            date = self.table.item(row,1).text() or date
            title = self.table.item(row,2).text() or title
        editor = TemplateEditor(self.template_settings, path, title, date, self.content_stack)
        self.template_editor = editor
        editor.accepted.connect(lambda: self._finish_template(True))
        editor.rejected.connect(lambda: self._finish_template(False))
        self.content_stack.addWidget(editor)
        self.content_stack.setCurrentWidget(editor)

    def _finish_template(self, accepted):
        editor = self.template_editor
        if editor is None:
            return
        if accepted:
            try:
                save_template(self.loaded_folder, editor.value)
            except (OSError, ValueError) as error:
                editor.default_status.setText('Could not save event template: '+str(error))
                return
            self.template_settings = copy.deepcopy(editor.value)
        editor.canvas.timer.stop()
        self.content_stack.setCurrentWidget(self.main_page)
        self.content_stack.removeWidget(editor)
        self.template_editor = None
        editor.deleteLater()
        if accepted:
            self._update_preview()
            self.status.setText('Template saved to highlight/template.json.')

    def create_slides(self):
        if self.busy or self.loaded_folder is None:
            return
        answer = QMessageBox.question(self, 'Create slideshow?',
            'Create slides from the highlight originals? Existing slides with matching filenames will be replaced. '
            'Highlight originals stay unchanged.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes or not self.save_data():
            return
        self.busy = True
        self._actions()
        self.progress.setRange(0, self.table.rowCount())
        self.progress.setValue(0)
        self.log.clear()
        self.status.setText(f'Creating slides using up to {render_worker_count(self.table.rowCount())} workers…')
        self.worker = RenderWorker(self.loaded_folder, self.slides(), self, template=self.template_settings)
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
            self.status.setText('Stopping… waiting for images already in progress.')

    def show_folder(self):
        if self.loaded_folder:
            folder = self.loaded_folder / 'slideshow'
            if not folder.is_dir():
                QMessageBox.information(self, 'Slideshow folder', 'Use Save data or create slides first.')
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
