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

## RadialMenu (2026-11-19)

- Registered as `radial-menu`; `RadialMenu/radial_gui.py` follows the shared page
  contract. The independent top-level RadialPopup is frameless and translucent.
- One RadialService per SuiteContext owns a Windows RegisterHotKey registration
  (default Ctrl+Alt+Space, MOD_NOREPEAT). A QAbstractNativeEventFilter receives thread WM_HOTKEY messages
  through Qt native dispatch (windows_dispatcher_MSG/windows_generic_MSG). No hook or extra dependency. Registration conflicts are
  reported inline. Listener remains armed after page switching and while other apps have focus;
  aboutToQuit unregisters. Multiple processes must choose distinct activation keys.
- `radial/count` (default 12, range 2–26) and `radial/key` use the existing shared
  settings file. Popup theme tracks shared appearance/accent. Default segments are a–l (up to z); per-application profiles override names, icons and sequences.
- Popup clamps to the cursor screen's available geometry, shrinking on tiny
  screens. Centre/outside clicks, right-click, Escape and focus loss dismiss it.
- Root test runner now includes a fifth, isolated RadialMenu suite.

- Validation 2026-11-19: all 115 tests passed (18 Launch, 27 Import, 19 Yearbook, 49 Slideshow, 2 RadialMenu). Native hotkey registration/WM_HOTKEY dispatch, Launcher loading, Escape dismissal and segment selection passed a separate offscreen smoke check. Junction tests require unrestricted filesystem access.

- Background follow-up: RadialService owns a system tray icon with settings,
  popup and Exit RadialMenu actions. With a tray available it disables automatic
  quit on last window close; the listener survives closing the Launcher. Run in
  background hides the host to the tray (minimises if no tray is available).
  Exit RadialMenu unregisters and restores normal quit behaviour, leaving visible
  suite windows alone. Tray settings recreates the host after it has been closed.
- Background validation: all 18 Launcher and 3 RadialMenu tests passed. Native registration/dispatch smoke check passed using the alternate shortcut when the default was occupied. Background test verifies host-close survival, tray restoration and stop without closing other visible suite windows.

- Fixed background activation: timer PeekMessage polling raced Qt's Windows
  event dispatcher, which consumed WM_HOTKEY first. Native filtering replaces
  polling; start/stop install/remove the filter alongside hotkey registration.
  Previous smoke checks called poll directly and did not validate Qt delivery.
  Regression checks must post WM_HOTKEY and let the normal event loop dispatch
  it while the host is hidden, rather than directly calling the handler.
- Hotkey fix validation: all 4 RadialMenu and 18 Launcher tests passed. The normal-event-loop reproduction failed before the fix and passed afterwards, both offscreen and on the Windows desktop with the host hidden. Regression covers unrelated messages, show/toggle while hidden, and ignoring messages after stop. This checks posted native hotkey delivery; it does not simulate physical key presses in another app.

- Letter actions: windows_input.py types HWND/pointer-sized APIs and SendInput
  structures for 32/64-bit Windows. Hotkey capture stores HWND/PID/thread before
  popup focus; own-process windows are excluded. Selection hides the popup,
  requests original focus once, then polls up to 5s for matching identity,
  foreground and released modifiers/mouse buttons. One VK letter down/up pair is
  sent; timeout/closed window/new activation/stop cancels. Preview clears targets.
  Windows integrity restrictions can reject SendInput; failure is reported.
  Segment count now caps at 26 to keep one alphabetic key per segment.
- Letter-action validation: all 119 tests passed (18 Launch, 27 Import, 19 Yearbook, 49 Slideshow, 6 RadialMenu). New checks cover focus/modifier gating, exactly-once delivery, preview, invalid target/timeout, input structure sizing and VK key down/up payload. Live external-app delivery remains unverified: the isolated receiver could not acquire Windows foreground focus in this automation session.

- Popup settings cog: a Fluent ToolButton sits inside the transparent window's
  top-right corner, outside the ring at normal size. Resize anchors it within the
  existing screen-clamped bounds. It hides the popup and opens/recreates the
  RadialMenu settings page. open_settings cancels target/pending letter delivery
  for both cog and tray entry points; the cog never selects a letter.
- Cog validation: all 6 RadialMenu tests passed; the background lifecycle test clicks the cog after closing the host, verifies settings recreation and confirms no pending target or key send. Light/dark popup renders were visually checked with Segoe UI: cog remains inside the top-right bounds and outside the ring.

## RadialMenu application button editor (2026-11-19)

- `button_profiles.py` stores JSON under `radial/profiles` in the existing suite
  settings file. Full normalised executable path is the application key; defaults
  remain letter buttons. Each of 26 slots stores name, icon, hover_icon, sequence.
  Reads refresh QSettings; malformed profiles/sequences report errors. Saves
  validate before replacing the application profile and report settings failures.
- `windows_input.application` queries the captured PID's executable with a typed
  QueryFullProcessImageNameW call. Live activation loads its profile before popup
  focus changes. The cog preselects that executable in configuration; other apps
  can be selected with an executable file chooser or the saved-profile selector.
- Configuration's **Edit Buttons** opens the embedded ButtonEditor page directly
  with the first button selected: application header, left radial
  selector, right name/normal-icon/hover-icon/sequence form. Embedded RadialPopup
  uses Widget flags and never hides on segment selection or focus loss. It retains
  selected-button highlighting and previews unsaved names/icons. Neither editor
  connects to runtime input injection. Drafts persist across segment switches;
  Save Buttons/Save and Back save all slots, Cancel discards pending drafts.
- Icons reference files rather than copying assets. Hover falls back to normal.
  Labels elide to segment width. Runtime reads saved profiles on each activation.
