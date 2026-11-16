"""PySide6 front end for reorg.py. Run: python reorg_gui.py [folder]"""

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
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from photo_tools.fluent import QPushButton, QLineEdit, QPlainTextEdit, QProgressBar, QTableWidget, QComboBox, PrimaryPushButton


from reorg import MoveResult, PlannedFile, ScanResult, apply_plan, scan_directory


class ImportWorker(QThread):
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
            options = dict(on_progress=self.progress.emit, cancelled=self.isInterruptionRequested)
            if self.plan is None:
                result = scan_directory(self.directory, on_file=self.scanned.emit, **options)
            else:
                result = apply_plan(self.plan, on_file=self.processed.emit, **options)
            self.result.emit(result)
        except Exception as error:
            self.failed.emit(str(error) or type(error).__name__)


class ImportWindow(QMainWindow):
    def __init__(self, directory: str = '', *, suite=None):
        super().__init__()
        self.settings = QSettings('CameraImport', 'Reorganise')
        self.plan = None
        self.worker = None
        self.closing = False
        self.busy = False
        self.setWindowTitle('Camera Import · Reorganise photos')
        self.resize(1080, 780)
        self.setMinimumSize(800, 650)
        self._build_ui()
        self.folder.setText(directory or self.settings.value('lastFolder', '', type=str))
        self._update_actions()
        self.suite_binding = bind_window(self, 'camera-import', suite)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(16)

        eyebrow = QLabel('CAMERA IMPORT')
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
        title = QLabel('A place for every photo')
        title.setObjectName('title')
        layout.addWidget(title)
        subtitle = QLabel('Group images by the date taken. Keep JPEG originals together in origJPG.')
        subtitle.setWordWrap(True)
        subtitle.setObjectName('muted')
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName('card')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.addWidget(QLabel('Import folder'))
        folder_row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText('Choose the folder containing your imported photos…')
        self.folder.setAccessibleName('Import folder')
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
        hint = QLabel('Top-level files only  ·  NEF → YYYYMMDD/  ·  JPEG → YYYYMMDD/origJPG/')
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        card_layout.addWidget(hint)
        layout.addWidget(card)

        summary = QHBoxLayout()
        self.counts = []
        for label in ('IMAGE FILES', 'READY TO MOVE', 'SKIPPED'):
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
        self.table.setHorizontalHeaderLabels(['File', 'Date taken', 'Destination / reason', 'Status'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 205)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        self.status = QLabel('Choose a folder, then preview the proposed moves.')
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
        self.open_folder = QPushButton('Open folder')
        self.open_folder.clicked.connect(self.show_folder)
        actions.addWidget(self.open_folder)
        note = QLabel('Moves files within this folder. Existing files are never replaced.')
        note.setObjectName('muted')
        note.setWordWrap(True)
        actions.addWidget(note, 1)
        self.cancel = QPushButton('Cancel')
        self.cancel.clicked.connect(self.cancel_work)
        self.cancel.hide()
        actions.addWidget(self.cancel)
        self.organise = PrimaryPushButton('Organise files')
        self.organise.setObjectName('primary')
        self.organise.clicked.connect(self.confirm_organise)
        actions.addWidget(self.organise)
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
        directory = QFileDialog.getExistingDirectory(self, 'Choose import folder', self.folder.text())
        if directory:
            self.folder.setText(directory)
            self.start_preview()

    @Slot(str)
    def _folder_changed(self, _text):
        self.plan = None
        self.table.setRowCount(0)
        for count in self.counts:
            count.setText('0')
        self.status.setText('Preview this folder to see the proposed moves.')
        self.progress.setValue(0)
        self._update_actions()

    def _update_actions(self):
        self.folder.setEnabled(not self.busy)
        self.browse.setEnabled(not self.busy)
        self.preview.setEnabled(not self.busy and bool(self.folder.text().strip()))
        self.open_folder.setEnabled(not self.busy and bool(self.folder.text().strip()))
        ready = self.plan.ready_count if self.plan is not None and not self.plan.cancelled else 0
        self.organise.setEnabled(not self.busy and ready > 0)
        self.organise.setText(f'Organise {ready:,} files' if ready else 'Organise files')
        self.cancel.setVisible(self.busy)
        self.cancel.setEnabled(self.busy)

    @Slot()
    def start_preview(self):
        if self.busy:
            return
        try:
            if not self.folder.text().strip():
                raise ValueError('Choose an import folder first.')
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
        self.status.setText('Reading photo dates… No files are being moved.')
        self._start_worker(directory)

    def _start_worker(self, directory, plan=None):
        self.busy = True
        self.progress.setRange(0, 0)
        self._update_actions()
        self.worker = ImportWorker(directory, plan, self)
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
        date = f'{item.date[:4]}-{item.date[4:6]}-{item.date[6:]}' if item.date else '—'
        detail = str(item.destination.relative_to(item.source.parent)) if item.ready else item.reason
        for column, value in enumerate((item.source.name, date, detail, 'Ready' if item.ready else 'Skipped')):
            cell = QTableWidgetItem(value)
            cell.setToolTip(value)
            self.table.setItem(row, column, cell)
        self._colour_status(row, 'Ready' if item.ready else 'Skipped')

    def _colour_status(self, row, status):
        success, warning, error, muted = (
            ('#83d5b1', '#efbf75', '#ff9a94', '#a6b9ae') if self.is_dark else
            ('#246b53', '#94621c', '#b13d36', '#64756f'))
        colour = {'Ready': success, 'Moved': success, 'Skipped': warning,
                  'Error': error, 'Not moved': muted}.get(status, muted)
        self.table.item(row, 3).setForeground(QColor(colour))

    @Slot(int, str, str)
    def _file_processed(self, row, status, message):
        self.table.item(row, 3).setText(status)
        self.table.item(row, 3).setToolTip(message)
        self._colour_status(row, status)
        if status != 'Moved':
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
                text = 'Preview cancelled. Preview again before organising files.'
            elif not result.files:
                text = 'No supported images found at the top level of this folder.'
            else:
                text = (f'Preview complete: {result.ready_count:,} ready, {skipped:,} skipped. '
                        f'{result.ignored:,} folders or other files ignored. No files moved.')
            self.status.setText(text)
            self.log.appendPlainText(text)
            for item in result.files:
                if item.reason:
                    self.log.appendPlainText(f'Skipped: {item.source.name} — {item.reason}')
        elif isinstance(result, MoveResult):
            text = (f'{"Cancelled" if result.cancelled else "Finished"}: {result.moved:,} moved, '
                    f'{result.skipped:,} skipped, {result.errors:,} errors.')
            if result.cancelled:
                text += ' Completed moves are kept; remaining files stay in place.'
            self.status.setText(text + ' Preview again to refresh the folder.')
            self.log.appendPlainText(text)
            self.plan = None
            self.counts[1].setText('0')
            self.counts[2].setText(f'{result.skipped:,}')
            for row in range(self.table.rowCount()):
                if self.table.item(row, 3).text() == 'Ready':
                    self.table.item(row, 3).setText('Not moved')
                    self._colour_status(row, 'Not moved')
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
    def confirm_organise(self):
        if self.busy or self.plan is None or not self.plan.ready_count or self.plan.cancelled:
            return
        answer = QMessageBox.question(
            self, 'Organise these files?',
            f'Move {self.plan.ready_count:,} files into date folders inside:\n\n'
            f'{self.plan.directory}\n\nJPEG files go into origJPG. Existing files will be skipped.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.status.setText('Organising files…')
            self._start_worker(self.plan.directory, self.plan)

    @Slot()
    def cancel_work(self):
        if self.worker is not None:
            self.worker.requestInterruption()
            self.cancel.setEnabled(False)
            self.status.setText('Stopping after the current file…')

    @Slot()
    def show_folder(self):
        path = Path(self.folder.text().strip()).expanduser()
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
    return run_app('camera-import', sys.argv[1] if len(sys.argv) > 1 else '', ImportWindow)


if __name__ == '__main__':
    raise SystemExit(main())
