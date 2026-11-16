# Slideshow

Open **slideshow_gui.bat** or choose **Slideshow** in the Photo Tools launcher.
Select an event folder containing `highlight`, then **Load photos**. JPG and JPEG
highlights are listed. Edit dates and titles in the table; blank cells use the
event folder name (for example `20260615 Holiday` gives `2026 06 15` and `Holiday`).

**Save dates and titles** writes `slideshow/data.txt` with Image,Date,Title columns.
Existing overrides are loaded automatically, including quoted commas and Unicode.
**Create slideshow** saves the table and renders fresh copies from highlight into
slideshow. Existing matching output images are replaced only after successful
rendering. Original highlights remain unchanged. Cancellation stops after the
current Photoshop image; completed slides remain. Photoshop must be installed.

**Open Photoshop template** opens this app's `template.psd`. Edit its `Title` and
`Date` text layers to change fonts and placement. Changes apply to subsequent
renders. This template is shared by all event folders.

The GUI uses the shared appearance, accent colour, menus and app ordering from
`../Launch`. It uses PySide6-Fluent-Widgets (QFluentWidgets for PySide6).

## Setup

Use Python 3.11 and install `requirements.txt` into this folder's `venv`.
The Photoshop rendering worker uses `venv/Scripts/python.exe`, even when the
GUI is opened from the launcher with Camera Import's Python environment.

## Original command-line workflow

`bootstrap.cmd` can still be copied into an event folder and run to create its
slideshow folder. Edit the generated data.txt and drop it onto run.lnk to render.
The original command line edits slideshow images in place; refresh them from
highlight before rendering again. The GUI always starts from highlight originals.

Yearbook collects the generated JPGs. It keeps existing yearbook copies, so
remove the specific old copies before collecting regenerated slides again.

## Checks

Run `python -m unittest discover -s tests -v` using the suite Python environment.
Tests use temporary folders and a simulated renderer, without changing photos.
