from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "memory" / "brain_mode_state.json"
BRAIN_ROOT = Path(r"D:\xxxx_memory")
STATUS_NOTE = BRAIN_ROOT / "00_Cerebro" / "_brain-mode-status.md"
PROFILE_NOTE = BRAIN_ROOT / "00_Cerebro" / "_jarvis-local-ai-profile.md"

_SLEEP_LOCK = threading.Lock()
_SLEEP_THREAD: threading.Thread | None = None
_STOP_SLEEP = threading.Event()
PARAMETER_MODULES: dict[str, dict[str, Any]] = {
    "normal": {"label": "normal", "description": "Uso leve com modelo 1B e esforco baixo.", "llm_mode": "normal", "context_budget_chars": 5000, "max_results": 6, "deep_count": 2, "per_note_chars": 1200, "max_context_budget_chars": 6000},
    "rapido": {"label": "rapido", "description": "Pesquisa equilibrada com modelo 4B e esforco medio.", "llm_mode": "fast", "context_budget_chars": 10000, "max_results": 10, "deep_count": 5, "per_note_chars": 1800, "max_context_budget_chars": 12000},
    "ultra": {"label": "ultra", "description": "Analise profunda sob demanda com modelo Gemma 4 8B e esforco alto.", "llm_mode": "ultra", "context_budget_chars": 18000, "max_results": 16, "deep_count": 8, "per_note_chars": 2600, "max_context_budget_chars": 20000},
}

MODULE_ALIASES = {
    "light": "normal", "leve": "normal", "plus": "normal", "padrao": "normal", "default": "normal",
    "fast": "rapido", "rapida": "rapido", "medio": "rapido", "pro": "rapido", "turbo": "rapido",
    "deep": "ultra", "profundo": "ultra", "alto": "ultra", "high": "ultra", "max": "ultra", "full": "ultra", "maximum": "ultra", "pro_max": "ultra",
    "ultra_max": "ultra", "laboratorio": "ultra", "lab": "ultra",
}


def _normalize_module_name(value: Any) -> str:
    name = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return MODULE_ALIASES.get(name, name)


def _module_parameters(module: Any) -> dict[str, Any]:
    key = _normalize_module_name(module)
    if key not in PARAMETER_MODULES:
        key = "normal"
    preset = dict(PARAMETER_MODULES[key])
    preset.pop("label", None)
    preset.pop("description", None)
    preset["module"] = key
    preset["sleep_mode"] = "background_manual_or_requested"
    preset["startup_policy"] = "do_not_preload_full_vault"
    return preset


def _default_operational_parameters() -> dict[str, Any]:
    return _module_parameters("normal")

def _default_state() -> dict[str, Any]:
    return {
        "profile": "local_ai_full_neural",
        "pinned": True,
        "parameter_module": "normal",
        "architecture": "local-first RAG over Obsidian vault with tool execution",
        "operational_parameters": _default_operational_parameters(),
        "research_enabled": True,
        "sleep_enabled": True,
        "sleep_running": False,
        "last_research_query": "",
        "last_research_at": "",
        "last_sleep_started_at": "",
        "last_sleep_completed_at": "",
        "last_sleep_seconds": 0.0,
        "last_sleep_error": "",
        "last_totals": {},
    }


def _load_state() -> dict[str, Any]:
    state = _default_state()
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                state.update(data)
                merged = _default_operational_parameters()
                merged.update(state.get("operational_parameters") or {})
                module = _normalize_module_name(state.get("parameter_module") or merged.get("module") or "normal")
                if module not in PARAMETER_MODULES:
                    module = "normal"
                merged["module"] = module
                state["parameter_module"] = module
                state["operational_parameters"] = merged
    except Exception:
        pass
    return state


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on", "enabled", "ativo"}


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + "\n[truncado]"


def _vault_totals() -> dict[str, Any]:
    from memory.memory_manager import scan_vault_structure

    structure = scan_vault_structure()
    md_count = 0
    md_bytes = 0
    if BRAIN_ROOT.exists():
        notes = list(BRAIN_ROOT.rglob("*.md"))
        md_count = len(notes)
        md_bytes = sum(p.stat().st_size for p in notes if p.exists())
    return {
        "vault_root": str(BRAIN_ROOT),
        "categories": len(structure),
        "indexed_notes": sum(structure.values()),
        "md_files": md_count,
        "md_mb": round(md_bytes / 1024 / 1024, 2),
    }


