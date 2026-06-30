#computer_control.py
import io
import json
import re
import string
import subprocess
import sys
import time
import random
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

try:
    import pygetwindow as gw
    _PYGETWINDOW = True
except ImportError:
    gw = None
    _PYGETWINDOW = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE         = _base_dir()
_CONFIG_PATH  = _BASE / "config" / "api_keys.json"
_MEMORY_PATH  = _BASE / "memory" / "long_term.json"

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _get_os() -> str:
    return _load_config().get("os_system", "windows").lower()


def _get_api_key() -> str:
    return _load_config().get("gemini_api_key", "")

_SAFE_SCREENSHOT_ROOTS = (
    Path.home(),
)

def _safe_screenshot_path(requested: str | None) -> Path:
    fallback = Path.home() / "Desktop" / "jarvis_screenshot.png"
    if not requested:
        return fallback
    try:
        p = Path(requested).expanduser().resolve()
        for root in _SAFE_SCREENSHOT_ROOTS:
            if p.is_relative_to(root.resolve()):
                p.parent.mkdir(parents=True, exist_ok=True)
                return p
    except Exception:
        pass
    return fallback

def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


def _require_pygetwindow():
    if not _PYGETWINDOW:
        raise RuntimeError("pygetwindow not installed. Run: pip install pygetwindow")

_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew", "Quinn",
    "Avery", "Blake", "Cameron", "Dakota", "Emerson", "Finley", "Harper",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
]
_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "proton.me", "mail.com"]


def _random_data(data_type: str) -> str:
    dt = data_type.lower().strip()

    if dt == "first_name":
        return random.choice(_FIRST_NAMES)

    if dt == "last_name":
        return random.choice(_LAST_NAMES)

    if dt == "name":
        return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"

    if dt == "email":
        first = random.choice(_FIRST_NAMES).lower()
        last  = random.choice(_LAST_NAMES).lower()
        num   = random.randint(10, 999)
        return f"{first}.{last}{num}@{random.choice(_DOMAINS)}"

    if dt == "username":
        return f"{random.choice(_FIRST_NAMES).lower()}{random.randint(100, 9999)}"

    if dt == "password":
        chars = string.ascii_letters + string.digits + "!@#$%"
        raw   = (
            random.choice(string.ascii_uppercase)
            + random.choice(string.digits)
            + random.choice("!@#$%")
            + "".join(random.choices(chars, k=9))
        )
        return "".join(random.sample(raw, len(raw)))

    if dt == "phone":
        return f"+1{random.randint(200,999)}{random.randint(1_000_000, 9_999_999)}"

    if dt == "birthday":
        y = random.randint(1980, 2000)
        m = random.randint(1, 12)
        d = random.randint(1, 28)
        return f"{m:02d}/{d:02d}/{y}"

    if dt == "address":
        num    = random.randint(100, 9999)
        street = random.choice(["Main St", "Oak Ave", "Park Blvd", "Elm St", "Cedar Ln"])
        return f"{num} {street}"

    if dt == "zip_code":
        return str(random.randint(10000, 99999))

    if dt == "city":
        return random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"])

    return f"random_{data_type}_{random.randint(1000, 9999)}"

def _user_profile() -> dict:
    """Read identity fields from long-term memory."""
    try:
        if _MEMORY_PATH.exists():
            data     = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
            identity = data.get("identity", {})
            return {k: v.get("value", "") for k, v in identity.items()}
    except Exception:
        pass
    return {}

def _type(text: str, interval: float = 0.03) -> str:
    _require_pyautogui()
    time.sleep(0.3)
    pyautogui.typewrite(text, interval=interval)
    return f"Typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _smart_type(text: str, clear_first: bool = True) -> str:
    _require_pyautogui()
    if clear_first:
        _clear_field()
        time.sleep(0.1)

    if len(text) > 20 and _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        return f"Smart-typed (clipboard): {text[:60]}{'…' if len(text) > 60 else ''}"

    pyautogui.typewrite(text, interval=0.04)
    return f"Smart-typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _type_for_me(text: str) -> str:
    """Wait for user to click a field, then type the text there."""
    _require_pyautogui()
    import pydirectinput
    time.sleep(0.5)
    pydirectinput.write(text, interval=0.05)
    return f"Typed at cursor: {text[:60]}{'…' if len(text) > 60 else ''}"


