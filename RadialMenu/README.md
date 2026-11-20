# RadialMenu

Run `RadialMenu.cmd` from the repository root, or open RadialMenu from the Launcher to start listening for Ctrl+Alt+Space.
The settings page offers 2–26 segments (default 12) and application button profiles.
Choose **Edit Hotkey**, directly below **Edit Buttons**, to change the global activation shortcut.
Select **Ctrl**, **Shift**, **Alt** and/or **Windows**, then type one letter or digit,
or choose a named key (including F1–F24) from **Special keys…**. The assembled shortcut
and its validity/Windows availability update immediately. **Save Hotkey** is enabled
only for a valid, available shortcut; choose it to apply the change. **Cancel** discards the edit. Escape is reserved for cancellation.
If Windows rejects the shortcut, the editor reports the conflict and restores the previous listener.
The saved hotkey also controls Hold and Repeat and is restored on the next launch.
Settings use the shared suite settings file; appearance and accent follow the suite.
The activation key is global and works while another application has focus.
Choose **Run in background** to hide the Launcher to the system tray. Closing the
Launcher also leaves RadialMenu listening when the system tray is available.
Double-click its tray icon to restore settings; right-click and choose **Exit
RadialMenu** to stop it. Other open suite windows remain open. Without a system
tray, Run in background minimises the window and closing the last window exits. A second process using the same hotkey reports
the conflict and can use another key.

Activation toggles a frameless, transparent ring at the mouse, constrained to the
current screen's available area. The default 12 segments are a–l (larger counts continue to z).
On hotkey activation the original foreground window is captured. Clicking a letter
hides the menu, requests focus back to that window, then waits up to five seconds
for it to be foreground and Ctrl/Alt/Shift/Windows and mouse buttons to be released.
It sends one letter key down/up pair, once. If focus does not return or the window
closes, the selection is cancelled. Preview never sends keys. Windows can block
input to an application running with higher privileges; delivery failure is shown
on the settings page. Key behaviour follows the target app and keyboard state. Escape, right-click, the centre, or losing focus
dismisses it. Normal uses the Windows hotkey registration. Hold and Repeat temporarily capture
the physical activation keys for one armed action; no additional dependency is needed.

Click the cog at the top right of the popup to open RadialMenu settings. This
closes the popup and cancels any letter delivery. Settings can also be restored
from the tray icon.

## Edit application buttons

Choose an executable using **Choose application…**, or open settings from the
popup cog to select the application captured by the hotkey. Saved applications
appear in the Application selector. Profiles match the full executable path,
case-insensitively, and apply to all windows of that executable.

Select **Edit Buttons** to open the editor directly, with the first button selected. The button editor shows
**Edit Buttons — application** in the window title bar, a radial selector on the
left and the selected button's fields starting at the top on the right. The form
scrolls in smaller windows; Save and Cancel stay visible beneath it. Clicking another segment switches buttons and
retains the current draft. The selected segment stays highlighted. Names and
icons update in the editor preview immediately.

Configure a name, Icon 1, Icon 2, and button sequence. Icons reference
image files (PNG, SVG, ICO, JPEG or BMP); keep those files available. Both icons display together when assigned; either slot may be left empty. Button sequences accept letters,
digits, F1–F24, and Enter, Tab, Space, Escape, Backspace, Delete, Insert, Home,
End, PageUp, PageDown and arrow keys. Use Ctrl, Alt, Shift or Win with `+` for
shortcuts; use commas for successive keys, for example `Ctrl+A, Ctrl+C`.
Use the Ctrl, Alt, Shift and Win checkboxes with a typed key or the special-key
dropdown (F1–F24, Tab, Space, Backspace, Return and navigation keys).
The key entry holds one key: each typed key replaces the previous one, and
pasting retains only the last inserted character. Backspace or Delete clears it. **Use key**
replaces the sequence; **Append key** adds another shortcut. You can also edit
the sequence directly. Letter keys are always shown and saved in uppercase (including existing profiles
when loaded); uppercase does not imply Shift. Choose Shift explicitly when needed.
Select **Modifiers only** to send Ctrl, Alt, Shift or Win without another key
(for example `Ctrl+Shift`). This works with Normal, Hold and Repeat. Hold keeps
the modifiers down for mouse actions such as modified dragging, until the hotkey
is pressed again. Use `Plus` or `Comma` for those literal keys. A blank sequence disables the action.

**Save Buttons** persists all button drafts for this application. **Save and
Back** saves and returns to configuration. **Cancel** returns without saving
the pending drafts. Editing and the tray preview never send input. Profiles are
stored in the existing shared settings file. Unconfigured applications retain
the default letter buttons. The next hotkey activation loads the saved profile.
The configured sequence uses the same focus/modifier guard as letter delivery.

## Button behaviour

The **Behaviour** dropdown applies to each button. A marker near the outer edge
of its radial segment shows the selected behaviour in both the editor and live menu:

- **Normal (`.`)**: select a button to send its sequence once, as before.
- **Hold (`-`)**: select a button, then press the activation hotkey once.
  That first press holds the configured key/combo down; press it again to release.
  Releasing the hotkey itself does not end the Hold. Hold accepts one combo.
  After stopping, the next hotkey press opens the menu again.
