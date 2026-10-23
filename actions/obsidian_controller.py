from __future__ import annotations

import os
import re
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


BASE_DIR = Path(__file__).resolve().parent.parent
BRAIN_ROOT = Path(r"D:\xxxx_memory")
PRIMARY_YYYY_ROOT = BRAIN_ROOT / "30_Sistema" / "obsidian_data" / "xxxx-vault" / "YYYY"
PRIMARY_LEARNED_ROOT = PRIMARY_YYYY_ROOT / "learned"
LEGACY_YYYY_ROOT = BRAIN_ROOT / "obsidian_data" / "xxxx-vault" / "YYYY"
LOCAL_LEARNED_ROOT = BASE_DIR / "memory" / "learned"

VAULT_ROOTS = [
    BRAIN_ROOT,
]

EXCLUDED_DIRS = {
    ".git",
    ".obsidian",
    "__pycache__",
}

CATEGORY_ALIASES = {
    "cerebro": "00_Cerebro",
    "cérebro": "00_Cerebro",
    "memoria": "00_Cerebro",
    "memória": "00_Cerebro",
    "brain": "00_Cerebro",
    "imoveis": "08_Imobiliario/Imobiliario",
    "imóveis": "08_Imobiliario/Imobiliario",
    "imovel": "08_Imobiliario/Imobiliario",
    "imóvel": "08_Imobiliario/Imobiliario",
    "imobiliario": "08_Imobiliario/Imobiliario",
    "imobiliário": "08_Imobiliario/Imobiliario",
    "imobiliaria": "08_Imobiliario/Imobiliario",
    "real_estate": "08_Imobiliario/Imobiliario",
    "real-estate": "08_Imobiliario/Imobiliario",
    "corretor": "09_Corretor_Vendas",
    "corretor_atendimento": "09_Corretor_Vendas/atendimento",
    "corretor_avaliacao": "09_Corretor_Vendas/avaliacao",
    "corretor_financiamento": "08_Imobiliario/financiamento",
    "corretor_gestao_leads": "09_Corretor_Vendas/gestao_leads",
    "corretor_legal": "08_Imobiliario/legal",
    "corretor_mercado": "08_Imobiliario/mercado",
    "corretor_venda_tecnicas": "09_Corretor_Vendas/venda_tecnicas",
    "marketing": "10_Marketing_Ads",
    "ads": "10_Marketing_Ads",
    "facebook_ads": "10_Marketing_Ads/facebook_ads",
    "google_ads": "10_Marketing_Ads/google_ads",
    "games": "07_Jogos",
    "game": "07_Jogos",
    "jogos": "07_Jogos",
    "jogo": "07_Jogos",
    "tech": "05_Tecnologia/Tecnologia",
    "tecnologia": "05_Tecnologia/Tecnologia",
    "programacao": "05_Tecnologia/programacao",
    "programação": "05_Tecnologia/programacao",
    "ia": "06_IA_Automacoes",
    "ai": "06_IA_Automacoes",
    "musica": "19_Musica",
    "música": "19_Musica",
    "audio": "19_Musica",
    "braille": "06_IA_Automacoes/braille",
    "cannabis": "12_Cannabis/Cannabis",
    "cannabis_equipment": "12_Cannabis/equipment",
    "cannabis_extraction": "12_Cannabis/extraction",
    "cannabis_genetics": "12_Cannabis/genetics",
    "cannabis_growing": "13_Cultivo/growing",
    "cannabis_medicine": "12_Cannabis/medicine",
    "cannabis_nutrients": "13_Cultivo/nutrients",
    "cannabis_problems": "13_Cultivo/problems",
    "cannabis_techniques": "13_Cultivo/techniques",
    "cultivo": "13_Cultivo/Cultivo",
    "hidroponia": "14_Hidroponia/Hidroponia",
    "hydroponics": "14_Hidroponia/Hidroponia",
    "finance": "11_Financas/Financas",
    "financas": "11_Financas/Financas",
    "health": "15_Saude/Saude",
    "saude": "15_Saude/Saude",
    "receitas": "17_Receitas/Receitas",
    "recipes": "17_Receitas/Receitas",
    "food": "17_Receitas/Receitas",
    "viagem": "20_Viagens/Viagem",
    "viagens": "20_Viagens/Viagem",
    "travel": "20_Viagens/Viagem",
    "estudo": "04_Estudo/Estudo",
    "dicionario": "22_Dicionario",
    "pesquisa": "23_Pesquisas",
    "projetos": "24_Projetos",
}

