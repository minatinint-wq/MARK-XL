from __future__ import annotations

import json
import os
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any


try:
    import pydirectinput

    pydirectinput.PAUSE = 0.03
    _DIRECTINPUT = True
except Exception:
    pydirectinput = None
    _DIRECTINPUT = False

try:
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.03
    _PYAUTOGUI = True
except Exception:
    pyautogui = None
    _PYAUTOGUI = False

try:
    import pygetwindow as gw

    _PYGETWINDOW = True
except Exception:
    gw = None
    _PYGETWINDOW = False


BASE_DIR = Path(__file__).resolve().parent.parent
PROFILE_PATH = BASE_DIR / "memory" / "game_control_profiles.json"

MAX_HOLD_SECONDS = 10.0
MAX_REPEAT = 50
MAX_SEQUENCE_STEPS = 40
MAX_MOUSE_DELTA = 3000

DEFAULT_BINDINGS = {
    "forward": "w",
    "back": "s",
    "left": "a",
    "right": "d",
    "jump": "space",
    "crouch": "ctrl",
    "sprint": "shift",
    "interact": "e",
    "reload": "r",
    "inventory": "i",
    "map": "m",
    "pause": "esc",
    "primary": "left",
    "secondary": "right",
}

_HELD_KEYS: set[str] = set()


def _backend_name() -> str:
    if _DIRECTINPUT:
        return "pydirectinput"
    if _PYAUTOGUI:
        return "pyautogui"
    return "none"


def _require_input():
    if not (_DIRECTINPUT or _PYAUTOGUI):
        raise RuntimeError("Input backend missing. Install pydirectinput or pyautogui.")


def _input():
    _require_input()
    return pydirectinput if _DIRECTINPUT else pyautogui


def _load_profiles() -> dict[str, Any]:
    if not PROFILE_PATH.exists():
        return {"default": {"bindings": dict(DEFAULT_BINDINGS), "notes": "Default WASD profile"}}
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("default", {"bindings": dict(DEFAULT_BINDINGS), "notes": "Default WASD profile"})
            return data
    except Exception:
        pass
    return {"default": {"bindings": dict(DEFAULT_BINDINGS), "notes": "Default WASD profile"}}


def _save_profiles(data: dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _profile_name(params: dict) -> str:
    return str(params.get("profile") or params.get("game") or "default").strip().lower() or "default"


def _bindings(params: dict) -> dict[str, str]:
    profiles = _load_profiles()
    profile = profiles.get(_profile_name(params), {})
    bindings = dict(DEFAULT_BINDINGS)
    if isinstance(profile, dict):
        custom = profile.get("bindings", {})
        if isinstance(custom, dict):
            bindings.update({str(k).lower(): str(v).lower() for k, v in custom.items()})
    return bindings


def _key_for(command_or_key: str, params: dict) -> str:
    value = str(command_or_key or "").strip().lower()
    return _bindings(params).get(value, value)


def _duration(value: Any, default: float = 0.2) -> float:
    try:
        duration = float(value)
    except Exception:
        duration = default
    return max(0.0, min(duration, MAX_HOLD_SECONDS))


def _repeat(value: Any, default: int = 1) -> int:
    try:
        repeat = int(value)
    except Exception:
        repeat = default
    return max(1, min(repeat, MAX_REPEAT))


def _mouse_delta(value: Any) -> int:
    try:
        delta = int(value)
    except Exception:
        delta = 0
    return max(-MAX_MOUSE_DELTA, min(delta, MAX_MOUSE_DELTA))


def _dry(params: dict, message: str) -> str | None:
    if bool(params.get("dry_run", False)):
        return f"DRY RUN: {message}"
    return None


def _press_key(key: str, presses: int = 1, interval: float = 0.05) -> None:
    inp = _input()
    inp.press(key, presses=presses, interval=interval)


def _key_down(key: str) -> None:
    _input().keyDown(key)
    _HELD_KEYS.add(key)


def _key_up(key: str) -> None:
    _input().keyUp(key)
    _HELD_KEYS.discard(key)


def _hotkey(keys: list[str]) -> None:
    if _PYAUTOGUI:
        pyautogui.hotkey(*keys)
        return
    for key in keys:
        _key_down(key)
    for key in reversed(keys):
        _key_up(key)


def _focus_window(title: str) -> str:
    title = (title or "").strip()
    if not title:
        return "Informe game/window_title para focar uma janela."

    if _PYGETWINDOW:
        try:
            windows = [w for w in gw.getAllWindows() if title.lower() in w.title.lower()]
            if windows:
                window = windows[0]
                try:
                    window.restore()
                except Exception:
                    pass
                window.activate()
                time.sleep(0.2)
                return f"Janela focada: {window.title}"
        except Exception:
            pass

    if os.name == "nt":
        try:
            script = f'(New-Object -ComObject WScript.Shell).AppActivate("{title}")'
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                timeout=5,
            )
            time.sleep(0.2)
            return f"Tentativa de foco enviada: {title}"
        except Exception as exc:
            return f"Falha ao focar janela: {exc}"

    return "Foco de janela nao suportado neste sistema."


