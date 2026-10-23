"""Create 50k compact, local memory atoms without touching user-authored notes.

The generated notes are deliberate retrieval scaffolding: they cover the Jarvis
domains with a concept, action, guardrail and context tag. They do not pretend to
be time-sensitive facts, so high-stakes/current questions still require sources.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRAIN_ROOT = Path(r"D:\xxxx_memory")
TARGET = 50_000
REPORT_PATH = PROJECT_ROOT / "memory" / "local_memory_50k_report.json"
MEMORY_FOLDER = "00_Memorias_Jarvis"

# Keep the domain list shared with the existing visible-10k generator.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from obsidian_generate_visible_10k import DIMENSIONS, LENSES, SUBJECTS, _slug, _title  # noqa: E402

PERSPECTIVES = (
    ("base", "resuma o princípio antes de sugerir uma ação"),
    ("decisao", "compare benefício, custo, prazo e reversibilidade antes de escolher"),
    ("execucao", "organize uma sequência curta, verificável e com resultado observável"),
    ("checagem", "identifique o dado que precisa ser confirmado antes de concluir"),
    ("integracao", "relacione o tema ao objetivo do usuário e à ferramenta disponível"),
)

# New visual regions are small navigation hubs. The 50k searchable atoms remain
# in their matching existing domains, which keeps the atlas semantically honest.
KNOWLEDGE_REGIONS = {
    "jarvis_local": ("memoria", "automacoes", "inteligencia_artificial", "voz_audio", "visao_computacional"),
    "engenharia_sistemas": ("tecnologia", "programacao", "python", "javascript", "hardware", "redes"),
    "negocios_estrategia": ("corretor", "marketing_ads", "financas", "crm_pipeline", "projetos"),
    "ciencias_vida": ("biologia", "microbiologia", "botanica", "ecologia", "ciencia"),
    "saude_bem_estar": ("saude", "sono", "nutricao", "exercicios", "psicologia"),
    "cultura_criatividade": ("cultura", "cinema", "literatura", "musica", "game_design"),
    "mundo_pratico": ("viagens", "receitas", "windows_pc", "seguranca_digital", "produtividade"),
    "aprendizado_linguagem": ("estudo", "aprendizado", "dictionary", "vocabulary", "linguagem"),
}


def _quota(subject_index: int) -> int:
    base, remainder = divmod(TARGET, len(SUBJECTS))
    return base + (1 if subject_index < remainder else 0)


def _note(note_id: int, subject: str, dimension: tuple[str, str], lens: tuple[str, str], perspective: tuple[str, str]) -> str:
    dimension_name, dimension_text = dimension
    lens_name, lens_text = lens
    perspective_name, perspective_text = perspective
    title = _title(subject)
    return "\n".join((
        "---",
        "type: jarvis-local-memory-atom",
        f"id: MEM50K-{note_id:05d}",
        f"domain: {subject}",
        f"dimension: {dimension_name}",
        f"lens: {lens_name}",
        f"perspective: {perspective_name}",
        f"created: {datetime.now().date().isoformat()}",
        f"tags: [jarvis-local-50k, {subject}, {dimension_name}, {lens_name}, {perspective_name}]",
        "---",
        "",
        f"# {title} · {dimension_name} · {lens_name} · {perspective_name}",
        "",
        "## Contexto recuperável",
        "",
        f"Em {title}, {dimension_text}. Nesta lente, {lens_text}. Para esta memória, {perspective_text}.",
        "",
        "## Uso no Jarvis",
        "",
        f"Quando a pergunta mencionar {subject}, {dimension_name} ou {lens_name}, use este átomo para estruturar uma resposta prática e explique o próximo passo.",
        "",
        "## Limite de confiança",
        "",
        "Esta é uma memória de organização local. Dados médicos, legais, financeiros ou que mudam com o tempo exigem fonte atual e confirmação adequada.",
        "",
    ))


def build_plan() -> dict:
    return {
        "target": TARGET,
        "subjects": len(SUBJECTS),
        "root": str(BRAIN_ROOT),
        "new_regions": sorted(KNOWLEDGE_REGIONS),
        "notes_per_subject": {subject: _quota(index) for index, subject in enumerate(SUBJECTS)},
    }


def _write_region_hubs() -> None:
    for region, subjects in KNOWLEDGE_REGIONS.items():
        folder = BRAIN_ROOT / region
        folder.mkdir(parents=True, exist_ok=True)
        links = "\n".join(f"- [[../{subject}/_index|{_title(subject)}]]" for subject in subjects)
        connection_tags = ", ".join(f"connect-{subject}" for subject in subjects)
        text = "\n".join((
            "---",
            "type: jarvis-knowledge-region",
            f"region: {region}",
            f"tags: [jarvis-local, knowledge-region, atlas, {connection_tags}]",
            "---",
            "",
            f"# {_title(region)}",
            "",
            "Hub local para ligar domínios relacionados no atlas 3D. As memórias pesquisáveis ficam em suas pastas temáticas de origem.",
            "",
            "## Domínios conectados",
            links,
            "",
        ))
        (folder / "_index.md").write_text(text, encoding="utf-8")


def _write_domain_hub(subject: str) -> None:
    root = BRAIN_ROOT / subject
    folder = root / MEMORY_FOLDER
    notes = sorted(folder.glob("MEM50K-*.md"))
    hub = "\n".join((
        "---",
        "type: jarvis-local-memory-folder",
        f"domain: {subject}",
        f"notes: {len(notes)}",
        "tags: [jarvis-local-50k, memoria-local]",
        "---",
        "",
        f"# Memórias Jarvis · {_title(subject)}",
        "",
        "Coleção de átomos locais pesquisáveis pelo Jarvis. Eles ficam separados das notas pessoais para manter a navegação limpa.",
        "",
        f"**{len(notes):,} memórias locais** neste domínio.",
        "",
    ))
    (folder / "_index.md").write_text(hub, encoding="utf-8")
    index_path = root / "_index.md"
    current = index_path.read_text(encoding="utf-8", errors="ignore") if index_path.exists() else f"# {_title(subject)}\n"
    start, end = "<!-- JARVIS_LOCAL_MEMORY_START -->", "<!-- JARVIS_LOCAL_MEMORY_END -->"
    block = "\n".join((start, "## Memórias locais do Jarvis", "", f"- [[{MEMORY_FOLDER}/_index|Abrir {len(notes):,} memórias locais]]", end, ""))
    if start in current and end in current:
        current = current.split(start, 1)[0].rstrip() + "\n\n" + block + current.split(end, 1)[1].lstrip()
    else:
        current = current.rstrip() + "\n\n" + block
    index_path.write_text(current, encoding="utf-8")


def apply() -> dict:
    if not BRAIN_ROOT.exists():
        raise FileNotFoundError(f"Cérebro não encontrado: {BRAIN_ROOT}")
    written = 0
    note_id = 1
    for subject_index, subject in enumerate(SUBJECTS):
        folder = BRAIN_ROOT / subject / MEMORY_FOLDER
        folder.mkdir(parents=True, exist_ok=True)
        quota = _quota(subject_index)
        made = 0
        for perspective in PERSPECTIVES:
            for dimension in DIMENSIONS:
                for lens in LENSES:
                    if made >= quota:
                        break
                    filename = f"MEM50K-{note_id:05d}-{_slug(dimension[0])}-{_slug(lens[0])}-{perspective[0]}.md"
                    (folder / filename).write_text(_note(note_id, subject, dimension, lens, perspective), encoding="utf-8")
                    made += 1
                    written += 1
                    note_id += 1
                if made >= quota:
                    break
            if made >= quota:
                break
        _write_domain_hub(subject)
    _write_region_hubs()
    manifest = {
        "kind": "jarvis-local-memory-50k",
        "created": datetime.now().isoformat(timespec="seconds"),
        "root": str(BRAIN_ROOT),
        "notes": written,
        "target": TARGET,
    }
    manifest_path = BRAIN_ROOT / "90_Archive" / "jarvis_local_memory_50k_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def distribute_existing() -> dict:
    """Move the already-created set into existing thematic folders safely."""
    source = BRAIN_ROOT / "00_Cerebro" / "jarvis_local_memory_50k"
    if not source.exists():
        return {"moved": 0, "source": str(source), "status": "not_found"}
    missing = [subject for subject in SUBJECTS if not (BRAIN_ROOT / subject).is_dir()]
    if missing:
        raise RuntimeError("Pastas temáticas ausentes: " + ", ".join(missing))
    moved = 0
    for subject in SUBJECTS:
        source_folder = source / subject
        target = BRAIN_ROOT / subject / MEMORY_FOLDER
        target.mkdir(parents=True, exist_ok=True)
        if not source_folder.is_dir():
            continue
        for note in source_folder.glob("MEM50K-*.md"):
            destination = target / note.name
            if destination.exists():
                # A locked Windows move can copy the destination then fail before
                # removing its source. Treat only byte-identical pairs as a safe
                # completed transfer; a different existing note is never replaced.
                if note.read_bytes() != destination.read_bytes():
                    raise FileExistsError(f"Memória já existe no destino: {destination}")
                note.unlink()
                moved += 1
                continue
            shutil.move(str(note), str(destination))
            moved += 1
        try:
            source_folder.rmdir()
        except OSError:
            pass
        _write_domain_hub(subject)
    _write_region_hubs()
    return {"moved": moved, "source": str(source), "status": "distributed"}


def refresh() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from memory.memory_manager import generate_vault_groups, generate_vault_index, generate_vault_search_index
    generate_vault_index()
    generate_vault_groups()
    generate_vault_search_index()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate 50,000 compact Jarvis local-memory atoms.")
    parser.add_argument("--apply", action="store_true", help="write only the generated memory set")
    parser.add_argument("--distribute-existing", action="store_true", help="move an older single-folder set into existing thematic folders")
    parser.add_argument("--refresh-index", action="store_true", help="rebuild visual and FTS indexes")
    args = parser.parse_args()
    plan = build_plan()
    try:
        REPORT_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        # The generator remains usable in a read-only application install; the
        # actual memories always live in the separate xxxx_memory vault.
        pass
    print(f"Plan: {TARGET} memories across {len(SUBJECTS)} domains")
    if args.apply:
        manifest = apply()
        print(f"Written: {manifest['notes']} memories")
    if args.distribute_existing:
        result = distribute_existing()
        print(f"Distributed: {result['moved']} memories")
    if args.refresh_index:
        refresh()
        print("Indexes refreshed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
