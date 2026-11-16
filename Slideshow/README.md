# Slideshow

Open **slideshow_gui.bat**, or choose **Slideshow** from the root launcher.
No Photoshop installation is required. All rendering uses the shared MyUtils
Python environment and the font files in this Slideshow directory.

## Edit photos and templates

1. Choose an event folder containing `highlight` and select **Load photos**.
   JPG and JPEG highlights are listed. Blank dates and titles use the event
   folder name: `20260615 Holiday` gives `2026 06 15` and `Holiday`.
2. Select a date/title cell to see the finished slide preview. Changes to the
   table update the text in that preview. It follows mouse and keyboard selection.
3. Select **Edit template**. Choose Title or Date, or click the text on the canvas.
   Drag text to move it; drag the blue square to resize it. Controls also set
   font, point size, position, alignment, visibility, text colour and outer glow.
   **Add font file** copies a TTF/OTF into Slideshow and makes it selectable.
4. **Apply template** returns the changes to the main view; **Cancel** discards
   template edits. **Reset to Photoshop layout** restores the shipped defaults.
5. **Save slideshow** persists the layout and all per-photo overrides in the
   event's **highlight/slideshow.json**. Creating slides also saves first.
6. **Create slideshow** renders fresh copies of highlights into `slideshow`.
   Existing matching outputs are replaced only after each successful render.

Template changes affect all photos in that event. Each event's settings reload
when opened. Other events start with their own saved settings or the defaults.
Unsaved changes prompt before leaving or closing the view.

## Default template

- Canvas: 1920 x 1080, JPEG output at 300 dpi, black background.
- Photo: centred and fitted inside the canvas without changing its proportions.
- Title: Filmotype LaSalle, 28.8 pt, right aligned at x=1825.5 with baseline y=128.1.
- Date: 7-Segment, 11.2 pt, left aligned at x=36.48 with baseline y=1017.30.
- Text: black with a white outer glow, approximating the Photoshop layer effects.

`default_template.json` was derived from the original PSD. At 300 dpi, the title
size is 120 pixels and the date approximately 47 pixels. The original font
contours match the PSD closely; anti-aliasing and glow can differ from Photoshop.
`template.psd` remains a reference file and is never loaded at runtime.

`FilmotypeLaSalle.otf` and `7segment.ttf` were copied from this user's installed
fonts. See `FONT-SOURCES.md` for provenance and font licence information.

## Saved project and compatibility

`highlight/slideshow.json` is authoritative once saved. It contains a version,
template and per-image date/title overrides, and is written atomically. Invalid
settings report an error rather than silently reverting or overwriting them.
If that JSON file is absent, the app imports legacy `slideshow/data.txt` CSV
columns `Image,Date,Title`. Save also exports this CSV for existing tools. To use
an externally edited CSV after a project exists, deliberately reconcile it with
the JSON; subsequent loads use the saved JSON rather than the CSV.

The GUI always renders from fresh highlight copies, avoiding stacked text on
repeated runs. Source photos are unchanged. Cancellation stops after the current
image, keeping completed slides. Rendering errors preserve the previous output.

The original `bootstrap.cmd`, `param.py` and `run.cmd` remain usable, with native
rendering. The old command path edits slideshow images in place; refresh those
from highlights before running again. The GUI handles that automatically.

Yearbook keeps existing yearbook copies; replace specific old copies intentionally
before recollecting updated slides. JPEG highlights produce JPEG outputs, but
Yearbook currently collects only files with the .jpg extension.

## Setup and tests

Use the single root `requirements.txt` and `venv` (Python 3.11).
See [commands.md](../commands.md) for setup and all-tests commands.
From this Slideshow folder:

```powershell
..\venv\Scripts\python.exe ..\run_tests.py
```

Tests cover actual native rendering and JPEG dimensions/DPI, safe replacement,
JSON/CSV persistence, template dragging/resizing/font edits, preview and workers.
They use temporary sample photos, not the user's photo collection.