def _active_window() -> str:
    if not _PYGETWINDOW:
        return "active window unavailable"
    try:
        win = gw.getActiveWindow()
        return win.title if win else "none"
    except Exception:
        return "active window unavailable"


def _launch(params: dict) -> str:
    platform = str(params.get("platform") or "").lower().strip()
    app_id = str(params.get("app_id") or "").strip()
    path = str(params.get("path") or params.get("exe") or "").strip()

    if platform == "steam" and app_id:
        if dry := _dry(params, f"abrir steam://rungameid/{app_id}"):
            return dry
        webbrowser.open(f"steam://rungameid/{app_id}")
        return f"Launch enviado para Steam AppID {app_id}."

    if platform == "epic" and app_id:
        if dry := _dry(params, f"abrir com.epicgames.launcher://apps/{app_id}?action=launch&silent=true"):
            return dry
        webbrowser.open(f"com.epicgames.launcher://apps/{app_id}?action=launch&silent=true")
        return f"Launch enviado para Epic app {app_id}."

    if path:
        exe = Path(path).expanduser()
        if exe.exists() and exe.suffix.lower() in {".exe", ".bat", ".cmd", ".lnk"}:
            if dry := _dry(params, f"executar {exe}"):
                return dry
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
            return f"Jogo/app iniciado: {exe.name}"
        return f"Executavel nao encontrado ou nao permitido: {path}"

    return "Informe platform+app_id ou path/exe para iniciar um jogo."


def _tap(params: dict) -> str:
    key = _key_for(params.get("key") or params.get("command") or "space", params)
    presses = _repeat(params.get("repeat"), 1)
    interval = _duration(params.get("interval"), 0.05)
    if dry := _dry(params, f"pressionar {key} x{presses}"):
        return dry
    _press_key(key, presses=presses, interval=interval)
    return f"Tecla enviada: {key} x{presses}"


def _hold(params: dict) -> str:
    key = _key_for(params.get("key") or params.get("command") or "w", params)
    seconds = _duration(params.get("seconds"), 0.5)
    if dry := _dry(params, f"segurar {key} por {seconds:.2f}s"):
        return dry
    _key_down(key)
    time.sleep(seconds)
    _key_up(key)
    return f"Segurei {key} por {seconds:.2f}s."


def _key_state(params: dict, down: bool) -> str:
    key = _key_for(params.get("key") or params.get("command") or "w", params)
    if dry := _dry(params, f"{'key_down' if down else 'key_up'} {key}"):
        return dry
    _key_down(key) if down else _key_up(key)
    return f"{'Segurando' if down else 'Soltei'}: {key}"


def _combo(params: dict) -> str:
    raw = params.get("keys") or params.get("key") or ""
    keys = [str(k).strip().lower() for k in raw] if isinstance(raw, list) else [k.strip().lower() for k in str(raw).replace(",", "+").split("+")]
    keys = [_key_for(k, params) for k in keys if k]
    if not keys:
        return "Informe keys, exemplo: alt+tab."
    if dry := _dry(params, f"combo {'+'.join(keys)}"):
        return dry
    _hotkey(keys)
    return f"Combo enviado: {'+'.join(keys)}"


def _mouse(params: dict) -> str:
    inp = _input()
    mode = str(params.get("mode") or params.get("mouse_action") or "move").lower().strip()
    dx = _mouse_delta(params.get("dx", 0))
    dy = _mouse_delta(params.get("dy", 0))
    x = params.get("x")
    y = params.get("y")
    button = str(params.get("button") or "left").lower()
    clicks = _repeat(params.get("clicks"), 1)
    duration = _duration(params.get("seconds"), 0.1)

    if dry := _dry(params, f"mouse {mode} dx={dx} dy={dy} x={x} y={y} button={button}"):
        return dry

    if mode in ("click", "primary", "secondary"):
        if mode == "secondary":
            button = "right"
        inp.click(x=x, y=y, button=button, clicks=clicks)
        return f"Mouse click {button} x{clicks}."

    if mode in ("move", "look", "aim"):
        if dx or dy:
            inp.moveRel(dx, dy, duration=duration)
            return f"Mouse relativo: dx={dx}, dy={dy}."
        if x is not None and y is not None:
            inp.moveTo(int(x), int(y), duration=duration)
            return f"Mouse para: {x},{y}."
        return "Informe dx/dy ou x/y para mover o mouse."

    if mode == "scroll":
        amount = int(params.get("amount", 1))
        inp.scroll(amount)
        return f"Mouse scroll {amount}."

    return f"Modo de mouse desconhecido: {mode}"


