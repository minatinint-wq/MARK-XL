from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRAIN_ROOT = Path(r"D:\xxxx_memory")
LEARNED_ROOT = BRAIN_ROOT / "30_Sistema" / "obsidian_data" / "xxxx-vault" / "YYYY" / "learned"
if not LEARNED_ROOT.exists():
    LEARNED_ROOT = BRAIN_ROOT / "obsidian_data" / "xxxx-vault" / "YYYY" / "learned"
COMPACT_ROOT = BRAIN_ROOT / "00_Cerebro" / "Cerebro" / "knowledge_compact"
if not COMPACT_ROOT.parent.exists():
    COMPACT_ROOT = BRAIN_ROOT / "Cerebro" / "knowledge_compact"
REPORT_PATH = PROJECT_ROOT / "memory" / "knowledge_compaction_plan.json"

PLACEHOLDER_PATTERNS = (
    r"\[Espa[cç]o para defini[cç][aã]o",
    r"\[Defini[cç][aã]o e explica[cç][aã]o",
    r"\[Descri[cç][aã]o\]",
    r"\[T[ií]tulo\]",
    r"\[Param\s*\d+\]",
    r"\[Valor\]",
    r"\[Como aplicar",
    r"-\s*Ponto\s+1\b",
    r"-\s*Ponto\s+2\b",
    r"-\s*Ponto\s+3\b",
)

GENERATED_MARKERS = (
    "Jarvis v4.0",
    "Neural Connection",
    "Tópico de vendas imobiliárias",
    "Topico de vendas imobiliarias",
    "Tópico de cultivo indoor",
    "Topico de cultivo indoor",
)

COMPACT_TARGETS = {
    "imoveis": "Imobiliario",
    "tech": "Tecnologia",
}


def _strip_frontmatter(text: str) -> tuple[dict[str, str], str]:
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


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        clean = line.strip()
        if clean.startswith("# "):
            return clean[2:].strip() or fallback
    return fallback


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return slug[:90] or "knowledge"


def _placeholder_score(text: str) -> int:
    return sum(1 for pattern in PLACEHOLDER_PATTERNS if re.search(pattern, text, re.IGNORECASE))


def _generated_score(text: str) -> int:
    return sum(1 for marker in GENERATED_MARKERS if marker.lower() in text.lower())


def _extract_category(text: str, metadata: dict[str, str], folder: str) -> str:
    if metadata.get("category"):
        return metadata["category"].strip()
    if metadata.get("folder"):
        return metadata["folder"].strip()
    match = re.search(r"Categoria:\s*([A-Za-zÀ-ÿ0-9_-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if "cultivo indoor" in text.lower():
        tags = metadata.get("tags", "")
        if "ambiente" in tags:
            return "cultivo-ambiente"
        if "cannabis" in tags:
            return "cultivo-cannabis"
        return "cultivo-indoor"
    return folder


def _compactable(path: Path, text: str) -> tuple[bool, str, int, int]:
    placeholder = _placeholder_score(text)
    generated = _generated_score(text)
    body_len = len(re.sub(r"\s+", "", text))
    if generated and placeholder >= 3:
        return True, "generated-placeholder", placeholder, generated
    if generated >= 2 and placeholder >= 2 and body_len < 9000:
        return True, "generated-light-template", placeholder, generated
    if path.parent.name == "imoveis" and placeholder >= 4:
        return True, "imoveis-placeholder", placeholder, generated
    return False, "keep", placeholder, generated


def _note_entry(path: Path, root: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    metadata, body = _strip_frontmatter(raw)
    title = _title(body, path.stem)
    compactable, reason, placeholder, generated = _compactable(path, raw)
    category = _extract_category(raw, metadata, path.parent.name)
    snippet = re.sub(r"\s+", " ", body).strip()[:420]
    try:
        rel = str(path.resolve().relative_to(root.resolve()))
    except Exception:
        rel = path.name
    return {
        "path": str(path),
        "relative_path": rel,
        "folder": path.parent.name,
        "name": path.name,
        "title": title,
        "category": category,
        "compactable": compactable,
        "reason": reason,
        "placeholder_score": placeholder,
        "generated_score": generated,
        "size": path.stat().st_size,
        "snippet": snippet,
        "tags": metadata.get("tags", ""),
        "type": metadata.get("type", ""),
    }


def scan() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for folder_name in sorted(COMPACT_TARGETS):
        folder = LEARNED_ROOT / folder_name
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md"), key=lambda p: p.name.lower()):
            try:
                entries.append(_note_entry(path, LEARNED_ROOT))
            except Exception as exc:
                entries.append({
                    "path": str(path),
                    "folder": folder_name,
                    "compactable": False,
                    "reason": f"read-error: {exc}",
                })

    compactable = [entry for entry in entries if entry.get("compactable")]
    by_folder = Counter(entry["folder"] for entry in entries)
    compact_by_folder = Counter(entry["folder"] for entry in compactable)
    compact_by_reason = Counter(entry["reason"] for entry in compactable)

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "learned_root": str(LEARNED_ROOT),
        "compact_root": str(COMPACT_ROOT),
        "total_scanned": len(entries),
        "total_compactable": len(compactable),
        "by_folder": dict(by_folder),
        "compact_by_folder": dict(compact_by_folder),
        "compact_by_reason": dict(compact_by_reason),
        "entries": entries,
    }


def write_report(plan: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def _compact_markdown(folder: str, canonical: str, entries: list[dict[str, Any]], stamp: str) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[str(entry.get("category") or folder)].append(entry)

    lines = [
        "---",
        "type: knowledge-compact",
        f"source-folder: {folder}",
        f"canonical-domain: {canonical}",
        f"generated: {datetime.now().isoformat(timespec='seconds')}",
        f"compacted-count: {len(entries)}",
        "tags: [knowledge-compact, neural, optimized-reading]",
        "---",
        "",
        f"# Knowledge Compact - {canonical}",
        "",
        f"Este hub substitui {len(entries)} notas geradas/template na leitura do JARVIS.",
        "As notas brutas foram movidas para `_archive/compacted_notes` e ficam fora do índice neural rápido.",
        "",
        "## Índice Rápido",
        "",
    ]
    for category, items in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0].lower())):
        lines.append(f"### {category}")
        for entry in sorted(items, key=lambda item: item["title"].lower()):
            title = entry["title"].strip("# ").strip()
            rel = entry.get("archive_relative_path") or entry["relative_path"]
            tags = f" | tags: {entry['tags']}" if entry.get("tags") else ""
            lines.append(f"- **{title}** (`{Path(entry['name']).stem}`) - {entry['reason']}{tags}. Fonte: `{rel}`")
        lines.append("")

    lines.extend(
        [
            "## Termos Para Busca",
            "",
            " ".join(sorted({entry["title"] for entry in entries})),
            "",
            "## Manifesto",
            "",
            f"- Lote: `{stamp}`",
            f"- Pasta original: `{folder}`",
            f"- Total compactado: `{len(entries)}`",
            "",
        ]
    )
    return "\n".join(lines)


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 10000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(path)


