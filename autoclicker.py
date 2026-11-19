"""Windows autoclicker with a CMD-style system tray icon."""

import os
import subprocess
import sys
import threading
import winreg
from pathlib import Path

from PIL import Image, ImageDraw
from pynput import keyboard, mouse
import pystray

CLICK_INTERVAL_SECONDS = 5
NOTIFY_ICON_SETTINGS_KEY = r"Control Panel\NotifyIconSettings"
ACTIVE_COLOR = "#22c55e"
INACTIVE_COLOR = "#ef4444"

click_enabled = threading.Event()
stop_program = threading.Event()
mouse_controller = mouse.Controller()
f6_pressed = False
status_file = Path(__file__).with_name("autoclicker_status.txt")
startup_file = (
    Path.home()
    / "AppData"
    / "Roaming"
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
    / "Autoclicker.cmd"
)
tray_icon: pystray.Icon | None = None


def current_status() -> str:
    """Return the status shown by the tray icon and terminal."""
    return "ACTIVO" if click_enabled.is_set() else "INACTIVO"


def write_status() -> None:
    """Keep a small status file available to the terminal window."""
    status_file.write_text(
        f"Autoclicker: {current_status()}\nPulsa F6 para cambiar el estado.\n",
        encoding="utf-8",
    )


def configure_startup() -> None:
    """Create the per-user Windows startup launcher for this script."""
    python_executable = Path(sys.executable)
    if python_executable.name.lower() == "python.exe":
        python_executable = python_executable.with_name("pythonw.exe")

    startup_file.parent.mkdir(parents=True, exist_ok=True)
    startup_file.write_text(
        "@echo off\n"
        f'start "" "{python_executable}" "{Path(__file__).resolve()}"\n',
        encoding="utf-8",
    )


def refresh_tray() -> None:
    """Refresh the tray icon, tooltip and menu after a state change."""
    if tray_icon is not None:
        tray_icon.icon = create_tray_image()
        tray_icon.title = f"Autoclicker: {current_status()}"
        tray_icon.update_menu()


def click_loop() -> None:
    """Click once every interval while clicking is enabled."""
    while not stop_program.is_set():
        if click_enabled.wait(timeout=0.1):
            mouse_controller.click(mouse.Button.left)
            stop_program.wait(CLICK_INTERVAL_SECONDS)


def on_press(key: keyboard.Key | keyboard.KeyCode) -> bool | None:
    """Toggle with F6 or exit completely with F7."""
    global f6_pressed

    if key == keyboard.Key.f6 and not f6_pressed:
        f6_pressed = True
        if click_enabled.is_set():
            click_enabled.clear()
        else:
            click_enabled.set()
        write_status()
        refresh_tray()
    elif key == keyboard.Key.f7:
        stop_program.set()
        click_enabled.clear()
        write_status()
        if tray_icon is not None:
            tray_icon.stop()
        return False
    return True


def create_tray_image(active: bool | None = None) -> Image.Image:
    """Create a small CMD-style icon with a green/red status dot.

    The dot is green while clicking is enabled and red otherwise, so the
    tray icon always shows the current state at a glance.
    """
    if active is None:
        active = click_enabled.is_set()

    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # CMD-style terminal window.
    draw.rounded_rectangle(
        (1, 1, size - 2, size - 2),
        radius=8,
        fill="#0c0c0c",
        outline="#f2f2f2",
        width=2,
    )
    draw.text((10, 12), ">_", fill="#f2f2f2", stroke_width=1)

    # Status dot in the bottom-right corner.
    radius = 17
    center = size - radius - 1
    dot_color = ACTIVE_COLOR if active else INACTIVE_COLOR
    draw.ellipse(
        (center - radius, center - radius, center + radius, center + radius),
        fill=dot_color,
        outline="#0c0c0c",
        width=3,
    )
    return image


