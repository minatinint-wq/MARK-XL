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
REPORT_PATH = PROJECT_ROOT / "memory" / "obsidian_balanced_restore_plan.json"

RESTORE_MAP: dict[str, str] = {
    "10_Knowledge/Auto-estudo": "Auto-estudo",
    "10_Knowledge/Biologia": "Biologia",
    "10_Knowledge/Cannabis": "Cannabis",
    "10_Knowledge/Cerebro": "Cerebro",
    "10_Knowledge/Cultivo": "Cultivo",
    "10_Knowledge/Cultura": "Cultura",
    "10_Knowledge/Estudo": "Estudo",
    "10_Knowledge/Financas": "Financas",
    "10_Knowledge/Hidroponia": "Hidroponia",
    "10_Knowledge/Imobiliario": "Imobiliario",
    "10_Knowledge/Receitas": "Receitas",
    "10_Knowledge/Saude": "Saude",
    "10_Knowledge/Tecnologia": "Tecnologia",
    "10_Knowledge/Viagem": "Viagem",
    "20_Pessoal/Mundo_Pessoal": "Mundo_Pessoal",
}

EMPTY_BUCKETS = ["00_Inbox", "10_Knowledge", "20_Pessoal"]


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


def _count_md(path: Path) -> int:
    try:
        return sum(1 for item in path.rglob("*.md") if item.is_file())
    except Exception:
        return 0


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


def build_plan(root: Path = BRAIN_ROOT) -> dict[str, Any]:
    moves = []
    skipped = []
    for source_rel, target_rel in RESTORE_MAP.items():
        source = root / source_rel
        target = root / target_rel
        if not source.exists():
            skipped.append({"source": str(source), "reason": "missing"})
            continue
        moves.append({
            "source": str(source),
            "target": str(target),
            "markdown": _count_md(source),
        })
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "moves": moves,
        "skipped": skipped,
        "empty_buckets": EMPTY_BUCKETS,
    }


def write_report(plan: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def apply_plan(plan: dict[str, Any], root: Path = BRAIN_ROOT) -> dict[str, Any]:
    ops: list[dict[str, Any]] = []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest_path = root / "90_Archive" / "balanced_restore_manifests" / f"{stamp}.json"

    for move in plan["moves"]:
        source = Path(move["source"])
        target = Path(move["target"])
        if not source.exists():
            ops.append({"kind": "skip_missing", "path": str(source)})
            continue
        if not _is_under(source, root) or not _is_under(target, root):
            raise ValueError(f"Unsafe move: {source} -> {target}")
        _merge_dir(source, target, ops)

    for rel in plan.get("empty_buckets", []):
        bucket = root / rel
        if not bucket.exists():
            continue
        if not _is_under(bucket, root):
            raise ValueError(f"Unsafe bucket: {bucket}")
        try:
            bucket.rmdir()
            ops.append({"kind": "remove_empty_dir", "path": str(bucket)})
        except OSError:
            ops.append({"kind": "keep_non_empty_dir", "path": str(bucket)})

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
    parser = argparse.ArgumentParser(description="Restore a more navigable Obsidian root while keeping system/archive buckets hidden.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()

    plan = build_plan()
    write_report(plan)
    print(f"Moves: {len(plan['moves'])}")
    for move in plan["moves"]:
        print(f"- {Path(move['source']).relative_to(BRAIN_ROOT)} ({move['markdown']} md) -> {Path(move['target']).relative_to(BRAIN_ROOT)}")
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
