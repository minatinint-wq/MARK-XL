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
REPORT_PATH = PROJECT_ROOT / "memory" / "obsidian_pro_max_plan.json"

AREAS: dict[str, dict[str, Any]] = {
    "00_Cerebro": {
        "title": "Cerebro do Jarvis",
        "purpose": "Nucleo de memoria, compactacoes, indices, preferencias globais e regras de leitura do MARK-XL.",
        "tags": ["jarvis", "cerebro", "memoria", "indice"],
        "sections": ["knowledge_compact", "indice", "Core", "camadas"],
    },
    "01_Inbox": {
        "title": "Entrada Rapida",
        "purpose": "Caixa de entrada para notas ainda nao classificadas, capturas temporarias e ideias que precisam virar conhecimento.",
        "tags": ["inbox", "triagem", "captura"],
        "sections": ["a_processar", "capturas", "rascunhos"],
    },
    "02_Comandos_Jarvis": {
        "title": "Comandos e Automacoes do Jarvis",
        "purpose": "Comandos padrao, macros, clipboard, alarmes, jogos, teclado, mouse, Spotify, visao e fluxos de voz.",
        "tags": ["jarvis", "comandos", "automacao", "pc"],
        "sections": ["atalhos", "rotinas", "pc_control", "voz"],
    },
    "03_Eu_Preferencias": {
        "title": "Eu, Preferencias e Perfil",
        "purpose": "Preferencias pessoais, identidade, desejos, relacionamentos, contexto de rotina e informacoes que personalizam respostas.",
        "tags": ["perfil", "preferencias", "pessoal"],
        "sections": ["identity", "preferences", "Eu", "relationships", "wishes", "emotions"],
    },
    "04_Estudo": {
        "title": "Estudo e Aprendizado",
        "purpose": "Ciclos de estudo, auto-estudo, tecnicas, formulas, revisoes e temas que o Jarvis deve expandir com o tempo.",
        "tags": ["estudo", "aprendizado", "revisao"],
        "sections": ["Estudo", "Auto-estudo", "techniques", "formulas"],
    },
    "05_Tecnologia": {
        "title": "Tecnologia e Programacao",
        "purpose": "Codigo, APIs, IA aplicada, infraestrutura, ferramentas, debug e conhecimento tecnico reutilizavel.",
        "tags": ["tech", "programacao", "ia", "software"],
        "sections": ["Tecnologia", "technologies", "projects", "apis"],
    },
    "06_IA_Automacoes": {
        "title": "IA, Voz, Visao e Automacoes",
        "purpose": "Modelos, prompts, sintetizador de voz, visao, camera, Braille, aprendizado visual e rotinas inteligentes.",
        "tags": ["ia", "voz", "visao", "braille", "automacao"],
        "sections": ["voice_synth", "vision", "braille", "learning_loop"],
    },
    "07_Jogos": {
        "title": "Jogos e Controle de Games",
        "purpose": "Perfis de jogos, comandos de abrir jogos, Task Bar Hero, Brawlhalla, Mine e automacoes de controle.",
        "tags": ["games", "jogos", "controle"],
        "sections": ["Task_Bar_Hero", "Minecraft", "Brawlhalla", "profiles"],
    },
    "08_Imobiliario": {
        "title": "Imobiliario",
        "purpose": "Mercado imobiliario, bairros, financiamento, captacao, avaliacao, documentacao e operacao de corretor.",
        "tags": ["imoveis", "imobiliario", "corretor"],
        "sections": ["Imobiliario", "mercado", "documentacao", "financiamento"],
    },
    "09_Corretor_Vendas": {
        "title": "Corretor, Atendimento e Vendas",
        "purpose": "Tecnicas de atendimento, qualificacao de leads, follow-up, objeções, propostas, CRM e scripts comerciais.",
        "tags": ["corretor", "vendas", "leads", "crm"],
        "sections": ["atendimento", "gestao_leads", "venda_tecnicas", "avaliacao"],
    },
    "10_Marketing_Ads": {
        "title": "Marketing, Ads e Conteudo",
        "purpose": "Facebook Ads, Meta Ads, Google Ads, criativos, funis, landing pages, pixels e metricas de campanha.",
        "tags": ["marketing", "ads", "facebook-ads", "google-ads"],
        "sections": ["facebook_ads", "google_ads", "pixel", "campanhas"],
    },
    "11_Financas": {
        "title": "Financas e Dinheiro",
        "purpose": "Financas pessoais, mercado, moedas, financiamento, bancos, formulas e calculos financeiros.",
        "tags": ["financas", "dinheiro", "mercado"],
        "sections": ["Financas", "currencies", "mercado", "calculos"],
    },
    "12_Cannabis": {
        "title": "Cannabis",
        "purpose": "Conhecimento sobre cannabis, genetica, medicina, problemas, extração, equipamentos e tecnicas gerais.",
        "tags": ["cannabis", "medicina", "genetica"],
        "sections": ["Cannabis", "genetics", "medicine", "equipment", "extraction"],
    },
    "13_Cultivo": {
        "title": "Cultivo",
        "purpose": "Cultivo indoor, solo, nutrientes, PPFD, VPD, pragas, tecnicas e rotinas de acompanhamento.",
        "tags": ["cultivo", "indoor", "plantas"],
        "sections": ["Cultivo", "cultivo_indoor", "nutrients", "ppfd", "vpd"],
    },
    "14_Hidroponia": {
        "title": "Hidroponia e Aquaponia",
        "purpose": "Hidroponia, aeroponia, aquaponia, sistemas, nutrientes liquidos, agua, peixes e plantas.",
        "tags": ["hidroponia", "aquaponia", "aeroponia"],
        "sections": ["Hidroponia", "aquaponia", "aeroponia", "hydroponics_systems"],
    },
    "15_Saude": {
        "title": "Saude e Corpo",
        "purpose": "Saude, corpo, rotina fisica, sono, alongamento, habitos, bem-estar e acompanhamento pessoal.",
        "tags": ["saude", "corpo", "habitos"],
        "sections": ["Saude", "health", "rotina", "bem_estar"],
    },
    "16_Biologia": {
        "title": "Biologia e Ciencia Natural",
        "purpose": "Biologia, animais, fungos, bacterias, ecossistemas, ciencia de plantas e base biologica do cultivo.",
        "tags": ["biologia", "bacteria", "fungi", "animais"],
        "sections": ["Biologia", "Animais", "bacteria", "fungi"],
    },
    "17_Receitas": {
        "title": "Receitas e Alimentacao",
        "purpose": "Receitas, comida, preparo, listas de ingredientes e conhecimento culinario reutilizavel.",
        "tags": ["receitas", "food", "culinaria"],
        "sections": ["Receitas", "food", "recipes"],
    },
    "18_Cultura": {
        "title": "Cultura e Entretenimento",
        "purpose": "Cultura, entretenimento, esportes, series, livros, referencias e gostos culturais.",
        "tags": ["cultura", "entretenimento", "esportes"],
        "sections": ["Cultura", "entertainment", "sports"],
    },
    "19_Musica": {
        "title": "Musica e Audio",
        "purpose": "Musicas, Spotify, playlists, frequencias, sintetizador de voz, audio e referencias sonoras.",
        "tags": ["musica", "spotify", "audio", "voz"],
        "sections": ["playlists", "frequencias", "voz", "spotify"],
    },
    "20_Viagens": {
        "title": "Viagens e Locais",
        "purpose": "Viagens, locais, hospedagem, aeroportos, atrações, rotas e preferencias de deslocamento.",
        "tags": ["viagem", "travel", "locais"],
        "sections": ["Viagem", "locations", "travel", "attractions"],
    },
    "21_Rotinas": {
        "title": "Rotinas e Habitos",
        "purpose": "Rotinas diarias, ciclos, checklists, habitos, revisoes e loops que o Jarvis acompanha.",
        "tags": ["rotina", "habitos", "ciclo"],
        "sections": ["rotinas", "routines", "habits", "checklists"],
    },
    "22_Dicionario": {
        "title": "Dicionario e Vocabulario",
        "purpose": "Palavras, significados, vocabulario, termos tecnicos, traducoes e memoria semantica.",
        "tags": ["dicionario", "vocabulario", "linguagem"],
        "sections": ["dictionary", "vocabulary", "letter_a", "letter_z"],
    },
    "23_Pesquisas": {
        "title": "Pesquisas e Referencias",
        "purpose": "Notas de pesquisa, fontes, resumos, achados, comparacoes, dados e conhecimento ainda em verificacao.",
        "tags": ["pesquisa", "referencias", "dados"],
        "sections": ["notes", "Conhecimento", "pesquisas", "referencias"],
    },
    "24_Projetos": {
        "title": "Projetos e Trabalho",
        "purpose": "Projetos ativos, trabalho, habilidades, planos, execucao, tarefas e entregaveis.",
        "tags": ["projetos", "trabalho", "skills"],
        "sections": ["projects", "Trabalho", "skills", "entregas"],
    },
}

