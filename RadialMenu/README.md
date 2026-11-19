# RadialMenu

Open RadialMenu from the Launcher to start listening for Ctrl+Alt+Space.
The settings page offers alternative keys, 2–26 segments (default 12), and Preview.
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
dismisses it. No keyboard/mouse hook or additional dependency is installed.

Click the cog at the top right of the popup to open RadialMenu settings. This
closes the popup and cancels any letter delivery. Settings can also be restored
from the tray icon.
