from __future__ import annotations

import importlib.util
import json
import random
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
VAULT = Path(r"D:\xxxx_memory\30_Sistema\obsidian_data\xxxx-vault\YYYY")
AUTO_STUDY = VAULT / "auto_study"
STATE_PATH = BASE_DIR / "memory" / "study_mode_state.json"

DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_TOPICS_PER_CYCLE = 3
MAX_TOPICS_PER_CYCLE = 8

_STOP_EVENT = threading.Event()
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()
_MAP_REFRESH_LOCK = threading.Lock()
_MAP_REFRESH_RUNNING = False


STUDY_TOPICS: list[dict[str, Any]] = [
    {
        "slug": "filosofia",
        "title": "Filosofia",
        "color": "#9B59B6",
        "facts": [
            "Existencialismo - filosofia que enfatiza existencia, liberdade e responsabilidade individual",
            "Utilitarismo - teoria etica baseada na maximizacao do bem-estar coletivo",
            "Ceticismo - metodo filosofico que testa limites e fundamentos do conhecimento",
            "Estoicismo - pratica racional de foco no que depende de nos",
            "Kant - investigacao critica das condicoes do conhecimento e da moral",
            "Fenomenologia - descricao rigorosa da experiencia consciente",
            "Nietzsche - critica dos valores herdados e afirmacao criativa da vida",
            "Sartre - liberdade radical e responsabilidade como estrutura da existencia",
        ],
    },
    {
        "slug": "matematica",
        "title": "Matematica",
        "color": "#F39C12",
        "facts": [
            "Teorema de Pitagoras - em triangulos retangulos, a soma dos quadrados dos catetos iguala o quadrado da hipotenusa",
            "Numero de Ouro - proporcao recorrente em geometria, arte e padroes naturais",
            "Calculo diferencial - estudo de taxas de variacao por derivadas",
            "Calculo integral - acumulacao de quantidades por integrais",
            "Probabilidade - modelagem de incerteza por eventos e distribuicoes",
            "Estatistica - coleta, resumo e inferencia a partir de dados",
            "Algebra linear - vetores, matrizes, transformacoes e sistemas lineares",
            "Topologia - estudo de propriedades preservadas por deformacoes continuas",
        ],
    },
    {
        "slug": "psicologia",
        "title": "Psicologia",
        "color": "#E91E63",
        "facts": [
            "Vies de confirmacao - tendencia a favorecer evidencias que confirmam crencas previas",
            "Efeito placebo - resposta real mediada por expectativa e contexto terapeutico",
            "Teoria do apego - modelos emocionais formados em relacoes iniciais",
            "Inteligencia emocional - reconhecer, regular e usar emocoes de forma adaptativa",
            "Resiliencia - capacidade de reorganizar comportamento apos estresse ou adversidade",
            "Behaviorismo - analise do comportamento observavel e suas contingencias",
            "Psicanalise - investigacao de processos inconscientes e conflitos psiquicos",
            "Cognitivismo - estudo de atencao, memoria, linguagem e pensamento",
        ],
    },
    {
        "slug": "astronomia",
        "title": "Astronomia",
        "color": "#34495E",
        "facts": [
            "Buracos negros - regioes onde a gravidade impede ate a luz de escapar",
            "Estrelas de neutrons - remanescentes ultradensos de supernovas",
            "Via Lactea - galaxia espiral onde o Sistema Solar esta localizado",
            "Exoplanetas - planetas que orbitam estrelas alem do Sol",
            "Nebulosas - nuvens interestelares de gas e poeira, frequentemente berco de estrelas",
            "Big Bang - modelo cosmologico de expansao inicial do universo observavel",
            "Asteroides - corpos rochosos menores, muitos no cinturao entre Marte e Jupiter",
            "Cometas - corpos ricos em gelo que desenvolvem coma e cauda perto do Sol",
        ],
    },
    {
        "slug": "literatura",
        "title": "Literatura",
        "color": "#8E44AD",
        "facts": [
            "Romantismo - movimento literario centrado em subjetividade, emocao e nacionalismo",
            "Realismo - representacao critica da sociedade e de seus conflitos concretos",
            "Modernismo - ruptura estetica com formas e valores tradicionais",
            "Machado de Assis - escritor brasileiro conhecido por ironia e analise psicologica",
            "Clarice Lispector - prosa introspectiva sobre consciencia e linguagem",
            "Borges - ficcao filosofica com labirintos, espelhos e infinitos",
            "Shakespeare - teatro de conflitos humanos, poder, amor e tragedia",
            "Realismo magico - fusao de cotidiano e elementos extraordinarios",
        ],
    },
    {
        "slug": "arte",
        "title": "Arte",
        "color": "#C0392B",
        "facts": [
            "Renascimento - recuperacao de proporcao, perspectiva e humanismo classico",
            "Impressionismo - pintura da percepcao luminosa e da atmosfera momentanea",
            "Surrealismo - exploracao visual do sonho e do inconsciente",
            "Barroco - dramaticidade, contraste e teatralidade visual",
            "Art Nouveau - ornamentacao organica e linhas sinuosas",
            "Arte contemporanea - praticas hibridas, conceito e critica institucional",
            "Fotografia - tecnica e linguagem visual de captura luminosa",
            "Street art - expressao urbana em espacos publicos",
        ],
    },
    {
        "slug": "musica",
        "title": "Musica",
        "color": "#C44DFF",
        "facts": [
            "Harmonia - combinacao simultanea de notas e acordes",
            "Ritmo - organizacao temporal dos sons e silêncios",
            "Melodia - sequencia de notas percebida como linha musical",
            "Jazz - linguagem musical marcada por improvisacao e swing",
            "MPB - campo diverso da musica popular brasileira",
            "Samba - matriz ritmica e cultural brasileira de origem afro-brasileira",
            "Musica eletronica - composicao por sintetizadores, samples e processamento digital",
            "Orquestracao - distribuicao de ideias musicais entre instrumentos",
        ],
    },
    {
        "slug": "tecnologia",
        "title": "Tecnologia",
        "color": "#3498DB",
        "facts": [
            "API - contrato de comunicacao entre sistemas de software",
            "RAG - recuperacao de documentos para fundamentar respostas de modelos de linguagem",
            "Fine-tuning - ajuste de parametros de modelo para tarefa ou estilo especifico",
            "Embeddings - vetores que representam significado para busca semantica",
            "Banco vetorial - indice otimizado para similaridade entre embeddings",
            "Agente de IA - sistema que combina modelo, ferramentas, memoria e ciclo de acao",
            "MCP - protocolo para conectar modelos a ferramentas e dados externos",
            "Automacao local - execucao de tarefas no computador por scripts e controle de UI",
        ],
    },
    {
        "slug": "negocios",
        "title": "Negocios",
        "color": "#2ECC71",
        "facts": [
            "Lean startup - ciclo construir, medir e aprender com minimo desperdicio",
            "MVP - produto minimo viavel para testar hipoteses reais",
            "Pivot - mudanca estrategica baseada em aprendizagem de mercado",
            "Scrum - framework agil com sprints, backlog e revisoes incrementais",
            "Funil de vendas - etapas que transformam interesse em conversao",
            "CAC - custo de aquisicao de cliente",
            "LTV - valor economico esperado de um cliente ao longo do tempo",
            "Product-market fit - aderencia forte entre produto e demanda real",
        ],
    },
    {
        "slug": "imobiliario",
        "title": "Imobiliario",
        "color": "#2980B9",
        "facts": [
            "SPIN Selling - perguntas de situacao, problema, implicacao e necessidade de solucao",
            "Cap rate - relacao entre renda operacional e valor do imovel",
            "SAC - amortizacao constante com parcelas decrescentes",
            "PRICE - parcelas fixas com composicao variavel de juros e amortizacao",
            "ITBI - imposto municipal na transferencia de imoveis",
            "Due diligence imobiliaria - verificacao juridica, fiscal e documental antes da compra",
            "CMA - analise comparativa de mercado para precificacao",
            "Pipeline imobiliario - organizacao dos leads por etapa de negociacao",
        ],
    },
]


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return _default_state()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            state = _default_state()
            state.update(data)
            state.setdefault("studied_fact_ids", [])
            state.setdefault("sessions", [])
            return state
    except Exception:
        pass
    return _default_state()


