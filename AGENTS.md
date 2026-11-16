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
  launcher, test suite, and native renderer. Do not add per-app environments or
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
| `requirements.txt` | Combined GUI, import and image dependencies |
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
| `Slideshow/slideshow_jobs.py` | Event JSON/CSV settings, fresh-image preparation, native rendering |
| `Slideshow/slideshow_gui.py` | Date/title editor, rendered slide preview, background render worker |
| `Slideshow/template_render.py` | Shared Qt renderer for live preview and JPEG output |
| `Slideshow/template_editor.py` | Visual template canvas, drag/resize, fonts and controls |
| `Slideshow/default_template.json` | Shipped layout measured from the PSD |
| `Slideshow/render_slide.py` | Legacy single-image native render command |
| `Slideshow/slideshow.py` | Compatibility create_slide API for native rendering |
| `Slideshow/template.psd` | Original layout reference, not a runtime dependency |

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

- Photoshop is no longer a dependency. `template_render.py` uses Qt QImage,
  QPainter and text paths for both live previews and JPEG output. Fonts are
  registered from TTF/OTF files in Slideshow; do this on the GUI thread before
  starting a render worker. `ensure_fonts()` retains a QApplication for CLI use.
- Output is 1920 x 1080 at 300 dpi with the photo centred and contained without
  distortion on a black background. Image readers apply EXIF orientation. JPEG
  density is set explicitly; point size becomes pixels via pt * 300 / 72.
- Shipped default_template.json was extracted from the PSD: title Filmotype
  LaSalle 28.8 pt, right baseline anchor (1825.5,128.10); date 7-Segment 11.2 pt,
  left baseline anchor (36.48,1017.30). Text is black with white glow, sizes 16/7
  pixels respectively. Font contours match the PSD within roughly two pixels
  on its sample text; Qt anti-aliasing and the soft-stroke glow are approximations.
- FilmotypeLaSalle.otf was copied from the user's installed Adobe font cache;
  7segment.ttf from the user's Windows fonts. Font identity was verified from
  metadata. See FONT-SOURCES.md for provenance/licences. Filmotype is commercial;
  the local project copy is not a grant of redistribution rights.
- `TemplateEditor` works on a deep copy: Apply returns changes to the view;
  Cancel leaves its template unchanged. Choose Title/Date, drag to move, drag
  the blue corner to resize, or edit font/size/position/alignment/visibility/
  colours/glow controls. Font imports copy files into Slideshow with collision
  handling. Preview and export share the same renderer.
- Main view previews the rendered slide including current date/title overrides,
  not just the source image. It follows mouse/keyboard selection; edits update
  the preview. A splitter controls preview width. Missing images and changed or
  empty folders must clear stale previews and invalidate create/save readiness.
- Save slideshow and Create slideshow persist `event/highlight/slideshow.json`
  with version, template and image overrides. JSON is authoritative once present.
  Missing JSON imports legacy slideshow/data.txt; save exports the CSV as well.
  Corrupt/unsupported JSON is reported, never silently discarded or reset.
- Blank date/title values use the event folder's defaults; blank is not a hide
  flag. Use each template layer's enabled setting to hide it. Settings are
  event-specific and reload on opening that event. Font files live in the app.
- Rendering starts from fresh highlight copies inside temporary output folders,
  replaces each destination after success and leaves highlight images untouched.
  Failures preserve prior slides; cancellation is between images. RenderWorker
  runs this in a QThread with a snapshot of the template, without a subprocess.
- Legacy param.py/run.cmd and create_slide remain native and load event settings
  where applicable. The old CSV CLI still edits existing slideshow images in
  place, so refresh them from highlights before rerendering. template.psd is
  retained solely as a design reference. No psd-tools or fontTools is needed at
  runtime (they were used only to inspect the PSD/fonts during migration).

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
- GUI tests use `QT_QPA_PLATFORM=offscreen` and temporary sample data.
  Slideshow tests now exercise actual native rendering, output dimensions/DPI,
  event settings and visual template interactions without Photoshop. Never
  exercise file-operation tests on the user's photo library.
- Camera Import has a temporary Windows junction test. Access denied while
  creating that junction can be a test-environment permission problem; verify
  with suitable access rather than weakening source-path protection.
- QFluentWidgets prints a promotional message on import. Subprocess tests that
  emit JSON must account for that extra stdout (current scale test reads the
  final output line).
- Offscreen Qt may expose no installed fonts in a restricted environment.
  Register Windows Segoe UI with QFontDatabase in the visual-check harness when
  necessary; missing-glyph screenshots are not automatically a production bug.
- Latest full validation on 2026-11-16, after the native-renderer migration:
  all 88 tests passed (Launch 18, Import 27, Yearbook 19, Slideshow 24).
  This includes actual native JPEG rendering at 1920 x 1080 / 300 dpi and source
  preservation, JSON round trips, font loading, drag/resize and numeric editing.
  Photoshop Python packages were uninstalled before the full run; pip check
  passed. Light/dark editor layouts were visually inspected. The original PSD's
  font geometry was inspected, but Photoshop itself was not used for rendering.

- Root launcher move validated on 2026-11-16: batch smoke check passed
  from a different working folder and a path containing spaces; arguments and
  exit status are forwarded. `Launch/run_gui.bat` remains the shared launcher
  implementation. The old `Launch/launcher.bat` was moved, not duplicated.

## Known maintenance points

- Modern batch launchers resolve the root environment
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
- Kept editable overrides; the original-image preview was subsequently upgraded
  to a live rendered slide preview during the native-renderer migration.
- Centralised dependency setup at root to avoid divergent per-app environments;
  combined on Pillow 11.3.0 and removed redundant pypiwin32 from the old setup.
- Added a root test runner and commands.md; this file is the ongoing architecture,
  decision, and gotcha record and must be maintained with future changes.

- Moved launcher.bat to the repository root so the main entry point sits beside
  commands.md, requirements.txt, and the shared environment.

- Replaced Photoshop automation with a native Qt renderer and visual template
  editor. Project settings now live in highlight/slideshow.json; legacy CSV is
  imported only before JSON exists and is still exported on save.
- Qt 6.12 can collapse Fluent DoubleSpinBox's embedded line edit to one pixel.
  The shared fluent.py adapter repairs its geometry when collapsed. Preserve
  the numeric visibility/editing test; model values alone do not catch this.
