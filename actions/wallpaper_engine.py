from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "wallpaper_engine.json"
STEAM_APP_ID = "431960"
_OS = platform.system()


def _default_config() -> dict[str, Any]:
    return {
        "exe_path": "",
        "default_monitor": None,
        "default_window_name": "JARVIS Wallpaper",
        "start_wait_seconds": 2,
        "saved_wallpapers": {},
        "saved_playlists": [],
        "saved_profiles": [],
    }


def _load_config() -> dict[str, Any]:
    cfg = _default_config()
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if v is not None})
    except Exception:
        pass
    return cfg


def _save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _candidate_paths() -> list[Path]:
    candidates: list[Path] = []
    env = os.environ.get("WALLPAPER_ENGINE_EXE")
    if env:
        candidates.append(Path(env))

    cfg = _load_config()
    if cfg.get("exe_path"):
        candidates.append(Path(str(cfg["exe_path"])))

    if _OS == "Windows":
        roots = [
            os.environ.get("PROGRAMFILES(X86)", ""),
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMW6432", ""),
        ]
        for root in roots:
            if not root:
                continue
            base = Path(root) / "Steam" / "steamapps" / "common" / "wallpaper_engine"
            candidates.extend([base / "wallpaper64.exe", base / "wallpaper32.exe"])

        steam_cfg_roots = [
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Steam" / "steamapps",
            Path(os.environ.get("PROGRAMFILES", "")) / "Steam" / "steamapps",
        ]
        for steamapps in steam_cfg_roots:
            library_vdf = steamapps / "libraryfolders.vdf"
            if not library_vdf.exists():
                continue
            try:
                text = library_vdf.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for raw in text.splitlines():
                if '"path"' not in raw:
                    continue
                parts = raw.split('"')
                if len(parts) < 4:
                    continue
                path = Path(parts[3].replace("\\\\", "\\"))
                base = path / "steamapps" / "common" / "wallpaper_engine"
                candidates.extend([base / "wallpaper64.exe", base / "wallpaper32.exe"])

    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        try:
            key = str(path.expanduser().resolve())
        except Exception:
            key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path.expanduser())
    return unique


def _find_exe() -> Path | None:
    for path in _candidate_paths():
        if path.exists() and path.is_file():
            return path
    return None


def _is_running() -> bool:
    if _OS != "Windows":
        return False
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for image_name in ("wallpaper64.exe", "wallpaper32.exe"):
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=creationflags,
            )
            if image_name in result.stdout.lower():
                return True
        except Exception:
            continue
    return False


def _start_via_steam() -> str:
    if _OS != "Windows":
        return "Abrir via Steam URI so esta configurado no Windows."
    try:
        os.startfile(f"steam://rungameid/{STEAM_APP_ID}")  # type: ignore[attr-defined]
        return "Abrindo Wallpaper Engine via Steam."
    except Exception as exc:
        return f"Nao consegui abrir via Steam: {exc}"