MOVE_MAP: dict[str, str] = {
    "00_Cerebro/Auto-estudo": "04_Estudo/Auto-estudo",
    "00_Cerebro/Cerebro/dictionary": "22_Dicionario/dictionary",
    "00_Cerebro/Cerebro/vocabulary": "22_Dicionario/vocabulary",
    "00_Cerebro/Cerebro/rotinas": "21_Rotinas/rotinas",
    "00_Cerebro/Cerebro/routines": "21_Rotinas/routines",
    "00_Cerebro/Cerebro/preferences": "03_Eu_Preferencias/preferences",
    "00_Cerebro/Cerebro/identity": "03_Eu_Preferencias/identity",
    "00_Cerebro/Cerebro/Eu": "03_Eu_Preferencias/Eu",
    "00_Cerebro/Cerebro/relationships": "03_Eu_Preferencias/relationships",
    "00_Cerebro/Cerebro/wishes": "03_Eu_Preferencias/wishes",
    "00_Cerebro/Cerebro/emotions": "03_Eu_Preferencias/emotions",
    "00_Cerebro/Cerebro/Vida": "03_Eu_Preferencias/Vida",
    "00_Cerebro/Cerebro/Trabalho": "24_Projetos/Trabalho",
    "00_Cerebro/Cerebro/skills": "24_Projetos/skills",
    "00_Cerebro/Cerebro/notes": "23_Pesquisas/notes",
    "00_Cerebro/Cerebro/Conhecimento": "23_Pesquisas/Conhecimento",
    "00_Cerebro/Cerebro/Cannabis": "12_Cannabis/Cerebro_Cannabis",
    "00_Cerebro/Cerebro/Cultivo": "13_Cultivo/Cerebro_Cultivo",
    "00_Cerebro/Cerebro/Hidroponia": "14_Hidroponia/Cerebro_Hidroponia",
    "00_Cerebro/Cerebro/Saude": "15_Saude/Cerebro_Saude",
    "00_Cerebro/Cerebro/Sade": "15_Saude/Cerebro_Sade",
    "00_Cerebro/Cerebro/Dinheiro": "11_Financas/Dinheiro",
    "00_Cerebro/Cerebro/Mercado": "11_Financas/Mercado",
    "00_Cerebro/Cerebro/XXXX": "03_Eu_Preferencias/XXXX",
    "01_Negocios_Imoveis/Imobiliario": "08_Imobiliario/Imobiliario",
    "01_Negocios_Imoveis/Financas": "11_Financas/Financas",
    "02_Cultivo_Cannabis/Cannabis": "12_Cannabis/Cannabis",
    "02_Cultivo_Cannabis/Cultivo": "13_Cultivo/Cultivo",
    "02_Cultivo_Cannabis/Hidroponia": "14_Hidroponia/Hidroponia",
    "03_Estudo_Tecnologia/Estudo": "04_Estudo/Estudo",
    "03_Estudo_Tecnologia/Tecnologia": "05_Tecnologia/Tecnologia",
    "04_Saude_Ciencia/Saude": "15_Saude/Saude",
    "04_Saude_Ciencia/Biologia": "16_Biologia/Biologia",
    "04_Saude_Ciencia/Receitas": "17_Receitas/Receitas",
    "05_Vida_Cultura/Cultura": "18_Cultura/Cultura",
    "05_Vida_Cultura/Mundo_Pessoal": "03_Eu_Preferencias/Mundo_Pessoal",
    "05_Vida_Cultura/Viagem": "20_Viagens/Viagem",
}

