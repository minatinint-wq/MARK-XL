from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from actions.operation_memory import record_operation


BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "iphone_bridge.json"
SYSTEM = platform.system()


def _load_config() -> dict[str, Any]:
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_config(data: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_log(player, text: str) -> None:
    try:
        if player:
            player.write_log(text)
    except Exception:
        pass


def _open_uri(uri: str) -> bool:
    if not uri:
        return False
    try:
        if SYSTEM == "Windows":
            os.startfile(uri)  # type: ignore[attr-defined]
            return True
        if SYSTEM == "Darwin":
            subprocess.Popen(["open", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        subprocess.Popen(["xdg-open", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _run_powershell(script: str, timeout: int = 8) -> tuple[bool, str]:
    if SYSTEM != "Windows":
        return False, "PowerShell Bluetooth inspection is only implemented on Windows."
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    wrapped = (
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); "
        "$OutputEncoding = [System.Text.UTF8Encoding]::new(); "
        + script
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", wrapped],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creationflags,
        )
        text = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode == 0, text
    except Exception as exc:
        return False, str(exc)


def _bluetooth_status() -> dict[str, Any]:
    if SYSTEM != "Windows":
        return {"supported": False, "message": f"Bluetooth bridge otimizado para Windows. Sistema atual: {SYSTEM}."}

    script = r"""
$svc = Get-Service bthserv -ErrorAction SilentlyContinue
$devices = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue |
  Where-Object { $_.FriendlyName } |
  Select-Object -First 30 FriendlyName,Status,Class
[pscustomobject]@{
  service = if ($svc) { $svc.Status.ToString() } else { "missing" }
  devices = $devices
} | ConvertTo-Json -Compress -Depth 4
"""
    ok, out = _run_powershell(script)
    if not ok:
        return {"supported": True, "service": "unknown", "devices": [], "error": out}
    try:
        data = json.loads(out)
        devices = data.get("devices") or []
        if isinstance(devices, dict):
            devices = [devices]
        return {
            "supported": True,
            "service": data.get("service", "unknown"),
            "devices": devices,
        }
    except Exception:
        return {"supported": True, "service": "unknown", "devices": [], "raw": out}


def _format_status(status: dict[str, Any]) -> str:
    if not status.get("supported", True):
        return str(status.get("message") or "iPhone Bridge indisponivel neste sistema.")
    lines = [
        "iPhone Bridge:",
        f"- Windows Bluetooth service: {status.get('service', 'unknown')}",
    ]
    devices = status.get("devices") or []
    if devices:
        lines.append("- Bluetooth devices:")
        for item in devices[:8]:
            if isinstance(item, dict):
                name = item.get("FriendlyName") or item.get("Name") or "device"
                state = item.get("Status") or "unknown"
                lines.append(f"  - {name}: {state}")
    else:
        lines.append("- No Bluetooth devices listed by Windows yet.")
    if status.get("error"):
        lines.append(f"- Warning: {status['error']}")
    return "\n".join(lines)


def _open_phone_link() -> str:
    if SYSTEM != "Windows":
        return "Phone Link para iPhone e Bluetooth esta disponivel no Windows 11."
    if _open_uri("ms-phone:"):
        return "Phone Link aberto."
    try:
        subprocess.Popen(
            ["explorer.exe", r"shell:AppsFolder\Microsoft.YourPhone_8wekyb3d8bbwe!App"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Phone Link aberto pelo pacote do Windows."
    except Exception as exc:
        return f"Nao consegui abrir o Phone Link automaticamente: {exc}"


def _open_config_html() -> str:
    path = CONFIG_PATH.parent / "iphone_social_config.html"
    if not path.exists():
        return f"HTML de config nao encontrado: {path}"
    return f"Config local aberto: {path}" if _open_uri(str(path)) else f"Nao consegui abrir: {path}"


def _copy_clipboard(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        return False


def _digits(value: str) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _media_key(action: str) -> str:
    try:
        import pyautogui
    except Exception:
        return "PyAutoGUI nao esta instalado para controlar midia."

    key_map = {
        "play": "playpause",
        "pause": "playpause",
        "play_pause": "playpause",
        "toggle_media": "playpause",
        "next": "nexttrack",
        "previous": "prevtrack",
        "prev": "prevtrack",
        "volume_up": "volumeup",
        "volume_down": "volumedown",
        "mute": "volumemute",
    }
    key = key_map.get(action)
    if not key:
        return "Acao de midia desconhecida."
    pyautogui.press(key)
    return f"Comando de midia enviado ao Windows/Bluetooth: {action}."


def iphone_bridge(parameters: dict[str, Any] | None = None, player=None, speak=None, **_) -> str:
    params = parameters or {}
    raw_action = str(params.get("action") or params.get("mode") or "status").lower().strip()
    action_parts = {part for part in re.split(r"[/|,; ]+", raw_action) if part}
    action = raw_action
    if "phone_link" in action_parts or "phonelink" in action_parts:
        action = "phone_link"
    elif "clash" in action_parts and "royale" in action_parts:
        action = "open_clash_royale"
    elif "open" in action_parts and ("phone" in action_parts or "link" in action_parts):
        action = "phone_link"
    elif "bluetooth" in action_parts:
        action = "bluetooth"
    target = str(params.get("target") or params.get("name") or params.get("device") or "").strip()
    number = str(params.get("number") or params.get("phone") or "").strip()
    message = str(params.get("message") or params.get("text") or "").strip()
    app_name = str(params.get("app_name") or params.get("app") or params.get("game") or "").strip()
    record_operation(
        "iphone",
        action,
        {
            "target": target,
            "number": number,
            "message": message,
        },
        sensitive=True,
    )

    _write_log(player, f"[iPhone] {action}")

    if action in {"status", "info", "devices", "listar", "list"}:
        return _format_status(_bluetooth_status())

    if action in {"config", "settings_ui", "html", "open_config", "config_ui"}:
        return _open_config_html()

    if action in {"set_name", "prefer", "preferred", "salvar_nome"}:
        if not target:
            return "Informe o nome do iPhone para salvar como preferido."
        data = _load_config()
        data["preferred_device"] = target
        _save_config(data)
        return f"iPhone preferido salvo: {target}"

    if action in {"open", "phone_link", "phonelink", "messages", "notifications", "calls", "call_history"}:
        result = _open_phone_link()
        if action != "open":
            result += " Use a aba correspondente no Phone Link para iPhone."
        return result

    if action in {"open_app", "open_game", "abrir_app", "abrir_jogo", "open_clash_royale"}:
        requested = app_name or target or ("Clash Royale" if action == "open_clash_royale" else "")
        if not requested:
            return "Informe app_name/game para abrir um app."
        if requested.lower().replace(" ", "") in {"clashroyale", "clash"}:
            try:
                from actions.open_app import open_app
                local = open_app(parameters={"app_name": "Clash Royale"}, player=player)
                if local and local.lower().startswith("opened"):
                    return local
            except Exception:
                pass
            _copy_clipboard("Clash Royale")
            phone_link = _open_phone_link()
            return (
                f"{phone_link}\n"
                "Nao da para abrir um app iOS diretamente pelo Bluetooth do Windows. "
                "Tentei abrir no PC/emulador e deixei 'Clash Royale' copiado. "
                "Para abrir no iPhone, crie um Atalho do iPhone com acao 'Abrir App > Clash Royale' "
                "e chame esse atalho pelo iPhone/Siri."
            )
        try:
            from actions.open_app import open_app
            return open_app(parameters={"app_name": requested}, player=player) or f"Tentei abrir {requested}."
        except Exception as exc:
            return f"Nao consegui abrir {requested}: {exc}"

    if action in {"connect", "setup", "pair", "parear", "bluetooth"}:
        opened_bt = _open_uri("ms-settings:bluetooth") if SYSTEM == "Windows" else False
        time.sleep(0.5)
        phone_link = _open_phone_link()
        prefix = "Bluetooth Settings aberto. " if opened_bt else ""
        return (
            f"{prefix}{phone_link}\n"
            "No iPhone: Ajustes > Bluetooth, deixe visivel/ativo. "
            "No Windows: pareie o iPhone e finalize no Phone Link com o QR Code."
        )

    if action in {"bluetooth_settings", "settings", "abrir_bluetooth"}:
        return "Bluetooth Settings aberto." if _open_uri("ms-settings:bluetooth") else "Nao consegui abrir as configuracoes Bluetooth."

    if action in {"call", "ligar", "phone_call"}:
        clean = _digits(number)
        if not clean:
            return "Informe number para ligar pelo iPhone/Phone Link."
        if _open_uri(f"tel:{clean}"):
            return f"Chamada preparada para {clean}. Confirme no Phone Link/iPhone se o Windows solicitar."
        return _open_phone_link() + f"\nNumero copiado? {'sim' if _copy_clipboard(clean) else 'nao'}: {clean}"

    if action in {"sms", "message", "send_sms", "mensagem"}:
        clean = _digits(number)
        if not clean:
            return "Informe number para preparar SMS pelo iPhone/Phone Link."
        copied = _copy_clipboard(message) if message else False
        uri = f"sms:{clean}"
        if _open_uri(uri):
            suffix = " Mensagem copiada para colar." if copied else ""
            return f"SMS aberto para {clean}.{suffix}"
        return _open_phone_link() + f"\nSMS para {clean}. Mensagem copiada: {'sim' if copied else 'nao'}."

    if action in {"copy_to_phone", "clipboard", "copy"}:
        if not message:
            return "Informe message/text para copiar."
        return "Texto copiado para o clipboard do PC." if _copy_clipboard(message) else "Nao consegui copiar para o clipboard."

    if action in {"play", "pause", "play_pause", "toggle_media", "next", "previous", "prev", "volume_up", "volume_down", "mute"}:
        return _media_key(action)

    if action in {"help", "ajuda"}:
        return (
            "Acoes iPhone Bridge: status, config, setup/connect, open/phone_link, bluetooth_settings, "
            "open_app/open_game, call, sms, copy_to_phone, play_pause, next, previous, volume_up, volume_down, mute. "
            "No iPhone, o envio direto silencioso e leitura completa de tela sao limitados pelo iOS."
        )

    return "Acao desconhecida no iPhone Bridge. Use action=status ou action=help."
