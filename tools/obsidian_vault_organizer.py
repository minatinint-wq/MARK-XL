from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRAIN_ROOT = Path(r"D:\xxxx_memory")
REPORT_PATH = PROJECT_ROOT / "memory" / "obsidian_organization_plan.json"

EXCLUDED_DIRS = {
    ".git",
    ".obsidian",
    "__pycache__",
    "_archive",
    "brains",
    "cache",
    "conversations",
    "data",
    "habits",
    "learning",
    "obsidian_data",
    "profile",
}

CANONICAL_MAP: dict[str, tuple[str, str]] = {
    "_indice": ("Cerebro", "indice"),
    "aeroponia": ("Cultivo", "aeroponia"),
    "aeroponics": ("Cultivo", "aeroponia"),
    "aprendizado": ("Estudo", "aprendizado"),
    "aquaponia": ("Cultivo", "aquaponia"),
    "aquaponics_fish": ("Cultivo", "aquaponia/fish"),
    "aquaponics_plants": ("Cultivo", "aquaponia/plants"),
    "attractions": ("Viagem", "atracoes"),
    "auto_study": ("Auto-estudo", "auto_study"),
    "bacteria": ("Biologia", "bacteria"),
    "biology": ("Biologia", "biology"),
    "books": ("Estudo", "books"),
    "cannabis": ("Cannabis", "geral"),
    "cannabis_equipment": ("Cannabis", "equipment"),
    "cannabis_extraction": ("Cannabis", "extraction"),
    "cannabis_genetics": ("Cannabis", "genetics"),
    "cannabis_growing": ("Cannabis", "growing"),
    "cannabis_medicine": ("Cannabis", "medicine"),
    "cannabis_nutrients": ("Cannabis", "nutrients"),
    "cannabis_problems": ("Cannabis", "problems"),
    "cannabis_techniques": ("Cannabis", "techniques"),
    "corretor": ("Imobiliario", "corretor/geral"),
    "corretor_atendimento": ("Imobiliario", "corretor/atendimento"),
    "corretor_avaliacao": ("Imobiliario", "corretor/avaliacao"),
    "corretor_financiamento": ("Imobiliario", "corretor/financiamento"),
    "corretor_gestao_leads": ("Imobiliario", "corretor/gestao_leads"),
    "corretor_legal": ("Imobiliario", "corretor/legal"),
    "corretor_mercado": ("Imobiliario", "corretor/mercado"),
    "corretor_venda_tecnicas": ("Imobiliario", "corretor/venda_tecnicas"),
    "currencies": ("Financas", "currencies"),
    "dictionary": ("Cerebro", "dictionary"),
    "emotions": ("Cerebro", "emotions"),
    "entertainment": ("Cultura", "entertainment"),
    "finance": ("Financas", "finance"),
    "financas": ("Financas", "geral"),
    "food": ("Receitas", "food"),
    "formulas": ("Estudo", "formulas"),
    "fungi": ("Biologia", "fungi"),
    "health": ("Saude", "health"),
    "hidroponia": ("Hidroponia", "geral"),
    "hydroponics_systems": ("Hidroponia", "systems"),
    "identity": ("Cerebro", "identity"),
    "imobiliario": ("Imobiliario", "geral"),
    "imobiliary": ("Imobiliario", "imobiliary"),
    "locations": ("Viagem", "locations"),
    "market_prices": ("Financas", "market_prices"),
    "mortgage": ("Imobiliario", "mortgage"),
    "music": ("Cultura", "music"),
    "notes": ("Cerebro", "notes"),
    "nutrients": ("Biologia", "nutrients"),
    "ppfd": ("Cultivo", "ppfd"),
    "preferences": ("Cerebro", "preferences"),
    "projects": ("Mundo_Pessoal", "projects"),
    "real_estate": ("Imobiliario", "real_estate"),
    "receitas": ("Receitas", "geral"),
    "recipes": ("Receitas", "recipes"),
    "relationships": ("Cerebro", "relationships"),
    "routines": ("Cerebro", "routines"),
    "saude": ("Saude", "geral"),
    "skills": ("Cerebro", "skills"),
    "sports": ("Cultura", "sports"),
    "tech": ("Tecnologia", "tech"),
    "technologies": ("Tecnologia", "technologies"),
    "techniques": ("Tecnologia", "techniques"),
    "tecnicas": ("Tecnologia", "tecnicas"),
    "travel": ("Viagem", "travel"),
    "viagem": ("Viagem", "geral"),
    "vocabulary": ("Cerebro", "vocabulary"),
    "vpd": ("Cultivo", "vpd"),
    "wishes": ("Cerebro", "wishes"),
    "work": ("Mundo_Pessoal", "work"),
    "XXXX": ("Mundo_Pessoal", "XXXX"),
    "YYYY": ("Mundo_Pessoal", "YYYY"),
    "ZZZZ": ("Mundo_Pessoal", "ZZZZ"),
    "Sem titulo": ("Outros", "sem_titulo"),
    "Sem título": ("Outros", "sem_titulo"),
}

