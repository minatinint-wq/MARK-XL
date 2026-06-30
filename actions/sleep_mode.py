"""MODO SONO — JARVIS dream engine

Quando o JARVIS "dorme", ele:
1. Revisa tudo que aprendeu/aprendeu no dia
2. Pesquisa informações relacionadas na web
3. Cruza dados do vault procurando conexões
4. Gera novas notas de conhecimento
5. Cria imagens conceituais
6. Escreve um diário de sonhos
"""

import os, re, json, time, random, threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

VAULT = Path(__file__).resolve().parent.parent / "memory"
DREAM_JOURNAL = VAULT / "auto_study" / "sonhos"
DREAM_IMAGES  = VAULT / "auto_study" / "visoes"
AUTO_STUDY    = VAULT / "auto_study"
BRAIN_DATA    = VAULT / "data"

SLEEP_STATE = {"status": "awake", "cycle": 0, "last_dream": None}


def _write_note(folder: Path, filename: str, content: str, tags: list[str] = None):
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[^a-zA-Z0-9_-]', '', filename.replace(' ', '-'))[:60]
    ts = datetime.now().strftime('%Y%m%d-%H%M')
    tag_str = ", ".join(tags or ["sonho", "auto-descoberta"])
    note = f"""---
created: {ts}
tags: [{tag_str}]
type: dream-generated
---

# {filename}

{content}

---
*Gerado durante ciclo de sono — {ts}*
"""
    path = folder / f"{safe}.md"
    path.write_text(note, encoding="utf-8")
    return path


