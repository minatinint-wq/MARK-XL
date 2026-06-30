#computer_settings.py
import json
import re
import sys
import time
import subprocess
import platform
import psutil
import os
import sqlite3
import ctypes
from pathlib import Path
from datetime import datetime

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

def _set_volume_windows(level: int) -> str:
    """Set system volume using pyautogui."""
    target = max(0, min(100, level))
    print(f"[DEBUG VOLUME] Setting to {target}%")

    # First, mute then set to target using keyboard
    # This is more reliable than pressing up/down many times
    try:
        # Press mute to reset reference
        pyautogui.press("volumemute")
        time.sleep(0.2)
        # Press volume up target times
        for _ in range(target):
            pyautogui.press("volumeup")
            time.sleep(0.03)
        return f"Volume set to {target}%"
    except Exception as e:
        return f"Volume error: {e}"

def _get_volume_windows() -> int:
    """Get current system volume from Windows."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
        level = int(vol.GetMasterVolumeLevelScalar() * 100)
        return level
    except Exception:
        try:
            result = subprocess.run(
                ["powershell", "-Command", "(Get-AudioDevice -PlaybackVolume)"],
                capture_output=True, text=True, timeout=3
            )
            if result.stdout.strip():
                return int(float(result.stdout.strip()))
        except Exception:
            pass
    # Fallback: assume 50%
    return 50

def _set_volume_macos(level: int) -> str:
    """Set system volume on macOS."""
    try:
        subprocess.run(["osascript", "-e", f"set volume output volume {level}"], capture_output=True)
        return f"Volume set to {level}%"
    except Exception as e:
        return f"Volume error: {e}"

def _set_volume_linux(level: int) -> str:
    """Set system volume on Linux."""
    try:
        subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"], capture_output=True)
        return f"Volume set to {level}%"
    except Exception as e:
        return f"Volume error: {e}"

def set_system_volume(level: int) -> str:
    """Set system volume - platform independent."""
    level = max(0, min(100, level))  # Clamp to 0-100
    os_name = platform.system()

    if os_name == "Windows":
        return _set_volume_windows(level)
    elif os_name == "Darwin":
        return _set_volume_macos(level)
    else:
        return _set_volume_linux(level)

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_api_key() -> str:
    path = _get_base_dir() / "config" / "api_keys.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

def _get_macos_wifi_interface() -> str:
    try:
        result = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            if "Wi-Fi" in line or "AirPort" in line:
                for j in range(i, min(i + 4, len(lines))):
                    if lines[j].startswith("Device:"):
                        return lines[j].split(":", 1)[1].strip()
    except Exception:
        pass
    return "en0" 

def volume_up():
    if _OS == "Windows":
        for _ in range(5): pyautogui.press("volumeup")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            "set volume output volume (output volume of (get volume settings) + 10)"],
            capture_output=True)
    else:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"],
            capture_output=True)

def volume_down():
    if _OS == "Windows":
        for _ in range(5): pyautogui.press("volumedown")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            "set volume output volume (output volume of (get volume settings) - 10)"],
            capture_output=True)
    else:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"],
            capture_output=True)

def volume_mute():
    if _OS == "Windows":
        pyautogui.press("volumemute")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e", "set volume with output muted"],
            capture_output=True)
    else:
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
            capture_output=True)

def volume_set(value: int):
    """Set volume using the platform-independent function"""
    return set_system_volume(value)

def brightness_up():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            'tell application "System Events" to key code 144'],
            capture_output=True)
    elif _OS == "Linux":
        if subprocess.run(["which", "brightnessctl"],
                capture_output=True).returncode == 0:
            subprocess.run(["brightnessctl", "set", "+10%"], capture_output=True)
        else:
            subprocess.run(
                'xrandr --output $(xrandr | grep " connected" | head -1 | cut -d " " -f1)'
                ' --brightness $(python3 -c "import subprocess; '
                'b=float(subprocess.check_output([\"xrandr\",\"--verbose\"]).decode()'
                '.split(\"Brightness:\")[1].split()[0]); print(min(1.0,b+0.1))")',
                shell=True, capture_output=True
            )
    else:
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
                 ".WmiSetBrightness(1, [math]::Min(100, "
                 "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness + 10))"],
                capture_output=True, timeout=5
            )
        except Exception as e:
            print(f"[Settings] Brightness up failed on Windows: {e}")

def brightness_down():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            'tell application "System Events" to key code 145'],
            capture_output=True)
    elif _OS == "Linux":
        if subprocess.run(["which", "brightnessctl"],
                capture_output=True).returncode == 0:
            subprocess.run(["brightnessctl", "set", "10%-"], capture_output=True)
        else:
            subprocess.run(
                'xrandr --output $(xrandr | grep " connected" | head -1 | cut -d " " -f1)'
                ' --brightness $(python3 -c "import subprocess; '
                'b=float(subprocess.check_output([\"xrandr\",\"--verbose\"]).decode()'
                '.split(\"Brightness:\")[1].split()[0]); print(max(0.1,b-0.1))")',
                shell=True, capture_output=True
            )
    else:
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
                 ".WmiSetBrightness(1, [math]::Max(0, "
                 "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness - 10))"],
                capture_output=True, timeout=5
            )
        except Exception as e:
            print(f"[Settings] Brightness down failed on Windows: {e}")

def close_app():
    if _OS == "Darwin": pyautogui.hotkey("command", "q")
    else:               pyautogui.hotkey("alt", "f4")

def close_window():
    if _OS == "Darwin": pyautogui.hotkey("command", "w")
    else:               pyautogui.hotkey("ctrl", "w")

def full_screen():
    if _OS == "Darwin": pyautogui.hotkey("ctrl", "command", "f")
    else:               pyautogui.press("f11")

def minimize_window():
    if _OS == "Darwin": pyautogui.hotkey("command", "m")
    else:               pyautogui.hotkey("win", "down")

def maximize_window():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            'tell application "System Events" to keystroke "f" '
            'using {control down, command down}'],
            capture_output=True)
    elif _OS == "Windows":
        pyautogui.hotkey("win", "up")
    else:
        try:
            subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-b", "add,maximized_vert,maximized_horz"],
                capture_output=True)
        except Exception:
            pyautogui.hotkey("super", "up")

def snap_left():
    if _OS == "Windows":
        pyautogui.hotkey("win", "left")
    elif _OS == "Linux":
        try:
            subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-e", "0,0,0,960,1080"],
                capture_output=True)
        except Exception:
            pass

def snap_right():
    if _OS == "Windows":
        pyautogui.hotkey("win", "right")
    elif _OS == "Linux":
        try:
            subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-e", "0,960,0,960,1080"],
                capture_output=True)
        except Exception:
            pass

def switch_window():
    if _OS == "Darwin": pyautogui.hotkey("command", "tab")
    else:               pyautogui.hotkey("alt", "tab")

def show_desktop():
    if _OS == "Darwin":   pyautogui.hotkey("fn", "f11")
    elif _OS == "Windows": pyautogui.hotkey("win", "d")
    else:                  pyautogui.hotkey("super", "d")

def open_task_manager():
    if _OS == "Windows":
        pyautogui.hotkey("ctrl", "shift", "esc")
    elif _OS == "Darwin":
        subprocess.Popen(["open", "-a", "Activity Monitor"])
    else:
        for cmd in [["gnome-system-monitor"], ["xfce4-taskmanager"], ["htop"]]:
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.Popen(cmd)
                break


def focus_search():
    if _OS == "Darwin": pyautogui.hotkey("command", "l")
    else:               pyautogui.hotkey("ctrl", "l")

def pause_video():      pyautogui.press("space")

def refresh_page():
    if _OS == "Darwin": pyautogui.hotkey("command", "r")
    else:               pyautogui.press("f5")

def close_tab():
    if _OS == "Darwin": pyautogui.hotkey("command", "w")
    else:               pyautogui.hotkey("ctrl", "w")

def new_tab():
    if _OS == "Darwin": pyautogui.hotkey("command", "t")
    else:               pyautogui.hotkey("ctrl", "t")

def next_tab():
    if _OS == "Darwin": pyautogui.hotkey("command", "shift", "bracketright")
    else:               pyautogui.hotkey("ctrl", "tab")

def prev_tab():
    if _OS == "Darwin": pyautogui.hotkey("command", "shift", "bracketleft")
    else:               pyautogui.hotkey("ctrl", "shift", "tab")

def go_back():
    if _OS == "Darwin": pyautogui.hotkey("command", "left")
    else:               pyautogui.hotkey("alt", "left")

def go_forward():
    if _OS == "Darwin": pyautogui.hotkey("command", "right")
    else:               pyautogui.hotkey("alt", "right")

def zoom_in():
    if _OS == "Darwin": pyautogui.hotkey("command", "equal")
    else:               pyautogui.hotkey("ctrl", "equal")

def zoom_out():
    if _OS == "Darwin": pyautogui.hotkey("command", "minus")
    else:               pyautogui.hotkey("ctrl", "minus")

def zoom_reset():
    if _OS == "Darwin": pyautogui.hotkey("command", "0")
    else:               pyautogui.hotkey("ctrl", "0")

def find_on_page():
    if _OS == "Darwin": pyautogui.hotkey("command", "f")
    else:               pyautogui.hotkey("ctrl", "f")

def reload_page_n(n: int):
    for _ in range(max(1, n)):
        refresh_page()
        time.sleep(0.8)


def scroll_up(amount: int = 500):    pyautogui.scroll(amount)
def scroll_down(amount: int = 500):  pyautogui.scroll(-amount)

# ============================================================
# ADMIN/ADVANCED SYSTEM CONTROL FUNCTIONS
# ============================================================

def get_system_info():
    """Get comprehensive system information"""
    info = []
    info.append(f"CPU: {psutil.cpu_percent(interval=1)}% | {psutil.cpu_count()} cores")
    info.append(f"RAM: {psutil.virtual_memory().percent}% used ({psutil.virtual_memory().used // (1024**3)}/{psutil.virtual_memory().total // (1024**3)} GB)")
    info.append(f"Disk: {psutil.disk_usage('/').percent}% used")
    try:
        battery = psutil.sensors_battery()
        if battery:
            info.append(f"Battery: {battery.percent}% {'(charging)' if battery.power_plugged else ''}")
    except Exception:
        pass
    info.append(f"Platform: {_OS}")
    return " | ".join(info)

def list_processes():
    """List running processes with CPU/RAM usage"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            name = proc.info['name']
            cpu = proc.cpu_percent(interval=0.1)
            mem = proc.memory_percent()
            pid = proc.info['pid']
            if cpu > 1 or mem > 0.5:
                processes.append((cpu, mem, pid, name))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    processes.sort(reverse=True)
    result = "Top processes:\n"
    for cpu, mem, pid, name in processes[:15]:
        result += f"  {name[:30]:30s} CPU:{cpu:5.1f}% RAM:{mem:5.1f}% PID:{pid}\n"
    return result.strip()

