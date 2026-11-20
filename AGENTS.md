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
| `run_tests.py` | Runs all five suites in separate processes |
| `RadialMenu.cmd` | Root RadialMenu command; delegates to `RadialMenu/run_gui.bat` |
| `Launch.cmd` | Root launch command; delegates to `Launch/run_gui.bat` |
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
| `RadialMenu/radial_gui.py` | Configuration page, button editor, radial popup, tray service |
| `RadialMenu/activation_monitor.py` | Temporary physical activation capture for Hold/Repeat |
| `RadialMenu/windows_input.py` | Windows hotkeys' target capture, app discovery/icons, key injection |
| `RadialMenu/button_profiles.py` | Per-executable button profiles, migration, sequence validation |
| `RadialMenu/icon_library.py` | Manifest discovery, offline icon picker and lazy SVG rendering |
| `RadialMenu/application_icons.py` | Persistent application-icon cache beside shared settings |
| `RadialMenu/import_icon_set.py` | Maintenance importer/updater for offline SVG libraries |
| `RadialMenu/assets/` | Tabler, Phosphor, Lucide, Remix SVGs, manifests and licenses |
| `RadialMenu/about_page.py` | Offline icon attributions and full license notices |

## Shared GUI architecture

- `photo_tools/shell.py` owns `SuiteContext`, `SuiteWindow`, shared navigation,
  page lifetime, window placement, app switching, and closing while work is busy.
