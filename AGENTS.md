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
| `Slideshow/default_template.json` | Shipped system layout; never overwrite on user-default save |
| `Slideshow/template.json` | Optional user default, created by Save user default |
| `Slideshow/render_slide.py` | Legacy single-image native render command |
| `Slideshow/slideshow.py` | Compatibility create_slide API for native rendering |

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

- `template_render.py` uses Qt QImage, QPainter and text paths for both previews
  and JPEG output. Register fonts on the GUI thread before starting workers;
  ensure_fonts() retains a QApplication for CLI use. There is no external editor
  integration. Keep external product names out of the interface and docs.
- Output is 1920 x 1080 at 300 dpi. Photo is centred and contained on black,
  without distortion; image readers apply EXIF orientation. JPEG density is set
  explicitly. Point size becomes pixels via pt * 300 / 72.
- Default title uses Windows Segoe Script, 28.8 pt, right baseline anchor
  (1825.5,128.10). Date uses bundled 7-Segment, 11.2 pt, left baseline anchor
  (36.48,1017.30). Text is black with white soft-stroke glow, sizes 16/7 pixels.
- Do not bundle Filmotype LaSalle: the project copy was removed for licensing.
  Do not extract commercial fonts from other applications' caches. Segoe Script
  and Segoe UI are used from Windows without copying them into the project.
  7segment.ttf is included under SIL OFL; see FONT-SOURCES.md and 7segment-OFL.txt.
  Add only font files with appropriate distribution rights. Installed fonts can
  be selected without copying them; absent fonts are reported before export.
- TemplateEditor is a QWidget page in SlideshowWindow's content_stack, not a
  dialog or separate window. Replace the normal main_page until Apply/Cancel;
  retain table edits, selection and app-switch state. Work on a deep copy;
  Apply atomically saves highlight/template.json before copying it back and
  returning. Do not save pending CSV edits on Apply. A failed save leaves the
  editor open, its edits pending and the previous file/model intact. Cancel
  discards only editor changes. A successful Apply does not mark a saved template
  dirty; preserve any existing unsaved data edits. The parent dirty property combines
  main-view edits and editor.is_dirty(); mark_clean prevents duplicate host-close
  prompts after discard is accepted. Stop pending canvas timers on editor removal.
- Drag text or its blue corner, or edit the font/size/position/alignment/
  visibility/colours/glow. The reset button remains **Reset to default** and loads
  the system layout. Preview/export share the same renderer.
- Reusable user default is Slideshow/template.json; shipped system default is
  Slideshow/default_template.json. Save user default atomically writes ONLY the
  user file, immediately and independently of cancelling event edits. Load user
  default / Load system default replace only the editor copy. Missing/corrupt
  user defaults show an inline error without discarding current edits. New events
  prefer the user default; saved event and migrated legacy layouts take precedence.
- FontPicker is a native Qt combo with Fluent-compatible colours. Reuse the
  native view's keyboardSearch for prefix search, repeated-letter cycling and
  timeout; allow spaces during active typing. Native popup highlighted changes
  must update the current index and render before Enter. Closed combo arrow keys
  also update the preview. Test both open and closed dropdowns. Escape should
  close the font popup before leaving the embedded editor.
- Main view previews the rendered slide and follows mouse/keyboard selection.
  Date/title edits update it. Missing images and changed/empty event folders
  must clear stale previews and invalidate create/save readiness.
- Date/title overrides MUST remain backwards-compatible CSV: header
  `Image,Date,Title`, UTF-8, normal CSV quoting, two-column rows accepted.
  Save to `event/highlight/data.txt` and mirror to `event/slideshow/data.txt`.
  Highlight CSV is authoritative; the old slideshow CSV is read when it is absent.
  Never store per-photo overrides in new JSON files or let JSON mask CSV edits.
- Store ONLY layout/styling in `event/highlight/template.json` using the existing
  versioned template schema. Save data and Create slideshow write CSV and
  template separately using atomic file replacement. CSV/JSON are not a single
  filesystem transaction; propagate errors instead of claiming a failed save worked.
- Migration: when CSVs are both absent, read overrides from the previous combined
  highlight/slideshow.json. When template.json is absent, its old template may
  be read too. Never write that combined format again. Leave the old file as an
  untouched backup; new template/CSV files take precedence. Invalid active
  templates report errors rather than silently discarding user settings.
- Blank CSV date/title cells use event-folder defaults; blank is not a hide flag.
  Layer visibility controls hide text. Settings are event-specific. Opening an
  old layout with an unavailable font requires selecting an installed font.
- RenderWorker is the QThread coordinator with a validated template snapshot.
  It runs a bounded ThreadPoolExecutor with min(photo count, logical CPU count)
  workers; max_workers is an optional backend/test override. Jobs only decode,
  composite and JPEG-save unique temporary photo copies. The coordinator alone
  publishes results, writes the run template snapshot and emits progress. Photos
  finish out of order; do not write tests that assume alphabetical completion.