def kill_process(name: str):
    """Kill a process by name"""
    killed = 0
    for proc in psutil.process_iter():
        try:
            if name.lower() in proc.name().lower():
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return f"Killed {killed} process(es) matching '{name}'"

def process_exists(name: str):
    """Check if a process is running"""
    for proc in psutil.process_iter():
        try:
            if name.lower() in proc.name().lower():
                return f"Yes, '{name}' is running (PID: {proc.pid})"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return f"No, '{name}' is not running"

def get_network_info():
    """Get network information"""
    info = []
    net_io = psutil.net_io_counters()
    info.append(f"Bytes sent: {net_io.bytes_sent / (1024**3):.2f} GB")
    info.append(f"Bytes recv: {net_io.bytes_recv / (1024**3):.2f} GB")
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        info.append(f"Local IP: {local_ip}")
        info.append(f"Hostname: {hostname}")
    except Exception:
        pass
    if _OS == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command", "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notmatch 'Loopback'}).IPAddress"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                info.append(f"IP addresses: {result.stdout.strip()}")
        except Exception:
            pass
    return " | ".join(info)

def get_disk_info():
    """Get disk usage information"""
    info = []
    partitions = psutil.disk_partitions()
    for part in partitions:
        try:
            usage = psutil.disk_usage(part.mountpoint)
            info.append(f"{part.device}: {usage.used // (1024**3)}/{usage.total // (1024**3)} GB ({usage.percent}%)")
        except Exception:
            pass
    return " | ".join(info) if info else "No disk info available"

def open_windows_settings(page: str):
    """Open specific Windows Settings pages"""
    if _OS != "Windows":
        return "This feature is Windows only"
    pages = {
        "wifi": "ms-settings:network",
        "bluetooth": "ms-settings:bluetooth",
        "display": "ms-settings:display",
        "sound": "ms-settings:sound",
        "notifications": "ms-settings:notifications",
        "apps": "ms-settings:appsfeatures",
        "privacy": "ms-settings:privacy",
        "network": "ms-settings:network",
        "date": "ms-settings:dateandtime",
        "power": "ms-settings:powersleep",
        "display": "ms-settings:display",
        "background": "ms-settings:background",
        "personalization": "ms-settings:personalization",
        "storage": "ms-settings:storagesense",
        "update": "ms-settings:windowsupdate",
        "security": "ms-settings:windowsdefender",
        "firewall": "ms-settings:windowsdefender",
        "accounts": "ms-settings:otherusers",
        "mouse": "ms-settings:mousetouchpad",
        "keyboard": "ms-settings:typing",
        "printer": "ms-settings:printers",
    }
    uri = pages.get(page.lower(), f"ms-settings:{page}")
    try:
        subprocess.Popen(["start", "", uri], shell=True)
        return f"Opened Settings: {page}"
    except Exception as e:
        return f"Failed to open settings: {e}"

def flush_dns():
    """Flush DNS cache"""
    if _OS == "Windows":
        try:
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
            return "DNS cache flushed successfully"
        except Exception as e:
            return f"Failed: {e}"
    else:
        try:
            subprocess.run(["sudo", "systemd-resolve", "--flush-caches"], capture_output=True)
            return "DNS cache flushed (systemd-resolve)"
        except Exception:
            try:
                subprocess.run(["sudo", "resolvectl", "flush-caches"], capture_output=True)
                return "DNS cache flushed (resolvectl)"
            except Exception as e:
                return f"Failed: {e}"

def open_control_panel(item: str):
    """Open Control Panel items"""
    if _OS != "Windows":
        return "This feature is Windows only"
    items = {
        "programs": "appwiz.cpl",
        "uninstall": "appwiz.cpl",
        "device_manager": "devmgmt.msc",
        "devices": "devmgmt.msc",
        "services": "services.msc",
        "task_manager": "taskmgr.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
        "regedit": "regedit.exe",
        "disk": "diskmgmt.msc",
        "firewall": "wf.msc",
        "security": "wscui.cpl",
        "system": "sysdm.cpl",
        "environment": "systempropertiesadvanced.exe",
        "remote": "sysdm.cpl",  # remote tab
    }
    item_lower = item.lower()
    if item_lower in items:
        try:
            subprocess.Popen(["start", "", items[item_lower]], shell=True)
            return f"Opened: {item}"
        except Exception as e:
            return f"Failed: {e}"
    return f"Unknown Control Panel item: {item}"