def _default_state() -> dict[str, Any]:
    return {
        "active": False,
        "session_id": "",
        "started_at": "",
        "last_cycle_at": "",
        "cycle": 0,
        "total_notes": 0,
        "total_facts": 0,
        "interval_seconds": DEFAULT_INTERVAL_SECONDS,
        "topics_per_cycle": DEFAULT_TOPICS_PER_CYCLE,
        "studied_fact_ids": [],
        "sessions": [],
    }


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _fact_id(topic_slug: str, fact: str) -> str:
    clean = re.sub(r"\W+", "-", fact.lower()).strip("-")
    return f"{topic_slug}:{clean[:80]}"


def _available_items(state: dict[str, Any]) -> list[tuple[dict[str, Any], str, str]]:
    studied = set(state.get("studied_fact_ids", []))
    items: list[tuple[dict[str, Any], str, str]] = []
    for topic in STUDY_TOPICS:
        for fact in topic["facts"]:
            fid = _fact_id(topic["slug"], fact)
            if fid not in studied:
                items.append((topic, fact, fid))
    if not items:
        state["studied_fact_ids"] = []
        studied = set()
        for topic in STUDY_TOPICS:
            for fact in topic["facts"]:
                fid = _fact_id(topic["slug"], fact)
                if fid not in studied:
                    items.append((topic, fact, fid))
    return items


