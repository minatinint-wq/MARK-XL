from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any


BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
MACROS_PATH = BASE_DIR / "memory" / "automation_macros.json"
MAX_STEPS = 50
MAX_REPEAT = 20
MAX_WAIT_SECONDS = 60.0

ALLOWED_TOOLS = {
    "computer_control",
    "open_app",
    "browser_control",
    "steam_store",
    "game_vision",
    "image_search",
    "maps_mode",
    "wallpaper_engine",
    "sound_learning",
    "jarvis_lab",
    "iphone_bridge",
    "iphone_shortcuts",
    "social_control",
    "operation_memory",
    "obsidian_control",
    "brain_mode",
    "local_llm",
    "smart_home",
    "spotify_control",
}

COMPUTER_SHORTCUTS = {
    "click",
    "double_click",
    "right_click",
    "move",
    "mouse_relative",
    "position",
    "drag",
    "hotkey",
    "press",
    "hold",
    "scroll",
    "type",
    "smart_type",
    "paste",
    "set_clipboard",
    "read_clipboard",
    "copy",
    "screenshot",
    "clear_field",
    "focus_window",
    "list_windows",
    "active_window",
    "close_window",
    "minimize_window",
    "maximize_window",
    "restore_window",
    "activate_window",
    "move_window",
    "resize_window",
    "arrange_window",
    "screen_find",
    "screen_click",
}

BLOCKED_COMPUTER_ACTIONS = {
    "key_down",
}

