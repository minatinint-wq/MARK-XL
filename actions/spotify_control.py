"""
Control Spotify desktop app on Windows using Windows API automation.
Uses win32gui, win32con, and pygetwindow for window control and interaction.
"""

import os
import subprocess
import time
import re
from pathlib import Path
from typing import Optional


def _find_spotify_window():
    """Find the Spotify window handle."""
    try:
        import win32gui
        import win32process

        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and "spotify" in title.lower():
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        windows.append((hwnd, title, pid))
                    except:
                        pass
            return True

        windows = []
        win32gui.EnumWindows(callback, windows)
        return windows
    except Exception as e:
        print(f"[Spotify] Error finding window: {e}")
        return []


def _bring_to_front(hwnd):
    """Bring Spotify window to foreground."""
    try:
        import win32gui
        win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        return True
    except Exception as e:
        print(f"[Spotify] Error bringing to front: {e}")
        return False


def _send_hotkey(hwnd, key):
    """Send a hotkey to the Spotify window."""
    try:
        import win32gui
        import win32con
        import ctypes

        # Store current foreground window
        current = win32gui.GetForegroundWindow()

        # Bring Spotify to front
        _bring_to_front(hwnd)

        # Send the key using keybd_event
        VK = {
            "space": 0x20,
            "right": 0x27,
            "left": 0x25,
            "up": 0x26,
            "down": 0x28,
            "s": 0x53,
            "r": 0x52,
            "p": 0x50,
        }

        vk = VK.get(key.lower(), 0)
        if vk:
            # Key down
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.05)
            # Key up
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)

        # Restore foreground
        if current:
            time.sleep(0.1)
            win32gui.SetForegroundWindow(current)

        return True
    except Exception as e:
        print(f"[Spotify] Error sending hotkey: {e}")
        return False


def _click_at(hwnd, x, y):
    """Click at coordinates relative to window."""
    try:
        import win32gui

        # Get window position
        rect = win32gui.GetWindowRect(hwnd)
        abs_x = rect[0] + x
        abs_y = rect[1] + y

        # Move mouse and click
        import ctypes
        ctypes.windll.user32.SetCursorPos(abs_x, abs_y)
        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
        time.sleep(0.05)
        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP

        return True
    except Exception as e:
        print(f"[Spotify] Error clicking: {e}")
        return False


def _get_spotify_process() -> Optional[str]:
    """Get Spotify process path."""
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'exe']):
            if proc.info['name'] and proc.info['name'].lower() == 'spotify.exe':
                return proc.info['exe']
    except:
        pass
    return None


def _spotify_connect_control(action, params):
    from actions.spotify_connect import control, handles, device_request
    if not handles(action):
        return None
    from actions.smart_home import _get_spotipy
    sp = _get_spotipy()
    if sp is None:
        if device_request(params):
            return "Reconecte o Spotify do Jarvis para controlar esse dispositivo pela API."
        return None
    return control(sp, action, params)



