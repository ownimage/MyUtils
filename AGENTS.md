# MyUtils agent notes

This file is the maintained record of project architecture, decisions, gotchas,
and validation. Read it before making changes anywhere in this repository.

## Keep this file current

- Update this file in the same change whenever architecture, dependencies,
  workflows, commands, decisions, or known limitations change.
- Record useful discoveries and the reason for non-obvious decisions. Revise or
  remove superseded notes rather than accumulating contradictory instructions.
- Keep notes concrete and tied to current source files. Distinguish verified
  behaviour from assumptions and work that has not been tested.
- Put user-facing setup and run commands in `commands.md`; keep it and this file
  consistent. Update app READMEs when their documented behaviour changes.
- For documentation-only changes, check accuracy and formatting; a full test run
  is not required unless executable behaviour or commands change.

## Scope and established decisions

- Work only in `P:\git\MyUtils`. Slideshow was brought into this repository;
  the old image-processing-examples folder is no longer the working source.
- Use one top-level `requirements.txt` and one top-level `venv` for every app,
  launcher, test suite, and Photoshop worker. Do not add per-app environments or
  dependency manifests. Do not commit `venv` (ignored by root `.gitignore`).
- The shared environment is Python 3.11 on Windows. GUI dependencies use
  PySide6 and **PySide6-Fluent-Widgets**; do not mix PyQt variants into it.
- Use QFluentWidgets for the common Windows 11 appearance. Maintain shared
  Light / Dark / Follow Windows and accent settings across all GUI apps.
- Keep source-photo protection, previews before file operations, responsive
  background work, cancellation, and existing CLI behaviour when making changes.

## Repository map

| Path | Responsibility |
| --- | --- |
| `requirements.txt` | Combined GUI, import, image, and Photoshop dependencies |
| `venv/` | Shared Python 3.11 environment; generated, not source |
| `commands.md` | Setup, launch, and full-test commands |
| `run_tests.py` | Runs all four suites in separate processes |
| `launcher.bat` | Root launch command; delegates to `Launch/run_gui.bat` |
| `Launch/launcher.py` | Python launcher entry point |
| `Launch/apps.json` | App registry: IDs, names, modules, classes, relative folders |
| `Launch/photo_tools/` | Shared shell, navigation, settings, Fluent controls, theme |
| `Import/reorg.py` | Camera import planning and file operations |
| `Import/reorg_gui.py` | Camera Import view and background worker |
| `Yearbook/yearbook.py` | Scan and collect existing slideshow JPGs |
| `Yearbook/yearbook_gui.py` | Yearbook view and background worker |
| `Slideshow/slideshow_jobs.py` | Overrides, fresh-image preparation, worker invocation |
| `Slideshow/slideshow_gui.py` | Date/title editor, selected-image preview, render worker |
| `Slideshow/render_slide.py` | Isolated Photoshop process entry point |
| `Slideshow/slideshow.py` | Resize image, apply PSD layers, save rendered JPEG |
| `Slideshow/template.psd` | Shared Photoshop layout and text styling |

## Shared GUI architecture

- `photo_tools/shell.py` owns `SuiteContext`, `SuiteWindow`, shared navigation,
  page lifetime, window placement, app switching, and closing while work is busy.
- Apps are loaded lazily using `registry.py` and `Launch/apps.json`. Current IDs
  are `camera-import`, `yearbook`, and `slideshow`. Adding an app updates the
  launcher tiles, Launch menu, and Settings > Apps through this registry.
- A compatible view is a `QMainWindow` taking `directory=''` and keyword-only
  `suite=None`. After building its UI, call `bind_window(self, app_id, suite)`.
  Provide `appearance`, `_appearance_changed()`, and `_apply_theme()`.
  Standalone startup uses `run_app()` so it shares the same shell.
- Busy views expose `busy` and `cancel_work()`. The host cancels workers and
  waits until all pages, including hidden pages, are idle before closing.
  Slideshow's `dirty` / `_discard()` are also consulted before host close.
- Switching pages preserves their edits, selection, previews, logs, and workers.
  Reordering app tiles should reuse them and avoid unnecessary theme updates.
- `photo_tools/fluent.py` adapts Fluent constructors to existing call sites:
  combo `addItem(text, userData)`, table `(rows, columns)`, line-edit initial text,
  and the settings Save/Cancel button box. Do not replace these blindly with
  direct Fluent imports: their constructor/signature differences matter.
- `theme.py` applies Fluent theme/accent plus styling for suite surfaces. Avoid
  broad styles that override Fluent controls' own appearance.
- Fluent theme and accent are process-wide. Settings previews affect open
  controls, so rejecting the dialog restores the saved global display settings.
- `preferences.py` stores shared settings under Qt GenericConfigLocation /
  `PhotoToolsPrototype/settings.ini`. `PHOTO_TOOLS_SETTINGS` overrides that path
  for tests or portable setup. Independent processes poll for changes each second.
- Apps also use their own `QSettings` for remembered folders. Tests must isolate
  both these per-app settings and the shared settings from real user preferences.

## Photo workflows and data

### Camera Import

- `reorg.py` scans top-level images, proposes date folders, then applies a plan.
  JPEG originals go under `YYYYMMDD/origJPG`; NEF and other supported types go
  under `YYYYMMDD`. Capture-date metadata takes precedence; no filesystem-date
  fallback. RAW metadata uses ExifRead, with Pillow for supported image formats.
- Preserve collision handling, changed-source checks, linked-path protections,
  and cancellation between files. Import moves files: do not casually change
  these protections or tests to make a failure disappear.

### Slideshow

- Select an event directory containing `highlight`, or its `highlight` /
  `slideshow` subdirectory. The GUI lists JPG and JPEG highlights.
