from __future__ import annotations

import ast
import json
import math
import re
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
COMMANDS_PATH = BASE_DIR / "memory" / "quick_commands.json"

ALLOWED_TOOLS = {
    "video_generation",
    "open_app",
    "browser_control",
    "computer_control",
    "game_control",
    "steam_store",
    "game_vision",
    "image_search",
    "maps_mode",
    "wallpaper_engine",
    "sound_learning",
    "jarvis_lab",
    "iphone_bridge",
    "iphone_shortcuts",
    "jarvis_bridge_gateway",
    "social_control",
    "operation_memory",
    "automation",
    "smart_home",
    "spotify_control",
    "obsidian_control",
    "brain_mode",
    "local_llm",
}

DEFAULT_COMMANDS: dict[str, dict[str, Any]] = {
    'ligar_tomada_deposito': {'description': 'ligar tomada do depósito', 'aliases': ['ligar tomada do depósito', 'liga tomada do depósito', 'acender luz do depósito', 'ligar tomada do deposito'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'on', 'device': 'smart plug'}}]},
    'desligar_tomada_deposito': {'description': 'desligar tomada do depósito', 'aliases': ['desligar tomada do depósito', 'desliga tomada do depósito', 'apagar luz do depósito', 'desligar tomada do deposito'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'off', 'device': 'smart plug'}}]},
    'status_tomada_deposito': {'description': 'status da tomada do depósito', 'aliases': ['status da tomada do depósito', 'status da tomada do deposito'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'status', 'device': 'smart plug'}}]},
    'ligar_cafeteira_deposito': {'description': 'ligar Cafeteira switch_1 do depósito', 'aliases': ['ligar cafeteira do depósito', 'liga cafeteira do depósito', 'ligar cafeteira switch 1', 'ligar cafeteira sweet'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'on', 'device': 'Cafeteira switch_1'}}]},
    'desligar_cafeteira_deposito': {'description': 'desligar Cafeteira switch_1 do depósito', 'aliases': ['desligar cafeteira do depósito', 'desliga cafeteira do depósito', 'desligar cafeteira switch 1', 'desligar cafeteira sweet'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'off', 'device': 'Cafeteira switch_1'}}]},
    'status_cafeteira_deposito': {'description': 'status da Cafeteira switch_1 do depósito', 'aliases': ['status cafeteira do depósito', 'status cafeteira switch 1', 'status cafeteira sweet'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'status', 'device': 'Cafeteira switch_1'}}]},
    'ligar_cafeteira_quarto': {'description': 'ligar Cafeteira do quarto', 'aliases': ['ligar cafeteira do quarto', 'liga cafeteira do quarto'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'on', 'device': 'Cafeteira'}}]},
    'desligar_cafeteira_quarto': {'description': 'desligar Cafeteira do quarto', 'aliases': ['desligar cafeteira do quarto', 'desliga cafeteira do quarto'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'off', 'device': 'Cafeteira'}}]},
    'status_cafeteira_quarto': {'description': 'status da Cafeteira do quarto', 'aliases': ['status cafeteira do quarto'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'status', 'device': 'Cafeteira'}}]},
    'ligar_luz_grow': {'description': 'ligar a luz do grow', 'aliases': ['ligar luz do grow', 'liga a luz do grow', 'ligue a luz do grow', 'acender luz do grow', 'acenda a luz do grow', 'ativar luz do grow', 'liga grow control'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'on', 'device': 'grow control'}}]},
    'desligar_luz_grow': {'description': 'desligar a luz do grow', 'aliases': ['desligar luz do grow', 'desliga a luz do grow', 'desligue a luz do grow', 'apagar luz do grow', 'apaga a luz do grow', 'desativar luz do grow', 'desliga grow control'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'off', 'device': 'grow control'}}]},
    'status_luz_grow': {'description': 'consultar a luz do grow', 'aliases': ['status luz do grow', 'estado da luz do grow', 'a luz do grow esta ligada', 'como esta a luz do grow', 'status grow control'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'status', 'device': 'grow control'}}]},
    'ligar_sistema_rega': {'description': 'ligar o sistema de rega', 'aliases': ['ligar sistema de rega', 'liga o sistema de rega', 'ligue o sistema de rega', 'ativar sistema de rega', 'ativa a rega', 'ative a rega', 'ligar rega'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'on', 'device': 'rega'}}]},
    'desligar_sistema_rega': {'description': 'desligar o sistema de rega', 'aliases': ['desligar sistema de rega', 'desliga o sistema de rega', 'desligue o sistema de rega', 'desativar sistema de rega', 'desativa a rega', 'desative a rega', 'desligar rega'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'off', 'device': 'rega'}}]},
    'status_sistema_rega': {'description': 'consultar o sistema de rega', 'aliases': ['status sistema de rega', 'estado do sistema de rega', 'a rega esta ligada', 'como esta a rega', 'status rega'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'status', 'device': 'rega'}}]},
    'configurar_google_home': {'description': 'configurar google home', 'aliases': ['configurar google home', 'abrir google home'], 'steps': [{'tool': 'smart_home', 'parameters': {'domain': 'google_home', 'action': 'setup', 'device': 'grow control'}}]},
    "status_modelo_local": {
        "description": "Mostrar status do modelo local real via Ollama.",
        "aliases": ["status modelo local", "status ia local", "quantos parametros local", "modelo local status"],
        "steps": [
            {"tool": "local_llm", "parameters": {"action": "status"}},
        ],
    },
    "iniciar_modelo_local": {
        "description": "Iniciar Ollama/modelo local em segundo plano.",
        "aliases": ["iniciar modelo local", "liga modelo local", "abrir ollama", "ativar ia local"],
        "steps": [
            {"tool": "local_llm", "parameters": {"action": "start"}},
        ],
    },
    "listar_modelos_locais": {
        "description": "Listar modelos instalados no Ollama.",
        "aliases": ["listar modelos locais", "modelos ollama", "quais modelos locais", "ver modelos locais"],
        "steps": [
            {"tool": "local_llm", "parameters": {"action": "list"}},
        ],
    },
    "modelo_local_normal": {
        "description": "Ativar modo Normal: modelo local 1B com esforco baixo.",
        "aliases": ["modelo local normal", "modo local normal", "ia local normal", "usar 1b local"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulo", "module": "normal"}},
            {"tool": "local_llm", "parameters": {"action": "normal"}},
        ],
    },
    "modelo_local_rapido": {
        "description": "Ativar modo Rapido: Qwen 4B com esforco medio.",
        "aliases": ["modelo local rapido", "modo local rapido", "ia local rapida", "usar 4b local"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulo", "module": "rapido"}},
            {"tool": "local_llm", "parameters": {"action": "fast"}},
        ],
    },
    "modelo_local_ultra": {
        "description": "Ativar modo Ultra: Gemma 4 8B com esforco alto.",
        "aliases": ["modelo local ultra", "modo local ultra", "modelo local profundo", "usar 8b profundo", "ia local ultra"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulo", "module": "ultra"}},
            {"tool": "local_llm", "parameters": {"action": "ultra"}},
        ],
    },
    "fixar_ia_local": {
        "description": "Fixar Jarvis como IA local-first com cerebro Obsidian e parametros operacionais elevados.",
        "aliases": ["fixar ia local", "jarvis ia local", "full neural fixar", "fixa o jarvis local"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "pin", "module": "normal"}},
        ],
    },
    "modulos_cerebro": {
        "description": "Listar modulos de parametros do cerebro Jarvis.",
        "aliases": ["modulos do cerebro", "listar modulos do cerebro", "parametros do cerebro", "niveis do cerebro"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulos"}},
        ],
    },
    "modulo_cerebro_normal": {
        "description": "Ativar modo Normal do cerebro com modelo 1B e esforco baixo.",
        "aliases": ["modulo normal", "cerebro normal", "modo normal cerebro", "modulo leve"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulo", "module": "normal"}},
        ],
    },
    "modulo_cerebro_rapido": {
        "description": "Ativar modo Rapido do cerebro com Qwen 4B e esforco medio.",
        "aliases": ["modulo rapido", "cerebro rapido", "modo rapido cerebro", "modulo plus", "modulo pro"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulo", "module": "rapido"}},
        ],
    },
    "modulo_cerebro_ultra": {
        "description": "Ativar modo Ultra do cerebro com Gemma 4 8B e esforco alto.",
        "aliases": ["modulo ultra", "cerebro ultra", "parametros ultra", "modo ultra cerebro", "aumenta tudo", "modulo max"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "modulo", "module": "ultra"}},
        ],
    },    "modo_pesquisa_cerebro": {
        "description": "Ativar modo pesquisa/full neural do cerebro Jarvis.",
        "aliases": ["modo pesquisa", "ativar modo pesquisa", "modo pesquisa cerebral", "full neural pesquisa"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "start", "mode": "pesquisa"}},
        ],
    },
    "modo_sono_cerebro": {
        "description": "Iniciar modo sono para reindexar e consolidar o cerebro em segundo plano.",
        "aliases": ["modo sono", "ativar modo sono", "coloca o jarvis pra dormir", "sono cerebral"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "sono"}},
        ],
    },
    "status_cerebro": {
        "description": "Mostrar status do brain mode e do cerebro Obsidian.",
        "aliases": ["status do cerebro", "status brain mode", "como esta o cerebro", "quantas notas no cerebro"],
        "steps": [
            {"tool": "brain_mode", "parameters": {"action": "status"}},
        ],
    },
    "abrir_mine": {
        "description": "Abrir Minecraft Launcher.",
        "aliases": ["abrir mine", "abre mine", "minecraft", "abrir minecraft"],
        "steps": [
            {"tool": "open_app", "parameters": {"app_name": "Minecraft Launcher"}},
        ],
    },
    "abrir_taskbar_hero": {
        "description": "Abrir Taskbar Hero / TBH pelo menu iniciar.",
        "aliases": [
            "abrir taskbar hero",
            "abrir task bar hero",
            "abrir task bar heroes",
            "abrir tbh",
            "taskbar hero",
            "task bar heroes",
        ],
        "steps": [
            {"tool": "open_app", "parameters": {"app_name": "Taskbar Hero"}},
        ],
    },
    "preco_taskbar_hero": {
        "description": "Consultar custos/precos atuais do TBH: Task Bar Hero na Steam.",
        "aliases": ["preco taskbar hero", "preços taskbar hero", "preco do tbh", "custos do tbh", "quanto custa taskbar hero"],
        "steps": [
            {"tool": "steam_store", "parameters": {"action": "taskbar_hero", "count": "{count}"}},
        ],
    },
    "salvar_precos_taskbar_hero": {
        "description": "Atualizar no cérebro/Obsidian a nota de preços e custos do TBH.",
        "aliases": ["salvar precos taskbar hero", "salvar preços taskbar hero", "salvar custos tbh no cerebro", "atualizar precos do tbh no cerebro"],
        "steps": [
            {"tool": "steam_store", "parameters": {"action": "save_taskbar_hero"}},
        ],
    },
    "ver_taskbar_hero": {
        "description": "Ativar modo visão de jogo para TBH: Task Bar Hero.",
        "aliases": ["ver taskbar hero", "modo visao taskbar hero", "modo visão taskbar hero", "ver o jogo tbh", "analisa o taskbar hero"],
        "steps": [
            {"tool": "game_vision", "parameters": {"action": "start", "game": "taskbar hero"}},
        ],
    },
    "abrir_brawlhalla": {
        "description": "Abrir Brawlhalla pela Steam.",
        "aliases": ["abrir brawlhalla", "abre brawlhalla", "brawlhalla"],
        "steps": [
            {"tool": "game_control", "parameters": {"action": "launch", "platform": "steam", "app_id": "291550", "game": "Brawlhalla"}},
        ],
    },
    "abrir_clash_royale": {
        "description": "Abrir Clash Royale no PC/emulador, se estiver instalado.",
        "aliases": ["abrir clash royale", "abre clash royale", "clash royale", "abrir clash", "abre clash"],
        "steps": [
            {"tool": "open_app", "parameters": {"app_name": "Clash Royale"}},
        ],
    },
    "abrir_laboratorio": {
        "description": "Abrir a tela complementar Nexus Lab do Jarvis.",
        "aliases": ["abrir laboratorio", "abre laboratorio", "modo laboratorio", "nexus lab", "tela complementar"],
        "steps": [
            {"tool": "jarvis_lab", "parameters": {"action": "open"}},
        ],
    },
    "abrir_phone_link": {
        "description": "Abrir Phone Link para iPhone no Windows.",
        "aliases": ["abrir phone link", "abre phone link", "conectar iphone", "conecta meu iphone"],
        "steps": [
            {"tool": "iphone_bridge", "parameters": {"action": "open"}},
        ],
    },
    "config_iphone_social": {
        "description": "Abrir HTML local de configuracao do iPhone, WhatsApp e Instagram.",
        "aliases": ["config iphone", "config social", "abrir config do iphone", "config whatsapp instagram"],
        "steps": [
            {"tool": "iphone_bridge", "parameters": {"action": "config"}},
        ],
    },
    "iniciar_atalhos_iphone": {
        "description": "Iniciar ponte local silenciosa para Atalhos do iPhone.",
        "aliases": ["iniciar atalhos iphone", "ponte atalhos iphone", "ativar atalhos iphone", "servidor iphone"],
        "steps": [
            {"tool": "iphone_shortcuts", "parameters": {"action": "start", "silent": True}},
        ],
    },
    "iniciar_jarvis_bridge": {
        "description": "Iniciar imediatamente a JARVIS Bridge/PWA do iPhone.",
        "aliases": [
            "iniciar bridge", "inicia bridge", "liga bridge", "ligar bridge",
            "abrir bridge", "abre bridge", "ativar bridge", "iniciar jarvis bridge",
            "ligar jarvis bridge", "ponte jarvis", "ponte iphone"
        ],
        "steps": [
            {"tool": "jarvis_bridge_gateway", "parameters": {"action": "start", "silent": True}},
        ],
    },
    "status_aprendizado_operacional": {
        "description": "Mostrar o que o Jarvis aprendeu sobre operacoes silenciosas.",
        "aliases": ["aprendizado operacional", "status operacional", "o que voce aprendeu das operacoes"],
        "steps": [
            {"tool": "operation_memory", "parameters": {"action": "status"}},
        ],
    },
    "abrir_whatsapp_web": {
        "description": "Abrir WhatsApp Web.",
        "aliases": ["abrir whatsapp", "abre whatsapp", "whatsapp web", "abrir zap"],
        "steps": [
            {"tool": "social_control", "parameters": {"action": "open", "platform": "whatsapp"}},
        ],
    },
    "abrir_instagram_direct": {
        "description": "Abrir Instagram Direct.",
        "aliases": ["abrir instagram direct", "abre direct", "abrir dm instagram", "mensagens instagram"],
        "steps": [
            {"tool": "social_control", "parameters": {"action": "direct", "platform": "instagram"}},
        ],
    },
    "pesquisar_dados": {
        "description": "Pesquisar dados no navegador. Use query/text para o assunto.",
        "aliases": ["pesquisar dados", "buscar dados", "procura dados"],
        "steps": [
            {"tool": "browser_control", "parameters": {"action": "search", "query": "{query}"}},
        ],
    },
    "pesquisar_formulas": {
        "description": "Pesquisar formulas no navegador. Use query/text para o assunto.",
        "aliases": ["pesquisar formulas", "pesquisar fórmula", "buscar formula", "formula"],
        "steps": [
            {"tool": "browser_control", "parameters": {"action": "search", "query": "formula {query}"}},
        ],
    },
    "colar_clipboard": {
        "description": "Colar o conteudo atual do clipboard.",
        "aliases": ["colar", "cola isso", "colar copiado"],
        "steps": [
            {"tool": "computer_control", "parameters": {"action": "paste_clipboard"}},
        ],
    },
    "buscar_video_salvar": {
        "description": "Buscar video por API e salvar na pasta padrao.",
        "aliases": ["buscar video e salvar", "salvar video stock", "baixar video stock"],
        "steps": [
            {"tool": "image_search", "parameters": {"action": "download", "media_type": "video", "query": "{query}", "count": "{count}"}},
        ],
    },
    "pausar_wallpaper_engine": {
        "description": "Pausar Wallpaper Engine.",
        "aliases": ["pausar wallpaper engine", "pausar wallpaper", "pausa wallpaper"],
        "steps": [
            {"tool": "wallpaper_engine", "parameters": {"action": "pause"}},
        ],
    },
    "retomar_wallpaper_engine": {
        "description": "Retomar Wallpaper Engine.",
        "aliases": ["retomar wallpaper engine", "retomar wallpaper", "play wallpaper"],
        "steps": [
            {"tool": "wallpaper_engine", "parameters": {"action": "play"}},
        ],
    },
    "proximo_wallpaper": {
        "description": "Avancar para o proximo wallpaper do Wallpaper Engine.",
        "aliases": ["proximo wallpaper", "trocar wallpaper engine", "passar wallpaper"],
        "steps": [
            {"tool": "wallpaper_engine", "parameters": {"action": "next"}},
        ],
    },
}