def _write_status_note(state: dict[str, Any], totals: dict[str, Any]) -> None:
    STATUS_NOTE.parent.mkdir(parents=True, exist_ok=True)
    params = state.get("operational_parameters") or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = [
        "---",
        f"updated: {now}",
        "tags: [cerebro, jarvis, brain-mode, pesquisa, sono]",
        "type: status",
        "folder: 00_Cerebro",
        "---",
        "",
        "# Brain Mode - Status",
        "",
        f"- Perfil: {state.get('profile') or 'local_ai_full_neural'}",
        f"- Fixado: {'sim' if state.get('pinned') else 'nao'}",
        f"- Modulo de parametros: {state.get('parameter_module') or params.get('module') or 'normal'}",
        f"- Modo LLM: {params.get('llm_mode') or 'normal'}",
        f"- Context budget: {params.get('context_budget_chars')} chars",
        f"- Max results: {params.get('max_results')}",
        f"- Deep notes: {params.get('deep_count')}",
        f"- Per-note chars: {params.get('per_note_chars')}",
        f"- Arquitetura: {state.get('architecture') or 'local-first RAG'}",
        f"- Modo pesquisa: {'ativo' if state.get('research_enabled') else 'inativo'}",
        f"- Modo sono: {'ativo' if state.get('sleep_enabled') else 'inativo'}",
        f"- Sono rodando: {'sim' if state.get('sleep_running') else 'nao'}",
        f"- Ultima pesquisa: {state.get('last_research_query') or 'nenhuma'}",
        f"- Ultima pesquisa em: {state.get('last_research_at') or 'nunca'}",
        f"- Ultimo sono iniciou: {state.get('last_sleep_started_at') or 'nunca'}",
        f"- Ultimo sono concluiu: {state.get('last_sleep_completed_at') or 'nunca'}",
        f"- Ultimo sono durou: {state.get('last_sleep_seconds') or 0}s",
        f"- Erro ultimo sono: {state.get('last_sleep_error') or 'nenhum'}",
        "",
        "## Totais",
        "",
        f"- Vault: {totals.get('vault_root')}",
        f"- Categorias: {totals.get('categories')}",
        f"- Notas indexaveis: {totals.get('indexed_notes')}",
        f"- Arquivos Markdown: {totals.get('md_files')}",
        f"- Markdown bruto: {totals.get('md_mb')} MB",
        f"- Itens no search index: {totals.get('search_index_files', 'indisponivel')}",
    ]
    STATUS_NOTE.write_text("\n".join(body) + "\n", encoding="utf-8")


def _write_profile_note(state: dict[str, Any], totals: dict[str, Any]) -> Path:
    PROFILE_NOTE.parent.mkdir(parents=True, exist_ok=True)
    params = state.get("operational_parameters") or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "---",
        f"updated: {now}",
        "tags: [cerebro, jarvis, local-ai, full-neural, rag]",
        "type: profile",
        "folder: 00_Cerebro",
        "---",
        "",
        "# Jarvis Local AI Profile",
        "",
        "Este arquivo fixa o Jarvis como uma IA local-first baseada no cerebro Obsidian.",
        "",
        "## Identidade operacional",
        "",
        f"- Perfil: {state.get('profile') or 'local_ai_full_neural'}",
        f"- Fixado: {'sim' if state.get('pinned') else 'nao'}",
        f"- Arquitetura: {state.get('architecture') or 'local-first RAG over Obsidian vault with tool execution'}",
        "- Modelo: externo/API quando necessario; memoria e conhecimento primario ficam locais no vault.",
        "- Parametros reais de rede neural: dependem do modelo chamado pela API.",
        "- Parametros locais: busca, contexto, ranking, leitura profunda, ferramentas e modo sono.",
        "",
        "## Parametros operacionais elevados",
        "",
        f"- Modulo ativo: {state.get('parameter_module') or params.get('module') or 'normal'}",
        f"- Modo LLM: {params.get('llm_mode') or 'normal'}",
        f"- Context budget: {params.get('context_budget_chars')} chars",
        f"- Max results: {params.get('max_results')}",
        f"- Deep notes: {params.get('deep_count')}",
        f"- Per-note chars: {params.get('per_note_chars')}",
        f"- Max context budget: {params.get('max_context_budget_chars')} chars",
        f"- Modulos disponiveis: {', '.join(PARAMETER_MODULES.keys())}",
        f"- Startup policy: {params.get('startup_policy')}",
        f"- Sleep mode: {params.get('sleep_mode')}",
        "",
        "## Otimizacao",
        "",
        "- O vault completo nao e carregado na inicializacao.",
        "- As respostas usam indice local rapido e so abrem o conteudo das melhores notas.",
        "- O modo sono reconstrui indices em segundo plano quando solicitado.",
        "- O Obsidian pode mostrar tudo; a pesquisa do Jarvis permanece seletiva para nao travar.",
        "",
        "## Estado atual",
        "",
        f"- Vault: {totals.get('vault_root')}",
        f"- Categorias: {totals.get('categories')}",
        f"- Notas indexaveis: {totals.get('indexed_notes')}",
        f"- Arquivos Markdown: {totals.get('md_files')}",
        f"- Markdown bruto: {totals.get('md_mb')} MB",
        f"- Itens no search index: {totals.get('search_index_files', 'indisponivel')}",
    ]
    PROFILE_NOTE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return PROFILE_NOTE