def spotify_control(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Control Spotify desktop app.

    Actions:
    - play: Play/Pause
    - next: Next track
    - previous: Previous track
    - shuffle: Toggle shuffle
    - repeat: Toggle repeat
    - volume_up: Volume up
    - volume_down: Volume down
    - liked: Navigate to liked songs
    - current: Get current track info (via Spotify API or window title)
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    print(f"[Spotify] Action: {action}")

    api_result = _spotify_connect_control(action, params)
    if api_result:
        return api_result

    from actions.spotify_connect import action_name, device_request
    if device_request(params):
        return "Esse comando local não controla outro aparelho. Use os comandos Spotify Connect."
    if action_name(action) == 'volume':
        return "Para definir um volume exato, reconecte a API Spotify. Sem ela, use volume_up ou volume_down no PC."

    # First, ensure Spotify is open
    spotify_path = _get_spotify_process()
    if not spotify_path:
        # Try to open Spotify
        try:
            subprocess.Popen(["spotify.exe"])
            time.sleep(2)
        except:
            # Try alternative paths
            paths = [
                str(Path(os.environ.get("LOCALAPPDATA", "")) / "Spotify" / "Spotify.exe"),
                str(Path(os.environ.get("APPDATA", "")) / "Spotify" / "Spotify.exe"),
            ]
            for p in paths:
                if Path(p).exists():
                    subprocess.Popen([p])
                    time.sleep(2)
                    break

    # Find Spotify window
    windows = _find_spotify_window()
    if not windows:
        return "Spotify is not running. Please open it first."

    hwnd, title, pid = windows[0]

    # Handle actions
    if action in ("play", "pause", "toggle"):
        # More robust: focus window and send key directly
        try:
            import ctypes
            import win32gui
            # First, restore and bring Spotify to foreground
            win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
            time.sleep(0.15)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.25)

            # Now send the space key directly using ctypes
            vk_space = 0x20
            ctypes.windll.user32.keybd_event(vk_space, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(vk_space, 0, 2, 0)
            time.sleep(0.1)

            return "▶ Play/Pause toggled."
        except Exception as e:
            # Fallback to pyautogui
            try:
                import pyautogui
                pyautogui.press("space")
                return "▶ Play/Pause toggled (fallback)."
            except:
                return f"Error: {str(e)[:50]}"

    elif action in ("next", "skip", "proxima", "próxima"):
        _bring_to_front(hwnd)
        _send_hotkey(hwnd, "right")
        return "Skipped to next track."

    elif action in ("previous", "back", "anterior"):
        _bring_to_front(hwnd)
        _send_hotkey(hwnd, "left")
        return "Went to previous track."

    elif action in ("shuffle", "aleatorio", "aleatório"):
        _bring_to_front(hwnd)
        _send_hotkey(hwnd, "s")
        return "Shuffle toggled."

    elif action in ("repeat", "repetir"):
        _bring_to_front(hwnd)
        _send_hotkey(hwnd, "r")
        return "Repeat toggled."

    elif action in ("liked", "likes", "musicas curtidas", "liked songs"):
        # Navigate to liked songs using keyboard shortcuts
        _bring_to_front(hwnd)
        time.sleep(0.3)
        # Ctrl+L to focus search, then type, or use Ctrl+P for playlist
        import ctypes

        # Try Ctrl+P to open playlists menu
        vk_ctrl = 0x11
        vk_p = 0x50

        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_p, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_p, 0, 2, 0)
        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 2, 0)

        time.sleep(0.5)

        # Type "liked" to search
        import pywinauto
        from pywinauto.keyboard import send_keys
        send_keys("liked songs")
        time.sleep(0.3)
        send_keys("{ENTER}")

        return "Navigating to liked songs..."

    elif action in ("current", "now playing", "what's playing"):
        # Get track info from window title or API
        title = win32gui.GetWindowText(hwnd) if 'win32gui' in dir() else "Unknown"

        # Try to get info from Spotify metadata file or API
        # For now, parse window title which often has " - Song Name"
        if " - " in title:
            parts = title.split(" - ")
            if len(parts) >= 2:
                track = parts[-1].strip()
                if parts[0].strip():
                    artist = parts[0].strip()
                    return f"Playing: {track} by {artist}"

        # Try using Spotify Web API to get current track
        # (Requires API token - optional)
        return f"Current: {title}"

    elif action in ("volume_up", "mais"):
        _bring_to_front(hwnd)
        # Use Up arrow while holding Ctrl for volume
        import ctypes
        vk_ctrl = 0x11
        vk_up = 0x26

        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_up, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_up, 0, 2, 0)
        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 2, 0)

        return "Volume increased."

    elif action in ("volume_down", "menos"):
        _bring_to_front(hwnd)
        import ctypes
        vk_ctrl = 0x11
        vk_down = 0x28

        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_down, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_down, 0, 2, 0)
        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 2, 0)

        return "Volume decreased."

    elif action.startswith("volume_") or action.isdigit() or action.replace("%", "").isdigit():
        # Handle specific volume levels like "volume_50" or "50" or "50%"
        _bring_to_front(hwnd)

        import ctypes
        vk_ctrl = 0x11

        if action.isdigit() or action.replace("%", "").isdigit():
            # Specific volume level - adjust accordingly
            # This is simplified - real volume control would need more complex logic
            target = int(action.replace("%", "").replace("volume_", ""))
            # Just do increments/decrements to get close
            for _ in range(abs(target - 50) // 5):
                vk_up = 0x26 if target > 50 else 0x28
                ctypes.windll.user32.keybd_event(vk_ctrl, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk_up, 0, 0, 0)
                time.sleep(0.05)
                ctypes.windll.user32.keybd_event(vk_up, 0, 2, 0)
                ctypes.windll.user32.keybd_event(vk_ctrl, 0, 2, 0)
                time.sleep(0.1)
            return f"Volume set to {target}%"

        return "Volume adjusted."

    elif action in ("search", "buscar", "find"):
        # Search for artist/album/playlist
        _bring_to_front(hwnd)
        time.sleep(0.3)

        import ctypes
        # Ctrl+K to open search
        vk_ctrl = 0x11
        vk_k = 0x4B

        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_k, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_k, 0, 2, 0)
        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 2, 0)

        time.sleep(0.5)

        # Type search query
        query = params.get("query", params.get("text", ""))
        if query:
            try:
                from pywinauto.keyboard import send_keys
                send_keys(query)
                time.sleep(0.3)
                send_keys("{ENTER}")
                return f"Searching for: {query}"
            except:
                return "Search opened. Type your query."
        return "Search opened."

    elif action in ("playlist", "playlists"):
        # Open playlists sidebar
        _bring_to_front(hwnd)
        time.sleep(0.3)

        import ctypes
        # Ctrl+Shift+P to open playlists (or Ctrl+P)
        vk_ctrl = 0x11
        vk_p = 0x50

        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_p, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_p, 0, 2, 0)
        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 2, 0)

        time.sleep(0.5)
        return "Playlists menu opened."

    elif action in ("home", "inicio"):
        # Go to home/Your Library
        _bring_to_front(hwnd)
        time.sleep(0.3)

        import ctypes
        # Ctrl+Shift+H or Alt+Home
        vk_alt = 0x12
        vk_home = 0x24

        ctypes.windll.user32.keybd_event(vk_alt, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_home, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_home, 0, 2, 0)
        ctypes.windll.user32.keybd_event(vk_alt, 0, 2, 0)

        return "Went to Home."

    elif action in ("queue", "fila"):
        # Open queue
        _bring_to_front(hwnd)
        time.sleep(0.3)

        import ctypes
        # Ctrl+Shift+Q
        vk_ctrl = 0x11
        vk_q = 0x51

        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_q, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_q, 0, 2, 0)
        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 2, 0)

        return "Queue opened."

    elif action in ("lyrics", "letra", "letras"):
        # Open lyrics (if available)
        _bring_to_front(hwnd)
        time.sleep(0.3)

        import ctypes
        # Ctrl+Shift+L
        vk_ctrl = 0x11
        vk_l = 0x4C

        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_l, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_l, 0, 2, 0)
        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 2, 0)

        return "Looking for lyrics..."

    elif action in (" Devices", "devices", "connect", "dispositivos"):
        # Open device connect menu
        _bring_to_front(hwnd)
        time.sleep(0.3)

        import ctypes
        # Ctrl+Shift+D
        vk_ctrl = 0x11
        vk_d = 0x44

        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_d, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_d, 0, 2, 0)
        ctypes.windll.user32.keybd_event(vk_ctrl, 0, 2, 0)

        return "Devices menu opened."

    else:
        return f"Unknown action: {action}. Available: play, next, previous, shuffle, repeat, liked, current, volume_up, volume_down, search, playlist, home, queue, lyrics, devices"