def _click(x=None, y=None, button: str = "left", clicks: int = 1) -> str:
    _require_pyautogui()
    if x is not None and y is not None:
        pyautogui.click(x, y, button=button, clicks=clicks)
        return f"{'Double-c' if clicks == 2 else 'C'}licked ({x}, {y}) [{button}]"
    pyautogui.click(button=button, clicks=clicks)
    return f"Clicked at current position [{button}]"


def _hotkey(*keys) -> str:
    _require_pyautogui()
    pyautogui.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


def _press(key: str) -> str:
    _require_pyautogui()
    pyautogui.press(key)
    return f"Pressed: {key}"


def _key_down(key: str) -> str:
    _require_pyautogui()
    pyautogui.keyDown(key)
    return f"Key down: {key}"


def _key_up(key: str) -> str:
    _require_pyautogui()
    pyautogui.keyUp(key)
    return f"Key up: {key}"


def _hold_key(key: str, seconds: float = 0.5) -> str:
    _require_pyautogui()
    seconds = max(0.0, min(float(seconds), 10.0))
    pyautogui.keyDown(key)
    time.sleep(seconds)
    pyautogui.keyUp(key)
    return f"Held: {key} for {seconds:.2f}s"


def _scroll(direction: str = "down", amount: int = 3) -> str:
    _require_pyautogui()
    vertical   = direction in ("up", "down")
    clicks     = amount if direction in ("up", "right") else -amount
    pyautogui.scroll(clicks) if vertical else pyautogui.hscroll(clicks)
    return f"Scrolled {direction} ×{amount}"


def _move(x: int, y: int, duration: float = 0.3) -> str:
    _require_pyautogui()
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse → ({x}, {y})"


def _move_relative(dx: int, dy: int, duration: float = 0.1) -> str:
    _require_pyautogui()
    dx = max(-3000, min(int(dx), 3000))
    dy = max(-3000, min(int(dy), 3000))
    pyautogui.moveRel(dx, dy, duration=max(0.0, min(float(duration), 2.0)))
    return f"Mouse relative: ({dx}, {dy})"


def _position() -> str:
    _require_pyautogui()
    x, y = pyautogui.position()
    return f"{x},{y}"


def _drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    _require_pyautogui()
    pyautogui.moveTo(x1, y1, duration=0.2)
    pyautogui.dragTo(x2, y2, duration=duration, button="left")
    return f"Dragged ({x1},{y1}) → ({x2},{y2})"


def _clipboard_get() -> str:
    if _PYPERCLIP:
        content = pyperclip.paste()
        if not content:
            return "(clipboard vazio)"
        return content
    _hotkey("ctrl", "c")
    time.sleep(0.2)
    return "(copied — pyperclip unavailable for read)"


def _clipboard_copy_selection() -> str:
    _require_pyautogui()
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.2)
    return _clipboard_get()


def _clipboard_set(text: str) -> str:
    if _PYPERCLIP:
        pyperclip.copy(text)
        return f"Clipboard atualizado: {text[:80]}{'...' if len(text) > 80 else ''}"
    return "pyperclip not available"


def _clipboard_paste(text: str | None = None) -> str:
    _require_pyautogui()
    if text is not None and str(text) != "":
        if not _PYPERCLIP:
            return "pyperclip not available"
        pyperclip.copy(str(text))
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        return f"Pasted: {str(text)[:60]}{'...' if len(str(text)) > 60 else ''}"
    pyautogui.hotkey("ctrl", "v")
    return "Clipboard colado."