def apply(plan: dict[str, Any]) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_root = BRAIN_ROOT / "90_Archive" / "compacted_notes" / stamp
    manifest_path = BRAIN_ROOT / "90_Archive" / "compaction_manifests" / f"{stamp}.json"
    operations: list[dict[str, Any]] = []

    compactable = [entry for entry in plan["entries"] if entry.get("compactable")]
    by_folder: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in compactable:
        by_folder[entry["folder"]].append(entry)

    COMPACT_ROOT.mkdir(parents=True, exist_ok=True)
    for folder, entries in sorted(by_folder.items()):
        canonical = COMPACT_TARGETS.get(folder, folder.title())
        folder_archive = archive_root / folder
        folder_archive.mkdir(parents=True, exist_ok=True)

        moved_entries = []
        for entry in entries:
            source = Path(entry["path"])
            if not source.exists():
                operations.append({"kind": "skip_missing", "path": str(source)})
                continue
            dest = _unique_path(folder_archive / source.name)
            shutil.move(str(source), str(dest))
            updated = dict(entry)
            try:
                updated["archive_relative_path"] = str(dest.resolve().relative_to(BRAIN_ROOT.resolve()))
            except Exception:
                updated["archive_relative_path"] = str(dest)
            moved_entries.append(updated)
            operations.append({"kind": "compact_move", "from": str(source), "to": str(dest), "reason": entry["reason"]})

        if moved_entries:
            compact_path = COMPACT_ROOT / f"{folder}-compact.md"
            compact_text = _compact_markdown(folder, canonical, moved_entries, stamp)
            compact_path.write_text(compact_text, encoding="utf-8")
            operations.append({"kind": "write_compact_hub", "path": str(compact_path), "count": len(moved_entries)})

    manifest = {
        "applied": datetime.now().isoformat(timespec="seconds"),
        "plan_generated": plan.get("generated"),
        "learned_root": str(LEARNED_ROOT),
        "archive_root": str(archive_root),
        "compact_root": str(COMPACT_ROOT),
        "operations": operations,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def refresh_indexes() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from memory.memory_manager import generate_vault_groups, generate_vault_index, generate_vault_search_index

    generate_vault_index()
    generate_vault_groups()
    generate_vault_search_index()


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact generated/template knowledge notes into fast hubs.")
    parser.add_argument("--apply", action="store_true", help="Move compactable notes to archive and write compact hubs.")
    parser.add_argument("--refresh-index", action="store_true", help="Refresh MARK-XL vault indexes after operation.")
    args = parser.parse_args()

    plan = scan()
    write_report(plan)
    print(f"Scanned: {plan['total_scanned']}")
    print(f"Compactable: {plan['total_compactable']}")
    print(f"By folder: {plan['by_folder']}")
    print(f"Compact by folder: {plan['compact_by_folder']}")
    print(f"Reasons: {plan['compact_by_reason']}")
    print(f"Report: {REPORT_PATH}")

    if args.apply:
        manifest = apply(plan)
        print(f"Operations: {len(manifest['operations'])}")
        print(f"Manifest: {BRAIN_ROOT / '90_Archive' / 'compaction_manifests'}")

    if args.refresh_index:
        refresh_indexes()
        print("Indexes refreshed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