def get_startup_programs():
    """List programs that run at startup"""
    if _OS == "Windows":
        result = []
        try:
            # Check Registry Run keys
            import winreg
            run_keys = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            ]
            for hkey, path in run_keys:
                try:
                    key = winreg.OpenKey(hkey, path)
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            result.append(f"  {name}: {value}")
                            i += 1
                        except WindowsError:
                            break
                    winreg.CloseKey(key)
                except Exception:
                    pass
            # Check Startup folder
            startup_folder = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            if startup_folder.exists():
                for f in startup_folder.iterdir():
                    result.append(f"  [Startup folder] {f.name}")
        except Exception as e:
            return f"Error: {e}"
        return "Startup programs:\n" + "\n".join(result) if result else "No startup programs found"
    return "This feature is Windows only"

def toggle_startup_program(name: str, enable: bool):
    """Enable or disable a startup program (Windows Registry)"""
    if _OS != "Windows":
        return "This feature is Windows only"
    try:
        import winreg
        path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            return "Note: Adding to startup requires the program path. Use remove_startup to disable."
        else:
            try:
                winreg.DeleteValue(key, name)
                return f"Disabled startup program: {name}"
            except FileNotFoundError:
                return f"Startup entry not found: {name}"
    except Exception as e:
        return f"Failed: {e}"


def add_jarvis_to_startup():
    """Add JARVIS to Windows startup"""
    if _OS != "Windows":
        return "This feature is Windows only"
    try:
        import winreg
        import os as os_module
        jarvis_path = sys.executable if getattr(sys, 'frozen', False) else sys.executable
        # Try to find pythonw.exe for the script
        if getattr(sys, 'frozen', False):
            exe_path = jarvis_path
        else:
            exe_path = sys.executable.replace("python.exe", "pythonw.exe")
            if not os_module.path.exists(exe_path):
                exe_path = jarvis_path

        script_path = Path(__file__).resolve().parent.parent / "main.py"
        startup_cmd = f'"{exe_path}" "{script_path}"'

        path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "J.A.R.V.I.S", 0, winreg.REG_SZ, startup_cmd)
        winreg.CloseKey(key)
        return "J.A.R.V.I.S. added to Windows startup. It will launch when you log in."
    except Exception as e:
        return f"Failed to add to startup: {e}"


def remove_jarvis_from_startup():
    """Remove JARVIS from Windows startup"""
    if _OS != "Windows":
        return "This feature is Windows only"
    try:
        import winreg
        path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, "J.A.R.V.I.S")
            winreg.CloseKey(key)
            return "J.A.R.V.I.S. removed from Windows startup."
        except FileNotFoundError:
            winreg.CloseKey(key)
            return "J.A.R.V.I.S. was not in Windows startup."
    except Exception as e:
        return f"Failed to remove from startup: {e}"


def is_jarvis_in_startup():
    """Check if JARVIS is in Windows startup"""
    if _OS != "Windows":
        return "This feature is Windows only"
    try:
        import winreg
        path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, "J.A.R.V.I.S")
            winreg.CloseKey(key)
            return f"J.A.R.V.I.S. is in startup: {value}"
        except FileNotFoundError:
            winreg.CloseKey(key)
            return "J.A.R.V.I.S. is NOT in Windows startup."
    except Exception as e:
        return f"Failed to check startup: {e}"


def get_startup_location():
    """Get the actual path where JARVIS would launch from"""
    if getattr(sys, 'frozen', False):
        return sys.executable
    script_path = Path(__file__).resolve().parent.parent / "main.py"
    exe_path = sys.executable.replace("python.exe", "pythonw.exe")
    if Path(exe_path).exists():
        return f'"{exe_path}" "{script_path}"'
    return f'"{sys.executable}" "{script_path}"'

def clear_clipboard():
    """Clear the system clipboard"""
    try:
        if _PYPERCLIP:
            pyperclip.copy("")
        elif _OS == "Windows":
            subprocess.run(["cmd", "/c", "echo off | clip"], capture_output=True)
        return "Clipboard cleared"
    except Exception as e:
        return f"Failed: {e}"

def show_clipboard():
    """Show current clipboard content"""
    try:
        if _PYPERCLIP:
            content = pyperclip.paste()
            if content:
                return f"Clipboard: {content[:500]}{'...' if len(content) > 500 else ''}"
            return "Clipboard is empty"
        return "pyperclip not available"
    except Exception as e:
        return f"Failed: {e}"

def get_windows_services():
    """List Windows services"""
    if _OS != "Windows":
        return "This feature is Windows only"
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object -First 20 Name,DisplayName,Status | Format-Table -AutoSize"],
            capture_output=True, text=True, timeout=10
        )
        return f"Running services:\n{result.stdout}"
    except Exception as e:
        return f"Failed: {e}"

def get_env_vars():
    """Get environment variables"""
    vars_to_show = ["PATH", "USERNAME", "COMPUTERNAME", "USERPROFILE", "TEMP", "SYSTEMROOT"]
    result = []
    for var in vars_to_show:
        val = os.environ.get(var, "(not set)")
        result.append(f"  {var}: {val}")
    return "\n".join(result)

def open_calculator():
    """Open calculator"""
    if _OS == "Windows":
        subprocess.Popen(["calc.exe"])
    elif _OS == "Darwin":
        subprocess.Popen(["open", "-a", "Calculator"])
    else:
        subprocess.Popen(["gnome-calculator"])
    return "Calculator opened"

def open_notepad(text: str = ""):
    """Open Notepad, optionally with text"""
    if _OS == "Windows":
        if text:
            temp_file = Path(os.environ.get("TEMP", "/tmp")) / "jarvis_note.txt"
            temp_file.write_text(text)
            subprocess.Popen(["notepad.exe", str(temp_file)])
        else:
            subprocess.Popen(["notepad.exe"])
    elif _OS == "Darwin":
        subprocess.Popen(["open", "-a", "TextEdit"])
    else:
        subprocess.Popen(["gedit"] if subprocess.run(["which", "gedit"], capture_output=True).returncode == 0 else ["nano"])
    return f"Notepad opened{' with content' if text else ''}"

def hibernate():
    """Put computer into hibernate mode"""
    if _OS == "Windows":
        subprocess.run(["shutdown", "/h"], capture_output=True)
    elif _OS == "Darwin":
        subprocess.run(["pmset", "hibernate"], capture_output=True)
    else:
        subprocess.run(["systemctl", "hibernate"], capture_output=True)
    return "Hibernating..."

def get_cpu_temp():
    """Get CPU temperature if available"""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            result = []
            for name, entries in temps.items():
                for entry in entries:
                    result.append(f"{entry.label or name}: {entry.current}°C")
            return " | ".join(result) if result else "No temperature data"
    except Exception:
        pass
    return "Temperature data not available"

def get_battery_status():
    """Get detailed battery status"""
    try:
        battery = psutil.sensors_battery()
        if battery:
            status = []
            status.append(f"Charge: {battery.percent}%")
            status.append(f"Plugged: {'Yes' if battery.power_plugged else 'No'}")
            if hasattr(battery, 'secsleft') and battery.secsleft != psutil.POWER_TIME_UNLIMITED:
                hours = battery.secsleft // 3600
                mins = (battery.secsleft % 3600) // 60
                status.append(f"Time left: {hours}h {mins}m")
            return " | ".join(status)
    except Exception:
        pass
    return "No battery detected"