DEFAULT_MACROS: dict[str, dict[str, Any]] = {
    "status_modelo_local": {
        "description": "Mostra status do modelo local via Ollama.",
        "aliases": ["status modelo local", "status ia local", "modelo local status"],
        "steps": [
            {"tool": "local_llm", "parameters": {"action": "status"}},
        ],
    },
    "modelo_local_rapido": {
        "description": "Ativa modelo local rapido 1B.",
        "aliases": ["modelo local rapido", "ia local rapida"],
        "steps": [
            {"tool": "local_llm", "parameters": {"action": "fast"}},
        ],
    },
    "modelo_local_profundo": {
        "description": "Ativa modelo local profundo 8B.",
        "aliases": ["modelo local profundo", "usar 8b profundo"],
        "steps": [
            {"tool": "local_llm", "parameters": {"action": "deep"}},
        ],
    },    "fixar_modelo_local_8b": {
        "description": "Configura llama3.1:8b como modelo local real.",
        "aliases": ["modelo local 8b", "usar llama 8b"],
        "steps": [
            {"tool": "local_llm", "parameters": {"action": "setup", "model": "llama3.1:8b", "parameters_b": 8}},
        ],
    },    "modulos_cerebro": {
        "description": "Lista modulos de parametros do cerebro Jarvis.",
        "aliases": ["modulos do cerebro", "parametros do cerebro"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulos"}},
        ],
    },
    "modulo_cerebro_pro": {
        "description": "Ativa modulo pro do cerebro com parametros elevados e otimizados.",
        "aliases": ["modulo pro", "aumentar parametros", "modo turbo cerebro"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulo", "module": "pro"}},
        ],
    },
    "modulo_cerebro_max": {
        "description": "Ativa modulo max para pesquisas pesadas.",
        "aliases": ["modulo max", "cerebro max"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulo", "module": "max"}},
        ],
    },
    "modulo_cerebro_ultra": {
        "description": "Ativa modulo ultra para analises longas.",
        "aliases": ["modulo ultra", "cerebro ultra", "aumenta tudo"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulo", "module": "ultra"}},
        ],
    },    "modo_pesquisa_cerebro": {
        "description": "Ativa o modo pesquisa/full neural do cerebro Jarvis.",
        "aliases": ["modo pesquisa", "full neural pesquisa"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "start", "mode": "pesquisa"}},
        ],
    },
    "modo_sono_cerebro": {
        "description": "Roda o modo sono para reindexar e consolidar o cerebro.",
        "aliases": ["modo sono", "sono cerebral"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "sono"}},
        ],
    },
    "pesquisar_e_copiar_link": {
        "description": "Abre uma pesquisa no navegador e prepara para copiar/usar o resultado.",
        "aliases": ["pesquisar e copiar link", "pesquisa rapida"],
        "steps": [
            {"tool": "browser_control", "parameters": {"action": "search", "query": "{query}"}},
        ],
    },
    "salvar_print": {
        "description": "Salva um print da tela na area de trabalho.",
        "aliases": ["salvar print", "tirar print", "screenshot rapido"],
        "steps": [
            {"tool": "computer_control", "parameters": {"action": "screenshot", "path": "{path}"}},
        ],
    },
    "copiar_e_ler": {
        "description": "Copia a selecao atual e retorna o texto do clipboard.",
        "aliases": ["copiar e ler", "le selecionado", "ler selecao"],
        "steps": [
            {"tool": "computer_control", "parameters": {"action": "copy"}},
        ],
    },
    "buscar_imagem_e_salvar": {
        "description": "Busca imagens na web e salva na pasta padrao configurada.",
        "aliases": ["buscar imagem e salvar", "salvar imagem da web"],
        "steps": [
            {"tool": "image_search", "parameters": {"action": "download", "query": "{query}", "count": "{count}"}},
        ],
    },
    "buscar_video_e_salvar": {
        "description": "Busca videos por API e salva na pasta padrao configurada.",
        "aliases": ["buscar video e salvar", "salvar video da web", "baixar video stock"],
        "steps": [
            {"tool": "image_search", "parameters": {"action": "download", "media_type": "video", "query": "{query}", "count": "{count}"}},
        ],
    },
    "pausar_wallpaper_engine": {
        "description": "Pausa todos os wallpapers animados do Wallpaper Engine.",
        "aliases": ["pausar wallpaper engine", "pausa wallpaper", "pausar wallpaper"],
        "steps": [
            {"tool": "wallpaper_engine", "parameters": {"action": "pause"}},
        ],
    },
    "retomar_wallpaper_engine": {
        "description": "Retoma os wallpapers animados do Wallpaper Engine.",
        "aliases": ["retomar wallpaper engine", "voltar wallpaper", "dar play no wallpaper"],
        "steps": [
            {"tool": "wallpaper_engine", "parameters": {"action": "play"}},
        ],
    },
    "preco_taskbar_hero": {
        "description": "Consulta preços/custos atuais do TBH: Task Bar Hero na Steam.",
        "aliases": ["preco taskbar hero", "preco do tbh", "custos do tbh"],
        "steps": [
            {"tool": "steam_store", "parameters": {"action": "taskbar_hero", "count": "{count}"}},
        ],
    },
    "salvar_precos_taskbar_hero": {
        "description": "Atualiza no cérebro/Obsidian a nota de preços e custos do TBH.",
        "aliases": ["salvar precos taskbar hero", "salvar custos tbh no cerebro"],
        "steps": [
            {"tool": "steam_store", "parameters": {"action": "save_taskbar_hero"}},
        ],
    },
    "modo_visao_taskbar_hero": {
        "description": "Ativa visão focada no TBH: Task Bar Hero.",
        "aliases": ["modo visao taskbar hero", "ver o jogo tbh", "analisa o taskbar hero"],
        "steps": [
            {"tool": "game_vision", "parameters": {"action": "start", "game": "taskbar hero"}},
        ],
    },
    "listar_janelas": {
        "description": "Lista as janelas abertas no PC.",
        "aliases": ["listar janelas", "ver janelas abertas", "janelas abertas"],
        "steps": [
            {"tool": "computer_control", "parameters": {"action": "list_windows", "limit": 30}},
        ],
    },
    "janela_ativa": {
        "description": "Mostra a janela ativa atual.",
        "aliases": ["janela ativa", "qual janela ativa", "ver janela atual"],
        "steps": [
            {"tool": "computer_control", "parameters": {"action": "active_window"}},
        ],
    },
    "maximizar_janela_ativa": {
        "description": "Maximiza a janela ativa.",
        "aliases": ["maximizar janela", "maximiza essa janela", "janela cheia"],
        "steps": [
            {"tool": "computer_control", "parameters": {"action": "maximize_window"}},
        ],
    },
    "restaurar_janela_ativa": {
        "description": "Restaura a janela ativa.",
        "aliases": ["restaurar janela", "volta janela", "desmaximizar janela"],
        "steps": [
            {"tool": "computer_control", "parameters": {"action": "restore_window"}},
        ],
    },
}


