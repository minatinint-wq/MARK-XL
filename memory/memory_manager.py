import json
import re
import sqlite3
import unicodedata
from datetime import datetime
from threading import Lock, Thread
from pathlib import Path
import sys
import time


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR          = get_base_dir()
MEMORY_PATH       = BASE_DIR / "memory" / "long_term.json"
NEURAL_ACTIVITY   = BASE_DIR / "memory" / "neural_activity.json"
VAULT_SEARCH_INDEX = BASE_DIR / "memory" / "vault_search_index.json"
VAULT_SEARCH_DB = BASE_DIR / "memory" / "vault_search_index.sqlite3"
BRAIN_ROOT = Path(r"D:\xxxx_memory")
NEW_YYYY_ROOT = BRAIN_ROOT / "30_Sistema" / "obsidian_data" / "xxxx-vault" / "YYYY"
LEGACY_YYYY_ROOT = BRAIN_ROOT / "obsidian_data" / "xxxx-vault" / "YYYY"
OBSIDIAN_VAULTS   = [
    BRAIN_ROOT,
]
EXCLUDED_DIRS = {".git", ".obsidian", "__pycache__"}
_lock             = Lock()
MAX_VALUE_LENGTH  = 380
MEMORY_MAX_CHARS  = 2200

# ============================================
# IN-MEMORY CACHE (8GB RAM optimization)
# ============================================
_VAULT_CACHE = {"data": None, "ts": 0, "ttl": 30}
_MEMORY_CACHE = {"data": None, "ts": 0, "ttl": 5, "dirty": False}
_SEARCH_INDEX_CACHE = {"data": None, "mtime": 0.0}
_VAULT_REFRESH_RUNNING = False
_SEARCH_INDEX_REFRESH_RUNNING = False
SEARCH_INDEX_MAX_TEXT_CHARS = 6000
SEARCH_INDEX_REFRESH_SECONDS = 300
VISUAL_SAMPLE_PER_CATEGORY = 180

def _vault_cache_valid():
    return _VAULT_CACHE["data"] is not None and (time.time() - _VAULT_CACHE["ts"]) < _VAULT_CACHE["ttl"]

def _memory_cache_valid():
    return _MEMORY_CACHE["data"] is not None and (time.time() - _MEMORY_CACHE["ts"]) < _MEMORY_CACHE["ttl"]


def _refresh_vault_artifacts_async() -> None:
    global _VAULT_REFRESH_RUNNING

    if _VAULT_REFRESH_RUNNING:
        return
    _VAULT_REFRESH_RUNNING = True

    def worker():
        global _VAULT_REFRESH_RUNNING
        try:
            generate_vault_index()
            generate_vault_groups()
            generate_vault_search_index()
        except Exception as e:
            print(f"[Memory] Vault refresh failed: {e}")
        finally:
            _VAULT_REFRESH_RUNNING = False

    Thread(target=worker, daemon=True, name="VaultArtifactRefresh").start()

# ============================================
# OBSIDIAN VAULT LOADER
# ============================================

def _existing_vaults() -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()
    for vault in OBSIDIAN_VAULTS:
        if not vault.exists():
            continue
        try:
            resolved = str(vault.resolve())
        except Exception:
            resolved = str(vault)
        if resolved not in seen:
            seen.add(resolved)
            roots.append(vault)
    return roots


def scan_vault_structure() -> dict[str, int]:
    """Scan Obsidian vault(s) and return {folder_name: file_count} for all subdirs."""
    if _vault_cache_valid():
        return _VAULT_CACHE["data"]
    vaults = _existing_vaults()
    if not vaults:
        return {}
    structure: dict[str, int] = {}
    for vault in vaults:
        for item in vault.iterdir():
            if not item.is_dir() or item.name in EXCLUDED_DIRS:
                continue
            count = len(list(item.glob("**/*.md")))
            if count > 0:
                structure[item.name] = structure.get(item.name, 0) + count
    _VAULT_CACHE["data"] = dict(sorted(structure.items()))
    _VAULT_CACHE["ts"] = time.time()
    return _VAULT_CACHE["data"]


def _visual_vaults() -> list[Path]:
    """Vault roots used by the HTML neural map.

    Search still includes learned/system roots. The visual map should mirror the
    folders the user navigates in Obsidian, so it starts from the visible vault
    root and relies on EXCLUDED_DIRS to hide system/archive buckets.
    """
    if BRAIN_ROOT.exists():
        return [BRAIN_ROOT]
    return _existing_vaults()


def scan_visual_vault_structure() -> dict[str, int]:
    vaults = _visual_vaults()
    if not vaults:
        return {}
    structure: dict[str, int] = {}
    for vault in vaults:
        for item in vault.iterdir():
            if not item.is_dir() or item.name in EXCLUDED_DIRS:
                continue
            count = len(list(item.glob("**/*.md")))
            if count > 0:
                structure[item.name] = structure.get(item.name, 0) + count
    return dict(sorted(structure.items()))


def load_vault_index_files() -> list[tuple[str, str]]:
    """Read key index/hub markdown files from all vaults. Returns [(folder, content), ...]."""
    vaults = _existing_vaults()
    if not vaults:
        return []
    results = []
    for vault in vaults:
        candidates = [
            vault / "_indice",
            vault / "Cerebro",
            vault / "imobiliario",
            vault / "Imobiliario",
            vault / "00_Cerebro" / "Cerebro",
            vault / "01_Negocios_Imoveis" / "Imobiliario",
            vault / "03_Estudo_Tecnologia" / "Tecnologia",
        ]
        try:
            for child in vault.iterdir():
                if child.is_dir() and child.name not in EXCLUDED_DIRS:
                    candidates.append(child)
        except Exception:
            pass
        seen_folders: set[str] = set()
        for folder in candidates:
            if not folder.exists() or not folder.is_dir():
                continue
            try:
                key = str(folder.resolve())
            except Exception:
                key = str(folder)
            if key in seen_folders:
                continue
            seen_folders.add(key)
            for md_file in sorted(folder.glob("**/*.md")):
                try:
                    if not _is_key_index_file(md_file):
                        continue
                    if "atlas_5000" in md_file.parts:
                        continue
                    if "_hub_" in md_file.stem:
                        continue
                    if any(part in EXCLUDED_DIRS for part in md_file.parts):
                        continue
                    text = md_file.read_text(encoding="utf-8", errors="ignore")
                    if "type: visual-10k-index" in text[:500]:
                        continue
                    text = _strip_yaml_frontmatter(text)
                    if len(text.strip()) > 100:
                        results.append((md_file.stem, text.strip()))
                except Exception:
                    pass
    return results