- **Repeat (`...`)**: select a button, then press the activation hotkey once.
  That first press starts repeating the configured sequence at up to 10 times per
  second. Press it again to stop. The following hotkey press opens the radial menu.

Quick taps work; you do not need to keep the hotkey held. Release the main key
(Space, R or F8) from the menu-opening press before pressing it again; Ctrl/Alt
may remain held across selecting a button. No extra activation press is needed. Nothing is sent just
by selecting a Hold or Repeat button. Escape, opening settings/preview, stopping
RadialMenu, losing the original window or pressing an unrelated modifier cancels
the armed action and releases keys inserted by Hold. Focus must return within
five seconds of selection. The app captures physical or mouse/remapper-generated activation keys only
while armed so Ctrl/Alt from the hotkey do not alter the configured output combo.
Its own injected output is tagged and ignored by the activation monitor, so
output cannot trigger itself. Existing profiles default to Normal. Blank sequences disable all three modes.

## Offline icon library and application list

Both icon fields offer **Icons…** for the bundled offline icon libraries and
**File…** for other images. Search by name or keyword, select an icon and click
**Use Icon** (or double-click). All 359 Design icons from Tabler Icons 3.52.0 are
bundled: 461 SVGs including available filled variants. No internet connection is
used by the picker. Library selections store portable `tabler:` references and
render in light/dark colours. Sources and the MIT license are in `assets/tabler`.

The Application dropdown refreshes whenever it opens. It combines running apps
with saved application profiles, grouping windows by executable. Running apps
show their window/taskbar icon and a window title; closed configured apps are
marked **(configured)**. Tool windows, owned utility windows and cloaked windows
are omitted. If a window icon is unavailable, its executable icon is used.

Application icons are cached as PNGs under `RadialMenu/app-icons` beside the
shared `settings.ini`. Filenames hash the normalised executable path. Closed
configured apps keep their cached icon across restarts, including when the
executable is no longer accessible. The cache follows `PHOTO_TOOLS_SETTINGS`
when that setting overrides the config location.

The closed Application dropdown shows the selected app’s icon as well as its name.

## Multiple icon sets and stable names

The offline picker now includes Phosphor 2.1.1: 1,512 icon names in six styles
(regular, thin, light, bold, fill and duotone), totalling 9,072 SVGs. Existing
Tabler Design assets remain available. Both retain their upstream MIT licenses.
Use the library/style filters and keyword search to narrow the list.

Overlapping names are kept, never merged. Display names always include the set
and style, for example **Phosphor / regular / palette** and **Tabler / outline /
palette**. Stored IDs have the stable format `<set-id>:<style>/<icon-name>.svg`:
`phosphor:regular/palette.svg` and `tabler:outline/palette.svg`.

Set IDs are permanent lowercase namespaces, and style/name follow upstream
identity. A release version belongs in the manifest, not in the stored ID, so
updating a library does not rename button assignments. Existing Tabler IDs are
unchanged. Files are grouped in `assets/<set-id>/<style>/`.

### Adding or updating a set

Each `assets/<set-id>/manifest.json` declares `id`, `label`, `version`, source,
archive checksum and icon entries (`name`, `style`, `path`, optional `tags`). The
picker discovers these manifests automatically. Keep the upstream license and
source notice beside the manifest. New namespaces prevent cross-set collisions.

`import_icon_set.py` imports pinned package archives containing SVGs under
`package/assets/<style>/`. It validates SVGs and IDs, normalises style suffixes
in filenames, preserves original SVG contents, and publishes the manifest last.
`--prefix` supports a different archive SVG root. For other package layouts,
adapt the import layout to the same manifest contract; runtime code is unchanged.

Reusing a set ID updates that set in place. Removed upstream IDs stay in the
manifest as `retired` and their files are retained: existing assignments still
render, while the picker hides retired entries. Do not delete a set's folder
before updating it. Restart RadialMenu after installing or updating libraries.

## Lucide, Remix Icon and attribution

The offline picker also includes Lucide (lucide-static 1.76.0, 2,404 SVGs including
upstream aliases) and Remix Icon 4.9.1 (3,229 SVGs). All four libraries appear in
the same picker and in both icon slots. There are 15,166 bundled variants total.
Stable IDs use `lucide:outline/<name>.svg` and `remix:line/<name>.svg`,
`remix:fill/<name>.svg`, or `remix:regular/<name>.svg` for unsuffixed icons.

**About & Licenses** on the configuration page and in the icon picker displays
all four sets' versions, creators/attribution, project and release links, and
the full offline licenses. Lucide's ISC notice includes the separate MIT notices
and icon list for Feather-derived work by Cole Bemis. Remix uses the **Remix Icon
License v1.0**, rather than Apache 2.0. The original notices are retained beside
each set's assets. Keep those files with distributed copies of the app.

The importer uses `--layout flat --prefix package/icons/` for Lucide and
`--layout remix --prefix package/icons/ --license-name License` for Remix. The
default `styles` layout still supports Phosphor. Attribution metadata is retained
on updates; review new releases' license/creator changes and update it as needed.

When **Hold** is selected, **Append key** is hidden and the sequence field accepts
only one key or shortcut. Switching a multi-entry sequence to Hold keeps its first
entry and shows a notice; save explicitly to persist the change. Normal and Repeat
retain the Append key option and multi-entry sequences.