- Overrides live in `event/slideshow/data.txt`: CSV columns `Image,Date,Title`.
  Use CSV quoting for commas and UTF-8 for Unicode. Blank date/title cells fall
  back to the event directory name, e.g. `20260615 Holiday` gives date
  `2026 06 15` and title `Holiday`. Blank is a fallback, not an explicit hide flag.
- The editor previews the selected **original highlight image**, not a Photoshop
  rendering with live text overlays. Mouse and keyboard selection both update it;
  first load selects the first image. A splitter controls table/preview width.
- `PhotoPreview` uses `QImageReader` auto-transform for image orientation,
  bounds decoded previews to fit 1600 x 1200, and preserves aspect ratio when
  resizing. Missing/unreadable images show a message. Folder changes and empty
  events must clear stale previews and invalidate create/save readiness.
- GUI rendering always starts from a fresh highlight copy. Each slide is rendered
  in a temporary directory inside the event's slideshow directory, then replaces
  its destination only after success. Highlights remain unchanged; a failed
  render preserves the previous output slide. Re-rendering avoids stacked text.
- `RenderWorker` is a QThread that invokes `render_slide.py` in a separate process
  using the root `venv/Scripts/python.exe`. Photoshop work stays out of the GUI
  thread and uses that environment even when opened through the launcher.
- Photoshop must be installed for real rendering. Cancellation is between images,
  so it waits for the current Photoshop call/process; it does not kill Photoshop.
- `slideshow.py` loads `template.psd` beside itself, independent of working
  directory. Text fonts, sizes, colours, and positions come from PSD layers
  `Title` and `Date`; the image layer is named `Image`. Python changes text
  contents and replaces the image. Output canvas is 1920 x 1080.
- Original `param.py` / `run.cmd` processing remains available. It edits slideshow
  images in place: refresh from highlights before rerendering through that path.
  `param.py` accepts a date in a two-column row and reads UTF-8/BOM CSV.

### Yearbook

- The GUI gathers existing slideshow JPGs; it does not add titles, dates, or
  render Photoshop/PDF output. Those are already baked into the copied images.
- Scan folders named `slideshow` at levels 0..3. Output is `yearbook` under the
  chosen year directory. Prefix copied names with the first eight characters of
  the slideshow's parent directory plus `_`.
- GUI copies keep existing yearbook files, skip collisions, and recheck sources.
  Regenerating a slideshow does not update old yearbook copies: specific old
  copies must be replaced intentionally before recollecting.
- Original `yearbook.py` CLI retains its overwrite behaviour. Separate legacy
  `refresh.py` / `create_from_highlights.py` are not run by the Yearbook GUI.

## Commands and validation

From the MyUtils root (PowerShell):

```powershell
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe .\run_tests.py
.\venv\Scripts\python.exe -m pip check
.\launcher.bat
```

- `run_tests.py` uses its own interpreter for each suite, with each app directory
  as working directory and `Launch` plus that app on `PYTHONPATH`. It continues
  after failures and returns nonzero if any suite fails.
- Keep suites in separate processes: duplicate test module names (`test_gui`)
  and QApplication/shared Qt state make combined discovery unreliable.
- GUI tests use `QT_QPA_PLATFORM=offscreen` and temporary sample data. Photoshop
  rendering is simulated; passing tests do not establish a successful real
  Photoshop run. Never exercise file-operation tests on the user's photo library.
- Camera Import has a temporary Windows junction test. Access denied while
  creating that junction can be a test-environment permission problem; verify
  with suitable access rather than weakening source-path protection.
- QFluentWidgets prints a promotional message on import. Subprocess tests that
  emit JSON must account for that extra stdout (current scale test reads the
  final output line).
- Offscreen Qt may expose no installed fonts in a restricted environment.
  Register Windows Segoe UI with QFontDatabase in the visual-check harness when
  necessary; missing-glyph screenshots are not automatically a production bug.
- Latest full validation on 2026-11-16, after environment consolidation: all
  76 tests passed from root `venv`; dependency imports and `pip check` passed.
  Real Photoshop rendering has not been verified in this work.

- Root launcher move validated on 2026-11-16: batch smoke check passed
  from a different working folder and a path containing spaces; arguments and
  exit status are forwarded. `Launch/run_gui.bat` remains the shared launcher
  implementation. The old `Launch/launcher.bat` was moved, not duplicated.

## Known maintenance points

- Modern batch launchers and the render worker resolve the root environment
  relative to their files. Keep those paths portable when changing layout.
- Legacy `Slideshow/bootstrap.cmd`, `Slideshow/run.lnk`, and
  `Yearbook/create_from_highlights.py` still contain references to
  `P:\git\MyUtils`. If relocating the repository, inspect/update these too.
  Existing shortcuts copied into photo event directories may retain old targets.
- The settings app-list drag overlay deliberately uses a painted Qt row at its
  actual size, rather than a Windows drag cursor that scales incorrectly. Preserve
  Escape/outside-drop cancellation and the high-DPI drag tests when changing it.

## Decisions recorded on 2026-11-16

- Consolidated Slideshow into MyUtils; subsequent work stays in this repository.
- Added Slideshow to the launcher and adopted shared Fluent controls/settings.
- Kept editable CSV overrides and added an original-image preview beside the table.
- Centralised dependency setup at root to avoid divergent per-app environments;
  combined on Pillow 11.3.0 and removed redundant pypiwin32 from the old setup.
- Added a root test runner and commands.md; this file is the ongoing architecture,
  decision, and gotcha record and must be maintained with future changes.

- Moved launcher.bat to the repository root so the main entry point sits beside
  commands.md, requirements.txt, and the shared environment.