def get_volume_status():
    """Get current volume level"""
    if _OS == "Windows":
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(interface, POINTER(IAudioEndpointVolume))
            level = vol.GetMasterVolumeLevelScalar() * 100
            muted = vol.GetMute()
            return f"Volume: {int(level)}% | Muted: {'Yes' if muted else 'No'}"
        except Exception:
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "(Get-AudioDevice -PlaybackVolume / 100)"],
                    capture_output=True, text=True, timeout=5
                )
                return result.stdout.strip() or "Volume info unavailable"
            except Exception:
                return "Volume control unavailable"
    elif _OS == "Darwin":
        try:
            result = subprocess.run(
                ["osascript", "-e", "output volume of (get volume settings)"],
                capture_output=True, text=True, timeout=5
            )
            vol = result.stdout.strip()
            muted = "output muted of (get volume settings)"
            result2 = subprocess.run(
                ["osascript", "-e", muted],
                capture_output=True, text=True, timeout=5
            )
            muted_state = result2.stdout.strip()
            return f"Volume: {vol}% | Muted: {muted_state}"
        except Exception:
            pass
    return "Volume status unavailable"

def get_brightness_status():
    """Get current brightness level"""
    if _OS == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                return f"Brightness: {result.stdout.strip()}%"
        except Exception:
            pass
        return "Brightness info unavailable"
    elif _OS == "Darwin":
        try:
            result = subprocess.run(
                ["brightness", "-l"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if "display 0" in line.lower():
                    parts = line.split(':')
                    if len(parts) > 1:
                        val = parts[1].strip().split()[0]
                        return f"Brightness: {float(val)*100:.0f}%"
        except Exception:
            pass
    return "Brightness status unavailable"

def get_wifi_networks():
    """List available WiFi networks"""
    if _OS == "Windows":
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True, text=True, timeout=15
            )
            return result.stdout
        except Exception as e:
            return f"Failed: {e}"
    elif _OS == "Darwin":
        try:
            result = subprocess.run(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-s"],
                capture_output=True, text=True, timeout=15
            )
            return result.stdout
        except Exception:
            pass
    return "WiFi scan not available"

def get_wifi_status():
    """Get current WiFi connection status"""
    if _OS == "Windows":
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout
            info = []
            for line in output.split('\n'):
                line = line.strip()
                if any(x in line for x in ["SSID", "State", "Signal", "Channel", "Radio type"]):
                    info.append(line)
            return " | ".join(info) if info else "WiFi disconnected"
        except Exception as e:
            return f"Failed: {e}"
    elif _OS == "Darwin":
        try:
            result = subprocess.run(
                ["networksetup", "-getairportnetwork", "en0"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except Exception:
            pass
    return "WiFi status unavailable"

def get_bluetooth_status():
    """Get Bluetooth status"""
    if _OS == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PnpDevice -Class Bluetooth | Select-Object Status, FriendlyName | Format-Table -AutoSize"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip() or "No Bluetooth devices"
        except Exception:
            pass
    return "Bluetooth status unavailable"

def get_all_settings_status():
    """Get all system settings at once"""
    results = []
    results.append(f"=== SYSTEM STATUS ===")
    results.append(get_system_info())
    results.append("")
    results.append(f"=== VOLUME ===")
    results.append(get_volume_status())
    results.append("")
    results.append(f"=== BRIGHTNESS ===")
    results.append(get_brightness_status())
    results.append("")
    results.append(f"=== BATTERY ===")
    results.append(get_battery_status())
    results.append("")
    results.append(f"=== NETWORK ===")
    results.append(get_wifi_status())
    results.append("")
    results.append(f"=== DISK ===")
    results.append(get_disk_info())
    return "\n".join(results)

def set_power_plan(plan: str):
    """Set Windows power plan (balanced, high performance, power saver)"""
    if _OS != "Windows":
        return "This feature is Windows only"
    plans = {
        "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
        "high": "8c5e7fda-a8bf-4cf1-8b9f-81f9c8a3e1c0",
        "power": "a1841308-3541-4fab-bc81-f71556f20b4a",
    }
    guid = plans.get(plan.lower())
    if not guid:
        return f"Unknown plan: {plan}. Options: balanced, high (performance), power (saver)"
    try:
        subprocess.run(["powercfg", "/setactive", guid], capture_output=True, timeout=10)
        return f"Power plan set to: {plan}"
    except Exception as e:
        return f"Failed: {e}"

def kill_by_port(port: int):
    """Kill process using a specific port"""
    if _OS == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command", f"(Get-NetTCPConnection -LocalPort {port}).OwningProcess"],
                capture_output=True, text=True, timeout=5
            )
            pids = [int(p) for p in result.stdout.strip().split('\n') if p.strip().isdigit()]
            killed = 0
            for pid in pids:
                try:
                    psutil.Process(pid).kill()
                    killed += 1
                except Exception:
                    pass
            return f"Killed {killed} process(es) on port {port}"
        except Exception as e:
            return f"Failed: {e}"
    else:
        try:
            result = subprocess.run(["lsof", "-t", f"-i:{port}"], capture_output=True, text=True)
            pids = [int(p) for p in result.stdout.strip().split('\n') if p.strip().isdigit()]
            killed = 0
            for pid in pids:
                try:
                    psutil.Process(pid).kill()
                    killed += 1
                except Exception:
                    pass
            return f"Killed {killed} process(es) on port {port}"
        except Exception as e:
            return f"Failed: {e}"

def open_terminal():
    """Open terminal/command prompt"""
    if _OS == "Windows":
        subprocess.Popen(["start", "cmd"], shell=True)
    elif _OS == "Darwin":
        subprocess.Popen(["open", "-a", "Terminal"])
    else:
        for term in ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"]:
            if subprocess.run(["which", term], capture_output=True).returncode == 0:
                subprocess.Popen([term])
                break
    return "Terminal opened"


def open_neural_map():
    """Open the neural memory map in browser"""
    try:
        import webbrowser
        base_dir = Path(__file__).resolve().parent.parent
        html_path = base_dir / "memory_map.html"
        if html_path.exists():
            webbrowser.open(f"file:///{html_path.absolute()}")
            return "Neural Memory Map opened in browser."
        else:
            return "Memory map file not found. It will be generated next time JARVIS runs."
    except Exception as e:
        return f"Failed to open neural map: {e}"

def open_explorer(path: str = ""):
    """Open File Explorer at path"""
    if _OS == "Windows":
        if path:
            subprocess.Popen(["explorer", path])
        else:
            subprocess.Popen(["explorer"])
    elif _OS == "Darwin":
        subprocess.Popen(["open", path or str(Path.home())])
    else:
        for fm in ["nautilus", "dolphin", "thunar", "nemo"]:
            if subprocess.run(["which", fm], capture_output=True).returncode == 0:
                subprocess.Popen([fm, path or str(Path.home())])
                break
    return f"Explorer opened{' at ' + path if path else ''}"

def scroll_top():
    if _OS == "Darwin": pyautogui.hotkey("command", "up")
    else:               pyautogui.hotkey("ctrl", "home")

def scroll_bottom():
    if _OS == "Darwin": pyautogui.hotkey("command", "down")
    else:               pyautogui.hotkey("ctrl", "end")

def page_up():   pyautogui.press("pageup")
def page_down(): pyautogui.press("pagedown")


def copy():
    if _OS == "Darwin": pyautogui.hotkey("command", "c")
    else:               pyautogui.hotkey("ctrl", "c")

def paste():
    if _OS == "Darwin": pyautogui.hotkey("command", "v")
    else:               pyautogui.hotkey("ctrl", "v")

def cut():
    if _OS == "Darwin": pyautogui.hotkey("command", "x")
    else:               pyautogui.hotkey("ctrl", "x")

def undo():
    if _OS == "Darwin": pyautogui.hotkey("command", "z")
    else:               pyautogui.hotkey("ctrl", "z")

def redo():
    if _OS == "Darwin": pyautogui.hotkey("command", "shift", "z")
    else:               pyautogui.hotkey("ctrl", "y")

def select_all():
    if _OS == "Darwin": pyautogui.hotkey("command", "a")
    else:               pyautogui.hotkey("ctrl", "a")

def save_file():
    if _OS == "Darwin": pyautogui.hotkey("command", "s")
    else:               pyautogui.hotkey("ctrl", "s")

def press_enter():   pyautogui.press("enter")
def press_escape():  pyautogui.press("escape")
def press_key(key: str): pyautogui.press(key)

def type_text(text: str, press_enter_after: bool = False):
    if not text:
        return
    if _PYPERCLIP:
        pyperclip.copy(str(text))
        time.sleep(0.15)
        paste()
    else:
        pyautogui.write(str(text), interval=0.03)
    if press_enter_after:
        time.sleep(0.1)
        pyautogui.press("enter")

def take_screenshot():
    if _OS == "Windows":
        pyautogui.hotkey("win", "shift", "s")
    elif _OS == "Darwin":
        pyautogui.hotkey("command", "shift", "3")
    else:
        for cmd in [["scrot"], ["gnome-screenshot"], ["import", "-window", "root", "screenshot.png"]]:
            if subprocess.run(["which", cmd[0]], capture_output=True).return_code == 0:
                subprocess.Popen(cmd)
                return
        pyautogui.hotkey("ctrl", "print_screen")

def screen_off():
    """Turn off the screen"""
    if _OS == "Windows":
        # Send message to turn off monitor
        subprocess.run(
            ["powershell", "-Command", "(Add-Type -MemberDefinition '[DllImport(\"user32.dll\")]public static extern int SendMessage(int hWnd,int msg,int wParam,int lParam);' -Name WinAPI -Namespace PInvoke)::SendMessage(-1,0x0112,0xF170,2)"],
            capture_output=True
        )
    elif _OS == "Darwin":
        subprocess.run(["pmset", "displaysleepnow"], capture_output=True)
    else:
        subprocess.run(["xset", "dpms", "force", "off"], capture_output=True)
    return "Screen turned off"

def screen_on():
    """Turn on / wake up the screen"""
    if _OS == "Windows":
        # Move mouse slightly to wake up
        pyautogui.move(1, 0)
        pyautogui.move(-1, 0)
    elif _OS == "Darwin":
        subprocess.run(["pmset", "displaysleepnow"], capture_output=True)
    else:
        subprocess.run(["xset", "dpms", "force", "on"], capture_output=True)
    return "Screen turned on"

def empty_trash():
    """Empty the Windows Recycle Bin"""
    if _OS == "Windows":
        try:
            # Method 1: PowerShell with bypass
            result = subprocess.run(
                ["powershell", "-Command",
                 "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return "Recycle Bin emptied successfully."
        except Exception:
            pass
        try:
            # Method 2: Shell32 API
            import ctypes
            # 0x00000006 = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000006)
            return "Recycle Bin emptied successfully."
        except Exception as e:
            return f"Failed to empty Recycle Bin: {e}"
    elif _OS == "Darwin":
        try:
            subprocess.run(["rm", "-rf", "$HOME/.Trash/*"], shell=True, capture_output=True)
            return "Trash emptied successfully."
        except Exception as e:
            return f"Failed: {e}"
    else:
        try:
            subprocess.run(["trash-empty"], capture_output=True)
            return "Trash emptied successfully."
        except Exception:
            return "Linux trash emptying not supported via CLI. Use file manager."

def lock_screen():
    if _OS == "Windows":
        pyautogui.hotkey("win", "l")
    elif _OS == "Darwin":
        subprocess.run(["pmset", "displaysleepnow"], capture_output=True)
    else:
        for cmd in [
            ["gnome-screensaver-command", "-l"],
            ["xdg-screensaver", "lock"],
            ["loginctl", "lock-session"],
        ]:
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.run(cmd, capture_output=True)
                return

def open_system_settings():
    if _OS == "Windows":
        pyautogui.hotkey("win", "i")
    elif _OS == "Darwin":
        subprocess.Popen(["open", "-a", "System Preferences"])
    else:
        for cmd in [["gnome-control-center"], ["xfce4-settings-manager"], ["kcmshell5"]]:
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.Popen(cmd)
                return

def open_file_explorer():
    if _OS == "Windows":
        pyautogui.hotkey("win", "e")
    elif _OS == "Darwin":
        subprocess.Popen(["open", str(Path.home())])
    else:
        for cmd in [["nautilus"], ["thunar"], ["dolphin"], ["nemo"]]:
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.Popen(cmd)
                return
        subprocess.Popen(["xdg-open", str(Path.home())])

def sleep_display():
    if _OS == "Windows":
        try:
            import ctypes
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        except Exception as e:
            print(f"[Settings] sleep_display failed: {e}")
    elif _OS == "Darwin":
        subprocess.run(["pmset", "displaysleepnow"], capture_output=True)
    else:
        subprocess.run(["xset", "dpms", "force", "off"], capture_output=True)

def open_run():
    if _OS == "Windows":
        pyautogui.hotkey("win", "r")

def set_brightness(level: int):
    """Set brightness to specific level (0-100)"""
    level = max(0, min(100, int(level)))
    if _OS == "Windows":
        try:
            subprocess.run(
                ["powershell", "-Command",
                 f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"],
                capture_output=True, timeout=5
            )
            return f"Brightness set to {level}%"
        except Exception as e:
            return f"Failed: {e}"
    elif _OS == "Darwin":
        try:
            subprocess.run(["brightness", str(level / 100)], capture_output=True)
            return f"Brightness set to {level}%"
        except Exception as e:
            return f"Failed: {e}"
    else:
        if subprocess.run(["which", "brightnessctl"], capture_output=True).returncode == 0:
            subprocess.run(["brightnessctl", "set", f"{level}%"], capture_output=True)
            return f"Brightness set to {level}%"
        return "Brightness control not available"

def dark_mode():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            'tell app "System Events" to tell appearance preferences '
            'to set dark mode to not dark mode'],
            capture_output=True)
    elif _OS == "Windows":
        try:
            import winreg
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            current, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, 1 - current)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, 1 - current)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[Settings] dark_mode registry failed: {e}")
    else:
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True
            )
            current = result.stdout.strip()
            new_scheme = "'default'" if "dark" in current else "'prefer-dark'"
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", new_scheme],
                capture_output=True
            )
        except Exception as e:
            print(f"[Settings] dark_mode Linux failed: {e}")