def _select_cycle_items(state: dict[str, Any], count: int) -> list[tuple[dict[str, Any], str, str]]:
    items = _available_items(state)
    random.shuffle(items)
    selected: list[tuple[dict[str, Any], str, str]] = []
    used_topics: set[str] = set()
    for item in items:
        topic = item[0]["slug"]
        if topic in used_topics and len(used_topics) < len(STUDY_TOPICS):
            continue
        selected.append(item)
        used_topics.add(topic)
        if len(selected) >= count:
            break
    if len(selected) < count:
        for item in items:
            if item not in selected:
                selected.append(item)
                if len(selected) >= count:
                    break
    return selected


def _load_neural_expanders() -> int:
    scripts = [
        Path(r"D:\xxxx_memory\cerebro_central.py"),
        Path(r"D:\xxxx_memory\dictionary_brain.py"),
        Path(r"D:\xxxx_memory\brain_expander.py"),
    ]
    expanded = 0
    for script in scripts:
        try:
            if not script.exists():
                continue
            spec = importlib.util.spec_from_file_location(f"study_expander_{expanded}", script)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            expanded += 1
        except Exception as exc:
            print(f"[StudyMode] Expander skipped {script}: {exc}")
    return expanded


def _write_cycle_notes(state: dict[str, Any], topics_per_cycle: int | None = None) -> dict[str, Any]:
    AUTO_STUDY.mkdir(parents=True, exist_ok=True)
    topics_per_cycle = max(1, min(int(topics_per_cycle or state.get("topics_per_cycle", DEFAULT_TOPICS_PER_CYCLE)), MAX_TOPICS_PER_CYCLE))
    state["cycle"] = int(state.get("cycle", 0)) + 1
    cycle = state["cycle"]
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    selected = _select_cycle_items(state, topics_per_cycle)
    notes: list[str] = []
    facts_count = 0

    for topic, fact, fid in selected:
        topic_folder = AUTO_STUDY / topic["slug"]
        topic_folder.mkdir(parents=True, exist_ok=True)
        note_path = topic_folder / f"{timestamp}-cycle-{cycle:04d}-{_slug(fact)}.md"
        content = _build_note(topic, fact, cycle, now)
        note_path.write_text(content, encoding="utf-8")
        state.setdefault("studied_fact_ids", []).append(fid)
        notes.append(str(note_path))
        facts_count += 1

    state["last_cycle_at"] = now.isoformat(timespec="seconds")
    state["total_notes"] = int(state.get("total_notes", 0)) + len(notes)
    state["total_facts"] = int(state.get("total_facts", 0)) + facts_count
    _append_session_log(state, notes, selected, now)
    _save_state(state)
    _refresh_map()
    return {"cycle": cycle, "notes": notes, "facts": facts_count}