def open_status_terminal(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
    """Open CMD with the current status and leave it available to inspect."""
    powershell_command = (
        f"while ($true) {{ Clear-Host; Get-Content -LiteralPath '{status_file}'; "
        "Write-Host ''; Write-Host 'F6 cambia el estado. Cierra esta ventana para salir.'; "
        "Start-Sleep -Seconds 1 }"
    )
    subprocess.Popen(
        [
            "cmd.exe",
            "/k",
            "title Autoclicker - estado ^& powershell.exe -NoProfile -Command",
            powershell_command,
        ]
    )


def toggle_from_menu(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
    """Toggle clicking from the tray menu."""
    if click_enabled.is_set():
        click_enabled.clear()
    else:
        click_enabled.set()
    write_status()
    refresh_tray()


def exit_from_menu(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
    """Stop the listeners and close the tray icon."""
    stop_program.set()
    click_enabled.clear()
    write_status()
    icon.stop()


def on_release(key: keyboard.Key | keyboard.KeyCode) -> bool | None:
    """Allow the next F6 press to toggle the state again."""
    global f6_pressed

    if key == keyboard.Key.f6:
        f6_pressed = False
    return True


def own_executable_paths() -> set[str]:
    """Return the normalized paths of the interpreters running this app."""
    executable = Path(sys.executable)
    candidates = {executable}
    if executable.name.lower() == "pythonw.exe":
        candidates.add(executable.with_name("python.exe"))
    elif executable.name.lower() == "python.exe":
        candidates.add(executable.with_name("pythonw.exe"))
    return {os.path.normcase(str(path)) for path in candidates}


def promote_tray_icon_once() -> tuple[bool, bool]:
    """Mark our notification icon as always visible in the taskbar.

    Windows 11 stores the taskbar/overflow state of every notification icon in
    ``HKCU\\Control Panel\\NotifyIconSettings``. Setting ``IsPromoted`` to 1
    does the same as dragging the icon out of the overflow menu, which is how
    applications such as OneDrive always stay next to the clock.

    :return: whether our icon was found and whether it was changed
    """
    targets = own_executable_paths()
    found = False
    changed = False

    try:
        root = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            NOTIFY_ICON_SETTINGS_KEY,
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        )
    except FileNotFoundError:
        return False, False

    with root:
        subkey_count = winreg.QueryInfoKey(root)[0]
        for index in range(subkey_count):
            try:
                subkey_name = winreg.EnumKey(root, index)
            except OSError:
                break
            try:
                with winreg.OpenKey(
                    root, subkey_name, 0, winreg.KEY_READ | winreg.KEY_WRITE
                ) as entry:
                    try:
                        executable = winreg.QueryValueEx(entry, "ExecutablePath")[0]
                    except FileNotFoundError:
                        continue
                    if os.path.normcase(executable) not in targets:
                        continue
                    found = True
                    try:
                        is_promoted = winreg.QueryValueEx(entry, "IsPromoted")[0]
                    except FileNotFoundError:
                        is_promoted = 0
                    if is_promoted != 1:
                        winreg.SetValueEx(entry, "IsPromoted", 0, winreg.REG_DWORD, 1)
                        changed = True
            except OSError:
                continue

    return found, changed


def explorer_running() -> bool:
    """Return whether the Windows shell is currently running."""
    result = subprocess.run(
        ["tasklist", "/fi", "imagename eq explorer.exe"],
        capture_output=True,
        text=True,
    )
    return "explorer.exe" in result.stdout.lower()


def restart_explorer() -> None:
    """Restart the Windows shell so the new tray settings are applied."""
    subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], capture_output=True)
    stop_program.wait(2)
    if not explorer_running():
        subprocess.Popen(["explorer.exe"])


def keep_tray_icon_visible() -> None:
    """Promote our tray icon and apply the change when needed.

    The registry entry only exists after Windows has shown the icon, so this
    waits for it right after startup and then stops.
    """
    stop_program.wait(2)
    for _ in range(30):
        if stop_program.is_set():
            return
        found, changed = promote_tray_icon_once()
        if found:
            if changed:
                restart_explorer()
            return
        stop_program.wait(1)


def main() -> None:
    global tray_icon

    click_enabled.clear()
    stop_program.clear()
    configure_startup()
    write_status()

    click_thread = threading.Thread(target=click_loop, daemon=True)
    click_thread.start()

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    promotion_thread = threading.Thread(target=keep_tray_icon_visible, daemon=True)
    promotion_thread.start()

    tray_icon = pystray.Icon(
        "autoclicker",
        create_tray_image(),
        "Autoclicker: INACTIVO",
        menu=pystray.Menu(
            pystray.MenuItem(
                lambda _item: f"Estado: {current_status()}",
                None,
                enabled=False,
            ),
            pystray.MenuItem("Activar/desactivar", toggle_from_menu),
            pystray.MenuItem("Abrir terminal y ver estado", open_status_terminal),
            pystray.MenuItem("Salir", exit_from_menu),
        ),
    )
    tray_icon.run()
    listener.stop()


if __name__ == "__main__":
    main()
