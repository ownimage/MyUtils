# Reorganise Camera Import

Organise imported camera images into folders named for the date they were taken.
NEF and other supported images go directly into a `YYYYMMDD` folder; JPEG files
go into its `origJPG` subfolder.

```text
Import folder/
  20250114/
    DSC_0001.NEF
    origJPG/
      DSC_0001.JPG
```

## Install

Use Python 3.10 or newer and install the dependencies in your environment.
From this project folder on Windows:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

If you already have a virtual environment, use its Python to install the updated
requirements. Activation is optional when using the full Python path below.

## Desktop app

On Windows, double-click **run_gui.bat** to launch using the project's `venv`.
Alternatively, from a terminal:

```powershell
.\venv\Scripts\python.exe reorg_gui.py
```

You can also supply an initial folder:

```powershell
.\venv\Scripts\python.exe reorg_gui.py "D:\Photos\Import"
```

1. Browse to the folder containing the imported images, or enter its path and
   click **Preview files**. Browsing automatically starts the preview.
2. Review each proposed destination and any skipped-file explanations.
   Previewing does not move files or create folders.
3. Click **Organise files** and confirm the move. The app stays responsive and
   reports progress and individual results. **Open folder** opens the import
   folder in your file manager.

Cancel stops after the current file. Files already moved remain in their date
folders. Files not yet processed remain in the import folder. Closing during a
scan or import requests cancellation and waits for the current file to finish.
Preview again after an import or a cancelled operation. The last chosen folder
is remembered between app sessions.

Use **Appearance** at the top right to choose **Light**, **Dark**, or
**Follow Windows** (the default). Your choice is remembered. Follow Windows
updates the app when the Windows colour mode changes, including while it is open.

## Command line

The original command still works:

```powershell
python reorg.py "D:\Photos\Import"
```

Preview without moving anything:

```powershell
python reorg.py "D:\Photos\Import" --dry-run
```

## Behaviour

- Only images immediately inside the chosen folder are processed. Subfolders
  are left alone, so existing date folders are not re-imported.
- Supported extensions: `.nef`, `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tif`,
  `.tiff`, `.webp` (case insensitive).
- Uses EXIF `DateTimeOriginal`, then `DateTimeDigitized`, then `DateTime`.
  ExifRead reads RAW metadata, with Pillow as a fallback for other formats.
  Files without a valid readable date are skipped; filesystem dates are not
  substituted. Empty or corrupt files are skipped too.
- Existing destinations are never overwritten. Both versions remain in place,
  with an explanation in the preview or activity log.
- Files changed since preview are left in place and reported as errors.
  Unreadable files or failed moves do not stop the rest of the import.
- Linked files and redirected destination folders are skipped or reported as
  errors. The app does not intentionally follow them outside the import folder.
- **This moves files; it does not create a backup.** On Windows, files are
  renamed within the import folder. On other platforms, files are copied to an
  exclusively created destination and removed from the source after success.

## Tests

The tests create temporary sample images; they do not touch your photos.

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

The GUI tests use Qt's offscreen platform and exercise previewing, moving,
cancellation, and closing while a worker is running.


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