def _build_note(topic: dict[str, Any], fact: str, cycle: int, now: datetime) -> str:
    slug = topic["slug"]
    title = topic["title"]
    color = topic.get("color", "#9370DB")
    created = now.isoformat(timespec="seconds")
    readable = now.strftime("%Y-%m-%d %H:%M")
    related = _related_topics(slug)
    return f"""---
created: {created}
tags: [auto_estudo, neural, ciclo-estudo, {slug}]
type: study-cycle-note
neural-color: {color}
folder: auto_study/{slug}
study-cycle: {cycle}
---

# {title}: ciclo {cycle}

> Aprendizado automatico em ciclo de estudo - {readable}

## Conceito estudado

- {fact}

## Expansao neural

Este conceito foi adicionado durante um ciclo continuo de estudo. Ele deve ser conectado ao conhecimento existente do MARK-XLIV e usado em respostas futuras quando houver relacao com o tema.

## Conexoes

- [[Cerebro-Central|Cerebro Central]]
- [[YYYY-Learning|Aprendizado]]
- [[Memoria-Central|Memoria Central]]
{related}

---
*Auto-estudo neural continuo - ciclo {cycle}*
"""


def _related_topics(slug: str) -> str:
    links = {
        "tecnologia": ["[[Agentes de IA]]", "[[RAG]]", "[[Automacao local]]"],
        "imobiliario": ["[[Corretor]]", "[[Pipeline Imobiliario]]", "[[Financiamento]]"],
        "psicologia": ["[[Memoria-Central|Memoria Central]]", "[[Comportamento]]"],
        "matematica": ["[[Estudo]]", "[[Formulas]]"],
        "negocios": ["[[Projetos]]", "[[Vendas]]"],
    }
    return "\n".join(f"- {link}" for link in links.get(slug, []))


def _slug(text: str) -> str:
    value = text.split(" - ", 1)[0]
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return value[:50] or "nota"


