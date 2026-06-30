from __future__ import annotations

from datetime import datetime
from pathlib import Path
from shutil import move


ROOT = Path(r"D:\xxxx_memory")
HIDDEN_LEARNED = ROOT / "30_Sistema" / "obsidian_data" / "xxxx-vault" / "YYYY" / "learned"
VISIBLE_RECOVERED = ROOT / "00_Cerebro" / "learned_recovered"

CATEGORY_NAMES = {
    "games": "jogos",
    "imoveis": "imoveis",
    "musica": "musica",
    "tech": "tecnologia",
}


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 100000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not choose unique path for {path}")


def _wiki_link(note: Path) -> str:
    rel = note.relative_to(ROOT).with_suffix("")
    return str(rel).replace("\\", "/")


def _write_category_index(folder: Path) -> int:
    notes = sorted(p for p in folder.rglob("*.md") if p.name != "_index.md")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "---",
        f"created: {now}",
        f"updated: {now}",
        "tags: [cerebro, jarvis, recovered, obsidian]",
        "type: hub",
        f"folder: {folder.relative_to(ROOT)}",
        "---",
        "",
        f"# Hub recuperado - {folder.name}",
        "",
        f"Total de notas visiveis neste hub: {len(notes)}.",
        "",
        "## Notas",
        "",
    ]
    for note in notes:
        lines.append(f"- [[{_wiki_link(note)}|{note.stem}]]")
    (folder / "_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(notes)


def repair() -> list[tuple[str, str, int, int]]:
    if not ROOT.exists():
        raise FileNotFoundError(f"Vault root not found: {ROOT}")

    VISIBLE_RECOVERED.mkdir(parents=True, exist_ok=True)
    summary: list[tuple[str, str, int, int]] = []

    if HIDDEN_LEARNED.exists():
        categories = sorted(p for p in HIDDEN_LEARNED.iterdir() if p.is_dir())
    else:
        categories = []

    for source_dir in categories:
        target_name = CATEGORY_NAMES.get(source_dir.name, source_dir.name)
        target_dir = VISIBLE_RECOVERED / target_name
        target_dir.mkdir(parents=True, exist_ok=True)
        moved = 0

        for source_file in sorted(source_dir.rglob("*.md")):
            relative = source_file.relative_to(source_dir)
            target = _unique_path(target_dir / relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            move(str(source_file), str(target))
            moved += 1

        total = _write_category_index(target_dir)
        summary.append((source_dir.name, target_name, moved, total))

    for target_dir in sorted(p for p in VISIBLE_RECOVERED.iterdir() if p.is_dir()):
        if not any(item[1] == target_dir.name for item in summary):
            total = _write_category_index(target_dir)
            summary.append((target_dir.name, target_dir.name, 0, total))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    top = ROOT / "00_Cerebro" / "_cerebro-jarvis.md"
    lines = [
        "---",
        f"created: {now}",
        f"updated: {now}",
        "tags: [cerebro, jarvis, hub, obsidian]",
        "type: hub",
        "folder: 00_Cerebro",
        "---",
        "",
        "# Cerebro Jarvis",
        "",
        "Este hub torna visivel no Obsidian o conhecimento que estava escondido em `30_Sistema/obsidian_data/xxxx-vault/YYYY/learned`, uma pasta ignorada pelo Obsidian.",
        "",
        "## Hubs recuperados",
        "",
    ]
    for source_name, target_name, moved, total in summary:
        lines.append(
            f"- [[00_Cerebro/learned_recovered/{target_name}/_index|{target_name}]] - {total} notas; {moved} movidas agora de `{source_name}`."
        )
    lines += [
        "",
        "## Hubs principais",
        "",
        "- [[00_Cerebro/_index|Indice antigo do cerebro]]",
        "- [[04_Estudo]]",
        "- [[05_Tecnologia]]",
        "- [[07_Jogos]]",
        "- [[08_Imobiliario]]",
        "- [[09_Corretor_Vendas]]",
        "- [[19_Musica]]",
    ]
    top.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = repair()
    print("Obsidian brain repair complete.")
    for item in result:
        print(item)
