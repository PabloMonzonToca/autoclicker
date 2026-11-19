# Windows Autoclicker

A simple left-click autoclicker controlled by global hotkeys.

## Setup

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/). Enable **Add Python to PATH** during installation.
2. Open PowerShell in this folder.
3. Install the dependency:

```powershell
py -m pip install -r requirements.txt
```

## Run

```powershell
py autoclicker.py
```

- Press **F6** to toggle clicking on or off.
- Press **F7** to stop the program completely, equivalent to `Ctrl+C`.
- Clicks occur once every 5 seconds at the current mouse position.
- The first run creates a per-user Windows startup entry named `Autoclicker.cmd`.
- When Windows starts it, the autoclicker is always **INACTIVO**; press **F6** to activate it.
- Startup uses `pythonw.exe`, so it runs without opening a console window.
- The CMD-style icon is always visible next to the clock, like the OneDrive cloud, and never hides behind the overflow arrow.
- The icon shows a status dot: **green** while the autoclicker is active and **red** while it is inactive.
- The first run (or any run where the icon is still hidden) restarts Windows Explorer once so the icon moves to the taskbar.
- Use the tray menu to see the status, toggle the autoclicker, open a CMD status window, or exit.