def toggle_bluetooth():
    """Toggle Bluetooth on/off"""
    if _OS == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "$bt = Get-PnpDevice -Class Bluetooth -Status OK; "
                 "if ($bt[0].Present) { Disable-PnpDevice -Id $bt[0].InstanceId -Confirm:$false } "
                 "else { Enable-PnpDevice -Id $bt[0].InstanceId -Confirm:$false }"],
                capture_output=True, timeout=10
            )
            return "Bluetooth toggled"
        except Exception as e:
            return f"Failed: {e}"
    elif _OS == "Darwin":
        try:
            result = subprocess.run(
                ["blueutil", "-p", "toggle"],
                capture_output=True, timeout=5
            )
            return "Bluetooth toggled"
        except Exception:
            return "blueutil not installed"
    return "Bluetooth toggle not supported"

def open_app(app_name: str):
    """Open an application by name"""
    if _OS == "Windows":
        try:
            subprocess.Popen(["start", "", app_name], shell=True)
            return f"Opened: {app_name}"
        except Exception as e:
            return f"Failed: {e}"
    elif _OS == "Darwin":
        try:
            subprocess.Popen(["open", "-a", app_name])
            return f"Opened: {app_name}"
        except Exception as e:
            return f"Failed: {e}"
    return "Not supported on this OS"

