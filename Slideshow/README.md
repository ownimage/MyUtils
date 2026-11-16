# Slideshow

Open **slideshow_gui.bat**, or choose **Slideshow** from the root launcher.
Rendering uses the shared MyUtils Python environment.

## Editing and saving

1. Choose an event folder containing `highlight` and select **Load photos**.
   JPG and JPEG highlights are listed. Blank dates and titles use the event
   folder name: `20260615 Holiday` gives `2026 06 15` and `Holiday`.
2. Select a date/title cell to see the finished slide preview. Table changes
   update the preview, which follows mouse and keyboard selection.
3. Select **Edit template**. It replaces the main window content while you edit;
   no separate editor window opens. Choose Title or Date, or click the text.
   Drag text to move it; drag its blue square to resize it. Controls set font,
   size, position, alignment, visibility, text colour and outer glow.
   Type a font-name prefix in the font selector to jump through the list, or use
   Up/Down to browse. The text renders as the highlighted font changes, including
   while the dropdown is open; Enter is not required to see a preview.
   **Apply template** immediately saves `highlight/template.json`, then returns
   to the photo table. It does not save pending date/title edits. If saving fails,
   the editor stays open with an error; the previous template remains intact.
   **Cancel** returns without saving template edits. Table edits and selection remain.
   Unsaved template edits also participate in the main window's close prompt.
4. **Save data** saves the following files in the event's highlight folder:

   - **data.txt**: ordinary CSV with the original `Image,Date,Title` header.
   - **template.json**: layout and styling only, with no image overrides.

   A matching CSV is also written to `slideshow/data.txt` for older tools.
   Creating slides saves these settings first.
5. **Create slideshow** renders fresh copies of highlights into `slideshow`.
   It also writes **slideshow/template.json**, recording the exact layout used
   for that run. Existing matching outputs are replaced after successful rendering.
   The template copy is updated before the first new slide is published, and
   remains available if a partially completed run is cancelled.

CSV is the source of truth for dates and titles. You can edit it externally;
use normal CSV quoting for commas/newlines and UTF-8 for Unicode. Two-column
rows (`Image,Date`) are accepted, with a blank title using the folder default.

Template edits affect all photos in that event. Each event's layout reloads
from `highlight/template.json`. New events use the saved user default when present,
otherwise the system default. Existing event layouts are not overwritten.
Unsaved changes prompt before leaving or closing the view.

## User and system defaults

Within the embedded template editor:

- **Save user default** immediately writes the current layout to
  **MyUtils/Slideshow/template.json**, using atomic replacement. This contains
  only template settings, never date/title overrides or image paths.
- **Load user default** loads that saved project-level layout into the editor.
  If no user default exists or it is invalid, the current edits stay unchanged
  and an inline message explains the problem.
- **Load system default** loads the shipped `Slideshow/default_template.json`.
- **Reset to default** is a shortcut for loading the system default.

The system default is never changed by Save user default. Loading either default
changes only the editor until **Apply template**. Save user default is a separate,
immediate action: cancelling event edits does not undo a deliberately saved user
default. **Apply template** saves the event's template immediately; **Save data**
keeps its existing CSV/template save behaviour.

## Default layout and fonts

- Canvas: 1920 x 1080; JPEG at 300 dpi; centred photo fitted without distortion.
- Background: black.
- Title: Windows Segoe Script, 28.8 pt; right aligned at x=1825.5,
  baseline y=128.1. This font is used from the local Windows installation;
  its file is not bundled or copied into this project.
- Date: bundled 7-Segment, 11.2 pt; left aligned at x=36.48,
  baseline y=1017.30. See `FONT-SOURCES.md` and `7segment-OFL.txt`.
- Text: black with a white outer glow. Fonts and every text property are editable.

Only fonts with suitable distribution rights should be added to the project.
Installed fonts are selectable without copying their files. When opening a saved
layout that needs a font absent from this computer, choose an available font in
Edit template before rendering.

## Compatibility and migration

Load precedence for dates/titles is `highlight/data.txt`, then the original
`slideshow/data.txt`. If neither CSV exists, the previous combined
`highlight/slideshow.json` can supply its saved overrides. Loading never changes
files. Saving writes CSV and `highlight/template.json`, never combined JSON.
Existing older JSON is left untouched as a backup and cannot override CSV edits.

For layouts, `highlight/template.json` takes priority; an older combined JSON
supplies its template only when the new file is absent. Invalid active template
settings report an error rather than silently resetting or overwriting them.

The GUI renders from fresh highlight copies, avoiding stacked text on repeated
runs. Source photos remain unchanged. Cancellation stops after the current
image, keeping completed slides. Errors preserve the previous output image.

The original `bootstrap.cmd`, `param.py` and `run.cmd` remain usable. The CSV CLI
edits slideshow images in place; refresh them from highlights before rerunning.
The GUI does that preparation automatically. Yearbook keeps existing copies;
replace specific old yearbook copies intentionally before recollecting updates.
JPEG highlights produce JPEG files, but Yearbook currently collects only .jpg.

## Setup and tests

Use the root `requirements.txt` and `venv` (Python 3.11).
See [commands.md](../commands.md) for setup and full-test commands.
From this Slideshow folder:

```powershell
..\venv\Scripts\python.exe ..\run_tests.py
```

Tests use temporary photos and cover native rendering, dimensions/DPI, safe
replacement, CSV/template persistence, old-format migration and visual editing.