- Render title/date/glow once per distinct resolved pair into an ARGB transparent
  overlay, entirely on the coordinator. No pool worker may use fonts, text_path,
  ensure_fonts or widgets. render_prepared_file/compose_image are font-free.
  Preview and normal render_file use the same overlay/composition implementation.
- Keep up to min(worker count,8) overlay QImages in memory and retain PNGs in the
  run staging directory. Reload evicted overlays from PNG without rerendering
  text. Workers share overlays read-only and paint only their independent output
  QImages. Qt's thread-painting guidance is documented at
  https://doc.qt.io/qt-6.10/threads-modules.html (Painting in Threads).
- Submit no more than one job per worker. Cancel stops new scheduling/publication;
  in-flight jobs finish only in staging and their results are discarded. On error,
  stop publishing, cancel pending work and wait before temporary cleanup. Existing
  published slides remain. Duplicate case-insensitive destinations are rejected.
  The coordinator must save template.json successfully before publishing the
  first result. A render failure or metadata-write error must not replace that
  image or source. Progress callbacks run on the coordinator, not pool threads.
- Legacy param.py/run.cmd/create_slide remain native. The CSV CLI still edits
  existing slideshow images in place, so refresh them from highlights first.

### Yearbook

- The GUI gathers existing slideshow JPGs; it does not add titles, dates, or
  generate new slides or PDF output. Those are already baked into the copied images.
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
  event settings and visual template interactions. Never
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
- Latest full validation on 2026-11-16: all 113 tests passed (Launch 18,
  Import 27, Yearbook 19, Slideshow 49) after parallel rendering and transparent
  overlay reuse. Checks prove concurrent workers, CPU-count sizing, coordinator-only
  font rendering, PNG cache reuse after memory eviction, transparent backgrounds,
  cancellation without publishing in-flight results, duplicate-name rejection,
  and byte-identical single-worker/parallel JPEGs. Existing defaults, CSV/template
  persistence, source protection, embedded editing and snapshot tests also pass.
  Diff formatting passed. Performance measurements are recorded below.

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

- Adopted native rendering and a visual template editor. Superseding storage
  decision: date/title overrides stay in CSV, with separate highlight/template.json.
  Do not return to combined project JSON. The commercial title font is excluded.
- Qt 6.12 can collapse Fluent DoubleSpinBox's embedded line edit to one pixel.
  The shared fluent.py adapter repairs its geometry when collapsed. Preserve
  the numeric visibility/editing test; model values alone do not catch this.

- Added separate user/system defaults and embedded the template editor in the main
  content stack. Font navigation now supports native prefix typing and live
  arrow-key preview. Tests isolate USER_DEFAULT_PATH so saved user layouts cannot
  leak into test runs and tests never overwrite the real project-level default.

- Save action labels are **Save user default** (project-level template) and
  **Save data** (main view). Apply template persists the event template immediately,
  independently of unsaved date/title data. Keep inline failure handling and the
  atomic-save/source/CSV-preservation checks when changing these actions.

- Create slideshow also writes event/slideshow/template.json from the run's
  validated template snapshot, not by copying a potentially changed event file.
  Save it atomically after the first successful render and before publishing that
  image; update it once per run. Partial/cancelled runs retain the snapshot.
  A first-image render failure leaves existing output metadata untouched; a
  template-write failure must not replace the existing image or source. This
  output copy is a record, not a replacement for highlight/template.json.

- Output-template copy validated on 2026-11-16: all 42 Slideshow tests passed,
  including snapshot refresh, partial cancellation and template-write failure.
  This was the output-template baseline before the parallel-rendering change.

- Parallel/overlay performance check on 2026-11-16 used 32 temporary 2400 x 1600
  samples and an explicit system template, avoiding real user defaults. Single
  worker: 3.63 s; automatic mode: 0.77 s. All 32 worker threads were used (21 peak
  simultaneously active native jobs); sequential/parallel JPEG hashes matched.
  Fonts are verified to render only on the coordinator; cache-eviction tests
  verify text is not rerendered. Preserve cancellation and source/image safeguards.

- Branching gotcha: after a squash merge, start the next feature from the latest
  origin/main rather than continuing the old PR branch. Otherwise rebase can try
  to replay already-merged commits and produce misleading add/add conflicts.
  For this repair, main's tree exactly matched the old feature parent (84bb091),
  so only the new parallel-rendering commit was replayed onto origin/main.
  Feature file content was verified unchanged; all 113 tests passed after rebase.
  The interrupted index/rebase/files were backed up under .git and the original
  tip retained in refs/backup/slideshow-before-main-rebase-20261116.
