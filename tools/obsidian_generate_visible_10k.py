from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRAIN_ROOT = Path(r"D:\xxxx_memory")
REPORT_PATH = PROJECT_ROOT / "memory" / "obsidian_visible_10k_report.json"

SUBJECTS = [
    "cannabis",
    "cannabis_equipment",
    "cannabis_extraction",
    "cannabis_genetics",
    "cannabis_growing",
    "cannabis_medicine",
    "cannabis_nutrients",
    "cannabis_problems",
    "cannabis_techniques",
    "corretor",
    "corretor_atendimento",
    "corretor_avaliacao",
    "corretor_financiamento",
    "corretor_gestao_leads",
    "corretor_legal",
    "corretor_mercado",
    "corretor_venda_tecnicas",
    "marketing_ads",
    "facebook_ads",
    "google_ads",
    "seo_local",
    "funis_vendas",
    "crm_pipeline",
    "financas",
    "currencies",
    "investimentos",
    "economia",
    "formulas",
    "calculos",
    "tecnologia",
    "programacao",
    "python",
    "javascript",
    "automacoes",
    "inteligencia_artificial",
    "visao_computacional",
    "voz_audio",
    "braille",
    "acessibilidade",
    "jogos",
    "task_bar_hero",
    "minecraft",
    "brawlhalla",
    "game_design",
    "estudo",
    "aprendizado",
    "memoria",
    "produtividade",
    "rotinas",
    "habitos",
    "dictionary",
    "vocabulary",
    "linguagem",
    "filosofia",
    "psicologia",
    "neurociencia",
    "saude",
    "sono",
    "nutricao",
    "exercicios",
    "biologia",
    "microbiologia",
    "botanica",
    "ecologia",
    "receitas",
    "culinaria",
    "fermentacao",
    "musica",
    "audio",
    "spotify",
    "cultura",
    "cinema",
    "literatura",
    "historia",
    "geografia",
    "viagens",
    "locais",
    "seguranca_digital",
    "privacidade",
    "redes",
    "hardware",
    "windows_pc",
    "obsidian",
    "knowledge_management",
    "pesquisa",
    "ciencia",
    "matematica",
    "fisica",
    "quimica",
    "astronomia",
    "clima",
    "jardinagem",
    "hidroponia",
    "aquaponia",
    "cultivo_indoor",
    "solo_vivo",
    "pragas",
    "nutrientes_plantas",
    "projetos",
    "trabalho",
]

DIMENSIONS = [
    ("fundamentos", "entender os fundamentos separa regra geral de excecao e deixa a resposta mais confiavel"),
    ("ferramentas", "mapear ferramentas ajuda o Jarvis a escolher entre automatizar, pesquisar, calcular ou pedir contexto"),
    ("fluxo_pratico", "um fluxo pratico transforma conhecimento em sequencia de passos verificaveis"),
    ("erros_comuns", "listar erros comuns reduz retrabalho e evita conclusoes bonitas porem fracas"),
    ("metricas", "metricas simples permitem comparar qualidade, custo, velocidade, risco e resultado"),
    ("exemplo_aplicado", "um exemplo aplicado mostra como a ideia muda uma decisao real"),
    ("checklist", "checklists curtos ajudam o Jarvis a agir sem esquecer pre-condicoes importantes"),
    ("conexoes", "conexoes entre areas aumentam recuperacao neural e criam respostas mais completas"),
    ("sinais_alerta", "sinais de alerta indicam quando pausar, verificar fonte ou pedir confirmacao"),
    ("proximo_passo", "um proximo passo bom e pequeno, observavel e facil de corrigir"),
]

LENSES = [
    ("definicao", "defina o termo em linguagem simples antes de usar detalhe tecnico"),
    ("diagnostico", "observe entrada, contexto, frequencia, excecao e resultado antes de concluir"),
    ("planejamento", "organize objetivo, restricoes, prioridade, tempo e criterio de pronto"),
    ("execucao", "execute em passos curtos e registre o que mudou para poder reverter"),
    ("revisao", "revise depois de testar, comparando expectativa com resultado real"),
    ("automacao", "automatize apenas o trecho repetitivo e mantenha ponto de controle humano"),
    ("fonte", "prefira fonte primaria quando houver risco tecnico, legal, financeiro ou medico"),
    ("risco", "se o custo de erro for alto, reduza escopo e valide antes de agir"),
    ("melhoria", "melhore uma variavel por vez para entender causa e efeito"),
    ("acao", "termine com uma acao concreta que aproxime o usuario do objetivo"),
]


