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
REPORT_PATH = PROJECT_ROOT / "memory" / "obsidian_taxonomy_plan.json"

TAXONOMY: dict[str, dict[str, Any]] = {
    "00_Cerebro": {
        "description": "Nucleo do Jarvis, preferencias, compactacoes, indices e auto-estudo.",
        "children": ["Cerebro", "Auto-estudo"],
    },
    "01_Negocios_Imoveis": {
        "description": "Imoveis, corretor, campanhas, financiamento, mercado e dinheiro aplicado ao trabalho.",
        "children": ["Imobiliario", "Financas"],
    },
    "02_Cultivo_Cannabis": {
        "description": "Cannabis, cultivo, hidroponia, nutrientes, equipamentos e tecnicas.",
        "children": ["Cannabis", "Cultivo", "Hidroponia"],
    },
    "03_Estudo_Tecnologia": {
        "description": "Estudo, tecnologia, programacao, formulas, tecnicas e aprendizado continuo.",
        "children": ["Estudo", "Tecnologia"],
    },
    "04_Saude_Ciencia": {
        "description": "Saude, biologia, receitas, corpo, alimentacao e conhecimento cientifico.",
        "children": ["Saude", "Biologia", "Receitas"],
    },
    "05_Vida_Cultura": {
        "description": "Vida pessoal, cultura, viagens, musica, lazer e rotinas fora do trabalho.",
        "children": ["Mundo_Pessoal", "Cultura", "Viagem"],
    },
}

ALIAS_TARGETS: dict[str, str] = {
    "cache": "90_Archive/legacy/cache",
    "cannabis_equipment": "02_Cultivo_Cannabis/Cannabis/equipment",
    "cannabis_extraction": "02_Cultivo_Cannabis/Cannabis/extraction",
    "cannabis_genetics": "02_Cultivo_Cannabis/Cannabis/genetics",
    "cannabis_growing": "02_Cultivo_Cannabis/Cannabis/growing",
    "cannabis_medicine": "02_Cultivo_Cannabis/Cannabis/medicine",
    "cannabis_nutrients": "02_Cultivo_Cannabis/Cannabis/nutrients",
    "cannabis_problems": "02_Cultivo_Cannabis/Cannabis/problems",
    "cannabis_techniques": "02_Cultivo_Cannabis/Cannabis/techniques",
    "corretor": "01_Negocios_Imoveis/Imobiliario/corretor",
    "corretor_atendimento": "01_Negocios_Imoveis/Imobiliario/corretor/atendimento",
    "corretor_avaliacao": "01_Negocios_Imoveis/Imobiliario/corretor/avaliacao",
    "corretor_financiamento": "01_Negocios_Imoveis/Imobiliario/corretor/financiamento",
    "corretor_gestao_leads": "01_Negocios_Imoveis/Imobiliario/corretor/gestao_leads",
    "corretor_legal": "01_Negocios_Imoveis/Imobiliario/corretor/legal",
    "corretor_mercado": "01_Negocios_Imoveis/Imobiliario/corretor/mercado",
    "corretor_venda_tecnicas": "01_Negocios_Imoveis/Imobiliario/corretor/venda_tecnicas",
    "currencies": "01_Negocios_Imoveis/Financas/currencies",
    "data": "30_Sistema/data",
    "dictionary": "00_Cerebro/Cerebro/dictionary",
    "emotions": "00_Cerebro/Cerebro/emotions",
    "conversations": "30_Sistema/conversations",
}

PROTECTED_ROOTS = {".git", ".obsidian", "30_Sistema", "90_Archive"}


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


def _all_targets() -> dict[str, str]:
    targets: dict[str, str] = {}
    for area, info in TAXONOMY.items():
        for child in info["children"]:
            targets[child] = f"{area}/{child}"
    targets.update(ALIAS_TARGETS)
    return targets


def build_plan(root: Path = BRAIN_ROOT) -> dict[str, Any]:
    targets = _all_targets()
    moves = []
    skipped = []
    for item in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        if item.name in PROTECTED_ROOTS or item.name in TAXONOMY:
            skipped.append({"name": item.name, "reason": "protected_or_area"})
            continue
        target_rel = targets.get(item.name)
        if not target_rel:
            skipped.append({"name": item.name, "reason": "no_taxonomy_target", "markdown": _count_md(item)})
            continue
        moves.append({
            "source": str(item),
            "target": str(root / target_rel),
            "markdown": _count_md(item),
        })

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "moves": moves,
        "skipped": skipped,
        "areas": {area: info["children"] for area, info in TAXONOMY.items()},
    }


def write_report(plan: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_area_indexes(root: Path, ops: list[dict[str, Any]]) -> None:
    for area, info in TAXONOMY.items():
        area_path = root / area
        if not area_path.exists():
            continue
        lines = [
            "---",
            "type: area-index",
            f"area: {area}",
            f"updated: {datetime.now().date().isoformat()}",
            "---",
            "",
            f"# {area}",
            "",
            str(info["description"]),
            "",
            "## Subpastas",
            "",
        ]
        for child in info["children"]:
            child_path = area_path / child
            if child_path.exists():
                lines.append(f"- [[{child}]]")
        lines.append("")
        index_path = area_path / "_index.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")
        ops.append({"kind": "write_index", "path": str(index_path)})


def apply_plan(plan: dict[str, Any], root: Path = BRAIN_ROOT) -> dict[str, Any]:
    ops: list[dict[str, Any]] = []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest_path = root / "90_Archive" / "taxonomy_manifests" / f"{stamp}.json"

    for area in TAXONOMY:
        area_path = root / area
        area_path.mkdir(parents=True, exist_ok=True)
        ops.append({"kind": "ensure_area", "path": str(area_path)})

    for move in plan["moves"]:
        source = Path(move["source"])
        target = Path(move["target"])
        if not source.exists():
            ops.append({"kind": "skip_missing", "path": str(source)})
            continue
        if not _is_under(source, root) or not _is_under(target, root):
            raise ValueError(f"Unsafe move: {source} -> {target}")
        _merge_dir(source, target, ops)

    _write_area_indexes(root, ops)

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
    parser = argparse.ArgumentParser(description="Organize the Obsidian vault into navigable knowledge areas.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()

    plan = build_plan()
    write_report(plan)
    print(f"Moves: {len(plan['moves'])}")
    for move in plan["moves"]:
        print(f"- {Path(move['source']).relative_to(BRAIN_ROOT)} ({move['markdown']} md) -> {Path(move['target']).relative_to(BRAIN_ROOT)}")
    print(f"Skipped: {len(plan['skipped'])}")
    for item in plan["skipped"]:
        if item.get("reason") == "no_taxonomy_target":
            print(f"! Unmapped: {item['name']} ({item.get('markdown', 0)} md)")
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