def _read_todays_activity() -> dict:
    """Retorna conversas, hábitos e aprendizado de hoje."""
    today = datetime.now().strftime('%Y-%m-%d')
    result = {"conversations": [], "habits": [], "learning": [], "vault_notes": []}

    data_dir = VAULT / "data"
    conv_dir = data_dir / "conversations"
    habits_dir = VAULT / "habits"
    learning_dir = data_dir / "learning"

    if conv_dir.exists():
        for f in sorted(conv_dir.glob("*.json"), reverse=True)[:5]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for entry in data:
                        if today in str(entry.get("timestamp", "")):
                            result["conversations"].append(entry)
            except: pass

    if habits_dir.exists():
        for f in sorted(habits_dir.glob("*.txt"), reverse=True)[:5]:
            try:
                result["habits"].append(f.read_text(encoding="utf-8")[:500])
            except: pass

    if learning_dir.exists():
        for f in sorted(learning_dir.glob("*.json"), reverse=True)[:5]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    result["learning"].extend(data[:10])
                elif isinstance(data, dict):
                    result["learning"].append(data)
            except: pass

    learned_dir = VAULT / "learned"
    if learned_dir.exists():
        for f in sorted(learned_dir.glob("**/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
            try:
                result["vault_notes"].append({
                    "path": str(f.relative_to(VAULT)),
                    "content": f.read_text(encoding="utf-8")[:300]
                })
            except: pass

    return result


def _find_cross_references(activity: dict) -> list[dict]:
    """Cruza dados do vault procurando conexões não-óbvias entre tópicos."""
    connections = []
    try:
        from memory.memory_manager import scan_vault_structure, search_vault_content

        structure = scan_vault_structure()
        folders = list(structure.keys())

        # Pega palavras-chave das atividades de hoje
        keywords = set()
        for conv in activity.get("conversations", []):
            text = str(conv.get("user_message", "")) + " " + str(conv.get("jarvis_response", ""))
            for w in text.split():
                if len(w) > 4:
                    keywords.add(w.lower())

        for note in activity.get("vault_notes", []):
            text = note.get("content", "")
            for w in text.split():
                if len(w) > 4:
                    keywords.add(w.lower())

        # Busca conexões no vault para cada keyword
        vault_note_paths = set()
        for note in activity.get("vault_notes", []):
            vault_note_paths.add(str(note.get("path", "")))

        for kw in list(keywords)[:6]:
            try:
                results = search_vault_content(kw, max_results=3)
            except Exception:
                continue
            for r in results:
                folder_match = r.get("folder", "")
                if folder_match and folder_match not in vault_note_paths:
                    connections.append({
                        "keyword": kw,
                        "folder": r.get("folder", ""),
                        "title": r.get("title", ""),
                        "snippet": r.get("snippet", "")
                    })

    except Exception as e:
        print(f"[Dream] Erro cross-reference: {e}")

    return connections


def _research_topic(topic: str, max_results: int = 3) -> str:
    """Pesquisa informação na web sobre um tópico."""
    try:
        import threading
        from actions.web_search import web_search
        result_container = []
        def _do_search():
            try:
                r = web_search(parameters={"query": topic, "mode": "search"}, player=None)
                result_container.append(r)
            except Exception:
                result_container.append("")
        t = threading.Thread(target=_do_search, daemon=True)
        t.start()
        t.join(timeout=8)
        if result_container and result_container[0] and isinstance(result_container[0], str) and len(result_container[0]) > 50:
            return result_container[0][:1500]
    except Exception as e:
        print(f"[Dream] Erro pesquisa web: {e}")
    return ""


def _make_wikilink(vault_root: Path, file_path: str) -> str:
    """Convert a full filesystem path to an Obsidian wikilink relative to vault root."""
    try:
        p = Path(file_path)
        rel = p.relative_to(vault_root)
        rel_norm = rel.as_posix().replace(".md", "")
        title = p.stem.replace("-", " ").replace("_", " ").title()
        return f"[[{rel_norm}|{title}]]"
    except Exception:
        return f"[[{Path(file_path).stem}]]"


def _generate_knowledge_notes(activity: dict, connections: list[dict], research: dict) -> int:
    """Gera novas notas de conhecimento a partir das conexões descobertas.
    Cada nota inclui wikilinks reais para conteúdo do vault."""
    count = 0
    today = datetime.now().strftime('%Y-%m-%d')
    ts = datetime.now().strftime('%Y%m%d-%H%M')
    vault_root = VAULT

    # --- Nota 1: Síntese do dia ---
    conv_count = len(activity.get("conversations", []))
    learn_count = len(activity.get("learning", []))
    note_count = len(activity.get("vault_notes", []))

    # Build wikilinks for conversations
    conv_links = []
    for conv in activity.get("conversations", []):
        msg = str(conv.get("user_message", ""))
        if msg:
            conv_links.append(f"- _{msg[:200]}_")

    # Build wikilinks for vault notes referenced today
    vault_links = []
    for n in activity.get("vault_notes", []):
        note_path = n.get("path", "")
        if note_path.endswith(".md"):
            rel = note_path.replace("\\", "/").replace(".md", "")
            vault_links.append(f"- [[{rel}|{Path(note_path).stem.replace('-', ' ').title()}]]")

    conn_links = []
    for conn in connections[:5]:
        cpath = conn.get("path", "")
        if cpath:
            wl = _make_wikilink(vault_root, cpath)
            conn_links.append(f"- **{conn['keyword']}** → {wl}")
        else:
            conn_links.append(f"- **{conn['keyword']}** → {conn['folder']}: {conn['title']}")

    synthesis = f"""## Temas do Dia
{"".join(conv_links) if conv_links else "- *Nenhuma conversa registrada*"}

## Notas do Vault Revisadas
{"".join(vault_links) if vault_links else "- *Nenhuma nota revisada*"}

## Conexões Descobertas Entre Tópicos
{"".join(conn_links) if conn_links else "- *Nenhuma conexão encontrada*"}
"""
    synthesis_path = AUTO_STUDY / "sintese-diaria"
    synthesis_path.mkdir(parents=True, exist_ok=True)
    (synthesis_path / f"sintese-{ts}.md").write_text(f"""---
created: {ts}
tags: [sintese, diario, sono, auto-descoberta]
type: dream-synthesis
---

# Síntese Neural — {today}

{synthesis}

*Gerado durante ciclo de sono — {ts}*
""", encoding="utf-8")
    count += 1

    # --- Nota 2: Pesquisas com wikilinks para o vault ---
    for topic, info in research.items():
        if not info:
            continue
        safe_topic = re.sub(r'[^a-zA-Z0-9_]', '', topic.replace(' ', '_'))[:30]
        note_path = AUTO_STUDY / "pesquisas"
        note_path.mkdir(parents=True, exist_ok=True)

        # Find vault notes matching this topic for cross-linking
        topic_links = []
        for conn in connections:
            if topic.lower() in conn['keyword'].lower() or conn['keyword'].lower() in topic.lower():
                if conn.get("path"):
                    topic_links.append(f"- {_make_wikilink(vault_root, conn['path'])}")

        content = f"""---
created: {ts}
tags: [pesquisa, expansao, {safe_topic}]
type: dream-research
---

# Pesquisa Noturna: {topic}

## Informações Coletadas

{info[:2000]}

## Conexões com o Vault
{"".join(topic_links) if topic_links else "- *Nenhuma conexão direta encontrada*"}

---
*Pesquisa gerada durante ciclo de sono — {ts}*
"""
        (note_path / f"pesquisa-{safe_topic}-{ts}.md").write_text(content, encoding="utf-8")
        count += 1

    # --- Nota 3: Expansão aleatória do vault com wikilinks ---
    try:
        from memory.memory_manager import load_obsidian_categories
        categories = load_obsidian_categories()
        folder_names = [f for f in categories.keys() if f not in {"", ".obsidian", ".git"}]
        random.shuffle(folder_names)

        for folder_name in folder_names[:2]:
            notes = categories.get(folder_name, [])
            if not notes:
                continue
            note = random.choice(notes[:20])
            note_title = note.get("title", "Nota")
            note_path_raw = note.get("path", "")
            wl = _make_wikilink(vault_root, note_path_raw) if note_path_raw else f"[[{folder_name}/{note_title}]]"
            _write_note(
                AUTO_STUDY / "expansao-vault",
                f"Explorando-{folder_name}-{note_title[:30]}",
                f"""## Explorando {folder_name}

Nota original: {wl}

> {note.get('snippet', '')[:500]}
---
*Descoberta durante ciclo de sono — {ts}*""",
                tags=["sonho", "expansao", folder_name]
            )
            count += 1
    except Exception as e:
        print(f"[Dream] Erro expansão vault: {e}")

    return count


def _generate_vision(topic: str, connections: list[str] = None) -> Optional[str]:
    """Gera uma 'visão' SVG — diagrama conceitual do que foi aprendido."""
    DREAM_IMAGES.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M')
    safe = re.sub(r'[^a-zA-Z0-9_-]', '', topic.replace(' ', '-'))[:30]

    conns = connections or ["cerebro", "vault", "conhecimento"]
    height = 100 + len(conns) * 60
    circles = ""
    lines = ""
    cx, cy = 300, 80
    circles += f'<circle cx="{cx}" cy="{cy}" r="35" fill="#6C5CE7" opacity="0.9"/><text x="{cx}" y="{cy+5}" text-anchor="middle" fill="white" font-size="14" font-family="sans-serif">{topic[:20]}</text>'

    for i, conn in enumerate(conns[:8]):
        angle = (i / max(len(conns[:8]), 1)) * 2 * 3.14159
        rx = cx + 180 * (0.6 + 0.4 * (i % 2))
        ry = cy + 120 * (0.3 if i < len(conns[:8])/2 else -0.3) + (i % 3) * 40
        angle_offset = 40 * (i - len(conns[:8])//2) / len(conns[:8])
        nx = cx + 170 * (0.7 if i < len(conns[:8])/2 else -0.7)
        ny = cy + 60 + (i - len(conns[:8])//2) * 70
        circles += f'<circle cx="{nx}" cy="{ny}" r="25" fill="#00B894" opacity="0.8"/><text x="{nx}" y="{ny+4}" text-anchor="middle" fill="white" font-size="10" font-family="sans-serif">{conn[:16]}</text>'
        lines += f'<line x1="{cx}" y1="{cy}" x2="{nx}" y2="{ny}" stroke="#6C5CE7" stroke-width="1.5" opacity="0.4"/>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 {height}" width="600" height="{height}">
  <rect width="600" height="{height}" fill="#1a1a2e" rx="12"/>
  <defs>
    <filter id="glow"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  {lines}
  <g filter="url(#glow)">{circles}</g>
  <text x="300" y="{height-20}" text-anchor="middle" fill="#636e72" font-size="11" font-family="sans-serif">Visão gerada durante ciclo de sono — {ts}</text>
</svg>'''
    path = DREAM_IMAGES / f"visao-{safe}-{ts}.svg"
    path.write_text(svg, encoding="utf-8")
    return str(path.relative_to(VAULT)) if path.exists() else None


def _write_dream_journal(total_notes: int, connections: list[dict], research: dict, duration: float, visions: list[str] = None, generated_files: list[Path] = None):
    """Escreve o diário de sonhos — relato do que aconteceu no ciclo.
    Inclui wikilinks para todas as notas geradas e conteúdo do vault."""
    DREAM_JOURNAL.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M')
    today = datetime.now().strftime('%Y-%m-%d')
    vault_root = VAULT

    # Wikilinks to vault content connected
    connections_text_parts = []
    for c in connections[:5]:
        if c.get("path"):
            connections_text_parts.append(f"- **{c['keyword']}** → {_make_wikilink(vault_root, c['path'])}")
        else:
            connections_text_parts.append(f"- **{c['keyword']}** → {c['folder']}: {c['title']}")
    connections_text = "\n".join(connections_text_parts) if connections_text_parts else "- *Nenhuma conexão nova encontrada*"

    research_text = "\n".join(
        f"- **{t}**: {i[:100]}..."
        for t, i in list(research.items())[:3]
    ) if research else "- *Nenhuma pesquisa realizada*"

    # Wikilinks to notes generated this cycle
    generated_links = ""
    if generated_files:
        generated_links = "\n### Notas Geradas\n"
        for gf in generated_files:
            try:
                rel = gf.relative_to(vault_root).as_posix().replace(".md", "")
                generated_links += f"- [[{rel}|{gf.stem.replace('-', ' ').title()}]]\n"
            except Exception:
                pass

    journal = f"""---
created: {ts}
tags: [diario, sonho, sono, ciclo]
type: dream-journal
---

# Diário de Sonhos — {today}

## Duração do Ciclo
{duration:.1f}s

## Processamento Noturno
{total_notes} novas notas e conexões processadas.

### Conexões Descobertas
{connections_text}

### Pesquisas Realizadas
{research_text}

{generated_links}"""
    if visions:
        journal += "\n### Visões Geradas\n"
        for v in visions:
            vis_path = v.replace("\\", "/")
            journal += f"- ![[{vis_path.replace('.md', '')}]]\n"

    journal += f"""
---
*Sonhado por JARVIS — {ts}*
"""
    (DREAM_JOURNAL / f"sonho-{ts}.md").write_text(journal, encoding="utf-8")


def _integrate_generated_notes():
    """Parse generated notes and feed into brain + update vault index with wikilinks.
    Scans all auto_study/ subfolders (sintese-diaria, pesquisas, expansao-vault,
    sonhos, visoes) and builds a comprehensive index at Cerebro/Indice-Auto-Estudo.md."""
    try:
        import sys as _sys
        learner_path = VAULT / "brains" / "xxxx_advanced_learner.py"
        if not learner_path.exists():
            return 0

        import importlib.util
        spec = importlib.util.spec_from_file_location("learner", learner_path)
        if not spec or not spec.loader:
            return 0
        learner = importlib.util.module_from_spec(spec)
        _sys.modules["learner_integration"] = learner
        spec.loader.exec_module(learner)

        folders_to_scan = [
            AUTO_STUDY / "sintese-diaria",
            AUTO_STUDY / "pesquisas",
            AUTO_STUDY / "expansao-vault",
            AUTO_STUDY / "sonhos",
            AUTO_STUDY / "visoes",
        ]

        integrated = 0
        synced = 0
        all_generated = []
        for folder in folders_to_scan:
            if not folder.exists():
                continue
            for md_file in sorted(folder.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
                try:
                    content = md_file.read_text(encoding="utf-8", errors="ignore")
                    title = md_file.stem.replace("-", " ").title()
                    all_generated.append(md_file)
                    result = learner.learn_everything(
                        f"Nota gerada durante sono: {title}. Conteudo: {content[:800]}"
                    )
                    if result.get("learned", 0) > 0:
                        integrated += result["learned"]
                    try:
                        learner.save_memory_to_disk("dream", title, content[:300])
                        synced += 1
                    except Exception:
                        pass
                except Exception:
                    continue

        # Build a comprehensive index with every generated note linked via wikilinks
        try:
            vault = VAULT
            index_path = vault / "Cerebro" / "Indice-Auto-Estudo.md"
            index_path.parent.mkdir(parents=True, exist_ok=True)

            ts_now = datetime.now().strftime('%Y-%m-%d %H:%M')
            header = f"---\ntags: [indice, cerebro, auto-estudo]\ntype: index\nupdated: {ts_now}\n---\n\n# Indice de Auto-Estudo e Sonhos\n\nNotas geradas automaticamente pelo JARVIS durante ciclos de estudo e sono. Todas linkadas ao cerebro.\n\n"

            sections = []
            for subfolder in sorted(AUTO_STUDY.iterdir()):
                if not subfolder.is_dir():
                    continue
                notes = sorted(subfolder.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
                if notes:
                    section = f"## {subfolder.name.replace('-', ' ').title()}\n"
                    for n in notes[:20]:
                        rel = n.relative_to(vault).as_posix().replace(".md", "")
                        display = n.stem.replace("-", " ").title()
                        section += f"- [[{rel}|{display}]]\n"
                    sections.append(section)

            new_content = header + "\n".join(sections)
            index_path.write_text(new_content, encoding="utf-8")

            # Create a cross-reference note for this cycle
            if all_generated:
                cross_path = AUTO_STUDY / "conexoes"
                cross_path.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime('%Y%m%d-%H%M')
                links = []
                for gf in all_generated[:10]:
                    rel = gf.relative_to(vault).as_posix().replace(".md", "")
                    links.append(f"- [[{rel}|{gf.stem.replace('-', ' ').title()}]]({rel})")
                cross_note = f"---\ntags: [conexoes, cerebro, sono]\ntype: cross-reference\ncreated: {ts}\n---\n\n# Conexoes do Ciclo de Sono\n\nNotas interligadas neste ciclo:\n\n" + "\n".join(links) + f"\n\n---\n*Ciclo de sono — {ts}*"
                (cross_path / f"conexoes-{ts}.md").write_text(cross_note, encoding="utf-8")
                synced += 1
        except Exception as e:
            print(f"[Dream] Erro ao atualizar índice: {e}")

        print(f"[Dream] Integrado: {synced} notas sincronizadas ({integrated} extracoes)")
        return synced
    except Exception as e:
        print(f"[Dream] Erro: {e}")
        return 0


def sleep_cycle(player=None, speak_func=None):
    """Executa UM ciclo completo de sono."""
    if SLEEP_STATE["status"] == "dreaming":
        return {"status": "error", "message": "Já estou sonhando. Aguarde o ciclo terminar."}

    SLEEP_STATE["status"] = "drowsy"
    start = time.time()
    cycle = SLEEP_STATE["cycle"] + 1

    print(f"[Dream] 🌙 Ciclo de sono #{cycle} iniciado...")

    # 1. Revisar atividade do dia
    if speak_func:
        speak_func("Iniciando ciclo de processamento noturno. Revisando atividades do dia.")
    activity = _read_todays_activity()
    conv_count = len(activity.get("conversations", []))
    learn_count = len(activity.get("learning", []))
    note_count = len(activity.get("vault_notes", []))
    print(f"[Dream] 📋 Revisão: {conv_count} conversas, {learn_count} aprendizados, {note_count} notas")

    # 2. Encontrar conexões (cross-reference)
    print(f"[Dream] 🔗 Cruzando dados do vault...")
    connections = _find_cross_references(activity)
    print(f"[Dream] 🔗 {len(connections)} conexões potenciais encontradas")

    # 3. Pesquisar tópicos relacionados
    topics_to_research = set()
    for conn in connections:
        topics_to_research.add(conn["keyword"])
    for note in activity.get("vault_notes", []):
        for w in note.get("content", "").split():
            if len(w) > 5:
                topics_to_research.add(w.lower())

    research = {}
    for topic in list(topics_to_research)[:4]:
        print(f"[Dream] 🌐 Pesquisando: {topic}")
        result = _research_topic(topic)
        if result:
            research[topic] = result
        time.sleep(0.3)

    # 4. Gerar notas de conhecimento
    print(f"[Dream] 📝 Gerando novas notas de conhecimento...")
    total_notes = _generate_knowledge_notes(activity, connections, research)
    print(f"[Dream] 📝 {total_notes} novas notas criadas")

    # 5. Gerar visões (diagramas conceituais SVG)
    visions = []
    print(f"[Dream] 🌌 Gerando visões...")
    vision_topics = [c["keyword"] for c in connections[:3]]
    if not vision_topics:
        vision_topics = ["cerebro", "conhecimento", "vault"]
    for vt in vision_topics[:3]:
        conns_for_vision = [c["title"] for c in connections if c["keyword"] == vt][:6]
        vis = _generate_vision(vt, conns_for_vision)
        if vis:
            visions.append(vis)
    if visions:
        print(f"[Dream] 🌌 {len(visions)} visões geradas")

    # 6. Escrever diário de sonhos com wikilinks para notas geradas
    duration = time.time() - start
    generated_files = list((AUTO_STUDY / "sintese-diaria").glob("*.md"))[-total_notes:] if total_notes else []
    _write_dream_journal(total_notes, connections, research, duration, visions, generated_files)

    # 7. Integrar notas geradas no cerebro neural
    integrated = _integrate_generated_notes()
    if integrated > 0:
        print(f"[Dream] 🧠 {integrated} notas integradas ao cerebro e indexadas no Cerebro/Indice-Auto-Estudo.md")

    # 8. Atualizar estado
    SLEEP_STATE["status"] = "awake"
    SLEEP_STATE["cycle"] = cycle
    SLEEP_STATE["last_dream"] = datetime.now().isoformat()

    print(f"[Dream] ✅ Ciclo de sono #{cycle} completo em {duration:.1f}s — {total_notes} notas geradas")

    return {
        "status": "complete",
        "cycle": cycle,
        "duration": round(duration, 1),
        "notes_created": total_notes,
        "notes_integrated": integrated,
        "connections_found": len(connections),
        "topics_researched": len(research),
        "message": f"Ciclo de sono #{cycle} completo. {total_notes} notas geradas, {integrated} integradas ao cerebro."
    }


def full_night(speak_func=None, player=None):
    """Executa múltiplos ciclos de sono em sequência."""
    results = []
    cycles = random.randint(2, 4)
    print(f"[Dream] 🌙 Noite completa iniciada — {cycles} ciclos")

    for i in range(cycles):
        result = sleep_cycle(speak_func=speak_func, player=player)
        results.append(result)
        if i < cycles - 1:
            sleep_time = random.uniform(1.0, 3.0)
            print(f"[Dream] ⏳ Intervalo entre ciclos: {sleep_time:.1f}s")
            time.sleep(sleep_time)

    total_notes = sum(r.get("notes_created", 0) for r in results)
    total_conns = sum(r.get("connections_found", 0) for r in results)

    return {
        "status": "complete",
        "cycles": cycles,
        "total_notes": total_notes,
        "total_connections": total_conns,
        "results": results,
        "message": f"Noite completa: {cycles} ciclos, {total_notes} notas geradas, {total_conns} conexões."
    }


def dream_plan() -> str:
    """Retorna um plano detalhado do que será feito no próximo ciclo de sono."""
    return f"""## 🌙 Plano de Sono

**Estado atual:** {SLEEP_STATE['status']}
**Ciclos realizados:** {SLEEP_STATE['cycle']}
**Último sonho:** {SLEEP_STATE.get('last_dream', 'Nunca')}

### Pipeline de processamento noturno:

1. **📋 Revisão do dia** — Ler conversas, hábitos e aprendizados de hoje
2. **🔗 Cruzamento de dados** — Encontrar conexões não-óbvias entre tópicos
3. **🌐 Pesquisa web** — Expandir tópicos com informações externas
4. **📝 Geração de notas** — Criar novas notas de conhecimento no vault
5. **🌌 Diário de sonhos** — Registrar o que foi processado

### Áreas que serão exploradas:
- auto_study/ — notas de estudo já existentes
- learned/ — conhecimento ensinado pelo usuário
- vault geral — conexões entre categorias diferentes
"""


def sleep_status() -> dict:
    """Retorna o estado atual do modo sono."""
    return dict(SLEEP_STATE)


def wake_up():
    """Interrompe o ciclo de sono atual."""
    SLEEP_STATE["status"] = "awake"
    return {"status": "awake", "message": "Acordei! Pronto para ajudar."}
