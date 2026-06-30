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
REPORT_PATH = PROJECT_ROOT / "memory" / "obsidian_root_simplification_plan.json"

ROOT_MAP: dict[str, str] = {
    "Auto-estudo": "10_Knowledge/Auto-estudo",
    "Biologia": "10_Knowledge/Biologia",
    "Cannabis": "10_Knowledge/Cannabis",
    "Cerebro": "10_Knowledge/Cerebro",
    "Cultivo": "10_Knowledge/Cultivo",
    "Cultura": "10_Knowledge/Cultura",
    "Estudo": "10_Knowledge/Estudo",
    "Financas": "10_Knowledge/Financas",
    "Hidroponia": "10_Knowledge/Hidroponia",
    "Imobiliario": "10_Knowledge/Imobiliario",
    "Receitas": "10_Knowledge/Receitas",
    "Saude": "10_Knowledge/Saude",
    "Tecnologia": "10_Knowledge/Tecnologia",
    "Viagem": "10_Knowledge/Viagem",
    "Mundo_Pessoal": "20_Pessoal/Mundo_Pessoal",
    "conversations": "30_Sistema/conversations",
    "data": "30_Sistema/data",
    "habits": "30_Sistema/habits",
    "profile": "30_Sistema/profile",
    "obsidian_data": "30_Sistema/obsidian_data",
    "brains": "30_Sistema/brains",
    "_archive": "90_Archive",
}

PROTECTED_ROOTS = {
    ".git",
    ".obsidian",
    "00_Inbox",
    "10_Knowledge",
    "20_Pessoal",
    "30_Sistema",
    "90_Archive",
}


def _is_under(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved_root = root.resolve()
        return resolved == resolved_root or resolved.is_relative_to(resolved_root)
    except Exception:
        return False


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


def _merge_dir(source: Path, target: Path, ops: list[dict[str, Any]]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for child in list(source.iterdir()):
        dest = _unique_path(target / child.name)
        shutil.move(str(child), str(dest))
        ops.append({"kind": "move", "from": str(child), "to": str(dest)})
    try:
        source.rmdir()
        ops.append({"kind": "remove_empty_dir", "path": str(source)})
    except OSError:
        pass


def _count_md(path: Path) -> int:
    try:
        return sum(1 for item in path.rglob("*.md") if item.is_file())
    except Exception:
        return 0


def build_plan(root: Path = BRAIN_ROOT) -> dict[str, Any]:
    moves = []
    skipped = []
    for item in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        name = item.name
        if name in PROTECTED_ROOTS:
            skipped.append({"name": name, "reason": "protected"})
            continue
        rel_target = ROOT_MAP.get(name)
        if not rel_target:
            skipped.append({"name": name, "reason": "no_mapping"})
            continue
        moves.append({
            "source": str(item),
            "target": str(root / rel_target),
            "name": name,
            "markdown": _count_md(item),
        })

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "moves": moves,
        "skipped": skipped,
        "target_roots": ["00_Inbox", "10_Knowledge", "20_Pessoal", "30_Sistema", "90_Archive"],
    }


def write_report(plan: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def apply_plan(plan: dict[str, Any], root: Path = BRAIN_ROOT) -> dict[str, Any]:
    ops: list[dict[str, Any]] = []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest_path = root / "90_Archive" / "root_simplification_manifests" / f"{stamp}.json"

    (root / "00_Inbox").mkdir(exist_ok=True)
    for move in plan["moves"]:
        source = Path(move["source"])
        target = Path(move["target"])
        if not source.exists():
            ops.append({"kind": "skip_missing", "path": str(source)})
            continue
        if not _is_under(source, root) or not _is_under(target, root):
            raise ValueError(f"Unsafe move: {source} -> {target}")
        if source.name in PROTECTED_ROOTS:
            ops.append({"kind": "skip_protected", "path": str(source)})
            continue
        _merge_dir(source, target, ops)

    manifest = {
        "applied": datetime.now().isoformat(timespec="seconds"),
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
    parser = argparse.ArgumentParser(description="Simplify D:/xxxx_memory Obsidian root into a few top-level buckets.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()

    plan = build_plan()
    write_report(plan)
    print(f"Moves: {len(plan['moves'])}")
    for move in plan["moves"]:
        print(f"- {move['name']} ({move['markdown']} md) -> {Path(move['target']).relative_to(BRAIN_ROOT)}")
    print(f"Skipped: {len(plan['skipped'])}")
    print(f"Report: {REPORT_PATH}")

    if args.apply:
        manifest = apply_plan(plan)
        print(f"Applied operations: {len(manifest['operations'])}")
    if args.refresh_index:
        refresh_indexes()
        print("Indexes refreshed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