def set_window_size(width: int, height: int):
    """Resize the active window to specific dimensions"""
    if _PYAUTOGUI:
        pyautogui.hotkey("alt", "space")
        time.sleep(0.1)
        pyautogui.press("s")
        time.sleep(0.2)
        type_text(f"{width}", press_enter_after=False)
        time.sleep(0.1)
        type_text(f"{height}", press_enter_after=True)
        return f"Window resized to {width}x{height}"
    return "pyautogui not available"

def move_window(x: int, y: int):
    """Move the active window to specific position"""
    if _PYAUTOGUI:
        pyautogui.hotkey("alt", "space")
        time.sleep(0.1)
        pyautogui.press("m")
        time.sleep(0.2)
        pyautogui.press("left")
        time.sleep(0.1)
        type_text(f"{x}", press_enter_after=False)
        time.sleep(0.1)
        type_text(f"{y}", press_enter_after=True)
        return f"Window moved to ({x}, {y})"
    return "pyautogui not available"

def open_url(url: str):
    """Open a URL in the default browser"""
    try:
        import webbrowser
        webbrowser.open(url)
        return f"Opened: {url}"
    except Exception as e:
        return f"Failed: {e}"

def click_at(x: int, y: int):
    """Click at specific screen coordinates"""
    if _PYAUTOGUI:
        pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})"
    return "pyautogui not available"

def double_click_at(x: int, y: int):
    """Double-click at specific screen coordinates"""
    if _PYAUTOGUI:
        pyautogui.doubleClick(x, y)
        return f"Double-clicked at ({x}, {y})"
    return "pyautogui not available"

def right_click_at(x: int, y: int):
    """Right-click at specific screen coordinates"""
    if _PYAUTOGUI:
        pyautogui.rightClick(x, y)
        return f"Right-clicked at ({x}, {y})"
    return "pyautogui not available"

def mouse_move(x: int, y: int):
    """Move mouse to specific coordinates"""
    if _PYAUTOGUI:
        pyautogui.moveTo(x, y)
        return f"Moved to ({x}, {y})"
    return "pyautogui not available"

def mouse_click():
    """Click at current mouse position"""
    if _PYAUTOGUI:
        pyautogui.click()
        return "Mouse clicked"
    return "pyautogui not available"

def mouse_double_click():
    """Double-click at current mouse position"""
    if _PYAUTOGUI:
        pyautogui.doubleClick()
        return "Mouse double-clicked"
    return "pyautogui not available"

def mouse_right_click():
    """Right-click at current mouse position"""
    if _PYAUTOGUI:
        pyautogui.rightClick()
        return "Mouse right-clicked"
    return "pyautogui not available"

def open_program_settings():
    """Open Programs and Features (Uninstall programs)"""
    if _OS == "Windows":
        subprocess.Popen(["control", "appwiz.cpl"])
    return "Opened Programs"

def open_device_manager():
    """Open Windows Device Manager"""
    if _OS == "Windows":
        subprocess.Popen(["devmgmt.msc"])
    return "Opened Device Manager"

def open_disk_management():
    """Open Windows Disk Management"""
    if _OS == "Windows":
        subprocess.Popen(["diskmgmt.msc"])
    return "Opened Disk Management"

def open_firewall():
    """Open Windows Firewall"""
    if _OS == "Windows":
        subprocess.Popen(["wf.msc"])
    return "Opened Firewall"

def open_environment_vars():
    """Open Windows Environment Variables"""
    if _OS == "Windows":
        subprocess.Popen(["systempropertiesadvanced.exe"])
    return "Opened Environment Variables"

def open_user_accounts():
    """Open Windows User Accounts settings"""
    if _OS == "Windows":
        subprocess.Popen(["netplwiz.exe"])
    return "Opened User Accounts"

def open_power_options():
    """Open Windows Power Options"""
    if _OS == "Windows":
        subprocess.Popen(["powercfg.cpl"])
    return "Opened Power Options"

def open_date_time():
    """Open Windows Date and Time settings"""
    if _OS == "Windows":
        subprocess.Popen(["timedate.cpl"])
    return "Opened Date and Time"

def open_region_settings():
    """Open Windows Region settings"""
    if _OS == "Windows":
        subprocess.Popen(["intl.cpl"])
    return "Opened Region Settings"

def eject_drive():
    """Eject all removable drives"""
    if _OS == "Windows":
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "Get-WmiObject -Class Win32_LogicalDisk -Filter 'DriveType=2' | ForEach-Object { $_.Eject() }"],
                capture_output=True, timeout=10
            )
            return "Ejecting drives..."
        except Exception as e:
            return f"Failed: {e}"
    return "Not supported"

def get_screen_resolution():
    """Get screen resolution"""
    if _PYAUTOGUI:
        size = pyautogui.size()
        return f"Screen: {size.width}x{size.height}"
    return "pyautogui not available"

def get_cursor_position():
    """Get current cursor position"""
    if _PYAUTOGUI:
        x, y = pyautogui.position()
        return f"Cursor at: ({x}, {y})"
    return "pyautogui not available"

def toggle_wifi():
    if _OS == "Darwin":
        iface = _get_macos_wifi_interface()
        result = subprocess.run(
            ["networksetup", "-getairportpower", iface],
            capture_output=True, text=True
        )
        state = "off" if "On" in result.stdout else "on"
        subprocess.run(["networksetup", "-setairportpower", iface, state],
            capture_output=True)
    elif _OS == "Windows":
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "$adapter = Get-NetAdapter | Where-Object {$_.PhysicalMediaType -eq 'Native 802.11'};"
                 "if ($adapter.Status -eq 'Up') { Disable-NetAdapter -Name $adapter.Name -Confirm:$false }"
                 "else { Enable-NetAdapter -Name $adapter.Name -Confirm:$false }"],
                capture_output=True, timeout=10
            )
        except Exception as e:
            print(f"[Settings] toggle_wifi Windows failed: {e}")
    else:
        try:
            result = subprocess.run(["nmcli", "radio", "wifi"], capture_output=True, text=True)
            state  = "off" if "enabled" in result.stdout else "on"
            subprocess.run(["nmcli", "radio", "wifi", state], capture_output=True)
        except Exception as e:
            print(f"[Settings] toggle_wifi Linux failed: {e}")

def restart_computer():
    if _OS == "Windows":
        subprocess.run(["shutdown", "/r", "/t", "10"], capture_output=True)
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            'tell application "System Events" to restart'],
            capture_output=True)
    else:
        subprocess.run(["systemctl", "reboot"], capture_output=True)

def shutdown_computer():
    if _OS == "Windows":
        subprocess.run(["shutdown", "/s", "/t", "10"], capture_output=True)
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            'tell application "System Events" to shut down'],
            capture_output=True)
    else:
        subprocess.run(["systemctl", "poweroff"], capture_output=True)