OLD_BUCKETS = [
    "01_Negocios_Imoveis",
    "02_Cultivo_Cannabis",
    "03_Estudo_Tecnologia",
    "04_Saude_Ciencia",
    "05_Vida_Cultura",
]

SYSTEM_ROOTS = {".git", ".obsidian", "30_Sistema", "90_Archive"}


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
    for source_rel, target_rel in MOVE_MAP.items():
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
        "areas": list(AREAS),
    }


def write_report(plan: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def _index_body(area: str, info: dict[str, Any], children: list[str]) -> str:
    lines = [
        "---",
        "type: area-index",
        f"area: {area}",
        f"title: {info['title']}",
        "status: active",
        f"updated: {datetime.now().date().isoformat()}",
        "tags: [" + ", ".join(info["tags"]) + "]",
        "---",
        "",
        f"# {info['title']}",
        "",
        str(info["purpose"]),
        "",
        "## Como o Jarvis deve usar",
        "",
        "- Usar esta area como ponto de entrada quando a pergunta tocar nos tags acima.",
        "- Preferir notas especificas, depois hubs compactados, depois indices antigos.",
        "- Manter respostas curtas quando o usuario pedir acao; aprofundar quando pedir estudo.",
        "- Se houver conflito entre nota antiga e nota nova, priorizar a mais especifica e recente.",
        "",
        "## Subpastas principais",
        "",
    ]
    if children:
        for child in children:
            lines.append(f"- [[{child}]]")
    else:
        lines.append("- Ainda sem subpastas movidas; usar este hub para novas notas.")
    lines.extend([
        "",
        "## Trilhas de conhecimento",
        "",
    ])
    for section in info["sections"]:
        lines.append(f"- {section}: conectar notas, comandos e exemplos praticos relacionados.")
    lines.extend([
        "",
        "## Politica de organizacao",
        "",
        "Esta pasta faz parte do layout Pro Max: conhecimento espalhado em areas legiveis, mas com busca otimizada por indice JSON. Evitar criar notas vazias; criar notas quando houver conteudo util, preferencia confirmada ou sinal de aprendizado forte.",
        "",
    ])
    return "\n".join(lines)


def _write_area_indexes(root: Path, ops: list[dict[str, Any]]) -> None:
    for area, info in AREAS.items():
        area_path = root / area
        area_path.mkdir(parents=True, exist_ok=True)
        children = sorted([p.name for p in area_path.iterdir() if p.is_dir()])
        index_path = area_path / "_index.md"
        index_path.write_text(_index_body(area, info, children), encoding="utf-8")
        ops.append({"kind": "write_index", "path": str(index_path)})


def _cleanup_empty_buckets(root: Path, ops: list[dict[str, Any]]) -> None:
    archive = root / "90_Archive" / "pro_max_old_area_indexes" / datetime.now().strftime("%Y%m%d-%H%M%S")
    for rel in OLD_BUCKETS:
        bucket = root / rel
        if not bucket.exists():
            continue
        if not _is_under(bucket, root) or bucket.name in SYSTEM_ROOTS:
            continue
        leftovers = [item for item in bucket.iterdir()]
        if leftovers and all(item.is_file() and item.name == "_index.md" for item in leftovers):
            archive.mkdir(parents=True, exist_ok=True)
            for item in leftovers:
                dest = _unique_path(archive / f"{bucket.name}-{item.name}")
                shutil.move(str(item), str(dest))
                ops.append({"kind": "archive_old_index", "from": str(item), "to": str(dest)})
        try:
            bucket.rmdir()
            ops.append({"kind": "remove_empty_dir", "path": str(bucket)})
        except OSError:
            ops.append({"kind": "keep_non_empty_dir", "path": str(bucket)})


def apply_plan(plan: dict[str, Any], root: Path = BRAIN_ROOT) -> dict[str, Any]:
    ops: list[dict[str, Any]] = []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest_path = root / "90_Archive" / "pro_max_manifests" / f"{stamp}.json"

    for area in AREAS:
        area_path = root / area
        area_path.mkdir(parents=True, exist_ok=True)
        ops.append({"kind": "ensure_area", "path": str(area_path)})

    # Move deeper paths first so nested folders are not hidden by parent moves.
    moves = sorted(plan["moves"], key=lambda item: len(Path(item["source"]).parts), reverse=True)
    for move in moves:
        source = Path(move["source"])
        target = Path(move["target"])
        if not source.exists():
            ops.append({"kind": "skip_missing", "path": str(source)})
            continue
        if not _is_under(source, root) or not _is_under(target, root):
            raise ValueError(f"Unsafe move: {source} -> {target}")
        _merge_dir(source, target, ops)

    _write_area_indexes(root, ops)
    _cleanup_empty_buckets(root, ops)

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
    parser = argparse.ArgumentParser(description="Expand Obsidian into a rich Pro Max layout while keeping optimized indexes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()

    plan = build_plan()
    write_report(plan)
    print(f"Areas: {len(AREAS)}")
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