def _slug(text: str) -> str:
    text = str(text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\u00c0-\u017f]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "command"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _load_commands() -> dict[str, dict[str, Any]]:
    if not COMMANDS_PATH.exists():
        _save_commands(dict(DEFAULT_COMMANDS))
        return dict(DEFAULT_COMMANDS)
    try:
        data = json.loads(COMMANDS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged = dict(DEFAULT_COMMANDS)
            for name, command in data.items():
                if isinstance(command, dict):
                    merged[str(name)] = command
            return merged
    except Exception:
        pass
    return dict(DEFAULT_COMMANDS)


def _save_commands(commands: dict[str, dict[str, Any]]) -> None:
    COMMANDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMMANDS_PATH.write_text(json.dumps(commands, indent=2, ensure_ascii=False), encoding="utf-8")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(",") if v.strip()]


def _find_command(commands: dict[str, dict[str, Any]], name: str) -> tuple[str | None, dict[str, Any] | None]:
    needle = _normalize(name)
    if not needle:
        return None, None
    slug = _slug(needle)
    if slug in commands:
        return slug, commands[slug]
    for key, command in commands.items():
        names = [key, command.get("description", "")]
        names.extend(_as_list(command.get("aliases", [])))
        if any(_normalize(item) == needle for item in names):
            return key, command
    for key, command in commands.items():
        aliases = [_normalize(a) for a in _as_list(command.get("aliases", []))]
        if needle in _normalize(key) or any(needle in alias or alias in needle for alias in aliases):
            return key, command
    return None, None