- Apps are loaded lazily using `registry.py` and `Launch/apps.json`. Current IDs
  are `camera-import`, `yearbook`, `slideshow`, and `radial-menu`. Adding an app updates the
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
.\Launch.cmd
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
- Pre-RadialMenu baseline validation on 2026-11-16: all 113 tests passed (Launch 18,
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

- Moved launcher.bat (now Launch.cmd) to the repository root so the main entry point sits beside
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

## RadialMenu (current behaviour, 2026-11-19)

### Launcher, background lifetime and activation

- Registered as `radial-menu` in Launch/apps.json. RadialMenuWindow follows the
  shared QMainWindow/bind_window contract; standalone uses the shared run_app
  shell and root environment. No extra environment or runtime dependency.
- One RadialService per SuiteContext owns the independent top-level RadialPopup,
  native hotkey filter, delivery timer and system-tray icon. Shared theme/accent
  changes update the popup. Default activation is Ctrl+Alt+Space; Edit Hotkey accepts a single supported
  key with optional Ctrl/Alt/Shift/Win modifiers (Escape is reserved for cancellation). RegisterHotKey uses MOD_NOREPEAT. Registration conflicts
  appear inline; separate processes must use distinct activation keys.
- HotkeyFilter uses QAbstractNativeEventFilter for windows_dispatcher_MSG and
  windows_generic_MSG. Start/stop install/remove it with the registration;
  aboutToQuit releases the registration. Do not restore timer-based PeekMessage
  polling: Qt consumed WM_HOTKEY before that timer, breaking background activation.
  Tests must post native messages and let Qt dispatch them, rather than directly
  calling the handler. Earlier direct polling smoke checks missed this bug.
- Run in background hides the host to the system tray. With a tray available,
  automatic quit on last window close is disabled and the listener survives host
  closure. Tray double-click/settings recreates or restores the host. Exit
  RadialMenu stops listening and restores normal quit behaviour, leaving visible
  suite windows open. Without a tray, background mode minimises; closing the last
  host exits. Restart resident code via tray Exit RadialMenu, then relaunch.

### Popup and input delivery

- Frameless, translucent, always-on-top popup shows only the radial segments and
  the top-right settings cog. Default segment count is 12 (a–l), configurable
  globally from 2 to 26. Position clamps to the cursor screen's available geometry,
  including negative monitor coordinates; diameter shrinks on tiny screens.
- Left-click selects a segment. Escape, right-click, centre/outside click or focus
  loss dismisses it. The cog hides the popup and opens RadialMenu configuration,
  preselecting the captured executable. Opening settings cancels pending input.
- Hotkey activation captures HWND/PID/thread before showing the popup, excludes
  this process's own windows and resolves the executable via a typed
  QueryFullProcessImageNameW call. It loads that executable's saved button profile;
  unconfigured applications use letter defaults. Invalid active profiles report
  an error instead of silently discarding their configuration.
- Selecting a Normal button hides the popup, requests original-window focus once and
  polls every 20ms for up to five seconds. Send only when the same HWND/PID/thread
  remains valid and foreground, with Ctrl/Alt/Shift/Windows and mouse buttons
  released. Closed/changed target, timeout, new activation or stop cancels input.
  A blank sequence disables the action. Tray preview and editing never send input.
- windows_input.py uses pointer-sized Windows API types and correctly sized
  INPUT unions. SendInput sends a single batch of key down/up pairs, balancing
  modifiers per chord and setting extended flags for navigation/Win keys. The
  focus/modifier guard is checked again immediately before sending. There is one
  delivery attempt; failure is reported. Keyboard state/layout and target-app
  shortcut handling apply. Windows integrity restrictions may reject injection
  into applications with higher privileges.
- Sequences support up to 32 comma-separated keys/chords, e.g. Ctrl+A, Ctrl+C.
  Modifiers: Ctrl, Alt, Shift, Win. Keys: ASCII letters/digits, F1–F24, Enter,
  Return, Tab, Space, Escape/Esc, Backspace, Delete, Insert, Home, End, PageUp,
  PageDown, arrows, Plus and Comma. Unsupported syntax is rejected before saving.
  This is key injection, not arbitrary command execution or text expansion.

### Configuration, editor and profile storage

- Application dropdown combines running taskbar-style apps with configured
  executables, deduplicated by normalised full executable path. It refreshes on
  opening, preserves selection if still listed and marks closed saved profiles
  '(configured)'. The selected-app control also shows its icon. File browsing
  supports configuring another executable that is not running.
- WindowsInput.running_applications excludes tool, owned utility and cloaked
  windows. Icon extraction uses bounded WM_GETICON/SendMessageTimeout, then class
  icons, then QFileIconProvider. QImage.fromHICON copies borrowed handles; never
  destroy another application's icon handle.
- ApplicationIcons caches 48px PNGs under the shared settings file's sibling
  RadialMenu/app-icons directory, with SHA-256 filenames from normalised executable
  paths and atomic QSaveFile commits. Closed configured apps retain their cached
  icons across restarts, even if their executable becomes unavailable. Temporary
  settings paths isolate the cache in tests.
- Edit Buttons opens ButtonEditor directly with button 1 selected; there is no
  intermediate radial popup. Application name/path appears at the top, embedded
  radial selector on the left and button fields on the right. Clicking another
  segment switches fields and retains drafts. Embedded RadialPopup uses Widget
  flags, stays visible on segment selection/focus loss, and highlights selection.
- Fields are Name, Icon 1, Icon 2, Behaviour and Button sequence. Both icons display together
  above the name, before and during hover; either can be empty. Both slots share
  all four icon libraries, with Icons… for the offline picker and File… for images.
  Labels elide to segment width. Draft names/icons update the editor ring live.
- Save Buttons persists all drafts for the selected executable. Save and Back
  saves then returns to configuration; Cancel returns without saving. Drafts are
  held in the page and should be saved explicitly before closing the host. Runtime
  activation reloads the saved profile, not unsaved editor drafts.
- Shared QSettings keys: radial/key, radial/count and radial/profiles. Profiles
  are JSON keyed by case-normalised full executable path, then zero-based slot
  strings. Each of 26 slots stores name, icon, secondary_icon, sequence and behaviour.
  Missing behaviour migrates to normal; unknown values fail validation. Hold
  permits one chord only (or blank to disable), while Repeat permits sequences.
  Existing hover_icon is migrated into secondary_icon on read and canonicalised
  on Save. Preserve this migration: the second icon is simultaneous, not a hover
  alternative. Validate sequences before replacing a profile; report save errors.

### Offline libraries, stable identities and updates

- Bundled assets: Tabler Icons 3.52.0 Design (461 SVG variants), Phosphor 2.1.1
  (9,072 variants), lucide-static 1.76.0 (2,404 outline SVGs, including upstream
  aliases), and Remix Icon 4.9.1 (3,229 line/fill/regular SVGs). Total: 15,166.
  All retain original SVG contents, source/version/archive SHA-256 and exact
  bundled license texts. No runtime network calls or new package dependency.
- Licenses: Tabler/Phosphor MIT; Lucide ISC plus MIT for Feather-derived icons
  (including the original list and Cole Bemis notice); Remix Icon License v1.0,
  not Apache 2.0. Preserve Remix's full terms and notices when distributing this
  functional app; its icons remain separately licensed from other assets.
- AboutPage (about_page.py), reached by About & Licenses in configuration, lists
  all libraries with versions, attribution, links to their sites/releases and
  every bundled license/copyright notice verbatim. A contents list jumps between
  sets. IconPicker also opens this information in a dialog. Notices are readable
  offline; external links open only when clicked. Manifest metadata supplies
  website/license_label/attribution; future manifests have generic fallbacks.
- icon_library.py discovers assets/*/manifest.json. Permanent IDs use
  <set-id>:<style>/<name>.svg, e.g. tabler:outline/palette.svg and
  phosphor:regular/palette.svg. Display labels include library/style/name.
  Same-name icons are kept in both sets; version is manifest metadata, never part
  of assignment identity. Existing Tabler references remain valid.
- Manifests contain id/label/version/source/checksum and icons with name/style/
  path/tags. Set IDs are permanent lowercase namespaces. New conforming manifests
  add libraries without picker code changes. File paths are allowlisted; absolute,
  traversal and noncanonical manifest paths are rejected lexically.
- Picker offers set/style filters and keyword search across all 15,166 active SVG
  variants. A native QStyledItemDelegate lazily renders visible thumbnails with
  bounded icon caching. Replace currentColor in memory for light/dark contrast.
  Do not use the Fluent list delegate for this IconMode grid: its labels were
  missing. Avoid per-entry filesystem resolves: cold opening measured 0.20s after
  replacing them with lexical validation; the palette filter drew 13 thumbnails.
- import_icon_set.py is a maintenance-only offline importer for pinned archives.
  It supports styles (Phosphor), flat (Lucide) and remix (category folders with
  -line/-fill suffixes; unsuffixed icons use regular) layouts, --prefix and
  --license-name overrides. It validates
  XML and IDs before writes, normalises style suffixes, atomically replaces SVGs
  and publishes the manifest last. Other archive layouts must map to the same
  manifest contract. Setup/reimport commands are in commands.md and the README.
- Updating under the same set ID retains missing upstream entries/files as
  retired=true so existing assignments still resolve; the picker hides retired
  entries. Never pre-delete a library folder before updating. Restart the resident
  app after library updates because catalog indexes are cached. Review upstream
  licenses on every update; update curated attribution metadata if terms change.
  The importer preserves website/license_label/attribution across updates.

### Validation and known limits

- Latest full run on 2026-11-19: all 132 tests passed (Launch 18, Import 27,
  Yearbook 19, Slideshow 49, RadialMenu 19). This includes all four libraries,
  simultaneous icons and About & Licenses. All 15,166 SVG variants rendered in
  light/dark; collision retention, filters, legacy references, importer layouts,
  future namespace import and retired-ID preservation passed. License tests
  compare exact upstream notices and verify About navigation. Migration and
  pixel checks prove both assigned icons stay visible before/during hover.
- Other regression coverage includes native message dispatch while hidden,
  tray persistence/host recreation, target/modifier gating, one delivery attempt,
  preview cancellation, invalid-target/timeout handling, input structure layout,
  balanced shortcut payloads, profile isolation/reload, invalid-save preservation,
  button-switch draft retention, cached app icons and direct editor navigation.
- Visual checks covered light/dark popup and cog, editor layout, selected-app
  icon/text spacing, combined library picker and two simultaneous icons. A native
  desktop smoke check enumerated 10 taskbar-style apps and copied 10 window icons.
- Real end-to-end key delivery into another application remains unverified:
  Windows prevented the isolated receiver from acquiring foreground focus in the
  automation session. Native message delivery and input payloads were tested;
  those results do not prove physical-hotkey-to-external-app delivery.
- About/license-page layout was rendered and inspected with Segoe UI; full
  notices wrap without horizontal overflow. New tests compare every exact LICENSE
  with the generated page, cover navigation and both new archive layouts.

## Changes on 2026-11-20

- Renamed the root launcher to Launch.cmd to match Launch/; RadialMenu.cmd
  delegates to RadialMenu/run_gui.bat. Both forward arguments and exit codes.
- ButtonEditor offers Ctrl/Alt/Shift/Win checkboxes, typed keys and a special-key
  dropdown including F1–F24 and all supported named keys. Use key replaces the
  sequence; Append key adds a comma-separated chord. Both validate before editing.
  The editable sequence and profile schema remain compatible. Selecting a button
  resets the builder and reflects its existing single chord.
- Validation: all 19 RadialMenu and 18 Launch tests passed on 2026-11-20.
  Editor coverage exercises all special-key options, combined modifiers,
  append/replace, profile persistence and empty-key protection. Isolated batch
  stubs verified both root wrappers from a different working directory and paths
  containing spaces, including argument and exit-code forwarding. Rendered editor
  layout inspected at the default host size; no clipping. External-app input
  delivery was not retested; the existing limitation above still applies.
- Standardised both root entry points on .cmd (Launch.cmd and RadialMenu.cmd).
  These wrappers run under cmd.exe; neither needs legacy DOS .bat compatibility.
  Repeated isolated wrapper checks passed after the extension change.
- Letter key tokens now normalise to uppercase in both editor key fields,
  profile loading/saving and default sequences. Button names retain their case.
  normalise_sequence preserves incomplete edits and spacing; validation remains
  authoritative at save. Uppercase never adds an implicit Shift modifier.
- Uppercase normalization validation: 7 profile/editor tests and 6 radial/input
  tests passed. Coverage verifies old-profile loading, canonical persisted text,
  immediate editor conversion and unchanged virtual keys/modifier payloads.
- SingleKeyEdit now overtypes each typed key and keeps only the last inserted
  character on paste, independent of cursor position. Backspace/Delete clear the
  whole key. Named keys from the dropdown or profile loading remain intact;
  sequence text still supports multiple chords. Space/plus/comma map to names.
- TDD: added an interaction regression first and observed failure (typing abc
  produced Abc rather than C), then implemented SingleKeyEdit. All 8 profile/editor
  tests pass, covering overtyping, cursor position, uppercase, paste, clearing,
  special-key selection and preservation of the multi-chord sequence editor.

## Button behaviours (2026-11-20)

- Per-button Behaviour dropdown: normal (.), hold (-), repeat (...). RadialPopup
  draws a marker near each segment's outer edge without replacing its name/icons.
- Normal retains one-shot guarded delivery. Hold/Repeat selection hides the menu
  and restores the captured HWND/PID/thread, with a five-second initial focus
  timeout. Release the menu-opening main key, then tap to start and tap again
  to stop; Ctrl/Alt may remain held across selection. Hold injects one chord's downs once. Repeat sends balanced sequences
  immediately and at most every 100ms. Release does not stop either mode. Both modes leave the menu hidden on
  the stopping press; the next press opens it, per the user's updated instructions.
- activation_monitor.py installs WH_KEYBOARD_LL only for the armed action, tracks
  physical/remapped key downs/ups (including left/right modifiers), and ignores
  only our own tagged injected events. The initial opening press releases normally; the subsequent activation
  components are swallowed so hotkey Ctrl/Alt do not contaminate output. Escape
  cancels. RegisterHotKey is suspended during capture and restored on completion
  to prevent configured output from generating recursive WM_HOTKEY messages.
- WindowsInput gesture methods check original-target focus, physical trigger and
  unrelated modifiers/mouse buttons immediately before injection (active Hold
  permits mouse use so modifier-only holds support modified dragging). Cancel on focus
  loss, invalid target, Escape, settings/preview, stop or delivery failure. Track
  actually inserted downs after partial SendInput, release in reverse order even
  after focus loss, and retry a failed cleanup batch once. Retain failed cleanup
  state for another attempt on stop/next cancellation. Hook and registration
  failures report errors. No new dependency; Normal needs no keyboard hook.
- Added profile/editor and runtime tests before implementation and observed their
  failures. New coverage exercises migration, persisted behaviours, Hold chord
  validation, initial-release/fresh-press arming, hold/repeat/release, cancellation,
  repeat timing, registration restoration, hook failure, real native hook install
  and removal, exact injected payloads and partial-send cleanup. End-to-end
  physical keyboard delivery to an external application remains unverified.
- Validation: the full 31-test RadialMenu run passed; after adding three extra
  lifecycle/marker/cleanup tests and strengthening cleanup, all 27 runtime,
  profile/editor and radial tests passed again (34 total with the 7 unchanged
  offline tests from the full run). All 18 Launch tests passed. Light/dark editor
  renders inspected at default host size: mode markers and dropdown are visible,
  both icon slots remain intact and Save actions fit. Diff formatting passed.

## Modifier-only actions and compact editor (2026-11-20)

- Modifiers only in the button builder sends one or more checked modifiers with
  no ordinary key. Sequence syntax accepts Ctrl, Ctrl+Alt, Shift+Win etc. Parser
  represents these as (modifiers, None); all three injection paths omit the absent
  key and balance actual modifier downs/ups. Duplicate modifiers and empty chords
  remain invalid. Hold permits mouse use once active, retaining target/modifier
  guards and release/cancel cleanup, so held modifiers can be used when dragging.
- Edit Buttons — executable is the actual window title, restored to RadialMenu
  on leaving the editor. No large heading occupies the content area. The app name
  remains above the left selector with the full path in its tooltip; the form
  starts at the top right. The selector scales from 240 to 360px. A native Qt scroll
  area hosts the form; status and Save/Back/Cancel stay outside it and visible.
  Scroll surfaces are transparent to preserve light/dark theme contrast.
- CurrentPageStack in shell.py computes size hints from the active page only;
  hidden launcher/app pages no longer force the RadialMenu editor beyond the
  screen. RadialMenu allows a 760x540 minimum host size; the launcher and other
  apps retain their 980x860 minimum. Configuration also scrolls. Other app page
  instances and edits remain retained when switching pages.
- TDD: observed failing modifier parsing/payload and title/layout tests first.
  Coverage includes modifier-only save/load and builder restoration, no empty
  modifier actions, exact Normal/Hold/Repeat payloads, mouse use during Hold,
  title-bar state and form/footer geometry in a 900x620 host.
- Opening RadialMenu clamps a non-maximized host's size and position to the
  available screen with room for its native frame/title bar. The short-screen
  regression verifies this against a simulated 1024x700 available area.
- Validation: all 31 affected RadialMenu runtime/editor/input tests and all 18
  Launch tests passed with exit code 0. Renders checked at 1000x720, 900x620 and
  760x540 in light/dark. Native Qt scroll areas use scoped scrollbar styling.
  Combined offscreen modules have intermittently crashed during native Qt teardown,
  even with native scroll areas; this is not proven to be caused by Fluent scroll
  wrappers. Isolating test modules in separate processes gives clean exits.

## Toggle Hold/Repeat and remapped activation fix (2026-11-20)

- Updated user requirement: both Hold and Repeat start on the first fresh hotkey
  press after selection and stop on the next press. Hotkey release does not stop
  either mode. Both stop and leave the following press to open the menu.
- ActivationMonitor counts rising complete-chord edges, not key auto-repeat, so
  quick taps completed between timer ticks still start/stop actions. Tag every
  SendInput KEYBDINPUT with process-specific INPUT_TAG. Ignore only that tagged
  output; previously ignoring every LLKHF_INJECTED event prevented activation
  from mouse software/remappers. Foreign injected hotkeys now work without our
  configured output changing activation state or triggering recursion.
- Tests first reproduced ignored remapper activation and failed quick-tap Hold;
  after clarification, added failing Repeat-toggle and separate menu-opening coverage.
  Native opt-in test (test_native_activation.py; command in commands.md) acquired
  a real foreground receiver, injected untagged Ctrl+Alt+Space remapper input,
  verified repeated balanced F24 presses with no leaked Ctrl/Alt, release
  persistence, stopping with the menu hidden and quick-tap Hold down/up across two taps.
  This verifies native hook/SendInput/Qt delivery to our own isolated receiver;
  real hardware and other applications still need hands-on verification.
- Validation: all 32 affected RadialMenu runtime/editor/radial regression tests
  passed with exit code 0; native receiver integration also passed with the final
  toggle logic. Active toggled actions allow mouse use while retaining target
  focus and unrelated-modifier guards; Repeat no longer stops just on a click.

- Repeat stopping behaviour revised per user: the stop press leaves the menu
  hidden, exactly like Hold. The following fresh hotkey press opens the menu.
  Updated the regression first and observed it fail, then removed immediate
  reopening and updated runtime hints, status, README and commands.

## First Hold activation press (2026-11-20)

- TDD reproduced the extra-press bug in both unit and native receiver tests:
  selecting Hold with Ctrl/Alt still held left ActivationMonitor waiting for all
  hotkey components to release, so the next Space tap was discarded. Readiness
  now depends only on releasing the main activation key (Space/R/F8). The first
  post-selection hotkey press starts Hold, even when modifiers stay held.
- begin_gesture clears logical downs for physically held activation modifiers
  using tagged key-ups while retaining their captured physical state. This
  prevents Ctrl/Alt leaking into the configured combo and does not count as a new
  activation. Right Ctrl/Alt releases carry extended flags. Selection still sends
  no configured key; the second subsequent press stops, leaving the menu hidden.
- Native integration now seeds Ctrl+Alt across selection, taps Space exactly
  once, asserts one unmodified F24 down, and asserts key-up on the second tap.
  It first failed with zero F24 events, then passed after the fix. The receiver
  may briefly join the foreground input queue to activate its own test window;
  it detaches before injection and still checks focus before sending any downs.
- Final validation: 17 behaviour/input, 11 profile/editor and 6 radial tests all
  passed in isolated processes with clean exits. The native receiver test also
  passed (35 tests total). Diff formatting passed. A combined offscreen run passed
  all assertions but hit the intermittent Qt teardown crash noted above; module
  isolation was used for the final verification rather than treating that crash
  as a successful run.


## Custom activation hotkey (2026-11-20)

- Edit Hotkey sits directly below Edit Buttons on RadialMenu configuration and
  opens an embedded page with Save Hotkey and Cancel. Opening it cancels pending
  input and hides the popup. Cancel discards its draft; Save validates one chord,
  registers it immediately and persists radial/key. The configuration summary
  follows changes. Failed registration restores the previous listener and leaves
  the editor open with an inline error; invalid syntax does not stop listening.
- activation_monitor.parse_hotkey shares the button sequence parser but rejects
  multiple chords, modifier-only chords and Escape. Both normal registration and
  Hold/Repeat use it, including Shift and either Windows key. Gesture setup clears
  held Shift/Win activation modifiers as well as Ctrl/Alt to avoid contaminating
  configured output. Existing preset settings remain compatible.
- Validation: all 43 RadialMenu tests and 18 Launch tests passed. The 11 profile
  tests passed with clean exits when isolated individually; running that whole
  module still hits the previously documented Qt teardown access violation after
  assertions pass. A native-platform attempt also hit a platform-dependent icon
  pixel assertion; the supported offscreen checks passed. New coverage verifies
  custom modifier mapping, rejected chords, button placement, page navigation,
  Save/Cancel, conflict recovery, persisted reload and native-registration flags.
  Light/dark settings and editor renders inspected at 900x620 with Segoe UI.
  Physical hotkey delivery to external applications was not retested.


## Hotkey builder and live validation (2026-11-20)

- HotkeyEditor now uses Ctrl/Shift/Alt/Windows checkboxes, SingleKeyEdit and a
  special-key dropdown, mirroring the button builder. It loads existing chords
  into those controls, displays the assembled shortcut and synchronises the
  dropdown when typing. Escape is excluded from the dropdown and still rejected
  by parse_hotkey. Save is disabled for missing/invalid/unavailable shortcuts.
- Live availability checks briefly RegisterHotKey with HOTKEY_ID + 1 and release
  it immediately. The existing listener remains registered; the current chord
  is recognised by parsed key/modifier values without probing. The native filter
  ignores the probe ID. Save checks registration again to handle availability
  changing after validation; its previous-listener recovery remains in place.
- Validation: all 3 hotkey tests, 17 behaviour/input tests and 18 Launch tests
  passed with clean exits. Coverage includes typing/overtyping, dropdown sync,
  invalid/empty/reserved keys, live availability conflict, immediate probe release,
  preserving the listener, Save/Cancel and registration-time conflict recovery.
  Light/dark renders inspected at the 760x540 host minimum; controls and footer fit.

- ButtonEditor now synchronises its special-key dropdown with its key field,
  matching HotkeyEditor: typing a letter/digit or clearing the key resets it to
  Special keys…, while a named key selects the matching entry. Signals are blocked
  during dropdown sync so it cannot overwrite the typed key or affect sequences.
- Validation: the existing key-entry interaction test now checks reset after typing/clearing and reselecting the same special key. It passed with a clean exit on retry; the first run passed assertions but hit the documented Qt teardown crash. Diff formatting passed.


## Hold editor single-entry controls (2026-11-20)

- ButtonEditor hides Append key for Hold, sets a no-comma validator on the
  sequence field and uses single-shortcut hint/placeholder text. Normal/Repeat
  restore the append action and multi-entry field. Switching to Hold retains
  the first entry and reports that change; drafts still require explicit Save.
- Programmatic multi-entry changes are reduced to the first chord in Hold;
  apply_key also replaces instead of appending in Hold. Existing model/save
  validation remains authoritative and still rejects multiple Hold chords.
- Validation: the Hold profile/editor regression passed, including mode changes, first-entry retention, typing a comma, direct multi-entry updates, forced append, persistence and restoring Normal/Repeat append. Existing key-entry and editor/navigation tests plus all 17 behaviour/input tests also passed with clean exits.
