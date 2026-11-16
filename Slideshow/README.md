# Slideshow

Open **slideshow_gui.bat**, or choose **Slideshow** from the root launcher.
Rendering uses the shared MyUtils Python environment.

## Editing and saving

1. Choose an event folder containing `highlight` and select **Load photos**.
   JPG and JPEG highlights are listed. Blank dates and titles use the event
   folder name: `20260615 Holiday` gives `2026 06 15` and `Holiday`.
2. Select a date/title cell to see the finished slide preview. Table changes
   update the preview, which follows mouse and keyboard selection.
3. Select **Edit template**. Choose Title or Date, or click the text on the canvas.
   Drag text to move it; drag its blue square to resize it. Controls set font,
   size, position, alignment, visibility, text colour and outer glow.
   **Reset to default** restores the shipped layout. **Apply template** returns
   edits to the main view; **Cancel** leaves the current template unchanged.
4. **Save slideshow** saves the following files in the event's highlight folder:

   - **data.txt**: ordinary CSV with the original `Image,Date,Title` header.
   - **template.json**: layout and styling only, with no image overrides.

   A matching CSV is also written to `slideshow/data.txt` for older tools.
   Creating slides saves these settings first.
5. **Create slideshow** renders fresh copies of highlights into `slideshow`.
   Existing matching outputs are replaced only after each successful render.

CSV is the source of truth for dates and titles. You can edit it externally;
use normal CSV quoting for commas/newlines and UTF-8 for Unicode. Two-column
rows (`Image,Date`) are accepted, with a blank title using the folder default.

Template edits affect all photos in that event. Each event's layout reloads
from `highlight/template.json`; other events use their saved layouts or defaults.
Unsaved changes prompt before leaving or closing the view.

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