ACTION_MAP: dict[str, callable] = {
    "volume_up":           volume_up,
    "volume_down":         volume_down,
    "mute":                volume_mute,
    "unmute":              volume_mute,
    "toggle_mute":         volume_mute,
    "brightness_up":       brightness_up,
    "brightness_down":     brightness_down,
    "sleep_display":       sleep_display,
    "screen_off":          sleep_display,
    "pause_video":         pause_video,
    "play_pause":          pause_video,
    "close_app":           close_app,
    "close_window":        close_window,
    "full_screen":         full_screen,
    "fullscreen":          full_screen,
    "minimize":            minimize_window,
    "maximize":            maximize_window,
    "snap_left":           snap_left,
    "snap_right":          snap_right,
    "switch_window":       switch_window,
    "show_desktop":        show_desktop,
    "task_manager":        open_task_manager,
    "focus_search":        focus_search,
    "refresh_page":        refresh_page,
    "reload":              refresh_page,
    "close_tab":           close_tab,
    "new_tab":             new_tab,
    "next_tab":            next_tab,
    "prev_tab":            prev_tab,
    "go_back":             go_back,
    "go_forward":          go_forward,
    "zoom_in":             zoom_in,
    "zoom_out":            zoom_out,
    "zoom_reset":          zoom_reset,
    "find_on_page":        find_on_page,
    "scroll_up":           scroll_up,
    "scroll_down":         scroll_down,
    "scroll_top":          scroll_top,
    "scroll_bottom":       scroll_bottom,
    "page_up":             page_up,
    "page_down":           page_down,
    "copy":                copy,
    "paste":               paste,
    "cut":                 cut,
    "undo":                undo,
    "redo":                redo,
    "select_all":          select_all,
    "save":                save_file,
    "enter":               press_enter,
    "escape":              press_escape,
    "screenshot":          take_screenshot,
    "lock_screen":         lock_screen,
    "open_settings":       open_system_settings,
    "file_explorer":       open_file_explorer,
    "open_run":            open_run,
    "dark_mode":           dark_mode,
    "toggle_wifi":         toggle_wifi,
    "restart":             restart_computer,
    "shutdown":            shutdown_computer,
    # ADMIN/ADVANCED FUNCTIONS
    "system_info":         get_system_info,
    "sysinfo":             get_system_info,
    "info":                get_system_info,
    "processes":           list_processes,
    "list_processes":      list_processes,
    "tasks":               list_processes,
    "kill_process":        kill_process,
    "kill":                kill_process,
    "process_exists":      process_exists,
    "is_running":          process_exists,
    "network_info":        get_network_info,
    "netinfo":             get_network_info,
    "net":                 get_network_info,
    "disk_info":           get_disk_info,
    "disks":               get_disk_info,
    "settings_page":       open_windows_settings,
    "open_settings_page":  open_windows_settings,
    "windows_settings":    open_windows_settings,
    "wifi_settings":       lambda: open_windows_settings("wifi"),
    "display_settings":    lambda: open_windows_settings("display"),
    "sound_settings":      lambda: open_windows_settings("sound"),
    "flush_dns":           flush_dns,
    "dns_flush":           flush_dns,
    "control_panel":       open_control_panel,
    "services":            get_windows_services,
    "windows_services":    get_windows_services,
    "startup_programs":    get_startup_programs,
    "startup":             get_startup_programs,
    "env_vars":            get_env_vars,
    "environment":         get_env_vars,
    "calculator":          open_calculator,
    "calc":                open_calculator,
    "notepad":             open_notepad,
    "note":                open_notepad,
    "hibernate":           hibernate,
    "cpu_temp":            get_cpu_temp,
    "temperature":         get_cpu_temp,
    "battery":             get_battery_status,
    "battery_status":       get_battery_status,
    "power_plan":          set_power_plan,
    "power":               set_power_plan,
    "kill_port":           kill_by_port,
    "port_kill":           kill_by_port,
    "terminal":            open_terminal,
    "cmd":                 open_terminal,
    "explorer":            open_explorer,
    "open_explorer":       open_explorer,
    "clipboard_clear":     clear_clipboard,
    "clear_clipboard":     clear_clipboard,
    "clipboard_show":      show_clipboard,
    "show_clipboard":      show_clipboard,
    "clipboard":           show_clipboard,
    "empty_trash":        empty_trash,
    "clear_trash":        empty_trash,
    "empty_recycle_bin":  empty_trash,
    # STARTUP MANAGEMENT
    "add_to_startup":      add_jarvis_to_startup,
    "remove_from_startup": remove_jarvis_from_startup,
    "check_startup":      is_jarvis_in_startup,
    "startup_status":      is_jarvis_in_startup,
    "enable_startup":     add_jarvis_to_startup,
    "disable_startup":    remove_jarvis_from_startup,
    # NEURAL MAP
    "open_neural_map":    open_neural_map,
    "open_memory_map":     open_neural_map,
    "show_memory_map":    open_neural_map,
    "memory_visualizer":   open_neural_map,
    # STATUS/INFO FUNCTIONS
    "volume_status":      get_volume_status,
    "brightness_status":   get_brightness_status,
    "wifi_status":         get_wifi_status,
    "bluetooth_status":    get_bluetooth_status,
    "wifi_networks":       get_wifi_networks,
    "scan_wifi":           get_wifi_networks,
    "all_status":          get_all_settings_status,
    "full_status":         get_all_settings_status,
    "status":              get_all_settings_status,
    # NEW FUNCTIONS - System Control
    "brightness":           set_brightness,
    "set_brightness":       set_brightness,
    "toggle_bluetooth":     toggle_bluetooth,
    "bluetooth":            toggle_bluetooth,
    "open_app":            open_app,
    "open_application":     open_app,
    "launch":              open_app,
    "window_size":         set_window_size,
    "resize_window":       set_window_size,
    "move_window":         move_window,
    "open_url":            open_url,
    "open_link":           open_url,
    "click_at":            click_at,
    "click":               mouse_click,
    "double_click":        mouse_double_click,
    "right_click":         mouse_right_click,
    "mouse_move":          mouse_move,
    "cursor_position":     get_cursor_position,
    "screen_resolution":   get_screen_resolution,
    "programs":            open_program_settings,
    "uninstall":          open_program_settings,
    "device_manager":      open_device_manager,
    "disk_management":     open_disk_management,
    "firewall":            open_firewall,
    "environment_vars":    open_environment_vars,
    "user_accounts":       open_user_accounts,
    "power_options":       open_power_options,
    "date_time":           open_date_time,
    "region":              open_region_settings,
    "eject":               eject_drive,
    "eject_drives":        eject_drive,
    # Mouse at current position
    "mouse_click":         mouse_click,
    "mouse_double_click":  mouse_double_click,
    "mouse_right_click":   mouse_right_click,
}

_DANGEROUS_ACTIONS = {"restart", "shutdown", "hibernate", "kill_process", "kill", "kill_port", "port_kill"}



def _detect_action(description: str) -> dict:

    from google import genai
    client = genai.Client(api_key=_get_api_key())

    available = ", ".join(sorted(ACTION_MAP.keys())) + \
                ", volume_set, type_text, press_key, reload_n, open_settings_page, kill_process, process_exists, set_power_plan"

    prompt = f"""You are an intent detector for a computer control assistant.

The user issued a command (possibly in any language): "{description}"

Available actions: {available}

Return ONLY a valid JSON object:
{{"action": "action_name", "value": null_or_value}}

Rules:
- Pick the single best matching action from the available list.
- For volume_set: value is an integer 0-100.
- For type_text: value is the exact text to type.
- For press_key: value is the key name (e.g. "f5", "tab", "enter").
- For reload_n: value is an integer (number of times to reload).
- If no clear match, pick the closest action.
- Return ONLY the JSON, no explanation, no markdown."""

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )
        text = re.sub(r"```(?:json)?", "", resp.text).strip().rstrip("`").strip()
        return json.loads(text)
    except Exception as e:
        print(f"[Settings] Intent detection failed: {e}")
        return {"action": description.lower().replace(" ", "_"), "value": None}

