# MyUtils commands

Run these commands in PowerShell from the MyUtils folder:

```powershell
Set-Location P:\git\MyUtils
```

## Set up or update the shared environment

All applications use the single top-level `venv` and `requirements.txt`.
Python 3.11 is used for all GUI apps and native image rendering.

For a fresh checkout:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

To update dependencies in an existing environment:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Activation is optional because the commands and batch launchers select this
shared Python explicitly. Do not create environments in the application folders.

## Run all tests

```shell
venv\Scripts\activate.bat && python .\run_tests.py
```

This runs the Launch, Camera Import, Yearbook and Slideshow suites in separate
processes using the shared environment. It runs every suite even if one fails
and returns a nonzero exit code if any suite fails. GUI tests run without
opening visible windows. Tests use temporary sample folders and perform native
native image rendering. Windows must allow the temporary folder-link
test in Camera Import.

## Open the launcher

```powershell
.\launcher.bat
```

## Open individual applications

```powershell
.\Import\run_gui.bat
.\Yearbook\yearbook_gui.bat
.\Slideshow\slideshow_gui.bat
```

Slideshow's background renderer and original `Slideshow/run.cmd` use the shared
environment. **Save data** writes date/title overrides as backwards-compatible
CSV in `highlight/data.txt` (also copied to `slideshow/data.txt`) and layout only
in `highlight/template.json`. For visual layout changes, load an event and select
**Edit template**; it replaces the main window content until Apply or Cancel.
**Apply template** saves `highlight/template.json` immediately before returning;
pending date/title edits remain unsaved until **Save data**.
**Save user default** writes `Slideshow/template.json`. **Load user default** restores
that layout; **Load system default** (or **Reset to default**) loads the unchanged
`Slideshow/default_template.json`. New events use the user default when saved.
Type a font-name prefix or use the font dropdown's Up/Down arrows for live preview.

**Create slideshow** also writes `slideshow/template.json` alongside the output
images, using the exact template snapshot for that run.

Slideshow creation automatically uses the available logical CPUs. Text/glow
overlays are prepared once per distinct title/date, then reused by image workers.
Cancel stops publishing new results and waits for active temporary jobs to finish.

## RadialMenu

Choose RadialMenu in the Launcher, then press Ctrl+Alt+Space. Configure an alternative
key or segment count on its page. Choose **Run in background** to hide to the
system tray; the global key works in other apps. Double-click the tray icon for
settings or use its **Exit RadialMenu** menu item to stop listening.
Standalone: `.\RadialMenu\run_gui.bat`. The full test command includes RadialMenu.

After updating RadialMenu, choose **Exit RadialMenu** from its tray menu and reopen
it from the Launcher so the resident listener loads the updated code.

RadialMenu defaults to letters a–l. Activate over the target app, then click a
letter to return focus and send that key. Preview sends no input. Focus must
return within five seconds; higher-privilege apps may reject Windows input.

The cog at the popup’s top right opens RadialMenu settings without sending a key.