CATEGORY_KEYWORDS = {
    "games": ("game", "games", "jogo", "jogos", "steam", "epic", "rpg", "task bar hero", "tbh"),
    "imoveis": ("imovel", "imóveis", "imobili", "lead", "corretor", "creci", "construtora"),
    "tech": ("python", "api", "codigo", "código", "program", "ia", "ai", "software", "github"),
    "musica": ("musica", "música", "spotify", "playlist", "rock", "audio"),
    "viagens": ("viagem", "passagem", "milha", "aeroporto", "hotel"),
    "estudo": ("estudo", "formula", "fórmula", "matematica", "matemática"),
}


def _existing_roots() -> list[Path]:
    return [root for root in VAULT_ROOTS if root.exists()]


def _safe_root_for_writes() -> Path:
    BRAIN_ROOT.mkdir(parents=True, exist_ok=True)
    return BRAIN_ROOT


def _is_under(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved_root = root.resolve()
        return resolved == resolved_root or resolved.is_relative_to(resolved_root)
    except Exception:
        return False


def _is_safe_path(path: Path) -> bool:
    return any(_is_under(path, root) for root in _existing_roots() + [_safe_root_for_writes()])


def _category(value: str | None) -> str:
    raw = (value or "geral").strip().lower()
    return CATEGORY_ALIASES.get(raw, re.sub(r"[^a-z0-9_-]+", "-", raw).strip("-") or "geral")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return slug[:80] or datetime.now().strftime("note-%Y%m%d-%H%M%S")


def _title_from_note(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip()
    return text


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip()
    body = text[end + 4 :].lstrip("\r\n")
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data, body


def _format_frontmatter(data: dict[str, str], body: str) -> str:
    if not data:
        return body
    lines = ["---"]
    for key, value in data.items():
        lines.append(f"{key}: {value}")
    lines.extend(["---", "", body.lstrip("\r\n")])
    return "\n".join(lines)


def _parse_tags(value: str) -> list[str]:
    value = (value or "").strip()
    split_on_space = True
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
        split_on_space = False
    raw_tags = value.split(",") if not split_on_space else re.split(r"[, ]+", value)
    tags = []
    for tag in raw_tags:
        clean = _clean_tag(tag)
        if clean and clean not in tags:
            tags.append(clean)
    return tags


def _clean_tag(value: str) -> str:
    clean = value.strip().strip("'\"").strip("#").strip()
    clean = clean.replace(":", "").replace("(", "").replace(")", "")
    clean = re.sub(r"\s+", "-", clean)
    clean = re.sub(r"-+", "-", clean).strip("-").lower()
    return clean


def _format_tags(tags: list[str]) -> str:
    cleaned = []
    for tag in tags:
        clean = _clean_tag(str(tag))
        if clean and clean not in cleaned:
            cleaned.append(clean)
    return "[" + ", ".join(cleaned) + "]"


def _relative_label(path: Path) -> str:
    for root in _existing_roots():
        if _is_under(path, root):
            return str(path.resolve().relative_to(root.resolve()))
    return str(path)


def _category_dir(category: str | None, create: bool = False) -> Path:
    cat = _category(category)
    roots = _existing_roots()

    for root in roots:
        candidate = root / cat
        if candidate.exists():
            return candidate
        if ("/" in cat or "\\" in cat) and root == BRAIN_ROOT:
            if create:
                candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        for child in root.iterdir() if root.is_dir() else []:
            if child.is_dir() and child.name.lower() == cat.lower():
                return child

    root = _safe_root_for_writes()
    candidate = root / cat
    if create:
        candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _resolve_note(params: dict, required: bool = True) -> Path | None:
    raw_path = params.get("path") or params.get("note_path")
    if raw_path:
        path = Path(str(raw_path)).expanduser()
        if not path.is_absolute():
            path = _safe_root_for_writes() / path
        if path.suffix.lower() != ".md":
            path = path.with_suffix(".md")
        if not _is_safe_path(path):
            raise ValueError(f"Caminho fora do vault: {path}")
        if path.exists() or not required:
            return path

    name = params.get("name") or params.get("title") or params.get("note")
    category = params.get("category")
    if name:
        base = _category_dir(category, create=not required)
        filename = str(name)
        if not filename.lower().endswith(".md"):
            filename = f"{_slug(filename)}.md"
        path = base / filename
        if path.exists() or not required:
            return path

    query = params.get("query")
    if query:
        found = _search_notes(str(query), category=category, limit=1)
        if not found and category:
            found = _search_notes(str(query), category=None, limit=1)
        if found:
            return found[0]["path"]

    if required:
        raise FileNotFoundError("Nota nao encontrada. Informe path, name/title ou query.")
    return None


def _iter_notes(category: str | None = None) -> list[Path]:
    roots: list[Path]
    if category:
        roots = [_category_dir(category)]
    else:
        roots = _existing_roots()
    notes: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for note in root.rglob("*.md"):
            try:
                relative_parts = note.resolve().relative_to(root.resolve()).parts
            except Exception:
                relative_parts = note.parts
            if any(part in EXCLUDED_DIRS for part in relative_parts):
                continue
            try:
                resolved = note.resolve()
            except Exception:
                continue
            if resolved not in seen:
                seen.add(resolved)
                notes.append(note)
    return notes


def _search_notes(query: str, category: str | None = None, limit: int = 10) -> list[dict]:
    terms = [t for t in re.split(r"\s+", query.lower()) if len(t) > 1]
    if not terms:
        return []

    try:
        from memory.memory_manager import search_vault_content

        indexed = search_vault_content(query, max_results=limit, category=category)
        return [
            {
                "path": Path(item["path"]),
                "score": item.get("score", 0),
                "title": item.get("title") or Path(item["path"]).stem,
                "snippet": item.get("snippet") or "",
            }
            for item in indexed
            if item.get("path")
        ][: max(1, limit)]
    except Exception:
        pass

    results: list[dict] = []
    for note in _iter_notes(category):
        try:
            text = note.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        haystack = f"{note.stem} {_relative_label(note)} {text[:20000]}".lower()
        score = sum(3 if term in note.stem.lower() else 0 for term in terms)
        score += sum(2 if term in str(note.parent).lower() else 0 for term in terms)
        score += sum(1 if term in haystack else 0 for term in terms)
        if score <= 0:
            continue
        body = _strip_frontmatter(text)
        idx = min((haystack.find(term) for term in terms if term in haystack), default=0)
        snippet_source = re.sub(r"\s+", " ", body)
        snippet = snippet_source[max(0, idx - 80) : idx + 220].strip()
        results.append({
            "path": note,
            "score": score,
            "title": _title_from_note(text, note.stem),
            "snippet": snippet[:300],
        })

    results.sort(key=lambda item: (item["score"], item["path"].stat().st_mtime), reverse=True)
    return results[: max(1, limit)]


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for index in range(2, 1000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Destino ja existe: {path}")


def _sync_vault_artifacts() -> None:
    try:
        from memory.memory_manager import generate_vault_groups, generate_vault_index

        generate_vault_index()
        generate_vault_groups()
    except Exception as exc:
        print(f"[Obsidian] Sync skipped: {exc}")


def _status() -> str:
    roots = _existing_roots()
    total = len(_iter_notes())
    lines = ["Obsidian pronto.", f"Vaults ativos: {len(roots)}", f"Notas indexaveis: {total}"]
    for root in roots:
        lines.append(f"- {root}")
    return "\n".join(lines)


def _list_categories() -> str:
    counts: dict[str, int] = {}
    for root in _existing_roots():
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir() or child.name in EXCLUDED_DIRS:
                continue
            count = len(list(child.rglob("*.md")))
            if count:
                counts[child.name] = counts.get(child.name, 0) + count
    if not counts:
        return "Nenhuma categoria encontrada no Obsidian."
    return "\n".join(f"{name}: {count} nota(s)" for name, count in sorted(counts.items()))


def _list_notes(params: dict) -> str:
    category = params.get("category")
    limit = int(params.get("limit") or 20)
    notes = sorted(_iter_notes(category), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    if not notes:
        return f"Nenhuma nota encontrada em {category or 'todos os vaults'}."
    return "\n".join(f"- {_relative_label(note)}" for note in notes)


def _read_note(params: dict) -> str:
    note = _resolve_note(params)
    max_chars = int(params.get("max_chars") or 6000)
    text = note.read_text(encoding="utf-8", errors="ignore")
    suffix = "" if len(text) <= max_chars else "\n\n[conteudo truncado]"
    return f"{_relative_label(note)}\n\n{text[:max_chars]}{suffix}"


def _create_note(params: dict) -> str:
    title = str(params.get("title") or params.get("name") or f"Nota {datetime.now():%Y-%m-%d %H:%M}")
    category = _category(params.get("category"))
    content = str(params.get("content") or "")
    tags = params.get("tags") or [category]
    if isinstance(tags, str):
        tags = _parse_tags(tags)
    if category not in tags:
        tags.append(category)

    folder = _category_dir(category, create=True)
    filename = params.get("name") or _slug(title)
    path = folder / (str(filename) if str(filename).lower().endswith(".md") else f"{_slug(str(filename))}.md")
    if path.exists() and not params.get("overwrite"):
        path = _unique_destination(path)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = content.strip() or "_Sem conteudo ainda._"
    text = (
        "---\n"
        f"created: {now}\n"
        f"updated: {now}\n"
        f"tags: {_format_tags(tags)}\n"
        "type: note\n"
        f"folder: {category}\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{body}\n"
    )
    path.write_text(text, encoding="utf-8")
    if str(params.get("sync", True)).lower() not in {"0", "false", "no", "nao", "não", "off"}:
        _sync_vault_artifacts()
    return f"Nota criada: {_relative_label(path)}"


def _append_note(params: dict) -> str:
    note = _resolve_note(params)
    content = str(params.get("content") or "").strip()
    if not content:
        return "Nada para adicionar."
    heading = str(params.get("heading") or "").strip()
    addition = f"\n\n## {heading}\n\n{content}\n" if heading else f"\n\n{content}\n"
    with note.open("a", encoding="utf-8") as fh:
        fh.write(addition)
    _touch_frontmatter(note)
    return f"Nota atualizada: {_relative_label(note)}"


def _replace_note(params: dict) -> str:
    note = _resolve_note(params)
    content = str(params.get("content") or "")
    if not content.strip():
        return "Conteudo vazio recusado."
    note.write_text(content, encoding="utf-8")
    _sync_vault_artifacts()
    return f"Nota substituida: {_relative_label(note)}"


def _touch_frontmatter(note: Path) -> None:
    text = note.read_text(encoding="utf-8", errors="ignore")
    data, body = _split_frontmatter(text)
    data["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note.write_text(_format_frontmatter(data, body), encoding="utf-8")


def _update_frontmatter(params: dict) -> str:
    note = _resolve_note(params)
    text = note.read_text(encoding="utf-8", errors="ignore")
    data, body = _split_frontmatter(text)
    for key in ("type", "folder", "status", "summary"):
        if params.get(key) is not None:
            data[key] = str(params[key])
    if params.get("tags") is not None:
        tags = params["tags"]
        data["tags"] = _format_tags(_parse_tags(tags) if isinstance(tags, str) else list(tags))
    data["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note.write_text(_format_frontmatter(data, body), encoding="utf-8")
    _sync_vault_artifacts()
    return f"Frontmatter atualizado: {_relative_label(note)}"


def _tag_note(params: dict, remove: bool = False) -> str:
    note = _resolve_note(params)
    tag = str(params.get("tag") or "").strip().strip("#")
    if not tag:
        return "Informe a tag."
    text = note.read_text(encoding="utf-8", errors="ignore")
    data, body = _split_frontmatter(text)
    tags = _parse_tags(data.get("tags", ""))
    if remove:
        tags = [item for item in tags if item.lower() != tag.lower()]
    elif tag not in tags:
        tags.append(tag)
    data["tags"] = _format_tags(tags)
    data["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note.write_text(_format_frontmatter(data, body), encoding="utf-8")
    _sync_vault_artifacts()
    return f"Tag {'removida' if remove else 'adicionada'} em {_relative_label(note)}"


def _move_note(params: dict) -> str:
    note = _resolve_note(params)
    destination = params.get("destination") or params.get("target_category") or params.get("category_to")
    if not destination:
        return "Informe destination/target_category."
    target_category = _category(destination)
    target_dir = _category_dir(target_category, create=True)

    if note.parent.resolve() == target_dir.resolve():
        _update_frontmatter({
            "path": str(note),
            "folder": target_category,
            "tags": _format_tags(_parse_tags(_split_frontmatter(note.read_text(encoding="utf-8", errors="ignore"))[0].get("tags", "")) + [target_category]),
        })
        return f"Nota ja esta em {target_category}: {_relative_label(note)}"

    target = _unique_destination(target_dir / note.name)

    text = note.read_text(encoding="utf-8", errors="ignore")
    data, body = _split_frontmatter(text)
    tags = _parse_tags(data.get("tags", ""))
    if target_category not in tags:
        tags.append(target_category)
    data["tags"] = _format_tags([t for t in tags if t.lower() not in {"imobiliário", "imobiliario"} or target_category == "imoveis"])
    data["folder"] = target_category
    data["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note.write_text(_format_frontmatter(data, body), encoding="utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    note.replace(target)
    _sync_vault_artifacts()
    return f"Nota movida: {_relative_label(target)}"


def _rename_note(params: dict) -> str:
    note = _resolve_note(params)
    new_name = str(params.get("new_name") or params.get("title") or "").strip()
    if not new_name:
        return "Informe new_name."
    target = note.with_name(new_name if new_name.lower().endswith(".md") else f"{_slug(new_name)}.md")
    target = _unique_destination(target)
    note.replace(target)
    _sync_vault_artifacts()
    return f"Nota renomeada: {_relative_label(target)}"


def _archive_note(params: dict) -> str:
    note = _resolve_note(params)
    archive_dir = _safe_root_for_writes() / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_destination(archive_dir / note.name)
    note.replace(target)
    _sync_vault_artifacts()
    return f"Nota arquivada: {_relative_label(target)}"


def _search(params: dict) -> str:
    query = str(params.get("query") or "").strip()
    if not query:
        return "Informe query."
    limit = int(params.get("limit") or 10)
    found = _search_notes(query, category=params.get("category"), limit=limit)
    if not found:
        return "Nenhuma nota encontrada."
    lines = []
    for item in found:
        lines.append(
            f"- {_relative_label(item['path'])} | score {item['score']} | {item['title']}\n"
            f"  {item['snippet']}"
        )
    return "\n".join(lines)


def _backlinks(params: dict) -> str:
    note = _resolve_note(params)
    title = note.stem
    patterns = (f"[[{title}", f"[[{title}|")
    matches = []
    for candidate in _iter_notes():
        if candidate == note:
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if any(pattern in text for pattern in patterns):
            matches.append(candidate)
    if not matches:
        return f"Nenhum backlink encontrado para {title}."
    return "\n".join(f"- {_relative_label(match)}" for match in matches[:50])


def _open(params: dict) -> str:
    note = _resolve_note(params, required=bool(params.get("path") or params.get("query") or params.get("name") or params.get("title")))
    path = note if note else _safe_root_for_writes()
    if os.name == "nt":
        url = "obsidian://open?path=" + quote(str(path.resolve()))
        webbrowser.open(url)
    else:
        webbrowser.open(str(path.resolve()))
    return f"Abrindo no Obsidian: {path}"


def _daily(params: dict) -> str:
    category = params.get("category") or "daily"
    today = params.get("date") or datetime.now().strftime("%Y-%m-%d")
    params = {
        **params,
        "category": category,
        "title": f"Diario {today}",
        "name": f"{today}.md",
        "content": params.get("content") or f"## {today}\n\n",
    }
    return _create_note(params)


def _organize(params: dict) -> str:
    source = params.get("category") or None
    dry_run = bool(params.get("dry_run", False))
    moved = []
    for note in _iter_notes(source):
        if note.parent.name in CATEGORY_KEYWORDS:
            continue
        try:
            text = note.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        haystack = f"{note.stem.lower()} {text[:10000]}"
        target_category = None
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(keyword in haystack for keyword in keywords):
                target_category = category
                break
        if not target_category:
            continue
        target_dir = _category_dir(target_category, create=not dry_run)
        target = _unique_destination(target_dir / note.name)
        moved.append(f"{_relative_label(note)} -> {target_category}/{target.name}")
        if not dry_run:
            note.replace(target)
    if not dry_run and moved:
        _sync_vault_artifacts()
    return "\n".join(moved) if moved else "Nada para reorganizar."


def obsidian_control(parameters: dict = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").strip().lower().replace("-", "_")

    if player:
        try:
            player.write_log(f"[Obsidian] {action}")
        except Exception:
            pass

    try:
        if action in ("status", "stats", "count", "count_notes"):
            from actions.brain_activity import reading_notes
            with reading_notes(player):
                return _status()
        if action in ("categories", "list_categories"):
            return _list_categories()
        if action in ("list", "list_notes"):
            return _list_notes(params)
        if action in ("search", "find"):
            return _search(params)
        if action == "read":
            return _read_note(params)
        if action in ("create", "create_note"):
            return _create_note(params)
        if action in ("append", "append_note"):
            return _append_note(params)
        if action in ("replace", "write", "replace_note"):
            return _replace_note(params)
        if action in ("frontmatter", "update_frontmatter"):
            return _update_frontmatter(params)
        if action in ("tag", "add_tag"):
            return _tag_note(params, remove=False)
        if action == "remove_tag":
            return _tag_note(params, remove=True)
        if action in ("move", "move_note"):
            return _move_note(params)
        if action in ("rename", "rename_note"):
            return _rename_note(params)
        if action in ("archive", "archive_note"):
            return _archive_note(params)
        if action == "backlinks":
            return _backlinks(params)
        if action in ("open", "open_note", "open_vault"):
            return _open(params)
        if action in ("daily", "daily_note"):
            return _daily(params)
        if action in ("organize", "reorganize"):
            return _organize(params)
        return (
            f"Acao Obsidian desconhecida: {action}. "
            "Use status, categories, list, search, read, create, append, replace, "
            "frontmatter, tag, remove_tag, move, rename, archive, backlinks, open, daily ou organize."
        )
    except Exception as exc:
        return f"Erro no Obsidian ({action}): {exc}"






