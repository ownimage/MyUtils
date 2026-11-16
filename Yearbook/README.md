# Yearbook

Collect the JPGs from a year's slideshow folders into one `yearbook` folder.
This gathers existing slideshow images; it does not generate a PDF or slideshow.

## Desktop app

Double-click **yearbook_gui.bat** or **run_gui.bat**. The interface matches the
Camera Import app, including Light, Dark, and Follow Windows appearance settings.
The last selected folder and appearance are remembered.

1. Choose the year folder with **Browse...**, or enter its path and select
   **Preview files**. Browsing starts the preview automatically.
2. Review the source slideshow folders, proposed filenames, and skipped files.
   Previewing does not copy files or create the output folder.
3. Select **Copy N photos** and confirm. **Open yearbook** opens the output folder.

The app stays responsive while scanning and copying. **Cancel** stops after the
current file. Closing while busy requests cancellation and waits for that file
to finish. Completed copies are kept; originals remain in place. Preview again
after copying or cancelling.

### Folder and filename rules

The app looks for folders named `slideshow` at the selected folder and up to
three levels below it, including `year/event/slideshow` and
`year/group/event/slideshow`. It copies only `.jpg` files directly inside each
slideshow folder, accepting upper- and lowercase names and extensions. It does
not descend further inside a slideshow folder or scan an existing `yearbook`.

Output names start with the **first eight characters of the slideshow's parent
folder**, followed by `_` and the original filename, matching `yearbook.py`:

```text
2026/
  20260615 Holiday/
    slideshow/
      001.jpg
  yearbook/
    20260615_001.jpg
```

The desktop app keeps existing yearbook files unchanged. If two photos produce
the same output name, the first in alphabetical folder/file order is ready and
the later photo is marked skipped. Existing files, collisions, and read errors
are explained in the preview or activity log. Changed or missing source files
are reported during copying, and other files continue. Linked folders and images
are skipped. No source photos are moved or deleted.

### Python setup

The launcher prefers this folder's `venv`, otherwise it reuses the Camera Import
app's existing `..\Import\venv`, then tries `python`.
No separate installation is needed if the Camera Import environment is available.

For an independent installation, use Python 3.10 or newer:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

You can launch directly or pass an initial year folder:

```powershell
.\venv\Scripts\python.exe yearbook_gui.py "D:\Photos\2026"
.\yearbook_gui.bat "D:\Photos\2026"
```

## Original command line

The original command still works without PySide6:

```powershell
python yearbook.py "D:\Photos\2026"
```

This retains the original script's behaviour, including replacing existing
output files with the same name. Use the desktop app for previewing and keeping
existing files unchanged. The `refresh.py` and `create_from_highlights.py`
utilities are separate tools and are not run by the desktop app.

## Tests

Tests use temporary sample files; they do not touch your photo collection.
GUI tests use Qt's offscreen platform.

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

If reusing the Camera Import environment, substitute its Python path above.


## Shared Photo Tools launcher

This app now participates in the workspace in `../Launch`. Its existing
batch launcher opens this app directly, with the shared **Settings** and
**Launch** menus. Start `../Launch/launcher.bat` for the front page.

**Settings > Display** sets a shared accent colour and Light / Dark / Follow
Windows appearance. The app's Appearance control also changes that shared
setting. **Settings > Apps** reorders the tiles and Launch menu, with a checkbox
per app: checked opens a new window, unchecked opens in the current window.
The shared `photo_tools` component supplies menus and styling to both apps.
Switching apps preserves each page's current work. See the launcher README for
setup, settings storage, and integration details. The command-line processing
behaviour is unchanged.

## Fluent Windows interface

The launcher, Camera Import, Yearbook, Slideshow and shared settings now use
QFluentWidgets controls. Install the updated requirements.txt in the Python
environment used by the batch launcher. Slideshow appears automatically in the
launcher, Launch menu and Settings > Apps, preserving existing preferences.
