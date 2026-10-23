"""Bring the existing Jarvis window forward when its launcher is opened again."""
import ctypes
from ctypes import wintypes
from actions.runtime_identity import WINDOW_TITLE

def focus_running_jarvis():
    user32=ctypes.WinDLL('user32',use_last_error=True)
    user32.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR]
    user32.FindWindowW.restype=wintypes.HWND
    user32.ShowWindowAsync.argtypes=[wintypes.HWND,ctypes.c_int]
    user32.ShowWindowAsync.restype=wintypes.BOOL
    user32.SetForegroundWindow.argtypes=[wintypes.HWND]
    user32.SetForegroundWindow.restype=wintypes.BOOL
    for title in (WINDOW_TITLE,'J.A.R.V.I.S — MARK XLI','JARVIS // CORE LINK'):
        hwnd=user32.FindWindowW(None,title)
        if hwnd:
            user32.ShowWindowAsync(hwnd,9)
            user32.SetForegroundWindow(hwnd)
            return True
    return False
