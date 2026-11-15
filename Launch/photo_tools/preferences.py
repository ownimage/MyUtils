"""One user settings file, shared by launcher and standalone app processes."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QStandardPaths, QTimer, Signal
from PySide6.QtGui import QColor


DEFAULT_ACCENT = '#246b53'


class Preferences(QObject):
    changed = Signal()

    def __init__(self, app_ids, parent=None, path=None):
        super().__init__(parent)
        self.app_ids = tuple(app_ids)
        config = Path(path or os.environ.get('PHOTO_TOOLS_SETTINGS') or (
            Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericConfigLocation))
            / 'PhotoToolsPrototype' / 'settings.ini'))
        self.settings = QSettings(str(config), QSettings.Format.IniFormat)
        self._state = self._read()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

    def _read(self):
        self.settings.sync()
        try:
            raw = json.loads(self.settings.value('suite/state', '{}', type=str))
        except (ValueError, TypeError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        accent = raw.get('accent', DEFAULT_ACCENT)
        if not isinstance(accent, str) or not QColor(accent).isValid():
            accent = DEFAULT_ACCENT
        appearance = raw.get('appearance', 'system')
        if appearance not in ('light', 'dark', 'system'):
            appearance = 'system'
        requested_order = raw.get('order', [])
        if not isinstance(requested_order, list):
            requested_order = []
        order = []
        for app_id in requested_order + list(self.app_ids):
            if app_id in self.app_ids and app_id not in order:
                order.append(app_id)
        windows = raw.get('new_windows', {})
        if not isinstance(windows, dict):
            windows = {}
        return dict(accent=QColor(accent).name(), appearance=appearance, order=order,
                    new_windows={key: windows.get(key) is True for key in self.app_ids})

    @property
    def state(self):
        return copy.deepcopy(self._state)

    def refresh(self):
        state = self._read()
        if state != self._state:
            self._state = state
            self.changed.emit()

    def update(self, **changes):
        state = self._read()
        state.update(changes)
        self.settings.setValue('suite/state', json.dumps(state))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError('Could not save shared settings. Check access to ' + self.settings.fileName())
        self.refresh()