- Sequences contain up to 32 comma-separated keys/chords. Supported modifiers are
  Ctrl/Alt/Shift/Win; keys are ASCII alphanumeric, F1–F24, common navigation keys,
  Plus and Comma. Blank disables a button. Unsupported input is rejected before
  saving. SendInput builds key down/up pairs with balanced modifier releases and
  extended flags for navigation/Win keys, after the original focus/modifier guard.
  This is a key sequence, not a text or arbitrary-command interpreter.

- Editor/profile validation: all 123 tests passed after the initial per-app editor
  change; profile isolation/reload, switch retention, invalid-save preservation,
  icon fields and balanced modifier input payloads are covered. Embedded editor
  layout was rendered and inspected with Segoe UI.

## Offline icons and application discovery (2026-11-19)

- Bundled the official @tabler/icons 3.52.0 package's Design category in
  RadialMenu/assets/tabler: 359 icon names, 461 SVG variants. LICENSE is the
  upstream MIT license. SOURCE.md and manifest.json record source, version,
  archive SHA-256, names, styles and tags. Only Design SVGs were extracted;
  no npm installation or runtime network dependency was added.
- icon_library.py discovers assets/*/manifest.json and resolves portable
  `<set-id>:<style>/<name>.svg` references against the combined allowlist. Original SVGs remain unchanged; currentColor
  is replaced in memory for light/dark rendering. IconPicker provides keyword
  search and preview for both fields. External image paths remain supported.
  Use the native QListWidget delegate for icon-grid labels; the Fluent list
  delegate does not lay out those labels correctly in IconMode.
- WindowsInput.running_applications enumerates visible taskbar-style windows,
  excluding tool/owned utility/cloaked windows, then deduplicates by executable.
  ApplicationPicker refreshes on opening, merges running apps and saved profiles,
  retains selection when still present and marks closed profiles '(configured)'.
  Executable browsing remains available for apps not currently running.
- Window/taskbar HICONs use bounded SendMessageTimeout(WM_GETICON), falling back
  to class icons then QFileIconProvider. QImage.fromHICON copies borrowed handles;
  never destroy an icon belonging to another process. Real-desktop smoke check
  found 10 taskbar-style applications and successfully copied 10 window icons.
- application_icons.py stores copied 48px PNGs in settings.ini's sibling
  RadialMenu/app-icons directory, named by SHA-256 of the normalised executable.
  QSaveFile commits atomically. Configured closed apps use cached icons even if
  the executable is unavailable. Tests' temporary settings isolate the cache.
- Final offline/profile validation: all 125 tests passed (Launch 18, Import 27, Yearbook 19, Slideshow 49, RadialMenu 12). Checks render all 461 SVGs in light/dark, filter/select library icons, retain cached icons across settings reload, merge/deduplicate running and configured apps, preserve profile edits and validate runtime sequences. Offline picker and editor with assigned icons were visually inspected. Native enumeration copied 10/10 taskbar-window icons; live key injection into another application remains subject to the earlier documented foreground-test limitation.

- Editor navigation refinement: removed the intermediate editor-selection popup;
  Edit Buttons loads the selected app and switches straight to ButtonEditor.
  ApplicationPicker synchronises its button-face icon with the selected item's
  icon and clears it when refreshed to an empty list. Cached configured-app icons
  appear both in the opened list and in the closed selected-app control.
- Direct-editor refinement validation: all 12 RadialMenu tests passed. Existing interaction tests now click Edit Buttons and assert immediate editor navigation with no intermediate popup; the cache test verifies the selected control icon matches its configured-app entry. The closed selector was rendered and visually checked for icon/text spacing, and clearing the selector clears its icon.

## Extensible offline icon sets (2026-11-19)

- Added official @phosphor-icons/core 2.1.1: 1,512 names, 9,072 SVGs across regular,
  thin, light, bold, fill and duotone. assets/phosphor retains upstream LICENSE,
  unmodified SVG contents, SOURCE.md, version/source/archive-SHA-256 manifest.
  Tabler's existing 461 SVGs and saved references remain unchanged.
- Permanent IDs use `<set-id>:<style>/<name>.svg`; display names include library,
  style and name, so same-name icons from different sets are always retained.
  Version is metadata, not part of identity. Manifest discovery supports future
  sets without runtime code changes. Style suffixes in Phosphor filenames are
  normalised when importing (palette-bold.svg -> bold/palette.svg).
- import_icon_set.py is a maintenance-only, offline importer for pinned package
  archives. It validates XML/path/ID collisions before writes, replaces SVGs
  atomically and publishes the manifest last. Missing upstream IDs are retained
  with retired=true and their previous files, preserving old assignments. The
  picker hides retired entries; resolver still supports them. Never pre-delete
  an existing library folder. Restart after updates because indexes are cached.
- IconPicker adds set/style filters with search over all 9,533 active variants.
  Native IconDelegate renders visible thumbnails only. Catalog path validation
  is lexical (absolute/traversal/noncanonical paths rejected), avoiding thousands
  of filesystem resolves on opening. Cold picker construction measured 0.20s
  after this change; the filtered palette view rendered only 13 thumbnails.
- New tests verify overlapping names/unique IDs, all SVGs in both themes,
  filters, selection, legacy Tabler refs, future namespace import and retaining
  removed IDs through a simulated update. Manifest data and updater tests use
  temporary directories. Picker layout with both sets was visually inspected.
- Phosphor validation: all 127 tests passed (Launch 18, Import 27, Yearbook 19, Slideshow 49, RadialMenu 14). Every one of the 9,533 SVG variants rendered successfully in light and dark; collision preservation, set/style filtering, legacy references and update retention passed. The combined palette view was visually checked, and cold picker construction measured 0.20 seconds with lazy thumbnails.