def _substitute(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        result = value
        for key, replacement in variables.items():
            result = result.replace("{" + key + "}", str(replacement or ""))
        return result.strip()
    if isinstance(value, dict):
        return {key: _substitute(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute(item, variables) for item in value]
    return value


def _call_tool(tool: str, parameters: dict, player=None, speak=None) -> str:
    if tool not in ALLOWED_TOOLS:
        return f"Ferramenta nao permitida em quick_commands: {tool}"

    if tool == "video_generation":
        from actions.video_generation import video_generation
        return video_generation(parameters=parameters, player=player, speak=speak)
    if tool == "open_app":
        from actions.open_app import open_app
        return open_app(parameters=parameters, player=player) or "OK"
    if tool == "browser_control":
        from actions.browser_control import browser_control
        return browser_control(parameters=parameters, player=player) or "OK"
    if tool == "computer_control":
        from actions.computer_control import computer_control
        return computer_control(parameters=parameters, player=player) or "OK"
    if tool == "game_control":
        from actions.game_control import game_control
        return game_control(parameters=parameters, player=player, speak=speak) or "OK"
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
    if tool == "jarvis_bridge_gateway":
        from actions.jarvis_bridge_gateway import jarvis_bridge_gateway
        return jarvis_bridge_gateway(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "social_control":
        from actions.social_control import social_control
        return social_control(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "operation_memory":
        from actions.operation_memory import operation_memory
        return operation_memory(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "automation":
        from actions.automation import automation
        return automation(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "smart_home":
        from actions.smart_home import smart_home
        return smart_home(parameters=parameters, player=player) or "OK"
    if tool == "spotify_control":
        from actions.spotify_control import spotify_control
        return spotify_control(parameters=parameters, player=player) or "OK"
    if tool == "obsidian_control":
        from actions.obsidian_controller import obsidian_control
        return obsidian_control(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "brain_mode":
        from actions.brain_mode import brain_mode
        return brain_mode(parameters=parameters, player=player, speak=speak) or "OK"
    if tool == "local_llm":
        from actions.local_llm import local_llm
        return local_llm(parameters=parameters, player=player, speak=speak) or "OK"
    return "OK"


def _safe_calculate(expression: str) -> str:
    expression = str(expression or "").strip().replace(",", ".")
    if not expression:
        return "Me passa a conta para calcular."

    allowed_names = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sqrt": math.sqrt,
        "pow": pow,
        "pi": math.pi,
        "e": math.e,
    }

    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"Nome nao permitido: {node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in allowed_names:
                raise ValueError("Funcao nao permitida nessa conta.")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("Use apenas numeros na conta.")
        if not isinstance(
            node,
            (
                ast.Expression,
                ast.BinOp,
                ast.UnaryOp,
                ast.Constant,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.FloorDiv,
                ast.Mod,
                ast.Pow,
                ast.USub,
                ast.UAdd,
                ast.Load,
                ast.Name,
                ast.Call,
            ),
        ):
            raise ValueError("Expressao nao permitida.")

    result = eval(compile(tree, "<quick-calc>", "eval"), {"__builtins__": {}}, allowed_names)
    return f"{expression} = {result}"


def _infer_steps(params: dict) -> list[dict[str, Any]]:
    steps = params.get("steps")
    if isinstance(steps, list):
        return steps

    tool = params.get("tool")
    tool_params = params.get("parameters") or params.get("tool_parameters")
    if tool and isinstance(tool_params, dict):
        return [{"tool": str(tool), "parameters": tool_params}]

    app_name = params.get("app_name")
    if app_name:
        return [{"tool": "open_app", "parameters": {"app_name": app_name}}]

    command = str(params.get("command") or params.get("text") or "").strip()
    lowered = command.lower()
    for prefix in ("abrir ", "abre ", "open "):
        if lowered.startswith(prefix):
            return [{"tool": "open_app", "parameters": {"app_name": command[len(prefix):].strip()}}]
    if lowered.startswith(("pesquisar ", "buscar ", "search ")):
        query = re.sub(r"^(pesquisar|buscar|search)\s+", "", command, flags=re.I).strip()
        return [{"tool": "browser_control", "parameters": {"action": "search", "query": query or "{query}"}}]

    return []


def quick_command(parameters: dict = None, player=None, speak=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action") or "run").lower().strip()
    commands = _load_commands()

    if player:
        player.write_log(f"[QuickCommand] {action}")

    if action in ("list", "listar", "commands", "status"):
        lines = [f"Comandos padrao salvos ({len(commands)}):"]
        for name, command in sorted(commands.items()):
            aliases = ", ".join(_as_list(command.get("aliases", []))[:3])
            suffix = f" — {aliases}" if aliases else ""
            lines.append(f"- {name}: {command.get('description', 'sem descricao')}{suffix}")
        return "\n".join(lines)

    if action in ("seed", "defaults", "reset_defaults"):
        commands.update(DEFAULT_COMMANDS)
        _save_commands(commands)
        return f"Comandos padrao atualizados em {COMMANDS_PATH}."

    if action in ("show", "read", "ver"):
        name = params.get("name") or params.get("command") or params.get("query")
        key, command = _find_command(commands, str(name or ""))
        if not command:
            return f"Comando '{name}' nao encontrado."
        return json.dumps({key: command}, indent=2, ensure_ascii=False)

    if action in ("delete", "remove", "apagar"):
        name = params.get("name") or params.get("command")
        key, _ = _find_command(commands, str(name or ""))
        if not key:
            return f"Comando '{name}' nao encontrado."
        commands.pop(key, None)
        _save_commands(commands)
        return f"Comando removido: {key}"

    if action in ("save", "salvar", "create", "criar"):
        raw_name = str(params.get("name") or params.get("command_name") or params.get("title") or "").strip()
        if not raw_name:
            return "Informe name para salvar o comando."
        steps = _infer_steps(params)
        if not steps:
            return "Informe steps ou um command/app_name para salvar."
        key = _slug(raw_name)
        if key in commands and not bool(params.get("overwrite", True)):
            return f"Comando '{key}' ja existe. Use overwrite=true para substituir."
        commands[key] = {
            "description": params.get("description") or f"Comando salvo: {raw_name}",
            "aliases": _as_list(params.get("aliases")) or [raw_name],
            "steps": steps,
        }
        _save_commands(commands)
        return f"Comando salvo: {key}"

    if action in ("calculate", "calc", "conta", "calcular"):
        expression = params.get("expression") or params.get("query") or params.get("text") or params.get("value")
        return _safe_calculate(str(expression or ""))

    if action in ("formula", "formulas", "pesquisar_formula"):
        query = params.get("query") or params.get("text") or params.get("value") or ""
        if not query:
            return "Qual formula voce quer pesquisar?"
        from actions.browser_control import browser_control
        return browser_control(parameters={"action": "search", "query": f"formula {query}"}, player=player)

    if action in ("search", "pesquisar", "dados", "pesquisar_dados"):
        query = params.get("query") or params.get("text") or params.get("value") or ""
        if not query:
            return "O que voce quer pesquisar?"
        from actions.browser_control import browser_control
        return browser_control(parameters={"action": "search", "query": str(query)}, player=player)

    name = params.get("name") or params.get("command") or params.get("query") or action
    key, command = _find_command(commands, str(name or ""))
    if not command:
        return f"Comando '{name}' nao encontrado. Use action=list para ver os comandos salvos."

    variables = {
        "query": params.get("query") or params.get("text") or params.get("value") or "",
        "text": params.get("text") or params.get("query") or params.get("value") or "",
        "value": params.get("value") or params.get("query") or params.get("text") or "",
        "expression": params.get("expression") or params.get("query") or params.get("text") or "",
    }

    outputs: list[str] = []
    for step in command.get("steps", []):
        if not isinstance(step, dict):
            continue
        tool = str(step.get("tool") or "").strip()
        step_params = _substitute(step.get("parameters") or {}, variables)
        outputs.append(f"{tool}: {_call_tool(tool, step_params, player=player, speak=speak)}")

    return f"Comando executado: {key}\n" + "\n".join(outputs)