def _normalize_search_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9#_./\\:-]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _term_count(haystack: str, term: str) -> int:
    if not haystack or not term:
        return 0
    if len(term) <= 3:
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack))
    return haystack.count(term)


def _has_term(haystack: str, term: str) -> bool:
    return _term_count(haystack, term) > 0


def _result_key(title: str, folder: str) -> str:
    clean = _normalize_search_text(title)
    clean = re.sub(r"(?<![a-z0-9])(?:copy|copia|duplicado|duplicate)\b", "", clean)
    clean = re.sub(r"[-_\s]+(?:2|3|4|5)$", "", clean).strip()
    return f"{folder.lower()}::{clean}"


def _is_key_index_file(path: Path) -> bool:
    name = path.name.lower()
    stem = path.stem.lower()
    return (
        name == "_index.md"
        or stem.startswith("indice")
        or stem.startswith("index")
        or stem.endswith("_index")
        or "compact" in stem
    )


def _category_search_terms(category_norm: str) -> list[str]:
    if not category_norm:
        return []
    groups = {
        "imoveis": ["imoveis", "imovel", "imobiliario", "corretor", "negocios_imoveis"],
        "imobiliario": ["imoveis", "imovel", "imobiliario", "corretor", "negocios_imoveis"],
        "corretor": ["corretor", "imobiliario", "vendas", "leads"],
        "marketing": ["marketing", "ads", "campanha", "facebook", "google"],
        "ads": ["marketing", "ads", "campanha", "facebook", "google"],
        "tech": ["tech", "tecnologia", "programacao", "ia", "software"],
        "tecnologia": ["tech", "tecnologia", "programacao", "ia", "software"],
        "games": ["games", "jogos", "game"],
        "jogos": ["games", "jogos", "game"],
        "cannabis": ["cannabis", "cultivo", "hidroponia"],
        "cultivo": ["cultivo", "cannabis", "hidroponia", "indoor"],
        "saude": ["saude", "health", "corpo", "biologia"],
        "dicionario": ["dicionario", "dictionary", "vocabulary", "vocabulario"],
        "musica": ["musica", "music", "audio", "spotify"],
        "financas": ["financas", "finance", "dinheiro", "currencies", "mercado"],
        "estudo": ["estudo", "aprendizado", "auto_estudo", "tecnicas"],
    }
    terms = [category_norm]
    for key, values in groups.items():
        if key in category_norm:
            terms.extend(values)
    deduped: list[str] = []
    for term in terms:
        normalized = _normalize_search_text(term)
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _iter_vault_search_files():
    extensions = {".md", ".txt", ".json"}
    seen: set[str] = set()
    for vault in _existing_vaults():
        if not vault.exists() or not vault.is_dir():
            continue
        for folder in sorted(vault.iterdir()):
            if not folder.is_dir() or folder.name in EXCLUDED_DIRS:
                continue
            for entry in folder.rglob("*"):
                if not entry.is_file() or entry.suffix.lower() not in extensions:
                    continue
                try:
                    resolved = str(entry.resolve())
                    rel_parts = entry.resolve().relative_to(vault.resolve()).parts
                except Exception:
                    resolved = str(entry)
                    rel_parts = entry.parts
                if resolved in seen or any(part in EXCLUDED_DIRS for part in rel_parts):
                    continue
                seen.add(resolved)
                yield vault, folder.name, entry