def _sequence(params: dict) -> str:
    sequence = params.get("sequence") or params.get("steps") or []
    if isinstance(sequence, str):
        sequence = [item.strip() for item in sequence.replace(">", ",").split(",") if item.strip()]
    if not isinstance(sequence, list) or not sequence:
        return "Informe sequence como lista ou texto separado por virgulas."
    sequence = sequence[:MAX_SEQUENCE_STEPS]
    delay = _duration(params.get("interval"), 0.08)
    planned: list[str] = []

    if params.get("dry_run", False):
        for item in sequence:
            planned.append(str(item))
        return "DRY RUN sequence: " + " -> ".join(planned)

    for item in sequence:
        if isinstance(item, dict):
            action = str(item.get("action") or "tap").lower()
            merged = {**params, **item, "dry_run": False}
            if action in ("tap", "press"):
                _tap(merged)
            elif action == "hold":
                _hold(merged)
            elif action in ("combo", "hotkey"):
                _combo(merged)
            elif action == "mouse":
                _mouse(merged)
            elif action == "wait":
                time.sleep(_duration(item.get("seconds"), delay))
            else:
                _tap({**merged, "key": action})
            planned.append(action)
        else:
            key = _key_for(str(item), params)
            _press_key(key)
            planned.append(key)
        time.sleep(delay)
    return "Sequencia executada: " + " -> ".join(planned)


def _stop_all(params: dict | None = None) -> str:
    params = params or {}
    common = set(_HELD_KEYS) | {"w", "a", "s", "d", "shift", "ctrl", "space", "alt", "left", "right"}
    if dry := _dry(params, "soltar teclas comuns e teclas rastreadas"):
        return dry
    released = []
    for key in list(common):
        try:
            _key_up(key)
            released.append(key)
        except Exception:
            pass
    return "Teclas soltas: " + ", ".join(sorted(set(released)))


def _profile(params: dict) -> str:
    action = str(params.get("profile_action") or "show").lower().strip()
    name = _profile_name(params)
    profiles = _load_profiles()

    if action in ("show", "get"):
        profile = profiles.get(name)
        if not profile:
            return f"Perfil de jogo nao encontrado: {name}"
        return json.dumps(profile, indent=2, ensure_ascii=False)

    if action in ("list", "profiles"):
        return "Perfis de jogo: " + ", ".join(sorted(profiles.keys()))

    if action in ("save", "set"):
        bindings = params.get("bindings")
        if isinstance(bindings, str):
            try:
                bindings = json.loads(bindings)
            except Exception:
                return "bindings deve ser JSON ou objeto."
        if not isinstance(bindings, dict):
            return "Informe bindings como objeto, exemplo {'jump':'space','inventory':'e'}."
        clean = {str(k).lower(): str(v).lower() for k, v in bindings.items()}
        profiles[name] = {
            "bindings": {**dict(DEFAULT_BINDINGS), **clean},
            "notes": str(params.get("notes") or ""),
            "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _save_profiles(profiles)
        return f"Perfil de jogo salvo: {name}"

    return "profile_action desconhecida. Use show, list ou save."


def _status() -> str:
    profiles = _load_profiles()
    return (
        "Game control pronto.\n"
        f"Backend: {_backend_name()}\n"
        f"pydirectinput: {_DIRECTINPUT}\n"
        f"pyautogui: {_PYAUTOGUI}\n"
        f"pygetwindow: {_PYGETWINDOW}\n"
        f"Janela ativa: {_active_window()}\n"
        f"Perfis: {', '.join(sorted(profiles.keys()))}"
    )


def game_control(parameters: dict = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").lower().strip().replace("-", "_")

    if player:
        try:
            player.write_log(f"[GameControl] {action}")
        except Exception:
            pass

    try:
        if action == "status":
            return _status()
        if action in ("focus", "focus_game", "focus_window"):
            return _focus_window(params.get("window_title") or params.get("game") or params.get("game_name") or "")
        if action in ("launch", "start"):
            return _launch(params)
        if action in ("tap", "press"):
            return _tap(params)
        if action == "hold":
            return _hold(params)
        if action in ("down", "key_down"):
            return _key_state(params, down=True)
        if action in ("up", "key_up", "release"):
            return _key_state(params, down=False)
        if action in ("combo", "hotkey"):
            return _combo(params)
        if action in ("mouse", "look", "aim", "click"):
            if action in ("look", "aim"):
                params = {**params, "mode": action}
            if action == "click":
                params = {**params, "mode": "click"}
            return _mouse(params)
        if action in ("sequence", "macro"):
            return _sequence(params)
        if action in ("stop", "stop_all", "panic"):
            return _stop_all(params)
        if action in ("profile", "bindings"):
            return _profile(params)

        # Natural game commands: forward, jump, reload, inventory, etc.
        if action in DEFAULT_BINDINGS or action in _bindings(params):
            command_params = {**params, "command": action}
            if action in {"forward", "back", "left", "right", "sprint", "crouch"}:
                return _hold(command_params)
            return _tap(command_params)

        return (
            f"Acao game_control desconhecida: {action}. "
            "Use status, focus, launch, tap, hold, key_down, key_up, combo, mouse, "
            "sequence, stop, profile ou comandos como forward, jump, reload, inventory."
        )
    except Exception as exc:
        try:
            _stop_all({"dry_run": False})
        except Exception:
            pass
        return f"Erro no game_control ({action}): {exc}"