def computer_settings(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    if not _PYAUTOGUI:
        return "pyautogui is not installed. Run: pip install pyautogui"

    params      = parameters or {}
    raw_action  = params.get("action", "").strip()
    description = params.get("description", "").strip()
    value       = params.get("value", None)

    if not raw_action and description:
        detected   = _detect_action(description)
        raw_action = detected.get("action", "")
        if value is None:
            value = detected.get("value")

    action = raw_action.lower().strip().replace(" ", "_").replace("-", "_")

    if not action:
        return "No action could be determined."

    print(f"[Settings] Action: {action}  Value: {value}  OS: {_OS}")
    if player:
        player.write_log(f"[Settings] {action}")

    if action in _DANGEROUS_ACTIONS:
        confirmed = str(params.get("confirmed", "")).lower()
        if confirmed not in ("yes", "true", "1", "confirm"):
            return (
                f"This will {action} the computer. "
                f"Please confirm by calling again with confirmed=yes."
            )

    if action == "volume_set":
        try:
            val_str = str(value).replace("%", "").strip().lower() if value else "50"
            if val_str in ("up", "down", "mute"):
                if val_str == "up":
                    volume_up()
                elif val_str == "down":
                    volume_down()
                else:
                    volume_mute()
                return f"Volume {val_str}."
            volume_set(int(val_str))
            return f"Volume set to {value}%."
        except ValueError:
            return f"Invalid volume value: {value}"
        except Exception as e:
            return f"Could not set volume: {e}"

    # Direct volume action without AI
    if action in ("volume", "set_volume", "volume_up", "volume_down"):
        if action in ("volume_up", "volume_down"):
            current = _get_volume_windows()
            level = current + 10 if action == "volume_up" else current - 10
        else:
            if value:
                val_str = str(value).replace("%", "").strip().lower()
                if val_str in ("up", "down", "mute"):
                    if val_str == "up":
                        volume_up()
                    elif val_str == "down":
                        volume_down()
                    else:
                        volume_mute()
                    return f"Volume {val_str}."
                try:
                    level = int(val_str)
                except ValueError:
                    return f"Invalid volume value: {value}"
            else:
                level = 50

        result = set_system_volume(level)
        return result

    if action in ("screen_off", "turn_off_screen", "desligar_tela", "tela_off"):
        return screen_off()

    if action in ("screen_on", "turn_on_screen", "ligar_tela", "tela_on", "acordar_tela"):
        return screen_on()

    if action in ("type_text", "write_on_screen", "type", "write"):
        text = str(value or params.get("text", "")).strip()
        if not text:
            return "No text provided to type."
        enter_after = str(params.get("press_enter", "false")).lower() in ("true", "1", "yes")
        type_text(text, press_enter_after=enter_after)
        return f"Typed: {text[:80]}"

    if action == "press_key":
        key = str(value or params.get("key", "")).strip()
        if not key:
            return "No key specified."
        press_key(key)
        return f"Pressed: {key}"

    if action in ("reload_n", "refresh_n", "reload_page_n"):
        try:
            reload_page_n(int(value or 1))
            return f"Reloaded {value or 1} time(s)."
        except Exception as e:
            return f"Reload failed: {e}"

    if action == "scroll_up":
        scroll_up(int(value or 500))
        return "Scrolled up."

    if action == "scroll_down":
        scroll_down(int(value or 500))
        return "Scrolled down."

    # Handle functions that take parameters via value
    if action in ("kill_process", "kill") and value:
        return kill_process(str(value))
    if action in ("process_exists", "is_running") and value:
        return process_exists(str(value))
    if action in ("open_windows_settings", "settings_page") and value:
        return open_windows_settings(str(value))
    if action == "open_control_panel" and value:
        return open_control_panel(str(value))
    if action in ("power_plan", "power") and value:
        return set_power_plan(str(value))
    if action in ("kill_port", "port_kill") and value:
        try:
            return kill_by_port(int(value))
        except ValueError:
            return f"Invalid port number: {value}"
    if action == "open_notepad" and value:
        return open_notepad(str(value))
    if action == "open_explorer" and value:
        return open_explorer(str(value))

    # Handle new parameterized actions
    if action in ("set_brightness", "brightness") and value is not None:
        try:
            val_str = str(value).replace("%", "").strip()
            return set_brightness(int(val_str))
        except ValueError:
            return f"Invalid brightness value: {value}"
    if action in ("toggle_bluetooth", "bluetooth"):
        return toggle_bluetooth()
    if action in ("open_app", "open_application", "launch") and value:
        return open_app(str(value))
    if action in ("window_size", "resize_window") and value:
        try:
            parts = str(value).replace(",", " ").split()
            if len(parts) >= 2:
                return set_window_size(int(parts[0]), int(parts[1]))
            return "Provide width and height: e.g., 800 600"
        except ValueError:
            return f"Invalid size: {value}"
    if action == "move_window" and value:
        try:
            parts = str(value).replace(",", " ").split()
            if len(parts) >= 2:
                return move_window(int(parts[0]), int(parts[1]))
            return "Provide x and y: e.g., 100 200"
        except ValueError:
            return f"Invalid position: {value}"
    if action in ("open_url", "open_link") and value:
        return open_url(str(value))
    if action == "click_at" and value:
        try:
            parts = str(value).replace(",", " ").split()
            if len(parts) >= 2:
                return click_at(int(parts[0]), int(parts[1]))
            return "Provide x and y: e.g., 500 300"
        except ValueError:
            return f"Invalid coordinates: {value}"
    if action == "double_click_at" and value:
        try:
            parts = str(value).replace(",", " ").split()
            if len(parts) >= 2:
                return double_click_at(int(parts[0]), int(parts[1]))
            return "Provide x and y: e.g., 500 300"
        except ValueError:
            return f"Invalid coordinates: {value}"
    if action == "right_click_at" and value:
        try:
            parts = str(value).replace(",", " ").split()
            if len(parts) >= 2:
                return right_click_at(int(parts[0]), int(parts[1]))
            return "Provide x and y: e.g., 500 300"
        except ValueError:
            return f"Invalid coordinates: {value}"
    if action == "mouse_move" and value:
        try:
            parts = str(value).replace(",", " ").split()
            if len(parts) >= 2:
                return mouse_move(int(parts[0]), int(parts[1]))
            return "Provide x and y: e.g., 500 300"
        except ValueError:
            return f"Invalid coordinates: {value}"
    if action in ("cursor_position", "cursor_pos"):
        return get_cursor_position()
    if action == "screen_resolution":
        return get_screen_resolution()
    if action in ("programs", "uninstall"):
        return open_program_settings()
    if action == "device_manager":
        return open_device_manager()
    if action == "disk_management":
        return open_disk_management()
    if action == "firewall":
        return open_firewall()
    if action == "environment_vars":
        return open_environment_vars()
    if action == "user_accounts":
        return open_user_accounts()
    if action == "power_options":
        return open_power_options()
    if action == "date_time":
        return open_date_time()
    if action in ("region", "region_settings"):
        return open_region_settings()
    if action in ("eject", "eject_drives"):
        return eject_drive()
    if action in ("mouse_click", "click"):
        return mouse_click()
    if action == "mouse_double_click":
        return mouse_double_click()
    if action == "mouse_right_click":
        return mouse_right_click()

    func = ACTION_MAP.get(action)
    if not func:
        return f"Unknown action: '{raw_action}'."

    try:
        result = func()
        # If function returns a string (like status/info), return it
        if result is not None:
            return str(result)
        return f"Done: {action}."
    except Exception as e:
        print(f"[Settings] Action failed ({action}): {e}")
        return f"Action failed ({action}): {e}"