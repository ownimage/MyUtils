"""PySide6 front end for yearbook.py. Run: python yearbook_gui.py [year-folder]"""

from __future__ import annotations

import sys
from pathlib import Path

# Keep the shared shell portable with the repository's existing folder layout.
_shared_ui = str(Path(__file__).resolve().parents[1] / 'Launch')
if _shared_ui not in sys.path:
    sys.path.insert(0, _shared_ui)
from photo_tools import apply_theme, bind_window, run_app

from PySide6.QtCore import QSettings, QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from yearbook import CopyResult, PlannedFile, ScanResult, copy_plan, scan_directory


class YearbookWorker(QThread):
    scanned = Signal(object)
    processed = Signal(int, str, str)
    progress = Signal(int, int)
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, directory: Path, plan: ScanResult | None = None, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.plan = plan

    def run(self):
        try:
            options = dict(cancelled=self.isInterruptionRequested)
            if self.plan is None:
                result = scan_directory(self.directory, on_file=self.scanned.emit, **options)
            else:
                result = copy_plan(self.plan, on_file=self.processed.emit,
                                   on_progress=self.progress.emit, **options)
            self.result.emit(result)
        except Exception as error:
            self.failed.emit(str(error) or type(error).__name__)


class YearbookWindow(QMainWindow):
    def __init__(self, directory: str = '', *, suite=None):
        super().__init__()
        self.settings = QSettings('Yearbook', 'Create')
        self.plan = None
        self.worker = None
        self.closing = False
        self.busy = False
        self.setWindowTitle('Yearbook · Collect slideshow photos')
        self.resize(1080, 840)
        self.setMinimumSize(900, 760)
        self._build_ui()
        self.folder.setText(directory or self.settings.value('lastFolder', '', type=str))
        self._update_actions()
        self.suite_binding = bind_window(self, 'yearbook', suite)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(12)

        eyebrow = QLabel('YEARBOOK')
        eyebrow.setObjectName('eyebrow')
        heading = QHBoxLayout()
        heading.addWidget(eyebrow)
        heading.addStretch()
        appearance_label = QLabel('Appearance')
        heading.addWidget(appearance_label)
        self.appearance = QComboBox()
        self.appearance.setAccessibleName('Appearance')
        appearance_label.setBuddy(self.appearance)
        self.appearance.addItem('Follow Windows', 'system')
        self.appearance.addItem('Light', 'light')
        self.appearance.addItem('Dark', 'dark')
        heading.addWidget(self.appearance)
        layout.addLayout(heading)
        title = QLabel('Bring the year together')
        title.setObjectName('title')
        layout.addWidget(title)
        subtitle = QLabel('Collect slideshow photos into one yearbook folder, ready for the next step.')
        subtitle.setWordWrap(True)
        subtitle.setObjectName('muted')
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName('card')
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.addWidget(QLabel('Year folder'))
        folder_row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText('Choose the year folder containing your slideshows…')
        self.folder.setAccessibleName('Year folder')
        self.folder.textChanged.connect(self._folder_changed)
        self.folder.returnPressed.connect(self.start_preview)
        folder_row.addWidget(self.folder, 1)
        self.browse = QPushButton('Browse…')
        self.browse.clicked.connect(self.choose_folder)
        folder_row.addWidget(self.browse)
        self.preview = QPushButton('Preview files')
        self.preview.clicked.connect(self.start_preview)
        folder_row.addWidget(self.preview)
        card_layout.addLayout(folder_row)
        hint = QLabel('Find slideshow folders up to 3 levels down  ·  Copy JPGs to yearbook/')
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        card_layout.addWidget(hint)
        layout.addWidget(card)

        summary = QHBoxLayout()
        self.counts = []
        for label in ('JPG FILES', 'READY TO COPY', 'SKIPPED'):
            box = QFrame()
            box.setObjectName('card')
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(16, 10, 16, 10)
            value = QLabel('0')
            value.setObjectName('count')
            caption = QLabel(label)
            caption.setObjectName('eyebrow')
            box_layout.addWidget(value)
            box_layout.addWidget(caption)
            self.counts.append(value)
            summary.addWidget(box, 1)
        layout.addLayout(summary)

        self.table = QTableWidget(0, 4)
        self.table.setMinimumHeight(145)
        self.table.setHorizontalHeaderLabels(['File', 'Slideshow folder', 'Yearbook filename / reason', 'Status'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 205)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(1, 225)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        self.status = QLabel('Choose a year folder, then preview the photos to collect.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText('Details and skipped-file explanations appear here.')
        self.log.setMaximumBlockCount(3000)
        self.log.setFixedHeight(86)
        self.log.setAccessibleName('Activity log')
        layout.addWidget(self.log)

        actions = QHBoxLayout()
        self.open_folder = QPushButton('Open yearbook')
        self.open_folder.clicked.connect(self.show_folder)
        actions.addWidget(self.open_folder)
        note = QLabel('Copies photos; originals stay in place. Existing yearbook files are kept.')
        note.setObjectName('muted')
        note.setWordWrap(True)
        actions.addWidget(note, 1)
        self.cancel = QPushButton('Cancel')
        self.cancel.clicked.connect(self.cancel_work)
        self.cancel.hide()
        actions.addWidget(self.cancel)
        self.create = QPushButton('Create yearbook')
        self.create.setObjectName('primary')
        self.create.clicked.connect(self.confirm_create)
        actions.addWidget(self.create)
        layout.addLayout(actions)

    @Slot()
    def _appearance_changed(self):
        try:
            self.suite_context.preferences.update(appearance=self.appearance.currentData())
        except OSError as error:
            self.suite_binding.refresh()
            QMessageBox.warning(self, 'Could not save display settings', str(error))

    def _system_is_dark(self):
        return QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def _apply_theme(self):
        self.is_dark = apply_theme(self, self.appearance.currentData(),
                                   self.suite_context.preferences.state['accent'])
        for row in range(self.table.rowCount()):
            self._colour_status(row, self.table.item(row, 3).text())

    @Slot()
    def choose_folder(self):
        directory = QFileDialog.getExistingDirectory(self, 'Choose year folder', self.folder.text())
        if directory:
            self.folder.setText(directory)
            self.start_preview()

    @Slot(str)
    def _folder_changed(self, _text):
        self.plan = None
        self.table.setRowCount(0)
        for count in self.counts:
            count.setText('0')
        self.status.setText('Preview this folder to see the photos to collect.')
        self.progress.setValue(0)
        self._update_actions()

    def _update_actions(self):
        self.folder.setEnabled(not self.busy)
        self.browse.setEnabled(not self.busy)
        self.preview.setEnabled(not self.busy and bool(self.folder.text().strip()))
        output = Path(self.folder.text().strip()) / 'yearbook'
        self.open_folder.setEnabled(not self.busy and bool(self.folder.text().strip()) and output.is_dir())
        ready = self.plan.ready_count if self.plan is not None and not self.plan.cancelled else 0
        self.create.setEnabled(not self.busy and ready > 0)
        self.create.setText(f'Copy {ready:,} photos' if ready else 'Create yearbook')
        self.cancel.setVisible(self.busy)
        self.cancel.setEnabled(self.busy)

    @Slot()
    def start_preview(self):
        if self.busy:
            return
        try:
            if not self.folder.text().strip():
                raise ValueError('Choose a year folder first.')
            directory = Path(self.folder.text().strip()).expanduser().resolve(strict=True)
            if not directory.is_dir():
                raise ValueError('Choose a folder, rather than a file.')
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Cannot preview folder', str(error))
            return
        self.folder.setText(str(directory))
        self.plan = None
        self.table.setRowCount(0)
        self.log.clear()
        for count in self.counts:
            count.setText('0')
        self.settings.setValue('lastFolder', str(directory))
        self.status.setText('Finding slideshow photos… No files are being copied.')
        self._start_worker(directory)

    def _start_worker(self, directory, plan=None):
        self.busy = True
        self.progress.setRange(0, 0)
        self._update_actions()
        self.worker = YearbookWorker(directory, plan, self)
        self.worker.scanned.connect(self._add_file)
        self.worker.processed.connect(self._file_processed)
        self.worker.progress.connect(self._progress)
        self.worker.result.connect(self._result)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    @Slot(object)
    def _add_file(self, item: PlannedFile):
        row = self.table.rowCount()
        self.table.insertRow(row)
        slideshow = str(item.source.parent.relative_to(Path(self.folder.text()))) or '.'
        detail = item.destination.name if item.ready else item.reason
        for column, value in enumerate((item.source.name, slideshow, detail, 'Ready' if item.ready else 'Skipped')):
            cell = QTableWidgetItem(value)
            cell.setToolTip(value)
            self.table.setItem(row, column, cell)
        self._colour_status(row, 'Ready' if item.ready else 'Skipped')

    def _colour_status(self, row, status):
        success, warning, error, muted = (
            ('#83d5b1', '#efbf75', '#ff9a94', '#a6b9ae') if self.is_dark else
            ('#246b53', '#94621c', '#b13d36', '#64756f'))
        colour = {'Ready': success, 'Copied': success, 'Skipped': warning,
                  'Error': error, 'Not copied': muted}.get(status, muted)
        self.table.item(row, 3).setForeground(QColor(colour))

    @Slot(int, str, str)
    def _file_processed(self, row, status, message):
        self.table.item(row, 3).setText(status)
        self.table.item(row, 3).setToolTip(message)
        self._colour_status(row, status)
        if status != 'Copied':
            self.table.item(row, 2).setText(message)
            self.table.item(row, 2).setToolTip(message)
        self.log.appendPlainText(f'{status}: {self.table.item(row, 0).text()} — {message}')

    @Slot(int, int)
    def _progress(self, current, total):
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(current)

    @Slot(object)
    def _result(self, result):
        if isinstance(result, ScanResult):
            self.plan = result
            skipped = len(result.files) - result.ready_count
            for label, value in zip(self.counts, (len(result.files), result.ready_count, skipped)):
                label.setText(f'{value:,}')
            if result.cancelled:
                text = 'Preview cancelled. Preview again before creating the yearbook.'
            elif not result.files:
                text = 'No JPG photos found in slideshow folders up to 3 levels down.'
            else:
                text = (f'Preview complete: {result.ready_count:,} ready, {skipped:,} skipped. '
                        f'{result.slideshows:,} slideshow folders found. No files copied.')
            self.status.setText(text)
            self.log.appendPlainText(text)
            for warning in result.warnings:
                self.log.appendPlainText(f'Warning: {warning}')
            if result.warnings:
                self.status.setText(text + f' {len(result.warnings):,} folder warnings; see the log.')
            for item in result.files:
                if item.reason:
                    self.log.appendPlainText(f'Skipped: {item.source.name} — {item.reason}')
        elif isinstance(result, CopyResult):
            text = (f'{"Cancelled" if result.cancelled else "Finished"}: {result.copied:,} copied, '
                    f'{result.skipped:,} skipped, {result.errors:,} errors.')
            if result.cancelled:
                text += ' Completed copies are kept; all originals stay in place.'
            self.status.setText(text + ' Preview again to refresh the folder.')
            self.log.appendPlainText(text)
            self.plan = None
            self.counts[1].setText('0')
            self.counts[2].setText(f'{result.skipped:,}')
            for row in range(self.table.rowCount()):
                if self.table.item(row, 3).text() == 'Ready':
                    self.table.item(row, 3).setText('Not copied')
                    self._colour_status(row, 'Not copied')
        self.progress.setRange(0, 100)
        self.progress.setValue(0 if result.cancelled else 100)

    @Slot(str)
    def _failed(self, message):
        self.plan = None
        self.status.setText('Could not finish. See the details below, then preview again.')
        self.log.appendPlainText(f'Error: {message}')
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    @Slot()
    def _finished(self):
        self.worker = None
        self.busy = False
        self._update_actions()
        if self.closing:
            QTimer.singleShot(0, self.close)

    @Slot()
    def confirm_create(self):
        if self.busy or self.plan is None or not self.plan.ready_count or self.plan.cancelled:
            return
        answer = QMessageBox.question(
            self, 'Create this yearbook?',
            f'Copy {self.plan.ready_count:,} photos into:\n\n'
            f'{self.plan.output}\n\nOriginals stay in place. Existing files will be skipped.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.status.setText('Copying photos to yearbook…')
            self._start_worker(self.plan.directory, self.plan)

    @Slot()
    def cancel_work(self):
        if self.worker is not None:
            self.worker.requestInterruption()
            self.cancel.setEnabled(False)
            self.status.setText('Stopping after the current file…')

    @Slot()
    def show_folder(self):
        path = Path(self.folder.text().strip()).expanduser() / 'yearbook'
        if not path.is_dir() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))):
            QMessageBox.warning(self, 'Cannot open folder', 'The folder is unavailable or could not be opened.')

    def closeEvent(self, event):
        if self.busy:
            self.closing = True
            self.cancel_work()
            event.ignore()
        else:
            event.accept()


def main():
    return run_app('yearbook', sys.argv[1] if len(sys.argv) > 1 else '', YearbookWindow)


if __name__ == '__main__':
    raise SystemExit(main())
