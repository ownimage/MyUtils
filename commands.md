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
.\Launch.cmd
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

Choose RadialMenu in the Launcher, then press Ctrl+Alt+Space. Use **Edit Hotkey**
below **Edit Buttons** in Settings to configure an alternative activation shortcut.
In Edit Buttons, **Keys** is read-only. Use **Build**, **Use key** / **Append key**,
and **Clear** to assemble or remove shortcuts. Build accepts printable characters,
including `[` and `]`, supported by the current Windows keyboard layout.

The radial popup settings cog opens **Edit Buttons** for the captured application.
Use **Main configuration** and **Edit Buttons** to move between pages without
losing drafts for that application; **Cancel** discards them.

Change the segment count on the main settings page. Choose **Run in background** to hide to the
system tray; the global key works in other apps. Double-click the tray icon for
settings or use its **Exit RadialMenu** menu item to stop listening and close the running UI.
Standalone: `.\RadialMenu.cmd` stops any existing standalone RadialMenu instances from this checkout, waits for them to exit, then starts a fresh instance in the background and returns to the command prompt. No Python console window is opened. Unsaved edits are discarded. Other Python applications and suite instances started through `Launch.cmd` are left running. Use `.\RadialMenu\run_gui.bat` to launch without stopping existing instances. The full test command includes RadialMenu.

After updating standalone RadialMenu, run `.\RadialMenu.cmd` again to load the updated code.
For RadialMenu opened through the Launcher, choose **Exit RadialMenu** from its tray
menu and reopen it from the Launcher.

RadialMenu defaults to letters a–l. Activate over the target app, then click a
letter to return focus and send that key. Preview sends no input. Focus must
return within five seconds; higher-privilege apps may reject Windows input.

The cog at the popup’s top right opens RadialMenu settings without sending a key.

To configure RadialMenu buttons for an application, choose its executable in the
Application selector and click **Edit Buttons**. The editor opens directly; use the radial menu on the left to switch buttons. Set name, Icon 1
and Icon 2, and a key sequence such as `Ctrl+C, Ctrl+V`. **Save Buttons**
saves the profile for that executable; **Save and Back** returns to configuration.
Opening settings through the live popup cog selects its captured application.
Choose a per-button **Behaviour**: Normal (`.`) sends once; Hold (`-`) holds one
combo; Repeat (`...`) repeats the sequence up to 10 times per second. Hold/Repeat
selection arms the action: the next hotkey press starts it (Ctrl/Alt may stay
held while selecting; release and re-press only the main key). Press again to stop, leaving the menu hidden. For both modes, the next
press after stopping opens the menu. Escape cancels.
Select **Modifiers only** to send just Ctrl/Alt/Shift/Win. The editor title is in
the window title bar; its top-aligned form scrolls on smaller screens while the
Save/Cancel actions remain visible.

The Application dropdown lists running and configured apps, with cached icons
for configured apps that are closed. Open it to refresh. In the button editor,
**Icons…** opens the offline Tabler Design library; **File…** chooses another image.

## Reimport or update offline icon libraries

Phosphor is bundled and needs no download at runtime. To reproduce its installed
release, run from the repository root:

```powershell
New-Item -ItemType Directory -Force work | Out-Null
Invoke-WebRequest -Uri 'https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz' -OutFile '.\work\phosphor-core-2.1.1.tgz'
.\venv\Scripts\python.exe .\RadialMenu\import_icon_set.py --archive .\work\phosphor-core-2.1.1.tgz --set phosphor --label Phosphor --source 'https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz'
```

For a later release, pin its version in both download/source URLs and the archive
filename; retain `--set phosphor`. Restart the resident app after importing.
Additional sets use distinct lowercase set IDs and the manifest contract in the
RadialMenu README. Never remove existing assets before an update: retired icons
are retained to preserve button assignments. The importer writes to the repository
and is a maintenance command, not part of the runtime app.

## Lucide, Remix Icon and About

All four icon sets are bundled offline. Open **About & Licenses** in RadialMenu
configuration or its icon picker for attribution and the complete local notices.

To reproduce the Lucide and Remix releases (from the repository root):

```powershell
New-Item -ItemType Directory -Force work | Out-Null
Invoke-WebRequest -Uri 'https://registry.npmjs.org/lucide-static/-/lucide-static-1.76.0.tgz' -OutFile '.\work\lucide-static.tgz'
.\venv\Scripts\python.exe .\RadialMenu\import_icon_set.py --archive .\work\lucide-static.tgz --set lucide --label Lucide --source 'https://registry.npmjs.org/lucide-static/-/lucide-static-1.76.0.tgz' --prefix package/icons/ --layout flat
Invoke-WebRequest -Uri 'https://registry.npmjs.org/remixicon/-/remixicon-4.9.1.tgz' -OutFile '.\work\remixicon.tgz'
.\venv\Scripts\python.exe .\RadialMenu\import_icon_set.py --archive .\work\remixicon.tgz --set remix --label 'Remix Icon' --source 'https://registry.npmjs.org/remixicon/-/remixicon-4.9.1.tgz' --prefix package/icons/ --layout remix --license-name License
```

For updates, pin the new release in each URL, keep the set ID, preserve the asset
directory and review license/attribution changes. Restart RadialMenu afterwards.

Native input integration check (opens an isolated receiver; injects only while
that receiver has foreground focus):

```powershell
$env:QT_QPA_PLATFORM = 'windows'
$env:PYTHONPATH = "$PWD\Launch;$PWD\RadialMenu"
$env:RADIALMENU_NATIVE_INPUT_TEST = '1'
.\venv\Scripts\python.exe -m unittest discover -s RadialMenu\tests -p test_native_activation.py -v
Remove-Item Env:RADIALMENU_NATIVE_INPUT_TEST
Remove-Item Env:QT_QPA_PLATFORM
Remove-Item Env:PYTHONPATH
```