def _research(params: dict[str, Any]) -> str:
    from memory.memory_manager import load_obsidian_context, search_vault_content

    query = str(params.get("query") or params.get("text") or "").strip()
    state = _load_state()
    operational = state.get("operational_parameters") or {}
    max_results = int(params.get("max_results") or params.get("limit") or operational.get("max_results") or 9)
    max_results = max(1, min(max_results, 25))
    max_chars = int(params.get("max_chars") or operational.get("context_budget_chars") or 9000)
    max_cap = int(operational.get("max_context_budget_chars") or 20000)
    max_cap = max(1200, min(max_cap, 32000))
    max_chars = max(1200, min(max_chars, max_cap))
    deep = _bool(params.get("deep"), True)
    deep_count = int(params.get("deep_count") or operational.get("deep_count") or 4)
    deep_count = max(0, min(deep_count, max_results, 12))
    per_note_chars = int(params.get("per_note_chars") or operational.get("per_note_chars") or 1600)
    per_note_chars = max(300, min(per_note_chars, 6000))

    state["research_enabled"] = True
    state["last_research_query"] = query
    state["last_research_at"] = datetime.now().isoformat(timespec="seconds")
    _save_state(state)

    if not query:
        context = load_obsidian_context(max_chars=max_chars)
        return _clip("[BRAIN_MODE pesquisa]\n" + context, max_chars)

    results = search_vault_content(query, max_results=max_results)
    lines = [
        "[BRAIN_MODE pesquisa]",
        f"Query: {query}",
        "Use estes trechos como contexto do cerebro antes de responder. Se forem fracos, diga isso e peca busca externa.",
        "",
    ]
    if not results:
        lines.append("Nenhum resultado relevante no cerebro.")
        return "\n".join(lines)

    lines.append(f"Resultados: {len(results)}")
    for index, item in enumerate(results, start=1):
        lines.append("")
        lines.append(f"{index}. {item.get('title') or 'Nota'}")
        lines.append(f"   Pasta: {item.get('folder') or ''}")
        lines.append(f"   Score: {item.get('score') or 0}")
        lines.append(f"   Caminho: {item.get('path') or ''}")
        snippet = str(item.get("snippet") or "").strip()
        if snippet:
            lines.append(f"   Trecho: {_clip(snippet, 700)}")

    if deep and deep_count:
        lines.append("")
        lines.append("## Conteudo profundo")
        for item in results[:deep_count]:
            path = Path(str(item.get("path") or ""))
            if not path.exists() or path.suffix.lower() != ".md":
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines.append("")
            lines.append(f"### {item.get('title') or path.stem}")
            lines.append(f"Fonte: {path}")
            lines.append(_clip(text.strip(), per_note_chars))

    return _clip("\n".join(lines), max_chars)


def _run_sleep_cycle() -> dict[str, Any]:
    from memory.memory_manager import generate_vault_groups, generate_vault_index, generate_vault_search_index

    state = _load_state()
    started = time.time()
    state["sleep_running"] = True
    state["last_sleep_started_at"] = datetime.now().isoformat(timespec="seconds")
    state["last_sleep_error"] = ""
    _save_state(state)

    try:
        if _STOP_SLEEP.is_set():
            raise RuntimeError("Modo sono cancelado antes de iniciar.")
        generate_vault_index()
        if _STOP_SLEEP.is_set():
            raise RuntimeError("Modo sono cancelado apos vault_index.")
        generate_vault_groups()
        if _STOP_SLEEP.is_set():
            raise RuntimeError("Modo sono cancelado apos vault_groups.")
        search_index = generate_vault_search_index()
        totals = _vault_totals()
        totals["search_index_files"] = search_index.get("total_files")
        state["last_totals"] = totals
        state["last_sleep_error"] = ""
    except Exception as exc:
        totals = _vault_totals()
        state["last_sleep_error"] = str(exc)
    finally:
        elapsed = round(time.time() - started, 2)
        state["sleep_running"] = False
        state["last_sleep_completed_at"] = datetime.now().isoformat(timespec="seconds")
        state["last_sleep_seconds"] = elapsed
        state["last_totals"] = totals
        _save_state(state)
        _write_status_note(state, totals)
        _write_profile_note(state, totals)
        _STOP_SLEEP.clear()
    return state