def _ensure_running(exe: Path | None, cfg: dict[str, Any]) -> str:
    if _is_running():
        return ""
    if exe and exe.exists():
        try:
            subprocess.Popen([str(exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(float(cfg.get("start_wait_seconds") or 2))
            return "Wallpaper Engine iniciado."
        except Exception as exc:
            return f"Nao consegui iniciar Wallpaper Engine: {exc}"
    return _start_via_steam()


def _append_target_args(args: list[str], params: dict[str, Any], cfg: dict[str, Any]) -> None:
    location = params.get("location")
    monitor = params.get("monitor", cfg.get("default_monitor"))
    if location not in (None, ""):
        args.extend(["-location", str(location)])
    elif monitor not in (None, ""):
        args.extend(["-monitor", str(monitor)])


def _run_control(command: str, params: dict[str, Any], cfg: dict[str, Any], wait: bool = True) -> tuple[bool, str]:
    exe = _find_exe()
    if not exe:
        return False, "Nao encontrei wallpaper64.exe/wallpaper32.exe. Use action='set_path' com o caminho do executavel."

    start_msg = _ensure_running(exe, cfg)
    args = [str(exe), "-control", command]
    _append_target_args(args, params, cfg)

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        if wait:
            result = subprocess.run(args, capture_output=True, text=True, timeout=12, creationflags=creationflags)
            output = (result.stdout or result.stderr or "").strip()
            if result.returncode != 0:
                return False, output or f"Wallpaper Engine retornou codigo {result.returncode}."
            if command == "getWallpaper":
                return True, output
            return True, output or start_msg or "OK"
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
        return True, start_msg or "OK"
    except Exception as exc:
        return False, f"Falha no controle do Wallpaper Engine: {exc}"


def _open_wallpaper(params: dict[str, Any], cfg: dict[str, Any]) -> str:
    exe = _find_exe()
    if not exe:
        return "Nao encontrei wallpaper64.exe/wallpaper32.exe. Use action='set_path' com o caminho do executavel."
    start_msg = _ensure_running(exe, cfg)
    raw_file = params.get("file") or params.get("path") or params.get("wallpaper") or params.get("video") or params.get("image")
    alias = str(params.get("name") or params.get("alias") or "").strip().lower()
    saved = cfg.get("saved_wallpapers") or {}
    if not raw_file and alias and isinstance(saved, dict):
        raw_file = saved.get(alias)
    if not raw_file:
        return "Me passa o caminho do wallpaper, video, project.json, scene.pkg ou um alias salvo."

    file_path = Path(str(raw_file)).expanduser()
    if not file_path.exists():
        return f"Arquivo de wallpaper nao encontrado: {file_path}"

    args = [str(exe), "-control", "openWallpaper", "-file", str(file_path)]
    _append_target_args(args, params, cfg)
    if params.get("preset"):
        args.extend(["-preset", str(params["preset"])])
    if params.get("play_in_window") or params.get("window"):
        name = str(params.get("play_in_window") or params.get("window") or cfg.get("default_window_name") or "JARVIS Wallpaper")
        args.extend(["-playInWindow", name])
        for key in ("width", "height", "x", "y"):
            if params.get(key) not in (None, ""):
                args.extend([f"-{key}", str(params[key])])
        if bool(params.get("activate")):
            args.append("-activate")
        if bool(params.get("borderless")):
            args.append("-borderless")

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.run(args, capture_output=True, text=True, timeout=12, creationflags=creationflags)
    except Exception as exc:
        return f"Falha ao abrir wallpaper: {exc}"

    return f"{start_msg + ' ' if start_msg else ''}Wallpaper aplicado: {file_path}"


def _apply_properties(params: dict[str, Any], cfg: dict[str, Any]) -> str:
    properties = params.get("properties") or params.get("json") or {}
    if isinstance(properties, str):
        raw = properties.strip()
        if not raw:
            return "Me passa as propriedades JSON para aplicar."
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
    else:
        parsed = properties
    if isinstance(parsed, str):
        raw_json = parsed
    else:
        raw_json = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    exe = _find_exe()
    if not exe:
        return "Nao encontrei wallpaper64.exe/wallpaper32.exe. Use action='set_path' com o caminho do executavel."
    start_msg = _ensure_running(exe, cfg)
    args = [str(exe), "-control", "applyProperties", "-properties", f"RAW~({raw_json})~END"]
    _append_target_args(args, params, cfg)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=12, creationflags=creationflags)
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode != 0:
            return output or f"Wallpaper Engine retornou codigo {result.returncode}."
        return f"{start_msg + ' ' if start_msg else ''}Propriedades aplicadas."
    except Exception as exc:
        return f"Falha ao aplicar propriedades: {exc}"


def _save_wallpaper_alias(params: dict[str, Any], cfg: dict[str, Any]) -> str:
    name = str(params.get("name") or params.get("alias") or "").strip().lower()
    raw_file = params.get("file") or params.get("path") or params.get("wallpaper")
    if not name or not raw_file:
        return "Informe name/alias e path/file para salvar o atalho de wallpaper."
    file_path = Path(str(raw_file)).expanduser()
    if not file_path.exists():
        return f"Arquivo nao encontrado: {file_path}"
    saved = cfg.setdefault("saved_wallpapers", {})
    if not isinstance(saved, dict):
        saved = {}
        cfg["saved_wallpapers"] = saved
    saved[name] = str(file_path)
    _save_config(cfg)
    return f"Atalho de wallpaper salvo: {name} -> {file_path}"


def wallpaper_engine(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").strip().lower().replace("-", "_")
    cfg = _load_config()

    if player:
        player.write_log(f"[WallpaperEngine] {action}")

    if action in {"status", "config", "help"}:
        exe = _find_exe()
        current = ""
        if exe and _is_running():
            ok, current = _run_control("getWallpaper", params, cfg)
            if not ok:
                current = ""
        saved = cfg.get("saved_wallpapers") or {}
        return (
            "Wallpaper Engine.\n"
            f"Executavel: {exe or 'nao encontrado'}\n"
            f"Rodando: {'sim' if _is_running() else 'nao'}\n"
            f"Atual: {current or 'indisponivel'}\n"
            f"Atalhos salvos: {len(saved) if isinstance(saved, dict) else 0}\n"
            "Acoes: open/start/pause/play/stop/mute/unmute/next/open_wallpaper/close/get/apply_properties/open_playlist/open_profile/hide_icons/show_icons."
        )

    if action in {"set_path", "configure", "configurar", "set_exe"}:
        raw = params.get("path") or params.get("exe_path") or params.get("file")
        if not raw:
            return "Me passa o caminho do wallpaper64.exe ou wallpaper32.exe."
        exe = Path(str(raw)).expanduser()
        if not exe.exists():
            return f"Executavel nao encontrado: {exe}"
        cfg["exe_path"] = str(exe)
        _save_config(cfg)
        return f"Caminho do Wallpaper Engine salvo: {exe}"

    if action in {"start", "open", "abrir"}:
        exe = _find_exe()
        msg = _ensure_running(exe, cfg)
        return msg or "Wallpaper Engine ja esta aberto."

    if action in {"save_wallpaper", "save_alias", "salvar_wallpaper", "alias"}:
        return _save_wallpaper_alias(params, cfg)

    if action in {"open_wallpaper", "set_wallpaper", "load", "aplicar", "aplicar_wallpaper"}:
        return _open_wallpaper(params, cfg)

    if action in {"apply_properties", "properties", "set_properties", "config_wallpaper"}:
        return _apply_properties(params, cfg)

    if action in {"playlist", "open_playlist"}:
        playlist = str(params.get("playlist") or params.get("name") or "").strip()
        if not playlist:
            return "Me passa o nome da playlist salva no Wallpaper Engine."
        exe = _find_exe()
        if not exe:
            return "Nao encontrei wallpaper64.exe/wallpaper32.exe. Use action='set_path' com o caminho do executavel."
        _ensure_running(exe, cfg)
        args = [str(exe), "-control", "openPlaylist", "-playlist", playlist]
        _append_target_args(args, params, cfg)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.run(args, capture_output=True, text=True, timeout=12, creationflags=creationflags)
            return f"Playlist aplicada: {playlist}"
        except Exception as exc:
            return f"Falha ao abrir playlist: {exc}"

    if action in {"profile", "open_profile"}:
        profile = str(params.get("profile") or params.get("name") or "").strip()
        if not profile:
            return "Me passa o nome do profile salvo no Wallpaper Engine."
        exe = _find_exe()
        if not exe:
            return "Nao encontrei wallpaper64.exe/wallpaper32.exe. Use action='set_path' com o caminho do executavel."
        _ensure_running(exe, cfg)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.run([str(exe), "-control", "openProfile", "-profile", profile], capture_output=True, text=True, timeout=12, creationflags=creationflags)
            return f"Profile aplicado: {profile}"
        except Exception as exc:
            return f"Falha ao abrir profile: {exc}"

    control_map = {
        "pause": "pause",
        "pausar": "pause",
        "play": "play",
        "resume": "play",
        "retomar": "play",
        "stop": "stop",
        "parar": "stop",
        "mute": "mute",
        "mutar": "mute",
        "unmute": "unmute",
        "desmutar": "unmute",
        "next": "nextWallpaper",
        "proximo": "nextWallpaper",
        "next_wallpaper": "nextWallpaper",
        "close": "closeWallpaper",
        "remove": "closeWallpaper",
        "fechar_wallpaper": "closeWallpaper",
        "get": "getWallpaper",
        "current": "getWallpaper",
        "atual": "getWallpaper",
        "hide_icons": "hideIcons",
        "show_icons": "showIcons",
    }
    command = control_map.get(action)
    if command:
        ok, msg = _run_control(command, params, cfg)
        if command == "getWallpaper" and ok:
            return f"Wallpaper atual: {msg or 'indisponivel'}"
        if not ok:
            return msg
        labels = {
            "pause": "Wallpapers pausados.",
            "play": "Wallpapers retomados.",
            "stop": "Wallpapers parados.",
            "mute": "Wallpapers mutados.",
            "unmute": "Wallpapers desmutados.",
            "nextWallpaper": "Proximo wallpaper acionado.",
            "closeWallpaper": "Wallpaper removido/fechado.",
            "hideIcons": "Icones da area de trabalho ocultados.",
            "showIcons": "Icones da area de trabalho exibidos.",
        }
        return labels.get(command, msg or "OK")

    if action in {"steam", "open_steam"}:
        return _start_via_steam()

    return "Acao desconhecida no Wallpaper Engine. Use action=status para ver comandos."


if __name__ == "__main__":
    print(wallpaper_engine({"action": "status"}))
