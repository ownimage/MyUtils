"""Declarative app discovery; no drive letters or per-window app menus."""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path


LAUNCHER_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class AppDefinition:
    id: str
    name: str
    description: str
    detail: str
    folder: Path
    module: str
    window_class: str
    icon: str


def load_apps(path=None):
    registry = Path(path or LAUNCHER_ROOT / 'apps.json')
    raw = json.loads(registry.read_text(encoding='utf-8'))
    apps = {}
    for record in raw:
        values = dict(record)
        values['folder'] = (registry.parent / values['folder']).resolve()
        app = AppDefinition(**values)
        if app.id in apps:
            raise ValueError(f'Duplicate app identifier: {app.id}')
        apps[app.id] = app
    return apps


def load_window_class(app):
    if not (app.folder / (app.module + '.py')).is_file():
        raise FileNotFoundError(f'{app.name} is unavailable. Expected {app.folder / (app.module + ".py")}')
    directory = str(app.folder)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    module = importlib.import_module(app.module)
    return getattr(module, app.window_class)