def _slug(text: str) -> str:
    text = str(text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\u00c0-\u017f]+", "_", text, flags=re.I)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80] or "macro"


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _load_macros() -> dict[str, dict[str, Any]]:
    if not MACROS_PATH.exists():
        _save_macros(dict(DEFAULT_MACROS))
        return dict(DEFAULT_MACROS)
    try:
        data = json.loads(MACROS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged = dict(DEFAULT_MACROS)
            for name, macro in data.items():
                if isinstance(macro, dict):
                    merged[str(name)] = macro
            return merged
    except Exception:
        pass
    return dict(DEFAULT_MACROS)


def _save_macros(macros: dict[str, dict[str, Any]]) -> None:
    MACROS_PATH.parent.mkdir(parents=True, exist_ok=True)
    MACROS_PATH.write_text(json.dumps(macros, indent=2, ensure_ascii=False), encoding="utf-8")


def _find_macro(macros: dict[str, dict[str, Any]], name: str) -> tuple[str | None, dict[str, Any] | None]:
    needle = re.sub(r"\s+", " ", str(name or "").lower()).strip()
    if not needle:
        return None, None
    slug = _slug(needle)
    if slug in macros:
        return slug, macros[slug]
    for key, macro in macros.items():
        names = [key, macro.get("description", "")]
        names.extend(_as_list(macro.get("aliases")))
        if any(re.sub(r"\s+", " ", str(item).lower()).strip() == needle for item in names):
            return key, macro
    for key, macro in macros.items():
        haystack = " ".join([key, macro.get("description", ""), *_as_list(macro.get("aliases"))]).lower()
        if needle in haystack:
            return key, macro
    return None, None


def _variables(params: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "query": "",
        "text": "",
        "value": "",
        "path": str(Path.home() / "Desktop" / "jarvis_screenshot.png"),
        "count": 1,
    }
    for key, value in params.items():
        if isinstance(key, str):
            defaults[key] = value
    defaults["query"] = params.get("query") or params.get("text") or params.get("value") or defaults["query"]
    defaults["text"] = params.get("text") or params.get("query") or params.get("value") or defaults["text"]
    defaults["value"] = params.get("value") or params.get("query") or params.get("text") or defaults["value"]
    return defaults


def _substitute(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        result = value
        for key, replacement in variables.items():
            result = result.replace("{" + key + "}", str(replacement))
        return result
    if isinstance(value, list):
        return [_substitute(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: _substitute(item, variables) for key, item in value.items()}
    return value


def _normalize_steps(raw_steps: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_steps, list):
        return []
    steps: list[dict[str, Any]] = []
    for raw in raw_steps[:MAX_STEPS]:
        if not isinstance(raw, dict):
            continue
        if raw.get("tool"):
            steps.append(dict(raw))
            continue
        action = str(raw.get("action") or "").lower().strip()
        if action in {"wait", "sleep", "esperar"}:
            steps.append({"tool": "wait", "parameters": {"seconds": raw.get("seconds", raw.get("duration", 1))}})
            continue
        if action in COMPUTER_SHORTCUTS:
            params = dict(raw)
            params["action"] = action
            steps.append({"tool": "computer_control", "parameters": params})
    return steps


def _validate_step(step: dict[str, Any]) -> str | None:
    tool = str(step.get("tool") or "").strip()
    if tool == "wait":
        return None
    if tool not in ALLOWED_TOOLS:
        return f"Ferramenta nao permitida em automacao: {tool or '(vazia)'}"
    params = step.get("parameters") or {}
    if not isinstance(params, dict):
        return f"Parametros invalidos para {tool}."
    if tool == "computer_control":
        action = str(params.get("action") or "").lower().strip()
        if action in BLOCKED_COMPUTER_ACTIONS:
            return f"Acao bloqueada em macro para evitar tecla presa: {action}. Use hold."
    return None


def _call_tool(tool: str, parameters: dict[str, Any], player=None, speak=None) -> str:
    if tool == "wait":
        seconds = max(0.0, min(float(parameters.get("seconds", 1)), MAX_WAIT_SECONDS))
        time.sleep(seconds)
        return f"wait {seconds:.2f}s"
    if tool == "computer_control":
        from actions.computer_control import computer_control
        return computer_control(parameters=parameters, player=player) or "OK"
    if tool == "open_app":
        from actions.open_app import open_app
        return open_app(parameters=parameters, player=player) or "OK"
    if tool == "browser_control":
        from actions.browser_control import browser_control
        return browser_control(parameters=parameters, player=player) or "OK"
    if tool == "steam_store":
        from actions.steam_store import steam_store
        return steam_store(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "game_vision":
        from actions.game_vision import game_vision
        return game_vision(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "image_search":
        from actions.image_search import image_search
        return image_search(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "maps_mode":
        from actions.maps_mode import maps_mode
        return maps_mode(parameters=parameters, player=player, speak=speak) or "OK"

    if tool == "wallpaper_engine":
        from actions.wallpaper_engine import wallpaper_engine
        return wallpaper_engine(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "sound_learning":
        from actions.sound_learning import sound_learning
        return sound_learning(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "jarvis_lab":
        from actions.jarvis_lab import jarvis_lab
        return jarvis_lab(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "iphone_bridge":
        from actions.iphone_bridge import iphone_bridge
        return iphone_bridge(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "iphone_shortcuts":
        from actions.iphone_shortcuts import iphone_shortcuts
        return iphone_shortcuts(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "social_control":
        from actions.social_control import social_control
        return social_control(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "operation_memory":
        from actions.operation_memory import operation_memory
        return operation_memory(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "obsidian_control":
        from actions.obsidian_controller import obsidian_control
        return obsidian_control(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "smart_home":
        from actions.smart_home import smart_home
        return smart_home(parameters=parameters, player=player) or "OK"
    if tool == "spotify_control":
        from actions.spotify_control import spotify_control
        return spotify_control(parameters=parameters, player=player) or "OK"
    if tool == "brain_mode":
        from actions.brain_mode import brain_mode
        return brain_mode(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "local_llm":
        from actions.local_llm import local_llm
        return local_llm(parameters=parameters, player=player, speak=speak) or "OK"
    return f"Ferramenta nao implementada: {tool}"


def _run_steps(steps: list[dict[str, Any]], params: dict[str, Any], player=None, speak=None) -> str:
    steps = _normalize_steps(steps)
    if not steps:
        return "Nenhum passo valido para executar."
    repeat = max(1, min(int(params.get("repeat") or params.get("times") or 1), MAX_REPEAT))
    variables = _variables(params)
    outputs: list[str] = []
    step_counter = 0
    for round_index in range(repeat):
        for step in steps:
            step_counter += 1
            if step_counter > MAX_STEPS * MAX_REPEAT:
                outputs.append("Limite de passos atingido; automacao interrompida.")
                return "\n".join(outputs)
            prepared = _substitute(step, variables)
            error = _validate_step(prepared)
            if error:
                outputs.append(f"{step_counter}. {error}")
                continue
            tool = str(prepared.get("tool") or "")
            tool_params = prepared.get("parameters") or {}
            try:
                result = _call_tool(tool, tool_params, player=player, speak=speak)
            except Exception as exc:
                result = f"falhou: {exc}"
            prefix = f"{step_counter}."
            if repeat > 1:
                prefix = f"{round_index + 1}/{repeat} {prefix}"
            outputs.append(f"{prefix} {tool}: {result}")
    return "\n".join(outputs)


def automation(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "run").lower().strip()
    macros = _load_macros()

    if player:
        player.write_log(f"[Automation] {action}")

    if action in {"status", "help", "ajuda"}:
        return (
            "Automacao pronta. Acoes: run, run_sequence, save, list, show, delete, defaults.\n"
            "Ferramentas permitidas: computer_control, open_app, browser_control, steam_store, game_vision, image_search, wallpaper_engine, iphone_bridge, iphone_shortcuts, social_control, operation_memory, obsidian_control, brain_mode, smart_home, spotify_control.\n"
            f"Macros salvas: {len(macros)} em {MACROS_PATH}"
        )

    if action in {"list", "listar", "macros"}:
        lines = [f"Macros de automacao ({len(macros)}):"]
        for name, macro in sorted(macros.items()):
            aliases = ", ".join(_as_list(macro.get("aliases"))[:3])
            suffix = f" - {aliases}" if aliases else ""
            lines.append(f"- {name}: {macro.get('description', 'sem descricao')}{suffix}")
        return "\n".join(lines)

    if action in {"defaults", "seed", "reset_defaults"}:
        macros.update(DEFAULT_MACROS)
        _save_macros(macros)
        return f"Macros padrao atualizadas em {MACROS_PATH}."

    if action in {"show", "ver", "read"}:
        name = params.get("name") or params.get("macro") or params.get("query")
        key, macro = _find_macro(macros, str(name or ""))
        if not macro:
            return f"Macro '{name}' nao encontrada."
        return json.dumps({key: macro}, indent=2, ensure_ascii=False)

    if action in {"delete", "remove", "apagar"}:
        name = params.get("name") or params.get("macro") or params.get("query")
        key, _ = _find_macro(macros, str(name or ""))
        if not key:
            return f"Macro '{name}' nao encontrada."
        macros.pop(key, None)
        _save_macros(macros)
        return f"Macro removida: {key}"

    if action in {"save", "salvar", "create", "criar"}:
        raw_name = str(params.get("name") or params.get("macro") or params.get("title") or "").strip()
        if not raw_name:
            return "Informe name para salvar a macro."
        steps = _normalize_steps(params.get("steps"))
        if not steps:
            return "Informe steps validos para salvar a macro."
        errors = [err for err in (_validate_step(step) for step in steps) if err]
        if errors:
            return "Macro nao salva: " + errors[0]
        key = _slug(raw_name)
        macros[key] = {
            "description": params.get("description") or f"Macro salva: {raw_name}",
            "aliases": _as_list(params.get("aliases")) or [raw_name],
            "steps": steps,
        }
        _save_macros(macros)
        return f"Macro salva: {key}"

    if action in {"run_sequence", "sequence", "sequencia", "executar_sequencia"}:
        return _run_steps(params.get("steps"), params, player=player, speak=speak)

    name = params.get("name") or params.get("macro") or params.get("query") or action
    key, macro = _find_macro(macros, str(name or ""))
    if not macro:
        return f"Macro '{name}' nao encontrada. Use action=list para ver as macros."
    result = _run_steps(macro.get("steps"), params, player=player, speak=speak)
    return f"Macro executada: {key}\n{result}"


if __name__ == "__main__":
    print(automation({"action": "status"}))