CANONICAL_NAMES = {
    "Auto-estudo",
    "Biologia",
    "Cannabis",
    "Cerebro",
    "Cultivo",
    "Cultura",
    "Estudo",
    "Financas",
    "Hidroponia",
    "Imobiliario",
    "Mundo_Pessoal",
    "Outros",
    "Receitas",
    "Saude",
    "Tecnologia",
    "Viagem",
}


def _count_files(path: Path, pattern: str = "*") -> int:
    try:
        return sum(1 for item in path.rglob(pattern) if item.is_file())
    except Exception:
        return 0


def _count_markdown(path: Path) -> int:
    return _count_files(path, "*.md")


def _is_effectively_empty(path: Path) -> bool:
    try:
        return not any(path.iterdir())
    except Exception:
        return False


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for index in range(2, 10000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"No unique path available for {path}")


def _target_inside_source(source: Path, target: Path) -> bool:
    source_text = str(source.resolve()).rstrip("\\/").lower()
    target_text = str(target).rstrip("\\/").lower()
    return target_text.startswith(source_text + "\\") or target_text.startswith(source_text + "/")


def _merge_move_dir(source: Path, target: Path, manifest_ops: list[dict[str, Any]]) -> None:
    if _target_inside_source(source, target):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        temp = _unique_path(source.parent / "_archive" / "organizer_tmp" / stamp / source.name)
        temp.mkdir(parents=True, exist_ok=True)
        for child in list(source.iterdir()):
            dest = _unique_path(temp / child.name)
            shutil.move(str(child), str(dest))
            manifest_ops.append({"kind": "stage_case_move", "from": str(child), "to": str(dest)})
        try:
            source.rmdir()
            manifest_ops.append({"kind": "remove_empty_dir", "path": str(source)})
        except OSError:
            pass

        target.mkdir(parents=True, exist_ok=True)
        for child in list(temp.iterdir()):
            dest = _unique_path(target / child.name)
            shutil.move(str(child), str(dest))
            manifest_ops.append({"kind": "move", "from": str(child), "to": str(dest)})
        try:
            temp.rmdir()
        except OSError:
            pass
        return

    target.mkdir(parents=True, exist_ok=True)
    for child in list(source.iterdir()):
        dest = _unique_path(target / child.name)
        shutil.move(str(child), str(dest))
        manifest_ops.append({"kind": "move", "from": str(child), "to": str(dest)})
    try:
        source.rmdir()
        manifest_ops.append({"kind": "remove_empty_dir", "path": str(source)})
    except OSError:
        pass