def _slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def _title(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _is_under(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved_root = root.resolve()
        return resolved == resolved_root or resolved.is_relative_to(resolved_root)
    except Exception:
        return False


def _note_text(note_id: int, subject: str, dimension: tuple[str, str], lens: tuple[str, str]) -> str:
    dim_name, dim_text = dimension
    lens_name, lens_text = lens
    subject_title = _title(subject)
    return "\n".join(
        [
            "---",
            "type: visual-10k-note",
            f"id: VIS10K-{note_id:05d}",
            f"domain: {subject}",
            f"dimension: {dim_name}",
            f"lens: {lens_name}",
            f"created: {datetime.now().date().isoformat()}",
            f"tags: [visual-10k, {subject}, {dim_name}, {lens_name}]",
            "---",
            "",
            f"# {subject_title} - {dim_name} - {lens_name}",
            "",
            "## Informacao",
            "",
            f"Em {subject_title}, {dim_text}. Para esta lente, {lens_text}.",
            "",
            "## Uso no Jarvis",
            "",
            f"Quando o usuario mencionar `{subject}` junto de `{dim_name}` ou `{lens_name}`, recuperar esta nota como contexto atomico e responder com uma orientacao pratica, nao apenas uma definicao.",
            "",
            "## Conexoes",
            "",
            f"- [[_index]]",
            f"- #{subject}",
            f"- #{dim_name}",
            f"- #{lens_name}",
            "",
        ]
    )


def build_plan(root: Path = BRAIN_ROOT) -> dict[str, Any]:
    files = []
    note_id = 1
    for subject in SUBJECTS:
        folder = root / subject
        for dim in DIMENSIONS:
            for lens in LENSES:
                name = f"VIS10K-{note_id:05d}-{_slug(dim[0])}-{_slug(lens[0])}.md"
                files.append({"path": str(folder / name), "subject": subject, "id": note_id})
                note_id += 1
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "subjects": len(SUBJECTS),
        "notes": len(files),
        "files": files,
    }


def _index_text(subject: str, note_names: list[str]) -> str:
    subject_title = _title(subject)
    lines = [
        "---",
        "type: visual-10k-index",
        f"domain: {subject}",
        f"notes: {len(note_names)}",
        f"updated: {datetime.now().date().isoformat()}",
        f"tags: [visual-10k, {subject}, hub]",
        "---",
        "",
        f"# {subject_title}",
        "",
        "Hub visual no estilo antigo: muitas notas pequenas, organizadas e pesquisaveis, com indice local para navegacao.",
        "",
        "## Notas",
        "",
    ]
    lines.extend(f"- [[{name}]]" for name in note_names)
    lines.append("")
    return "\n".join(lines)


def apply_plan(root: Path = BRAIN_ROOT) -> dict[str, Any]:
    if not _is_under(root, BRAIN_ROOT):
        raise ValueError(f"Unsafe root: {root}")

    ops: list[dict[str, Any]] = []
    note_id = 1
    for subject in SUBJECTS:
        folder = root / subject
        folder.mkdir(parents=True, exist_ok=True)
        note_names: list[str] = []
        for dim in DIMENSIONS:
            for lens in LENSES:
                stem = f"VIS10K-{note_id:05d}-{_slug(dim[0])}-{_slug(lens[0])}"
                path = folder / f"{stem}.md"
                path.write_text(_note_text(note_id, subject, dim, lens), encoding="utf-8")
                note_names.append(stem)
                ops.append({"kind": "write_note", "path": str(path)})
                note_id += 1
        index_path = folder / "_index.md"
        index_path.write_text(_index_text(subject, note_names), encoding="utf-8")
        ops.append({"kind": "write_index", "path": str(index_path), "notes": len(note_names)})

    manifest_path = root / "90_Archive" / "visible_10k_manifests" / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "applied": datetime.now().isoformat(timespec="seconds"),
        "subjects": len(SUBJECTS),
        "notes": len(SUBJECTS) * len(DIMENSIONS) * len(LENSES),
        "operations": ops,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def refresh_indexes() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from memory.memory_manager import generate_vault_groups, generate_vault_index, generate_vault_search_index

    generate_vault_index()
    generate_vault_groups()
    generate_vault_search_index()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate 10k visible optimized Obsidian notes in legacy-style folders.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()

    plan = build_plan()
    REPORT_PATH.write_text(json.dumps({k: v for k, v in plan.items() if k != "files"}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Subjects: {plan['subjects']}")
    print(f"Notes: {plan['notes']}")
    print(f"Report: {REPORT_PATH}")

    if args.apply:
        manifest = apply_plan()
        print(f"Applied operations: {len(manifest['operations'])}")
    if args.refresh_index:
        refresh_indexes()
        print("Indexes refreshed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
