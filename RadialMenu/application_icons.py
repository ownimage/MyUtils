"""Persistent application icons for profiles whose applications are closed."""
import hashlib
from pathlib import Path
from PySide6.QtCore import QIODevice, QSaveFile
from PySide6.QtGui import QIcon
from button_profiles import app_key

class ApplicationIcons:
    def __init__(self, settings):
        self.root = Path(settings.fileName()).parent/'RadialMenu'/'app-icons'

    def path(self, executable):
        digest = hashlib.sha256(app_key(executable).encode('utf-8')).hexdigest()
        return self.root/(digest+'.png')

    def cached(self, executable):
        path = self.path(executable)
        return QIcon(str(path)) if path.is_file() else QIcon()

    def remember(self, executable, icon):
        if icon.isNull():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        output = QSaveFile(str(self.path(executable)))
        if not output.open(QIODevice.OpenModeFlag.WriteOnly):
            raise OSError(output.errorString())
        if not icon.pixmap(48, 48).save(output, 'PNG'):
            output.cancelWriting()
            raise OSError('Could not cache application icon.')
        if not output.commit():
            raise OSError(output.errorString())