def _start_sleep_background() -> str:
    global _SLEEP_THREAD
    with _SLEEP_LOCK:
        if _SLEEP_THREAD and _SLEEP_THREAD.is_alive():
            return "Modo sono ja esta rodando em segundo plano."
        _STOP_SLEEP.clear()
        _SLEEP_THREAD = threading.Thread(target=_run_sleep_cycle, daemon=True, name="JarvisBrainSleep")
        _SLEEP_THREAD.start()
    return "Modo sono iniciado em segundo plano: reindexando cerebro, grupos e mapa neural."


def _status() -> str:
    state = _load_state()
    totals = state.get("last_totals") or _vault_totals()
    params = state.get("operational_parameters") or {}
    lines = [
        "Brain mode pronto.",
        f"Perfil: {state.get('profile') or 'local_ai_full_neural'}",
        f"Fixado como IA local: {'sim' if state.get('pinned') else 'nao'}",
        f"Modulo ativo: {state.get('parameter_module') or params.get('module') or 'normal'}",
        f"Modo LLM: {params.get('llm_mode') or 'normal'}",
        f"Parametros: context={params.get('context_budget_chars')} chars, results={params.get('max_results')}, deep={params.get('deep_count')}, per_note={params.get('per_note_chars')} chars",
        f"Modo pesquisa: {'ativo' if state.get('research_enabled') else 'inativo'}",
        f"Modo sono: {'rodando' if state.get('sleep_running') else 'parado'}",
        f"Ultimo sono: {state.get('last_sleep_completed_at') or 'nunca'}",
        f"Erro sono: {state.get('last_sleep_error') or 'nenhum'}",
        f"Categorias: {totals.get('categories')}",
        f"Notas indexaveis: {totals.get('indexed_notes')}",
        f"Markdown: {totals.get('md_files')} arquivos / {totals.get('md_mb')} MB",
        f"Status note: {STATUS_NOTE}",
        f"Profile note: {PROFILE_NOTE}",
    ]
    return "\n".join(lines)


def get_active_llm_mode() -> str:
    """Return the local model tier attached to the active brain preset."""
    state = _load_state()
    operational = state.get("operational_parameters") or {}
    configured = str(operational.get("llm_mode") or "").strip().lower()
    if configured in {"normal", "fast", "ultra"}:
        return configured
    module = _normalize_module_name(state.get("parameter_module") or operational.get("module") or "normal")
    return str(PARAMETER_MODULES.get(module, PARAMETER_MODULES["normal"])["llm_mode"])


def _available_modules_text() -> str:
    lines = ["Modulos de parametros do cerebro:"]
    for key, preset in PARAMETER_MODULES.items():
        lines.append(
            f"- {key}: context={preset['context_budget_chars']} chars, "
            f"results={preset['max_results']}, deep={preset['deep_count']}, "
            f"per_note={preset['per_note_chars']} chars, llm={preset['llm_mode']}. {preset['description']}"
        )
    lines.append("Use brain_mode action='modulo' com module='normal|rapido|ultra'.")
    return "\n".join(lines)


def _set_parameter_module(params: dict[str, Any]) -> str:
    requested = params.get("module") or params.get("modulo") or params.get("level") or params.get("name") or params.get("preset") or params.get("mode") or "normal"
    module = _normalize_module_name(requested)
    if module not in PARAMETER_MODULES:
        return f"Modulo desconhecido: {requested}.\n" + _available_modules_text()

    state = _load_state()
    operational = _module_parameters(module)
    state.update(
        {
            "parameter_module": module,
            "profile": state.get("profile") or "local_ai_full_neural",
            "pinned": True,
            "research_enabled": True,
            "sleep_enabled": True,
            "operational_parameters": operational,
        }
    )
    totals = state.get("last_totals") or _vault_totals()
    state["last_totals"] = totals
    _save_state(state)
    _write_status_note(state, totals)
    profile_note = _write_profile_note(state, totals)
    return (
        f"Modulo de parametros ativado: {module}.\n"
        f"Context={operational['context_budget_chars']} chars, results={operational['max_results']}, "
        f"deep={operational['deep_count']}, per_note={operational['per_note_chars']} chars, llm={operational['llm_mode']}.\n"
        "Startup continua otimizado: o vault nao e pre-carregado.\n"
        f"Nota de perfil: {profile_note}"
    )

