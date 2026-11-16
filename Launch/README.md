# Photo Tools Launcher

A shared desktop workspace for **Camera Import**, **Yearbook**, and **Slideshow**. The workspace lives
in `P:\git\MyUtils` with the sibling folders `Launch`, `Import`, and `Yearbook`.

## Start

Double-click **launcher.bat** or **run_gui.bat** in this folder. The launcher uses
this folder's `venv` if available, otherwise the existing environment in
`../Import/venv`, then `python`.

For a separate environment, use Python 3.10 or newer:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe launcher.py
```

The Camera Import and Yearbook batch launchers still work. They start directly
on their app page, with the same shared menus and settings as the launcher.

## Using the launcher

Click a tile to open its app. The **Launch** menu lists the same apps in the same
order and includes **Launcher home**. **All apps** returns to the front page.
App pages remain alive when you switch, keeping folder choices, previews, logs,
and ongoing work. Opening an app again in the current window returns to its page.

The menu has two entries:

- **Settings** opens a dialog with **Display** and **Apps** tabs.
- **Launch** opens the app submenu, also available from both child apps.

### Display

Choose a shared accent colour using the colour picker, a colour name, or a hex
value. The dialog previews the colour; **Save** applies it, and **Cancel** leaves
settings unchanged. The full interface wash follows the accent, including window
and card backgrounds, borders, headers, muted text, disabled controls, selections,
buttons, and progress indicators. This applies in both light and dark modes.
Text contrast adjusts for pale or dark accents.

Light, Dark, and Follow Windows appearance settings are also shared. An app's
existing Appearance control now changes this shared preference. This supersedes
the older per-app appearance preference; each app still remembers its own folder.

All windows in the same process update immediately. Independently launched apps
pick up saved settings within about one second.

### Apps

Drag the list to reorder apps, or use **Move up** and **Move down**. The order is
used by the front-page tiles and every Launch menu. The drag preview is captured
from the painted row and shown in a separate, non-interactive app overlay, rather
than a Windows drag cursor. This keeps it the same size as the row on scaled
displays. A line marks the insertion point; Escape cancels the drag. Releasing
outside the list also cancels. The list scrolls when dragging near its edges.

The checkboxes under **Open in a new window** control where an app opens:

- **Checked:** open a new top-level window.
- **Unchecked:** open within the current window (the default).

A new window has the same shared Settings and Launch menus. Closing one window
does not close other windows. New windows are offset from the window that
launched them, with positioning adjusted at screen edges. Reordering reuses the
existing front-page tiles and does not reapply themes to open app previews.
Closing a window with active work cancels its
workers and waits for the current file to finish, including work on hidden pages.
The app's normal cancellation rules determine what happens to completed files.

## Shared component and future apps

The shared implementation lives in **photo_tools/**. Menus, the settings dialog,
the settings store, and styling are defined once here. The two existing GUI
modules have a small integration that imports this package and binds their views
to the shared shell. Their processing modules and command-line tools are unchanged.

**apps.json** is the app registry. Each record supplies an ID, name, description,
relative folder, Python module, and window class. Adding a compatible app there
adds its tile, settings row, and Launch-menu entry without editing existing menus.
The module is loaded only when its app is opened; missing app files produce a
readable message without closing the launcher.

An app view is a `QMainWindow` accepting `directory=''` and the keyword-only
argument `suite=None`. It calls `bind_window(self, app_id, suite)` after building
its UI, provides an Appearance combo and `_apply_theme()`, and uses `run_app()`
for standalone startup. Worker apps expose `busy` and `cancel_work()` so the shell
can wait for them during closing. See the two integrated GUIs for working examples.

Paths are relative to this repository layout, with no hard-coded drive letter.
When moving the prototype into a new repository, keep the `Yearbook`,
`Import`, and `Launch` sibling folders together, or
update registry paths and the child modules' shared-package import location.

Settings are per user, outside the repository, in
`%LOCALAPPDATA%/PhotoToolsPrototype/settings.ini` on Windows. The actual base
location comes from Qt's `GenericConfigLocation`; set `PHOTO_TOOLS_SETTINGS` to
an explicit settings-file path for isolated testing or a portable configuration.

## Checks

Run from this folder with the environment above or the existing Camera Import
environment:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover switching and preserving app state, new-window preferences, app order,
shared menus, saving and cancelling settings, cross-process updates, invalid
preferences, unavailable apps, and closing while a hidden worker is running.
The original app tests remain in their respective `tests` folders and use an
isolated shared-settings file. Tests use temporary data, not real photo folders.

## Fluent Windows interface

The launcher, Camera Import, Yearbook, Slideshow and shared settings now use
QFluentWidgets controls. Install the updated requirements.txt in the Python
environment used by the batch launcher. Slideshow appears automatically in the
launcher, Launch menu and Settings > Apps, preserving existing preferences.