def _screenshot(save_path: str | None = None) -> str:
    _require_pyautogui()
    path = _safe_screenshot_path(save_path)
    img  = pyautogui.screenshot()
    img.save(str(path))
    return f"Screenshot saved: {path}"


def _clear_field() -> str:
    _require_pyautogui()
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    return "Field cleared"

def _focus_window(title: str) -> str:
    os_name = _get_os()

    if os_name == "windows":
        try:
            script = f'(New-Object -ComObject WScript.Shell).AppActivate("{title}")'
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (Windows) failed: {e}"

    if os_name == "mac":
        script = (
            f'tell application "System Events" to '
            f'set frontmost of (first process whose name contains "{title}") to true'
        )
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (macOS) failed: {e}"

    if os_name == "linux":
        try:
            result = subprocess.run(
                ["wmctrl", "-a", title],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                time.sleep(0.3)
                return f"Focused window: {title}"
        except FileNotFoundError:
            pass
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", title, "windowactivate"],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except FileNotFoundError:
            return "focus_window (Linux) requires wmctrl or xdotool"
        except Exception as e:
            return f"focus_window (Linux) failed: {e}"

    return f"focus_window: unknown OS '{os_name}'"


def _window_candidates(title: str = ""):
    _require_pygetwindow()
    windows = [w for w in gw.getAllWindows() if getattr(w, "title", "").strip()]
    needle = str(title or "").lower().strip()
    if not needle:
        return windows
    return [w for w in windows if needle in w.title.lower()]


def _list_windows(limit: int = 30) -> str:
    windows = _window_candidates()
    limit = max(1, min(int(limit), 100))
    if not windows:
        return "Nenhuma janela encontrada."
    lines = [f"Janelas abertas ({len(windows)}):"]
    for index, window in enumerate(windows[:limit], 1):
        marker = "min" if getattr(window, "isMinimized", False) else "open"
        lines.append(f"{index}. {window.title} [{marker}] {window.left},{window.top} {window.width}x{window.height}")
    return "\n".join(lines)


def _active_window() -> str:
    _require_pygetwindow()
    window = gw.getActiveWindow()
    if not window:
        return "Nenhuma janela ativa detectada."
    return f"Janela ativa: {window.title} ({window.left},{window.top} {window.width}x{window.height})"


def _pick_window(title: str = "", require_title_for_close: bool = False):
    _require_pygetwindow()
    if title:
        matches = _window_candidates(title)
        if matches:
            return matches[0]
        raise RuntimeError(f"Janela nao encontrada: {title}")
    if require_title_for_close:
        raise RuntimeError("Informe title para fechar janela com seguranca.")
    window = gw.getActiveWindow()
    if not window:
        raise RuntimeError("Nenhuma janela ativa detectada.")
    return window


def _manage_window(action: str, title: str = "", **kwargs) -> str:
    action = str(action or "").lower().strip()
    require_title = action == "close_window" and not bool(kwargs.get("active", False))
    window = _pick_window(title, require_title_for_close=require_title)
    label = window.title

    if action == "close_window":
        window.close()
        return f"Janela fechada: {label}"
    if action == "minimize_window":
        window.minimize()
        return f"Janela minimizada: {label}"
    if action == "maximize_window":
        window.maximize()
        return f"Janela maximizada: {label}"
    if action == "restore_window":
        window.restore()
        return f"Janela restaurada: {label}"
    if action == "activate_window":
        window.activate()
        return f"Janela ativada: {label}"
    if action == "move_window":
        x = int(kwargs.get("x", window.left))
        y = int(kwargs.get("y", window.top))
        window.moveTo(x, y)
        return f"Janela movida: {label} -> {x},{y}"
    if action == "resize_window":
        width = max(120, int(kwargs.get("width", window.width)))
        height = max(80, int(kwargs.get("height", window.height)))
        window.resizeTo(width, height)
        return f"Janela redimensionada: {label} -> {width}x{height}"
    if action == "arrange_window":
        x = int(kwargs.get("x", window.left))
        y = int(kwargs.get("y", window.top))
        width = max(120, int(kwargs.get("width", window.width)))
        height = max(80, int(kwargs.get("height", window.height)))
        window.moveTo(x, y)
        window.resizeTo(width, height)
        return f"Janela organizada: {label} -> {x},{y} {width}x{height}"

    return f"Acao de janela desconhecida: {action}"

def _screen_find(description: str) -> tuple[int, int] | None:
    api_key = _get_api_key()
    if not api_key:
        print("[ComputerControl] ⚠️ No API key for screen_find")
        return None

    try:
        from google import genai
        from google.genai import types as gtypes

        _require_pyautogui()
        w, h  = pyautogui.size()
        img   = pyautogui.screenshot()
        buf   = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        client = genai.Client(api_key=api_key)
        prompt = (
            f"This is a screenshot of a {w}×{h} pixel screen. "
            f"Locate the UI element described as: '{description}'. "
            f"Reply with ONLY the center coordinates as: x,y "
            f"If the element is not visible, reply: NOT_FOUND"
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                gtypes.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt,
            ],
        )

        text = (response.text or "").strip()
        if "NOT_FOUND" in text.upper():
            return None

        match = re.search(r"(\d+)\s*,\s*(\d+)", text)
        if match:
            return int(match.group(1)), int(match.group(2))

    except Exception as e:
        print(f"[ComputerControl] ⚠️ screen_find failed: {e}")

    return None