def _archive_empty_dir(source: Path, archive_root: Path, manifest_ops: list[dict[str, Any]]) -> None:
    target = _unique_path(archive_root / source.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    manifest_ops.append({"kind": "archive_empty_dir", "from": str(source), "to": str(target)})


def _delete_empty_dir(source: Path, manifest_ops: list[dict[str, Any]]) -> None:
    source.rmdir()
    manifest_ops.append({"kind": "delete_empty_dir", "path": str(source)})


def _prune_empty_dirs(root: Path, manifest_ops: list[dict[str, Any]]) -> None:
    if not root.exists() or not root.is_dir():
        return
    for path in sorted([p for p in root.rglob("*") if p.is_dir()], key=lambda p: len(p.parts), reverse=True):
        try:
            path.rmdir()
            manifest_ops.append({"kind": "prune_empty_dir", "path": str(path)})
        except OSError:
            pass
    try:
        root.rmdir()
        manifest_ops.append({"kind": "prune_empty_dir", "path": str(root)})
    except OSError:
        pass


def build_plan(root: Path = BRAIN_ROOT) -> dict[str, Any]:
    if not root.exists():
        raise FileNotFoundError(root)

    folders: list[dict[str, Any]] = []
    moves: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for folder in sorted([item for item in root.iterdir() if item.is_dir()], key=lambda p: p.name.lower()):
        name = folder.name
        markdown = _count_markdown(folder)
        files = _count_files(folder)
        folders.append({
            "name": name,
            "path": str(folder),
            "markdown": markdown,
            "files": files,
            "empty": _is_effectively_empty(folder),
        })

        if name in EXCLUDED_DIRS:
            skipped.append({"name": name, "reason": "excluded"})
            continue
        if name in CANONICAL_NAMES:
            skipped.append({"name": name, "reason": "canonical"})
            continue

        mapping = CANONICAL_MAP.get(name)
        if not mapping:
            skipped.append({"name": name, "reason": "no_mapping"})
            continue

        canonical, subfolder = mapping
        target = root / canonical / Path(subfolder)
        action = "archive_empty" if _is_effectively_empty(folder) else "merge_move"
        moves.append({
            "source": str(folder),
            "target": str(target),
            "canonical": canonical,
            "subfolder": subfolder,
            "action": action,
            "markdown": markdown,
            "files": files,
        })

    by_canonical: dict[str, dict[str, int]] = {}
    for move in moves:
        stats = by_canonical.setdefault(move["canonical"], {"folders": 0, "markdown": 0, "files": 0})
        stats["folders"] += 1
        stats["markdown"] += int(move["markdown"])
        stats["files"] += int(move["files"])

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "total_top_level_folders": len(folders),
        "total_markdown": sum(int(item["markdown"]) for item in folders),
        "folders": folders,
        "moves": moves,
        "skipped": skipped,
        "summary_by_canonical": by_canonical,
        "safety": {
            "touches_project_scripts": False,
            "excluded_dirs": sorted(EXCLUDED_DIRS),
            "apply_scope": "D:/xxxx_memory top-level aliases only",
        },
    }


def write_report(plan: dict[str, Any], path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def apply_plan(plan: dict[str, Any], root: Path = BRAIN_ROOT) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest_path = root / "_archive" / "organization_manifests" / f"{stamp}.json"
    ops: list[dict[str, Any]] = []

    for move in plan.get("moves", []):
        source = Path(move["source"])
        target = Path(move["target"])
        if not source.exists() or not source.is_dir():
            ops.append({"kind": "skip_missing", "path": str(source)})
            continue
        if source.name in EXCLUDED_DIRS or source.name in CANONICAL_NAMES:
            ops.append({"kind": "skip_protected", "path": str(source)})
            continue
        if move.get("action") == "archive_empty" and _is_effectively_empty(source):
            _delete_empty_dir(source, ops)
        else:
            _merge_move_dir(source, target, ops)

    _prune_empty_dirs(root / "_archive" / "empty_aliases", ops)
    _prune_empty_dirs(root / "_archive" / "organizer_tmp", ops)

    manifest = {
        "applied": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "plan_generated": plan.get("generated"),
        "operations": ops,
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
    parser = argparse.ArgumentParser(description="Safe Obsidian vault organizer for D:/xxxx_memory.")
    parser.add_argument("--root", default=str(BRAIN_ROOT), help="Vault brain root. Default: D:/xxxx_memory")
    parser.add_argument("--apply", action="store_true", help="Apply the planned moves. Default only writes a report.")
    parser.add_argument("--refresh-index", action="store_true", help="Refresh MARK-XL vault indexes after planning/apply.")
    args = parser.parse_args()

    root = Path(args.root)
    plan = build_plan(root)
    write_report(plan)

    print(f"Root: {plan['root']}")
    print(f"Top-level folders: {plan['total_top_level_folders']}")
    print(f"Markdown files under root: {plan['total_markdown']}")
    print(f"Planned folder operations: {len(plan['moves'])}")
    for canonical, stats in sorted(plan["summary_by_canonical"].items()):
        print(f"- {canonical}: {stats['folders']} folder(s), {stats['markdown']} md, {stats['files']} file(s)")
    print(f"Report: {REPORT_PATH}")

    if args.apply:
        manifest = apply_plan(plan, root=root)
        print(f"Applied operations: {len(manifest['operations'])}")
        print(f"Manifest: {root / '_archive' / 'organization_manifests'}")

    if args.refresh_index:
        refresh_indexes()
        print("Indexes refreshed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