def generate_vault_search_index() -> dict:
    """Build the on-disk FTS index used by local knowledge search.

    Keeping every note body in a Python/JSON cache becomes expensive once the
    vault reaches tens of thousands of memories. SQLite FTS keeps that corpus
    local and indexed on disk; a search only returns matching rows.
    """
    payload = {
        "version": 2,
        "backend": "sqlite-fts5",
        "updated": datetime.now().isoformat(),
        "updated_ts": time.time(),
        "total_files": 0,
        "vault_roots": [str(v) for v in _existing_vaults()],
    }
    try:
        temp_db = VAULT_SEARCH_DB.with_suffix(".building.sqlite3")
        if temp_db.exists():
            temp_db.unlink()
        connection = sqlite3.connect(temp_db)
        try:
            connection.executescript("""
                PRAGMA journal_mode=OFF;
                PRAGMA synchronous=OFF;
                CREATE VIRTUAL TABLE notes USING fts5(
                    title, meta, content, path UNINDEXED, folder UNINDEXED,
                    relative_path UNINDEXED, tags UNINDEXED, preview UNINDEXED,
                    tokenize='unicode61 remove_diacritics 2'
                );
            """)
            batch: list[tuple[str, str, str, str, str, str, str, str]] = []
            total = 0
            for vault, folder_name, entry in _iter_vault_search_files():
                try:
                    raw = entry.read_text(encoding="utf-8", errors="ignore")
                    text, tags = _strip_yaml_frontmatter_and_tags(raw) if entry.suffix.lower() == ".md" else (raw, [])
                    first_line = text.strip().split("\n")[0].strip("# *").strip() if text.strip() else entry.stem
                    try:
                        rel_path = str(entry.resolve().relative_to(vault.resolve()))
                    except Exception:
                        rel_path = entry.name
                    preview = re.sub(r"\s+", " ", text).strip()[:1200]
                    batch.append((
                        first_line or entry.stem,
                        f"{entry.stem} {folder_name} {rel_path} {' '.join(str(tag) for tag in tags)}",
                        text[:SEARCH_INDEX_MAX_TEXT_CHARS],
                        str(entry), folder_name, rel_path,
                        json.dumps(tags, ensure_ascii=False), preview,
                    ))
                    if len(batch) >= 512:
                        connection.executemany(
                            "INSERT INTO notes(title, meta, content, path, folder, relative_path, tags, preview) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            batch,
                        )
                        total += len(batch)
                        batch.clear()
                except Exception:
                    continue
            if batch:
                connection.executemany(
                    "INSERT INTO notes(title, meta, content, path, folder, relative_path, tags, preview) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
                total += len(batch)
            connection.commit()
            payload["total_files"] = total
        finally:
            connection.close()
        temp_db.replace(VAULT_SEARCH_DB)
        VAULT_SEARCH_INDEX.parent.mkdir(parents=True, exist_ok=True)
        VAULT_SEARCH_INDEX.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _SEARCH_INDEX_CACHE["data"] = payload
        _SEARCH_INDEX_CACHE["mtime"] = VAULT_SEARCH_INDEX.stat().st_mtime
    except Exception as exc:
        print(f"[Memory] Local FTS index failed: {exc}")
    return payload


def _load_vault_search_index() -> dict | None:
    try:
        mtime = VAULT_SEARCH_INDEX.stat().st_mtime
    except Exception:
        return None

    if _SEARCH_INDEX_CACHE["data"] is not None and _SEARCH_INDEX_CACHE["mtime"] == mtime:
        return _SEARCH_INDEX_CACHE["data"]

    try:
        data = json.loads(VAULT_SEARCH_INDEX.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        _SEARCH_INDEX_CACHE["data"] = data
        _SEARCH_INDEX_CACHE["mtime"] = mtime
        return data
    except Exception:
        return None


def _refresh_vault_search_index_async() -> None:
    global _SEARCH_INDEX_REFRESH_RUNNING

    if _SEARCH_INDEX_REFRESH_RUNNING:
        return
    _SEARCH_INDEX_REFRESH_RUNNING = True

    def worker():
        global _SEARCH_INDEX_REFRESH_RUNNING
        try:
            generate_vault_search_index()
        except Exception as exc:
            print(f"[Memory] Search index refresh failed: {exc}")
        finally:
            _SEARCH_INDEX_REFRESH_RUNNING = False

    Thread(target=worker, daemon=True, name="VaultSearchIndexRefresh").start()


def _ensure_vault_search_index() -> dict | None:
    data = _load_vault_search_index()
    if data:
        updated_ts = float(data.get("updated_ts") or 0.0)
        if updated_ts and time.time() - updated_ts > SEARCH_INDEX_REFRESH_SECONDS:
            _refresh_vault_search_index_async()
        return data
    return generate_vault_search_index()


def _search_vault_fts(query: str, max_results: int, category: str | None) -> list[dict] | None:
    """Query the compact SQLite FTS index without loading the whole vault in RAM."""
    if not VAULT_SEARCH_DB.exists():
        return None
    terms = [term for term in _normalize_search_text(query).split() if len(term) > 1]
    if not terms:
        return []
    # Quote each token so punctuation in a voice command cannot become FTS syntax.
    expression = " AND ".join('"' + term.replace('"', ' ') + '"' for term in terms)
    category_terms = _category_search_terms(_normalize_search_text(category or ""))
    try:
        connection = sqlite3.connect(f"file:{VAULT_SEARCH_DB.as_posix()}?mode=ro", uri=True)
        try:
            rows = connection.execute(
                "SELECT title, path, folder, relative_path, tags, preview, bm25(notes, 8.0, 3.0, 1.0) AS rank "
                "FROM notes WHERE notes MATCH ? ORDER BY rank LIMIT ?",
                (expression, max(max_results * 24, 96)),
            ).fetchall()
        finally:
            connection.close()
    except (sqlite3.Error, OSError):
        return None

    results: list[dict] = []
    seen: set[str] = set()
    for title, path, folder, relative_path, raw_tags, preview, rank in rows:
        category_blob = _normalize_search_text(f"{folder} {relative_path} {raw_tags}")
        if category_terms and not any(term in category_blob for term in category_terms):
            continue
        key = _result_key(str(title), str(folder))
        if key in seen:
            continue
        seen.add(key)
        try:
            tags = json.loads(raw_tags) if raw_tags else []
        except (TypeError, json.JSONDecodeError):
            tags = []
        results.append({
            "title": title or "Nota",
            "path": path or "",
            "folder": folder or "",
            "snippet": preview or "",
            # FTS ranks are negative where lower is better; keep a positive, readable score.
            "score": round(max(0.0, 100.0 + float(rank or 0.0)), 1),
            "tags": tags if isinstance(tags, list) else [],
        })
        if len(results) >= max_results:
            break
    return results


def _search_vault_index(query: str, max_results: int = 10, category: str | None = None) -> list[dict] | None:
    data = _ensure_vault_search_index()
    if not data:
        return None

    if data.get("backend") == "sqlite-fts5":
        return _search_vault_fts(query, max_results, category)

    query_norm = _normalize_search_text(query)
    terms = [term for term in query_norm.split() if len(term) > 1]
    if not terms:
        return []

    category_norm = _normalize_search_text(category or "")
    category_terms = _category_search_terms(category_norm)
    scored: list[tuple[float, dict]] = []
    for item in data.get("files", []):
        category_blob = _normalize_search_text(
            " ".join(
                [
                    str(item.get("folder") or ""),
                    str(item.get("relative_path") or ""),
                    str(item.get("path") or ""),
                    str(item.get("meta_search") or ""),
                ]
            )
        )
        if category_terms and not any(term in category_blob for term in category_terms):
            continue

        title = str(item.get("title_search") or "")
        meta = str(item.get("meta_search") or "")
        haystack = str(item.get("search") or "")
        if not haystack:
            continue

        score = 0.0
        if query_norm and query_norm in title:
            score += 28.0
        elif query_norm and query_norm in meta:
            score += 18.0
        elif query_norm and query_norm in haystack:
            score += 12.0

        matched = 0
        for term in terms:
            term_score = 0.0
            if _has_term(title, term):
                term_score += 8.0
            if _has_term(meta, term):
                term_score += 4.0
            count = _term_count(haystack, term)
            if count:
                term_score += 1.0 + min(6.0, count * 0.35)
            if term_score > 0:
                matched += 1
                score += term_score

        required_matches = 2 if len(terms) >= 3 else 1
        if matched < required_matches:
            continue
        if len(terms) > 1:
            score += matched * 10.0
            score += (matched / len(terms)) * 6.0
            score -= (len(terms) - matched) * 4.0
            if matched == len(terms):
                score += 12.0

        path_text = _normalize_search_text(str(item.get("path") or ""))
        name_text = _normalize_search_text(str(item.get("name") or item.get("title") or ""))
        query_is_for_index = any(term in {"indice", "index"} for term in terms)
        if not query_is_for_index and re.match(r"^(indice|index)(?:[^a-z0-9]|$)", name_text):
            score -= 16.0
        if all(_has_term(title, term) for term in terms):
            score += 18.0
        if "knowledge_compact" in path_text:
            score += 6.0

        try:
            age_days = max(0.0, (time.time() - float(item.get("mtime") or 0.0)) / 86400.0)
            score += max(0.0, 1.0 - min(age_days, 90.0) / 90.0)
        except Exception:
            pass

        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda pair: (pair[0], float(pair[1].get("mtime") or 0.0)), reverse=True)
    results: list[dict] = []
    seen_result_keys: set[str] = set()
    for score, item in scored:
        key = _result_key(str(item.get("title") or item.get("name") or ""), str(item.get("folder") or ""))
        if key in seen_result_keys:
            continue
        seen_result_keys.add(key)
        text = ""
        tags = item.get("tags") or []
        try:
            path = Path(str(item["path"]))
            text = path.read_text(encoding="utf-8", errors="ignore")
            if path.suffix.lower() == ".md":
                text, tags = _strip_yaml_frontmatter_and_tags(text)
        except Exception:
            text = str(item.get("preview") or "")

        results.append({
            "title": item.get("title") or item.get("name") or "Nota",
            "path": str(item.get("path") or ""),
            "folder": item.get("folder") or "",
            "snippet": _get_search_snippet(text or str(item.get("preview") or ""), query),
            "score": round(score, 1),
            "tags": tags,
        })
        if len(results) >= max_results:
            break
    return results


def search_vault_content(query: str, max_results: int = 10, category: str | None = None) -> list[dict]:
    """Search Obsidian vault by title, content, folder name, tags, and filenames.
    Includes .md, .txt, and .json files.
    Returns [{title, path, folder, snippet, score}, ...] sorted by relevance."""
    indexed = _search_vault_index(query, max_results=max_results, category=category)
    if indexed is not None:
        return indexed

    vaults = _existing_vaults()
    if not vaults or not query.strip():
        return []

    query_orig = query.strip()
    query_lower = query_orig.lower()
    terms = [t for t in query_lower.split() if len(t) > 1]
    if not terms:
        return []

    seen: set[str] = set()
    results = []
    extensions = ("*.md", "*.txt", "*.json")

    for vault in vaults:
        for folder in sorted(vault.iterdir()):
            if not folder.is_dir() or folder.name in EXCLUDED_DIRS:
                continue

            folder_name_lower = folder.name.lower()
            folder_matches = any(term in folder_name_lower for term in terms)

            for ext in extensions:
                for entry in sorted(folder.glob(f"**/{ext}")):
                    if entry.stem in seen:
                        continue
                    seen.add(entry.stem)

                    score = 0.0
                    title_lower = entry.stem.lower()
                    tags: list[str] = []

                    # Title match — highest weight
                    for term in terms:
                        if term in title_lower:
                            score += 3.0

                    # Folder name match
                    if folder_matches:
                        score += 1.0

                    try:
                        text = entry.read_text(encoding="utf-8", errors="ignore")
                        text, tags = _strip_yaml_frontmatter_and_tags(text)
                        content_lower = text.lower()
                    except Exception:
                        content_lower = ""
                        text = ""

                    # Content match
                    for term in terms:
                        if term in content_lower:
                            count = content_lower.count(term)
                            score += 1.0 + min(count * 0.2, 4.0)

                    # Tag match
                    tag_text = " ".join(t.lower() for t in tags)
                    for term in terms:
                        if term in tag_text:
                            score += 2.0

                    if score > 0:
                        first_line = ""
                        if text.strip():
                            fl = text.strip().split("\n")[0].strip("# *").strip()
                            first_line = fl if fl else entry.stem
                        snippet = _get_search_snippet(text or "", query_lower)
                        results.append({
                            "title": first_line or entry.stem,
                            "path": str(entry),
                            "folder": folder.name,
                            "snippet": snippet,
                            "score": round(score, 1),
                        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results]


def _strip_yaml_frontmatter_and_tags(text: str) -> tuple[str, list[str]]:
    """Remove YAML frontmatter and extract tags. Returns (clean_text, tags_list)."""
    tags: list[str] = []
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            front = text[3:end]
            # Extract tags array or inline tags
            for line in front.split("\n"):
                line = line.strip()
                if line.startswith("tags:"):
                    rest = line[5:].strip()
                    if rest.startswith("["):
                        try:
                            parsed = json.loads(rest)
                            if isinstance(parsed, list):
                                tags.extend(parsed)
                        except Exception:
                            pass
                    elif rest:
                        tags.append(rest)
                elif line.startswith("- "):
                    tags.append(line[2:].strip())
            return text[end + 3:], tags
    return text, tags


def search_vault_deep(query: str, top_n: int = 3, max_chars: int = 3000) -> str:
    """Deep search — returns full content of best-matching notes for AI reading.
    Returns a formatted string with full note content."""
    results = search_vault_content(query, max_results=top_n)
    if not results:
        return ""

    parts = []
    for r in results:
        try:
            path = Path(r["path"])
            text = path.read_text(encoding="utf-8", errors="ignore")
            text = _strip_yaml_frontmatter(text)
            size = len(text)
            parts.append(f"📄 {r['title']}  [{r['folder']}]")
            parts.append(f"{'─' * 60}")
            parts.append(text[:max_chars] if size > max_chars else text)
            if size > max_chars:
                parts.append("… (continuation available)")
            parts.append("")
        except Exception:
            pass
    return "\n".join(parts)


def _get_search_snippet(text: str, query: str, context_chars: int = 120) -> str:
    """Extract a snippet of text around the first match of query."""
    text = text.strip()
    if not text:
        return ""
    haystack = text.lower()
    query_lower = query.strip().lower()
    idx = haystack.find(query_lower)
    if idx == -1:
        for term in [t for t in re.split(r"\s+", query_lower) if len(t) > 1]:
            idx = haystack.find(term)
            if idx != -1:
                query_lower = term
                break
    if idx == -1:
        return text[:200]
    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(query_lower) + context_chars)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def _strip_yaml_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (--- ... ---) from markdown content."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:]
    return text


def _extract_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return YAML-ish frontmatter fields and body without requiring PyYAML."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end]
    body = text[end + 3:]
    fields: dict[str, str] = {}
    current_key = ""
    list_values: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            list_values.append(stripped[2:].strip())
            fields[current_key] = ", ".join(list_values)
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            current_key = key.strip()
            list_values = []
            fields[current_key] = value.strip()
    return fields, body


def _frontmatter_tags(fields: dict[str, str]) -> list[str]:
    raw = (fields.get("tags") or "").strip()
    if not raw:
        return []
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
        chunks = raw.split(",")
    else:
        chunks = re.split(r"[, ]+", raw)
    tags: list[str] = []
    for chunk in chunks:
        tag = chunk.strip().strip("'\"#")
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _vault_label(vault: Path) -> str:
    text = str(vault)
    if "obsidian_data" in text and vault.name == "learned":
        return "Obsidian/YYYY/learned"
    if "obsidian_data" in text and vault.name == "auto_study":
        return "Obsidian/YYYY/auto_study"
    if "obsidian_data" in text:
        return "Obsidian/YYYY"
    if vault == Path(r"D:\xxxx_memory"):
        return "D:/xxxx_memory"
    try:
        return str(vault.relative_to(BASE_DIR))
    except Exception:
        return str(vault)


def get_brain_state() -> tuple:
    """Return (total_notes, category_count, newest_ts, recent_count, domain_preview).

    Provides a live snapshot of the Obsidian vault so JARVIS knows his
    own brain state at connect time.
    """
    structure = scan_vault_structure()
    total = sum(structure.values())
    cats  = len(structure)
    top   = sorted(structure.items(), key=lambda x: -x[1])[:10]

    import os
    from datetime import datetime as _dt

    newest_ts = ""
    for vault in _existing_vaults():
        md_files = sorted(vault.rglob("*.md"), key=os.path.getmtime, reverse=True)
        if md_files:
            ts = _dt.fromtimestamp(os.path.getmtime(md_files[0]))
            newest_ts = ts.strftime("%Y-%m-%d %H:%M")
            break

    import time as _time
    cut = _time.time() - 86400
    recent_count = 0
    for vault in _existing_vaults():
        for f in vault.rglob("*.md"):
            try:
                if os.path.getmtime(f) > cut:
                    recent_count += 1
            except Exception:
                pass

    domain_preview = "\n".join(
        f"  {k}: {v} notes" for k, v in top
    )

    return total, cats, newest_ts, recent_count, domain_preview


def load_recent_vault_notes(n: int = 15) -> str:
    """Return content snippets from the N most recently modified vault notes."""
    vaults = _existing_vaults()
    if not vaults:
        return ""
    candidates = []
    for vault in vaults:
        for folder in vault.iterdir():
            if not folder.is_dir() or folder.name in EXCLUDED_DIRS:
                continue
            for md_file in folder.glob("**/*.md"):
                try:
                    mod = md_file.stat().st_mtime
                    text = md_file.read_text(encoding="utf-8", errors="ignore")
                    text = _strip_yaml_frontmatter(text)
                    first = text.strip().split("\n")[0].strip("# *").strip() if text.strip() else md_file.stem
                    candidates.append((mod, md_file, folder.name, first, text))
                except Exception:
                    pass
    candidates.sort(reverse=True)
    parts = []
    seen = set()
    for mod, md_file, folder, title, text in candidates:
        if md_file.stem in seen:
            continue
        seen.add(md_file.stem)
        snippet = text.strip()[:300]
        parts.append(f"📄 {title}  [{folder}]\n{snippet}\n")
        if len(parts) >= n:
            break
    if parts:
        return "[RECENTES NOTAS DO VAULT - Conteudo fresco disponivel]\n" + "\n".join(parts) + "\n"
    return ""


def load_obsidian_context(max_chars: int = 3000) -> str:
    """Build a token-efficient summary of all Obsidian vaults for AI context."""
    if not _existing_vaults():
        return ""

    structure = scan_vault_structure()
    if not structure:
        return ""

    parts = []
    parts.append("[OBSIDIAN VAULT - Neural Knowledge Base]")

    # 1. Folder structure overview (lightweight)
    folder_lines = []
    total_files = sum(structure.values())
    for folder, count in structure.items():
        folder_lines.append(f"  {folder}: {count} notes")
    parts.append(f"Structure ({total_files} total notes across {len(structure)} categories):\n" + "\n".join(folder_lines))

    # 2. Key index content (up to max_chars)
    index_entries = load_vault_index_files()
    index_text = ""
    for name, content in index_entries:
        entry = f"\n--- {name} ---\n{content[:800]}"
        if len(index_text) + len(entry) > max_chars:
            break
        index_text += entry
    if index_text:
        parts.append(f"\nKey index/hub content:{index_text}")

    # 3. Brief summary of knowledge domains (consolidated vault)
    domains = {
        "cannabis": {"label": "Cannabis — genética, cultivo, extração, medicina", "folders": ["Cannabis", "cannabis", "cannabis_equipment", "cannabis_extraction", "cannabis_genetics", "cannabis_growing", "cannabis_medicine", "cannabis_nutrients", "cannabis_problems", "cannabis_techniques"]},
        "cultivo": {"label": "Cultivo — aeroponia, aquaponia, ppfd, vpd", "folders": ["Cultivo", "aeroponia", "aeroponics", "aquaponia", "aquaponics_fish", "aquaponics_plants", "ppfd", "vpd"]},
        "hidroponia": {"label": "Hidroponia — sistemas, nutrientes, hidroponia", "folders": ["Hidroponia", "hidroponia", "hydroponics_systems"]},
        "imobiliario": {"label": "Imobiliário — vendas, financiamento, mercado, corretagem", "folders": ["08_Imobiliario", "09_Corretor_Vendas", "Imobiliario", "imobiliario", "imobiliary", "corretor", "corretor_atendimento", "corretor_avaliacao", "corretor_financiamento", "corretor_gestao_leads", "corretor_legal", "corretor_mercado", "corretor_venda_tecnicas", "real_estate", "mortgage"]},
        "estudo": {"label": "Estudo — aprendizado, livros, estudo", "folders": ["04_Estudo", "Estudo", "aprendizado", "auto_study", "books", "formulas"]},
        "autoestudo": {"label": "Auto-estudo — auto-estudo", "folders": ["Auto-estudo"]},
        "tecnologia": {"label": "Tecnologia — hardware, software, IA, técnicas", "folders": ["05_Tecnologia", "06_IA_Automacoes", "Tecnologia", "tech", "technologies", "techniques", "tecnicas"]},
        "financas": {"label": "Finanças — investimentos, câmbio, mercado", "folders": ["11_Financas", "Financas", "financas", "finance", "currencies", "market_prices"]},
        "viagem": {"label": "Viagem — destinos, atrações, países, moedas", "folders": ["Viagem", "viagem", "travel", "attractions", "locations"]},
        "biologia": {"label": "Biologia — biologia, fungos, bactérias, nutrientes", "folders": ["Biologia", "biology", "bacteria", "fungi", "nutrients"]},
        "saude": {"label": "Saúde — saúde, health", "folders": ["Saude", "saude", "health"]},
        "cerebro": {"label": "Cérebro — núcleo neural, identidade, índices, memórias", "folders": ["00_Cerebro", "Cerebro", "memoria", "dictionary", "preferences", "relationships", "routines", "skills", "vocabulary", "wishes", "notes"]},
        "receitas": {"label": "Receitas — culinária, alimentos, food", "folders": ["17_Receitas", "Receitas", "receitas", "recipes", "food"]},
        "pessoal": {"label": "Mundo Pessoal — trabalho, projetos, pessoal", "folders": ["Mundo_Pessoal", "work", "projects", "XXXX", "YYYY", "ZZZZ"]},
        "cultura": {"label": "Cultura — entretenimento, música, esportes", "folders": ["18_Cultura", "19_Musica", "Cultura", "entertainment", "music", "sports"]},
    }
    domain_lines = []
    for key, info in domains.items():
        existing = [f for f in info["folders"] if f in structure]
        if existing:
            count = sum(structure[f] for f in existing)
            domain_lines.append(f"  {info['label']}: {count} notes")
    if domain_lines:
        parts.append(f"\nKnowledge domains:\n" + "\n".join(domain_lines))

    result = "\n".join(parts)
    if len(result) > 4000:
        result = result[:3997] + "…"
    return result


def generate_vault_index():
    """Write a JSON index of the entire vault to memory/vault_index.json for the HTML map."""
    structure = scan_visual_vault_structure()
    if not structure:
        return
    index_path = BASE_DIR / "memory" / "vault_index.json"
    data = {
        "updated": datetime.now().isoformat(),
        "total_files": sum(structure.values()),
        "total_categories": len(structure),
        "vault_roots": [{"path": str(v), "label": _vault_label(v)} for v in _visual_vaults()],
        "categories": {},
    }
    for folder, count in structure.items():
        files = []
        sampled = 0
        sources: dict[str, int] = {}
        total_size = 0
        newest_mtime = 0.0
        seen: set[str] = set()
        for vault in _visual_vaults():
            folder_path = vault / folder
            if not folder_path.exists():
                continue
            source = _vault_label(vault)
            for md_file in sorted(folder_path.glob("**/*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    resolved = str(md_file.resolve())
                except Exception:
                    resolved = str(md_file)
                if resolved in seen:
                    continue
                seen.add(resolved)
                try:
                    stat = md_file.stat()
                    total_size += stat.st_size
                    newest_mtime = max(newest_mtime, stat.st_mtime)
                    sources[source] = sources.get(source, 0) + 1
                    # The map is a visual sample, not a second full-text database.
                    # A cap keeps a 50k+ local vault responsive in WebGL; the real
                    # count remains in file_count and fast search uses SQLite FTS.
                    if sampled >= VISUAL_SAMPLE_PER_CATEGORY:
                        continue
                    text = md_file.read_text(encoding="utf-8", errors="ignore")
                    fields, body = _extract_frontmatter(text)
                    first_line = body.strip().split("\n")[0].strip("# *").strip() if body.strip() else md_file.stem
                    try:
                        rel_path = str(md_file.resolve().relative_to(vault.resolve()))
                    except Exception:
                        rel_path = md_file.name
                    files.append({
                        "name": md_file.stem,
                        "title": first_line or md_file.stem,
                        "size": stat.st_size,
                        "path": str(md_file),
                        "relative_path": rel_path,
                        "folder": folder,
                        "source": source,
                        "vault": str(vault),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "tags": _frontmatter_tags(fields),
                        "type": fields.get("type", ""),
                        "frontmatter_folder": fields.get("folder", ""),
                    })
                    sampled += 1
                except Exception:
                    pass
        data["categories"][folder] = {
            "file_count": count,
            "sample_files": files,
            "sampled_count": len(files),
            "sources": sources,
            "total_size": total_size,
            "latest_modified": datetime.fromtimestamp(newest_mtime).isoformat() if newest_mtime else "",
        }
    try:
        index_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        _write_neural_map_data()
    except Exception:
        pass


def generate_vault_groups():
    """Generate color-coded group mapping for all vault categories (vault_groups.json).
    Assigns OKLCH colors based on semantic group + note count."""
    structure = scan_visual_vault_structure()
    if not structure:
        return

    PREFIX_GROUPS = [
        # Ordem importa: termos especificos antes dos genericos.
        (["auto-estudo", "auto_study"], "Auto-estudo", 260),
        (["estudo", "aprendizado", "books"], "Estudo", 260),

        (["cannabis"], "Cannabis", 140),
        (["cultivo", "cultivo_indoor", "aeropon", "aquapon", "ppfd", "vpd", "jardinagem", "solo_vivo", "nutrientes_plantas", "pragas", "botanica", "ecologia"], "Cultivo_Agro", 120),
        (["hidroponia", "hydropon"], "Hidroponia", 100),
        (["biologia", "biology", "bacteria", "fungi", "microbiologia"], "Biologia", 200),
        (["saude", "health", "nutricao", "exercicios", "sono", "neurociencia"], "Saude", 200),

        (["imob", "imov", "corretor", "real_estate"], "Imobiliario", 30),
        (["crm", "funis_vendas", "facebook_ads", "google_ads", "marketing_ads", "10_marketing_ads", "seo_local"], "Marketing_Vendas", 15),
        (["financas", "finance", "currenc", "market_price", "mortgage", "economia", "investimentos"], "Financas", 45),

        (["05_tecnologia", "tecnologia", "tech"], "Tecnologia", 220),
        (["ia_automacoes", "inteligencia_artificial", "automacoes", "automation", "obsidian", "knowledge_management", "memoria", "pesquisa", "23_pesquisas"], "IA_Automacoes", 225),
        (["programacao", "programming", "python", "javascript", "code", "software"], "Programacao", 235),
        (["hardware", "windows_pc", "redes", "network"], "Hardware_Redes", 215),
        (["seguranca", "privacidade", "security", "privacy"], "Seguranca_Privacidade", 20),

        (["game_design", "game", "jogo", "brawlhalla", "minecraft", "task_bar_hero"], "Jogos", 320),
        (["audio", "voz_audio", "spotify", "musica", "19_musica"], "Audio_Musica", 165),
        (["visao_computacional", "braille", "acessibilidade"], "Acessibilidade_Visao", 185),
        (["receitas", "recipes", "food", "culinaria", "fermentacao"], "Receitas", 290),

        (["viagem", "viagens", "travel", "attractions", "locations", "locais", "20_viagens", "geografia", "clima"], "Viagens_Locais", 80),
        (["cultura", "18_cultura", "cinema", "literatura", "historia", "filosofia", "psicologia", "linguagem"], "Cultura_Humanas", 160),
        (["astronomia", "ciencia", "fisica", "quimica", "matematica", "calculos"], "Ciencias_Exatas", 55),
        (["rotinas", "21_rotinas", "habitos", "produtividade", "trabalho"], "Rotinas_Produtividade", 75),
        (["projetos", "24_projetos", "mundo_pessoal", "work", "projects", "xxxx", "yyyy", "zzzz"], "Projetos_Pessoal", 50),

        (["comandos_jarvis", "02_comandos_jarvis", "sistema", "30_sistema", "archive", "90_archive", "inbox", "01_inbox"], "Sistema_Arquivo", 345),
        (["dicionario", "22_dicionario", "dictionary", "vocab", "formulas"], "Cerebro", 180),
        (["cerebro", "00_cerebro", "_indice", "emotions", "identity", "preferen", "skill", "relatio", "routine", "notes", "wishes"], "Cerebro", 180),
    ]
    def find_group(name):
        nl = name.lower()
        for prefixes, label, hue in PREFIX_GROUPS:
            for p in prefixes:
                if p.lower() in nl:
                    return label, hue
        return "Outros", 0

    groups = {}
    used_hues = set()
    for i, (cat, count) in enumerate(sorted(structure.items())):
        label, base_hue = find_group(cat)
        variation = (i * 17.3) % 25 - 12.5
        hue = (base_hue + variation) % 360
        while round(hue, 1) in used_hues:
            hue = (hue + 3.7) % 360
        used_hues.add(round(hue, 1))

        if count > 500:
            chroma, lightness = 0.18, 62
        elif count > 100:
            chroma, lightness = 0.15, 58
        elif count > 20:
            chroma, lightness = 0.12, 54
        elif count > 5:
            chroma, lightness = 0.10, 52
        else:
            chroma, lightness = 0.08, 50
        if label == "Cerebro":
            chroma, lightness = 0.14, 60
        if count <= 2:
            chroma = max(chroma, 0.10)

        groups[cat] = {
            "group": label,
            "count": count,
            "oklch": f"oklch({lightness}% {chroma} {round(hue,1)})",
            "hue": round(hue, 1),
        }

    group_agg = {}
    for cat, info in groups.items():
        g = info["group"]
        if g not in group_agg:
            group_agg[g] = {"categories": [], "total": 0}
        group_agg[g]["categories"].append(cat)
        group_agg[g]["total"] += info["count"]

    output = {
        "updated": datetime.now().isoformat(),
        "total": sum(v["count"] for v in groups.values()),
        "total_categories": len(groups),
        "groups": dict(sorted(group_agg.items())),
        "categories": groups,
    }
    path = BASE_DIR / "memory" / "vault_groups.json"
    try:
        path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        _write_neural_map_data()
    except Exception:
        pass


def _write_neural_map_data() -> None:
    """Write JS globals so memory_map.html works when opened directly as file://."""
    index_path = BASE_DIR / "memory" / "vault_index.json"
    groups_path = BASE_DIR / "memory" / "vault_groups.json"
    data_path = BASE_DIR / "memory" / "neural_map_data.js"
    try:
        index_data = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else None
    except Exception:
        index_data = None
    try:
        groups_data = json.loads(groups_path.read_text(encoding="utf-8")) if groups_path.exists() else None
    except Exception:
        groups_data = None
    payload = (
        "window.JARVIS_VAULT_INDEX = "
        + json.dumps(index_data, ensure_ascii=False)
        + ";\nwindow.JARVIS_VAULT_GROUPS = "
        + json.dumps(groups_data, ensure_ascii=False)
        + ";\n"
    )
    data_path.write_text(payload, encoding="utf-8")


def load_obsidian_categories() -> dict[str, list[dict]]:
    """Load all Obsidian notes organized by category folder across all vaults.
    Returns {folder: [{title, path, snippet}, ...]}"""
    vaults = _existing_vaults()
    if not vaults:
        return {}
    result: dict[str, list[dict]] = {}
    seen: set[str] = set()
    for vault in vaults:
        for folder in sorted(vault.iterdir()):
            if not folder.is_dir() or folder.name in EXCLUDED_DIRS:
                continue
            notes = []
            for md_file in sorted(folder.glob("**/*.md")):
                if md_file.stem in seen:
                    continue
                seen.add(md_file.stem)
                try:
                    text = md_file.read_text(encoding="utf-8", errors="ignore")
                    text = _strip_yaml_frontmatter(text)
                    first_line = text.strip().split("\n")[0] if text.strip() else md_file.stem
                    first_line = first_line.strip("# *").strip()
                    notes.append({
                        "title": first_line or md_file.stem,
                        "path": str(md_file),
                        "snippet": text.strip()[:200],
                    })
                except Exception:
                    pass
            if notes:
                key = folder.name
                if key in result:
                    result[key].extend(notes)
                    result[key] = result[key][:50]
                else:
                    result[key] = notes[:50]
    return dict(sorted(result.items()))


def _empty_memory() -> dict:
    return {
        "identity":      {},
        "preferences":   {},
        "projects":      {},
        "relationships": {},
        "wishes":        {},
        "notes":         {},
    }

def load_memory() -> dict:
    if _memory_cache_valid() and not _MEMORY_CACHE["dirty"]:
        return _MEMORY_CACHE["data"]
    if not MEMORY_PATH.exists():
        return _empty_memory()
    with _lock:
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _empty_memory()
                for key in base:
                    if key not in data:
                        data[key] = {}
                _MEMORY_CACHE["data"] = data
                _MEMORY_CACHE["ts"] = time.time()
                _MEMORY_CACHE["dirty"] = False
                return data
            return _empty_memory()
        except Exception as e:
            print(f"[Memory] ⚠️ Load error: {e}")
            return _empty_memory()

def _all_entries(memory: dict) -> list[tuple]:
    entries = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            if isinstance(entry, dict) and "value" in entry:
                entries.append((cat, key, entry))
    return entries


def _trim_to_limit(memory: dict) -> dict:
    if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
        return memory
    entries = _all_entries(memory)
    entries.sort(key=lambda t: t[2].get("updated", "0000-00-00"))
    for cat, key, _ in entries:
        if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
            break
        del memory[cat][key]
        print(f"[Memory] 🗑️  Trimmed {cat}/{key}")
    return memory

def save_memory(memory: dict) -> None:
    if not isinstance(memory, dict):
        return
    memory = _trim_to_limit(memory)
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    # Update in-memory cache
    _MEMORY_CACHE["data"] = memory
    _MEMORY_CACHE["ts"] = time.time()
    _MEMORY_CACHE["dirty"] = False
    # Notify neural map
    _notify_neural_update()
    # Refresh vault cache (mark stale)
    _VAULT_CACHE["ts"] = 0
    # Refresh vault index + color groups without blocking interaction startup.
    _refresh_vault_artifacts_async()


def _notify_neural_update():
    """Notify neural map of memory update via activity log"""
    activity_path = NEURAL_ACTIVITY
    activity_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        activity = {}
        if activity_path.exists():
            with open(activity_path, 'r', encoding='utf-8') as f:
                activity = json.load(f)

        # Add new pulse
        pulse = {
            "timestamp": datetime.now().isoformat(),
            "type": "memory_update"
        }

        if "pulses" not in activity:
            activity["pulses"] = []
        activity["pulses"].append(pulse)

        # Keep only last 50 pulses
        if len(activity["pulses"]) > 50:
            activity["pulses"] = activity["pulses"][-50:]

        with open(activity_path, 'w', encoding='utf-8') as f:
            json.dump(activity, f, indent=2)
    except Exception as e:
        print(f"[Neural] ⚠️ Failed to notify: {e}")


def record_conversation_entry(text: str) -> None:
    """Record conversation for neural pattern analysis"""
    activity_path = NEURAL_ACTIVITY
    activity_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        activity = {}
        if activity_path.exists():
            with open(activity_path, 'r', encoding='utf-8') as f:
                activity = json.load(f)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "text": text[:500],
            "type": "conversation"
        }

        if "conversations" not in activity:
            activity["conversations"] = []
        activity["conversations"].append(entry)

        if len(activity["conversations"]) > 100:
            activity["conversations"] = activity["conversations"][-100:]

        with open(activity_path, 'w', encoding='utf-8') as f:
            json.dump(activity, f, indent=2)
    except Exception as e:
        print(f"[Neural] ⚠️ Failed to record: {e}")


def log_interaction(action: str, details: str) -> None:
    """Log any Jarvis interaction for pattern learning"""
    activity_path = NEURAL_ACTIVITY
    activity_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        activity = {}
        if activity_path.exists():
            with open(activity_path, 'r', encoding='utf-8') as f:
                activity = json.load(f)

        interaction = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details[:200]
        }

        if "interactions" not in activity:
            activity["interactions"] = []
        activity["interactions"].append(interaction)

        if len(activity["interactions"]) > 200:
            activity["interactions"] = activity["interactions"][-200:]

        with open(activity_path, 'w', encoding='utf-8') as f:
            json.dump(activity, f, indent=2)
    except Exception:
        pass


def _truncate_value(val: str) -> str:
    if isinstance(val, str) and len(val) > MAX_VALUE_LENGTH:
        return val[:MAX_VALUE_LENGTH].rstrip() + "…"
    return val


def _recursive_update(target: dict, updates: dict) -> bool:
    changed = False
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value):
                changed = True
        else:
            new_val  = _truncate_value(str(value["value"] if isinstance(value, dict) else value))
            entry    = {"value": new_val, "updated": datetime.now().strftime("%Y-%m-%d")}
            existing = target.get(key, {})
            if not isinstance(existing, dict) or existing.get("value") != new_val:
                target[key] = entry
                changed = True
    return changed