def computer_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Dispatch table for all computer control actions.

    parameters keys (all optional unless noted):
      action        : (required) one of the actions listed below
      text          : text to type or paste
      x, y          : screen coordinates
      button        : 'left' | 'right' (default: left)
      keys          : hotkey string, e.g. 'ctrl+c'
      key           : single key name, e.g. 'enter'
      direction     : 'up' | 'down' | 'left' | 'right'
      amount        : scroll amount (default: 3)
      seconds       : wait duration
      title         : window title fragment for focus_window
      description   : natural-language element description for screen_find/click
      type          : data type for random_data
      field         : memory field name for user_data
      clear_first   : bool, clear field before typing (default: true)
      path          : save path for screenshot (must be inside home dir)

    Actions:
      type          — type text at cursor
      smart_type    — clear field + type (clipboard-backed)
      click         — left click
      double_click  — double left click
      right_click   — right click
      move          — move mouse
      mouse_relative — move mouse by dx/dy
      position      — current mouse position
      drag          — click-drag between two points
      hotkey        — key combination
      press         — single key
      key_down      — hold key down until key_up
      key_up        — release key
      hold          — hold key for up to 10 seconds
      scroll        — scroll the wheel
      read_clipboard — read clipboard content
      copy          — copy selected text/content and return clipboard
      set_clipboard — set clipboard without pasting
      paste         — paste provided text, or current clipboard when text omitted
      screenshot    — capture screen (safe path only)
      wait          — sleep N seconds
      clear_field   — select-all + delete
      focus_window  — bring window to foreground
      list_windows  — list open windows
      active_window — show active window title and geometry
      close_window/minimize_window/maximize_window/restore_window/activate_window
      move_window/resize_window/arrange_window — window geometry automation
      screen_find   — AI element finder (returns x,y)
      screen_click  — AI element finder + click
      random_data   — generate fake form data
      user_data     — pull real data from memory
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    if not action:
        return "No action specified for computer_control."

    if player:
        player.write_log(f"[Computer] {action}")

    print(f"[ComputerControl] ▶ {action}  {params}")

    try:

        if action == "type":
            return _type(params.get("text", ""))

        if action == "smart_type":
            return _smart_type(
                params.get("text", ""),
                clear_first=params.get("clear_first", True),
            )

        if action == "type_for_me":
            return _type_for_me(params.get("text", ""))

        if action in ("click", "left_click"):
            return _click(params.get("x"), params.get("y"), "left", 1)

        if action == "double_click":
            return _click(params.get("x"), params.get("y"), "left", 2)

        if action == "right_click":
            return _click(params.get("x"), params.get("y"), "right", 1)

        if action == "move":
            return _move(int(params.get("x", 0)), int(params.get("y", 0)))

        if action == "mouse_relative":
            return _move_relative(
                int(params.get("dx", 0)),
                int(params.get("dy", 0)),
                float(params.get("seconds", 0.1)),
            )

        if action in ("position", "cursor_position", "cursor_pos"):
            return _position()

        if action == "drag":
            return _drag(
                int(params.get("x1", 0)), int(params.get("y1", 0)),
                int(params.get("x2", 0)), int(params.get("y2", 0)),
            )

        if action == "hotkey":
            raw  = params.get("keys", "")
            keys = [k.strip() for k in raw.split("+")] if isinstance(raw, str) else raw
            return _hotkey(*keys)

        if action == "press":
            return _press(params.get("key", "enter"))

        if action == "key_down":
            return _key_down(params.get("key", "enter"))

        if action == "key_up":
            return _key_up(params.get("key", "enter"))

        if action == "hold":
            return _hold_key(params.get("key", "enter"), float(params.get("seconds", 0.5)))

        if action == "scroll":
            return _scroll(
                direction=params.get("direction", "down"),
                amount=int(params.get("amount", 3)),
            )

        if action in ("read_clipboard", "clipboard", "clipboard_read", "get_clipboard", "ler_clipboard", "ler_copiado"):
            return _clipboard_get()

        if action in ("copy", "copy_selection", "copiar"):
            return _clipboard_copy_selection()

        if action in ("set_clipboard", "clipboard_set", "write_clipboard"):
            return _clipboard_set(params.get("text", ""))

        if action in ("paste", "paste_clipboard", "colar"):
            return _clipboard_paste(params.get("text"))

        if action == "screenshot":
            return _screenshot(params.get("path"))

        if action == "screen_find":
            coords = _screen_find(params.get("description", ""))
            return f"{coords[0]},{coords[1]}" if coords else "NOT_FOUND"

        if action == "screen_click":
            desc   = params.get("description", "")
            coords = _screen_find(desc)
            if coords:
                time.sleep(0.2)
                _click(x=coords[0], y=coords[1])
                return f"Clicked '{desc}' at {coords}"
            return f"Element not found on screen: '{desc}'"

        if action == "wait":
            secs = float(params.get("seconds", 1.0))
            secs = min(secs, 30.0)
            time.sleep(secs)
            return f"Waited {secs}s"

        if action == "clear_field":
            return _clear_field()

        if action == "focus_window":
            return _focus_window(params.get("title", ""))

        if action in ("list_windows", "windows"):
            return _list_windows(int(params.get("limit", 30)))

        if action in ("active_window", "current_window"):
            return _active_window()

        if action in (
            "close_window",
            "minimize_window",
            "maximize_window",
            "restore_window",
            "activate_window",
            "move_window",
            "resize_window",
            "arrange_window",
        ):
            window_params = {key: value for key, value in params.items() if key not in {"action", "title"}}
            return _manage_window(action, params.get("title", ""), **window_params)

        if action == "random_data":
            dt     = params.get("type", "name")
            result = _random_data(dt)
            print(f"[ComputerControl] 🎲 random {dt} → {result}")
            return result

        if action == "user_data":
            field   = params.get("field", "name")
            profile = _user_profile()
            value   = profile.get(field, "")
            if not value:
                value = _random_data(field)
                print(f"[ComputerControl] ⚠️ No '{field}' in memory, using random: {value}")
            return value

        return f"Unknown action: '{action}'"

    except Exception as e:
        print(f"[ComputerControl] ❌ {action}: {e}")
        return f"computer_control '{action}' failed: {e}"
