from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "game_vision.json"

KNOWN_GAMES = {
    "tbh": {
        "name": "TBH: Task Bar Hero",
        "window_title": "Task Bar Hero",
        "platform": "steam",
        "app_id": "3678970",
        "prompt": (
            "Analise a tela do jogo TBH: Task Bar Hero. Foque em HUD, party, loot, inventario, "
            "drops, recursos, botoes, alertas, mensagens, progresso e qualquer item que pareca vender no Market. "
            "Se nao vir o jogo, diga no log que a janela precisa ser focada."
        ),
    },
    "taskbar hero": {
        "name": "TBH: Task Bar Hero",
        "window_title": "Task Bar Hero",
        "platform": "steam",
        "app_id": "3678970",
        "prompt": (
            "Analise a tela do jogo TBH: Task Bar Hero. Foque em HUD, party, loot, inventario, "
            "drops, recursos, botoes, alertas, mensagens, progresso e qualquer item que pareca vender no Market. "
            "Se nao vir o jogo, diga no log que a janela precisa ser focada."
        ),
    },
    "task bar hero": {
        "name": "TBH: Task Bar Hero",
        "window_title": "Task Bar Hero",
        "platform": "steam",
        "app_id": "3678970",
        "prompt": (
            "Analise a tela do jogo TBH: Task Bar Hero. Foque em HUD, party, loot, inventario, "
            "drops, recursos, botoes, alertas, mensagens, progresso e qualquer item que pareca vender no Market. "
            "Se nao vir o jogo, diga no log que a janela precisa ser focada."
        ),
    },
}


def _default_config() -> dict[str, Any]:
    return {
        "default_game": "taskbar hero",
        "default_interval": 3.5,
        "auto_focus": True,
        "auto_launch": False,
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


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on", "enabled"}


def _game_profile(params: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    raw = str(params.get("game") or params.get("game_name") or cfg.get("default_game") or "taskbar hero").lower().strip()
    if raw in KNOWN_GAMES:
        return dict(KNOWN_GAMES[raw])
    for key, profile in KNOWN_GAMES.items():
        if key in raw or raw in key:
            return dict(profile)
    return {
        "name": params.get("game_name") or params.get("game") or raw or "jogo",
        "window_title": params.get("window_title") or params.get("game_name") or params.get("game") or raw,
        "platform": params.get("platform"),
        "app_id": params.get("app_id"),
        "prompt": f"Analise a tela do jogo {raw}. Foque em HUD, recursos, menus, estado atual e proximas acoes visiveis.",
    }


def _focus_game(profile: dict[str, Any], player=None, speak=None) -> str:
    from actions.game_control import game_control

    title = str(profile.get("window_title") or profile.get("name") or "").strip()
    if not title:
        return "Sem titulo de janela para focar."
    return game_control({"action": "focus", "window_title": title}, player=player, speak=speak)


def _launch_game(profile: dict[str, Any], player=None, speak=None) -> str:
    from actions.game_control import game_control

    app_id = str(profile.get("app_id") or "").strip()
    platform = str(profile.get("platform") or "").strip()
    if platform and app_id:
        return game_control({"action": "launch", "platform": platform, "app_id": app_id, "game": profile.get("name")}, player=player, speak=speak)
    return "Sem platform/app_id para iniciar automaticamente."


def game_vision(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "start").lower().strip().replace("-", "_")
    cfg = _load_config()

    if player:
        try:
            player.write_log(f"[GameVision] {action}")
        except Exception:
            pass

    if action in {"status", "config"}:
        profile = _game_profile(params, cfg)
        return (
            "Game vision pronto.\n"
            f"Jogo padrao: {cfg.get('default_game')}\n"
            f"Perfil atual: {profile.get('name')}\n"
            f"Janela: {profile.get('window_title')}\n"
            f"Steam AppID: {profile.get('app_id') or 'nao definido'}\n"
            f"Intervalo: {cfg.get('default_interval')}s"
        )

    if action in {"set_config", "configurar"}:
        for key in ("default_game", "default_interval", "auto_focus", "auto_launch"):
            if params.get(key) is not None:
                cfg[key] = params[key]
        _save_config(cfg)
        return "Config game vision salva."

    if action in {"stop", "parar", "off"}:
        from actions.live_vision import stop_live_vision

        return stop_live_vision()

    profile = _game_profile(params, cfg)
    messages: list[str] = []

    launch = _as_bool(params.get("launch"), _as_bool(cfg.get("auto_launch"), False))
    focus = _as_bool(params.get("focus"), _as_bool(cfg.get("auto_focus"), True))
    if launch:
        messages.append(_launch_game(profile, player=player, speak=speak))
    if focus:
        messages.append(_focus_game(profile, player=player, speak=speak))

    user_text = str(params.get("text") or params.get("prompt") or profile.get("prompt") or "").strip()
    if params.get("market_hint"):
        user_text += f" Procure sinais relacionados ao Market/precos: {params['market_hint']}."

    if action in {"once", "analyze", "analisar", "snapshot"}:
        from actions.screen_processor import screen_process

        result = screen_process({"angle": "screen", "text": user_text}, player=player)
        messages.append(str(result))
        return "\n".join(item for item in messages if item)

    from actions.live_vision import live_vision

    interval = float(params.get("interval") or cfg.get("default_interval") or 3.5)
    interval = max(1.5, min(interval, 30.0))
    result = live_vision(
        {
            "mode": "screen",
            "text": user_text,
            "continuous": True,
            "interval": interval,
        },
        player=player,
        speak=speak,
    )
    messages.append(str(result))
    return "\n".join(item for item in messages if item)


if __name__ == "__main__":
    print(game_vision({"action": "status"}))