def _append_session_log(state: dict[str, Any], notes: list[str], selected: list[tuple[dict[str, Any], str, str]], now: datetime) -> None:
    session_id = state.get("session_id") or now.strftime("%Y%m%d-%H%M%S")
    session_dir = AUTO_STUDY / "_sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    log_path = session_dir / f"study-session-{session_id}.md"
    lines = []
    if not log_path.exists():
        lines.append(f"# Sessao de estudo {session_id}\n")
    lines.append(f"\n## Ciclo {state.get('cycle', 0)} - {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
    for (topic, fact, _), note in zip(selected, notes):
        rel = Path(note).name
        lines.append(f"- {topic['title']}: {fact} (`{rel}`)")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _refresh_map() -> None:
    global _MAP_REFRESH_RUNNING
    with _MAP_REFRESH_LOCK:
        if _MAP_REFRESH_RUNNING:
            return
        _MAP_REFRESH_RUNNING = True

    def worker() -> None:
        global _MAP_REFRESH_RUNNING
        try:
            from memory.memory_manager import generate_vault_groups, generate_vault_index

            generate_vault_index()
            generate_vault_groups()
        except Exception as exc:
            print(f"[StudyMode] Map refresh skipped: {exc}")
        finally:
            with _MAP_REFRESH_LOCK:
                _MAP_REFRESH_RUNNING = False

    threading.Thread(target=worker, daemon=True, name="StudyModeMapRefresh").start()


def _study_loop(player=None, speak=None, initial_delay: bool = True) -> None:
    if initial_delay:
        interval = int(_load_state().get("interval_seconds", DEFAULT_INTERVAL_SECONDS))
        if _STOP_EVENT.wait(max(30, interval)):
            return
    while not _STOP_EVENT.is_set():
        with _LOCK:
            state = _load_state()
            if not state.get("active"):
                break
            result = _write_cycle_notes(state)
        msg = f"Modo estudo ciclo {result['cycle']}: {len(result['notes'])} nota(s), {result['facts']} conceito(s)."
        print(f"[StudyMode] {msg}")
        if player:
            try:
                player.write_log(f"[StudyMode] {msg}")
            except Exception:
                pass
        interval = int(_load_state().get("interval_seconds", DEFAULT_INTERVAL_SECONDS))
        if _STOP_EVENT.wait(max(30, interval)):
            break


def _start(params: dict, player=None, speak=None) -> str:
    global _THREAD
    interval = int(params.get("interval_seconds") or params.get("interval") or DEFAULT_INTERVAL_SECONDS)
    interval = max(30, min(interval, 3600))
    topics_per_cycle = int(params.get("topics_per_cycle") or params.get("batch") or DEFAULT_TOPICS_PER_CYCLE)
    topics_per_cycle = max(1, min(topics_per_cycle, MAX_TOPICS_PER_CYCLE))
    run_now = params.get("run_now", True)

    with _LOCK:
        state = _load_state()
        if state.get("active") and _THREAD and _THREAD.is_alive():
            return _status()
        session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        state.update({
            "active": True,
            "session_id": session_id,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "interval_seconds": interval,
            "topics_per_cycle": topics_per_cycle,
        })
        state.setdefault("sessions", []).append(session_id)
        state["sessions"] = state["sessions"][-20:]
        _save_state(state)
        expanded = _load_neural_expanders()
        if run_now:
            first = _write_cycle_notes(state, topics_per_cycle=topics_per_cycle)
        else:
            first = {"cycle": state.get("cycle", 0), "notes": [], "facts": 0}
        _STOP_EVENT.clear()
        _THREAD = threading.Thread(
            target=_study_loop,
            kwargs={"player": player, "speak": speak, "initial_delay": True},
            daemon=True,
            name="StudyModeCycle",
        )
        _THREAD.start()

    if player:
        try:
            player.muted = True
            player.write_log("SYS: Modo Estudo ATIVADO - ciclo continuo")
        except Exception:
            pass
    return (
        f"Modo Estudo em ciclo ativado. Intervalo: {interval}s. "
        f"Topicos por ciclo: {topics_per_cycle}. "
        f"Expansores carregados: {expanded}. "
        f"Primeiro ciclo: {len(first['notes'])} nota(s), {first['facts']} conceito(s)."
    )


def _stop(player=None) -> str:
    global _THREAD
    _STOP_EVENT.set()
    with _LOCK:
        state = _load_state()
        state["active"] = False
        state["stopped_at"] = datetime.now().isoformat(timespec="seconds")
        _save_state(state)
    if player:
        try:
            player.write_log("SYS: Modo Estudo DESATIVADO")
        except Exception:
            pass
    return "Modo Estudo parado. O ciclo continuo foi desativado."


def _status() -> str:
    state = _load_state()
    running = bool(_THREAD and _THREAD.is_alive())
    return (
        f"Modo Estudo: {'ativo' if state.get('active') else 'parado'} "
        f"({'thread rodando' if running else 'sem thread'}).\n"
        f"Sessao: {state.get('session_id') or 'nenhuma'}\n"
        f"Ciclos: {state.get('cycle', 0)}\n"
        f"Notas geradas: {state.get('total_notes', 0)}\n"
        f"Conceitos estudados: {state.get('total_facts', 0)}\n"
        f"Ultimo ciclo: {state.get('last_cycle_at') or 'nunca'}\n"
        f"Intervalo: {state.get('interval_seconds', DEFAULT_INTERVAL_SECONDS)}s"
    )


def _once(params: dict) -> str:
    topics_per_cycle = int(params.get("topics_per_cycle") or params.get("batch") or DEFAULT_TOPICS_PER_CYCLE)
    with _LOCK:
        state = _load_state()
        result = _write_cycle_notes(state, topics_per_cycle=topics_per_cycle)
    return f"Ciclo unico concluido: {len(result['notes'])} nota(s), {result['facts']} conceito(s), ciclo {result['cycle']}."


def study_mode(parameters: dict = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or params.get("mode") or "start").lower().strip()
    if action in ("auto", "deep", "expand", "start", "iniciar", "entrar"):
        return _start(params, player=player, speak=speak)
    if action in ("stop", "parar", "sair", "off"):
        return _stop(player=player)
    if action in ("status", "stats"):
        return _status()
    if action in ("once", "single", "ciclo", "cycle"):
        return _once(params)
    return "Ação de estudo desconhecida. Use start, stop, status ou once."