def _pin_local_ai(params: dict[str, Any]) -> str:
    state = _load_state()
    requested_module = params.get("module") or params.get("modulo") or params.get("level")
    if requested_module:
        operational = _module_parameters(requested_module)
    else:
        operational = dict(state.get("operational_parameters") or _default_operational_parameters())

    if params.get("context_budget_chars") is not None:
        operational["context_budget_chars"] = max(1200, min(int(params["context_budget_chars"]), 32000))
    if params.get("max_results") is not None:
        operational["max_results"] = max(1, min(int(params["max_results"]), 25))
    if params.get("deep_count") is not None:
        operational["deep_count"] = max(0, min(int(params["deep_count"]), 12))
    if params.get("per_note_chars") is not None:
        operational["per_note_chars"] = max(300, min(int(params["per_note_chars"]), 6000))
    if params.get("max_context_budget_chars") is not None:
        operational["max_context_budget_chars"] = max(1200, min(int(params["max_context_budget_chars"]), 32000))

    module = operational.get("module") or state.get("parameter_module") or "normal"
    state.update(
        {
            "profile": str(params.get("profile") or "local_ai_full_neural"),
            "pinned": True,
            "parameter_module": module,
            "architecture": "local-first RAG over Obsidian vault with tool execution",
            "research_enabled": True,
            "sleep_enabled": True,
            "operational_parameters": operational,
        }
    )
    totals = _vault_totals()
    state["last_totals"] = totals
    _save_state(state)
    _write_status_note(state, totals)
    profile_note = _write_profile_note(state, totals)
    return (
        "Jarvis fixado como IA local-first baseada no cerebro.\n"
        f"Perfil: {state['profile']}\n"
        f"Modulo: {module}\n"
        f"Parametros: results={operational.get('max_results')}, deep={operational.get('deep_count')}, "
        f"context={operational.get('context_budget_chars')} chars, per_note={operational.get('per_note_chars')} chars.\n"
        f"Nota de perfil: {profile_note}"
    )

def brain_mode(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or params.get("mode") or "status").lower().strip().replace("-", "_")

    if player:
        try:
            player.write_log(f"[BrainMode] {action}")
        except Exception:
            pass

    if action in {"status", "stats", "estado"}:
        from actions.brain_activity import reading_notes
        with reading_notes(player):
            return _status()

    if action in {"modules", "modulos", "listar_modulos", "parameter_modules"}:
        return _available_modules_text()

    if action in {"module", "modulo", "set_module", "parametros", "parameters", "aumentar_parametros"}:
        return _set_parameter_module(params)

    if action in {"pin", "fixar", "local_ai", "full_neural"}:
        return _pin_local_ai(params)

    if action in {"pesquisa", "research", "search", "context", "contexto"}:
        return _research(params)

    if action in {"sono", "sleep", "sleep_start", "start_sleep"}:
        state = _load_state()
        state["sleep_enabled"] = True
        _save_state(state)
        if _bool(params.get("wait"), False) or _bool(params.get("sync"), False):
            _run_sleep_cycle()
            return "Modo sono concluido.\n" + _status()
        return _start_sleep_background()

    if action in {"sleep_once", "rebuild", "reindex", "reindexar", "compactar"}:
        _run_sleep_cycle()
        return "Modo sono concluido.\n" + _status()

    if action in {"stop", "stop_sleep", "parar_sono"}:
        _STOP_SLEEP.set()
        return "Pedido de parada enviado ao modo sono."

    if action in {"start", "enable", "ativar"}:
        mode = str(params.get("mode") or "full_neural").lower().strip()
        state = _load_state()
        if mode in {"pesquisa", "research", "full_neural"}:
            state["research_enabled"] = True
        if mode in {"sono", "sleep", "full_neural"}:
            state["sleep_enabled"] = True
        state["pinned"] = True
        state["profile"] = state.get("profile") or "local_ai_full_neural"
        _save_state(state)
        if mode in {"sono", "sleep", "full_neural"} and _bool(params.get("run_sleep"), mode == "sono"):
            return _start_sleep_background()
        return f"Brain mode ativado: {mode}."

    if action in {"disable_research", "desativar_pesquisa"}:
        state = _load_state()
        state["research_enabled"] = False
        _save_state(state)
        return "Modo pesquisa desativado."

    return "Acao brain_mode desconhecida. Use status, pesquisa, sono, sleep_once, modulo, modulos, pin, start ou stop_sleep."


if __name__ == "__main__":
    print(brain_mode({"action": "status"}))
