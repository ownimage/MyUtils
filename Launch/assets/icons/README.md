# MyUtils application icons

Original vector artwork created for this suite. No external icon library, font,
or runtime download is used. Each app has its own colour and symbol; launcher
uses a matching four-tile mark.

- `camera-import`: teal camera and import arrow
- `yearbook`: purple open book and bookmark
- `slideshow`: amber photo stack and play symbol
- `radial-menu`: blue radial selector with one highlighted segment
- `launcher`: slate grid using the four app colours

SVG files are the editable sources. ICO files contain transparent 16, 20, 24,
32, 40, 48, 64, 128 and 256 pixel images for Windows and Qt. Rebuild them from
the repository root with:

```powershell
.\venv\Scripts\python.exe Launch/tools/build_icons.py
```

`Launch/apps.json` chooses each app's icon basename. `photo_tools/app_icons.py`
loads assets relative to the package and sets native Windows per-window
AppUserModelID and relaunch icon metadata. `shell.py` applies icons to tiles,
menus, app views and the active host. Returning home restores the launcher icon.
RadialMenu uses its new app icon in the system tray as well.