def update_memory(memory_update: dict) -> dict:
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory()
    memory = load_memory()
    if _recursive_update(memory, memory_update):
        save_memory(memory)
        print(f"[Memory] 💾 Saved: {list(memory_update.keys())}")
    return memory

def format_memory_for_prompt(memory: dict | None = None, include_vault: bool = True) -> str:
    if memory is None:
        memory = load_memory()
    if not memory:
        return ""

    lines = []

    identity  = memory.get("identity", {})
    id_fields = ["name", "age", "birthday", "city", "job", "language", "school", "nationality"]
    for field in id_fields:
        entry = identity.get(field)
        if entry:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"{field.title()}: {val}")
    for key, entry in identity.items():
        if key in id_fields:
            continue
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val:
            lines.append(f"{key.replace('_', ' ').title()}: {val}")

    prefs = memory.get("preferences", {})
    if prefs:
        lines.append("")
        lines.append("Preferences:")
        for key, entry in list(prefs.items())[:15]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    projects = memory.get("projects", {})
    if projects:
        lines.append("")
        lines.append("Active Projects / Goals:")
        for key, entry in list(projects.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    rels = memory.get("relationships", {})
    if rels:
        lines.append("")
        lines.append("People in their life:")
        for key, entry in list(rels.items())[:10]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    wishes = memory.get("wishes", {})
    if wishes:
        lines.append("")
        lines.append("Wishes / Plans / Wants:")
        for key, entry in list(wishes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    notes = memory.get("notes", {})
    if notes:
        lines.append("")
        lines.append("Other notes:")
        for key, entry in list(notes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key}: {val}")

    if not lines:
        return ""

    header = "[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]\n"
    result = header + "\n".join(lines)
    if len(result) > 2000:
        result = result[:1997] + "…"

    result += "\n"

    # Append Obsidian vault context
    if include_vault:
        vault_ctx = load_obsidian_context(max_chars=3000)
        if vault_ctx:
            result += vault_ctx + "\n"

    return result

def remember(key: str, value: str, category: str = "notes") -> str:
    valid = {"identity", "preferences", "projects", "relationships", "wishes", "notes"}
    if category not in valid:
        category = "notes"
    update_memory({category: {key: {"value": value}}})
    return f"Remembered: {category}/{key} = {value}"


def forget(key: str, category: str = "notes") -> str:
    memory = load_memory()
    cat    = memory.get(category, {})
    if key in cat:
        del cat[key]
        memory[category] = cat
        save_memory(memory)
        return f"Forgotten: {category}/{key}"
    return f"Not found: {category}/{key}"


forget_memory = forget



