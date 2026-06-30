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
REPORT_PATH = PROJECT_ROOT / "memory" / "obsidian_atlas_5000_report.json"
CARDS_PER_AREA = 200
CARDS_PER_FILE = 50

LENSES = [
    ("conceito", "definir o conceito antes de agir evita resposta generica e melhora a escolha da ferramenta certa"),
    ("sinal", "observar sinais de contexto ajuda o Jarvis a separar curiosidade, problema real e tarefa acionavel"),
    ("erro_comum", "o erro comum e tratar o tema como isolado quando ele depende de objetivo, restricao e prazo"),
    ("metrica", "uma metrica simples deve comparar qualidade, tempo, custo, risco e clareza da decisao"),
    ("pergunta", "a pergunta-chave e o que muda na proxima acao se esta informacao for verdadeira"),
    ("rotina", "uma rotina curta de revisao transforma informacao solta em conhecimento reutilizavel"),
    ("conexao", "a conexao util aparece quando o tema cruza comportamento, ferramenta, ambiente e resultado"),
    ("exemplo", "um exemplo pratico deve mostrar entrada, processo, saida esperada e criterio de sucesso"),
    ("risco", "o risco principal e responder com certeza onde falta fonte, contexto ou confirmacao do usuario"),
    ("proximo_passo", "o proximo passo bom e pequeno, verificavel e facil de desfazer se a hipotese estiver errada"),
]

AREAS: dict[str, dict[str, Any]] = {
    "00_Cerebro": {
        "tag": "cerebro",
        "themes": [
            "memoria de longo prazo", "indice neural", "grafo de conhecimento", "recuperacao de contexto",
            "compactacao de notas", "preferencias do usuario", "estado da sessao", "resumo persistente",
            "hierarquia de pastas", "validacao de fonte", "conflito entre notas", "prioridade de resposta",
            "tagging semantico", "busca por similaridade", "mapa mental", "curadoria de conhecimento",
            "rotas de leitura", "metadados uteis", "controle de ruido", "ciclo de aprendizagem",
        ],
    },
    "01_Inbox": {
        "tag": "inbox",
        "themes": [
            "captura rapida", "triagem diaria", "nota sem categoria", "rascunho de ideia", "entrada de voz",
            "print de tela", "link para revisar", "anotacao temporaria", "prioridade incerta", "fonte pendente",
            "limpeza semanal", "fila de processamento", "pendencia de decisao", "hipotese inicial",
            "pergunta aberta", "tarefa pequena", "conteudo duplicado", "entrada incompleta", "marcador de urgencia",
            "transformacao em nota permanente",
        ],
    },
    "02_Comandos_Jarvis": {
        "tag": "comandos",
        "themes": [
            "atalho de abrir app", "macro de teclado", "controle de mouse", "clipboard", "alarme no pc",
            "spotify connect", "janela ativa", "screenshot", "controle de jogos", "comando padrao",
            "rotina por voz", "modo mudo temporario", "leitura do copiado", "colar texto", "pesquisa rapida",
            "calculo por voz", "navegador", "task bar hero", "brawlhalla", "minecraft",
        ],
    },
    "03_Eu_Preferencias": {
        "tag": "perfil",
        "themes": [
            "preferencia de tom", "rotina pessoal", "energia do dia", "foco profundo", "descanso",
            "limite de notificacao", "gosto musical", "jogo favorito", "objetivo de estudo", "contexto familiar",
            "memoria afetiva", "preferencia visual", "modo de trabalho", "aversao a bagunca", "ritmo de resposta",
            "habito digital", "prioridade atual", "plano pessoal", "motivador interno", "sinal de cansaco",
        ],
    },
    "04_Estudo": {
        "tag": "estudo",
        "themes": [
            "repeticao espacada", "recall ativo", "tecnica Feynman", "mapa conceitual", "intercalacao",
            "pomodoro", "anotacao Cornell", "resumo progressivo", "flashcards", "autoavaliacao",
            "questao guia", "erro como feedback", "aula sintetizada", "exercicio pratico", "revisao semanal",
            "curva do esquecimento", "aprendizagem por projeto", "rubrica de qualidade", "trilha de estudo",
            "modo estudo ciclico",
        ],
    },
    "05_Tecnologia": {
        "tag": "tecnologia",
        "themes": [
            "api rest", "websocket", "fila de tarefas", "cache local", "banco json", "sqlite",
            "git", "teste automatizado", "log estruturado", "tratamento de erro", "timeout", "retry",
            "observabilidade", "interface web", "frontend", "backend", "script powershell", "python",
            "node", "deploy",
        ],
    },
    "06_IA_Automacoes": {
        "tag": "ia",
        "themes": [
            "prompt do sistema", "rag", "embedding", "busca neural", "sintese de voz", "fft de audio",
            "visao computacional", "camera", "braille por dedos", "deteccao de gesto", "modo live view",
            "modo visao", "classificador local", "feedback humano", "aprendizado incremental", "limiar de confianca",
            "memoria episodica", "agente executor", "planejador", "fallback seguro",
        ],
    },
    "07_Jogos": {
        "tag": "jogos",
        "themes": [
            "task bar hero", "brawlhalla", "minecraft", "perfil de controle", "latencia de input",
            "hotkey", "hud", "game loop", "balanceamento", "progressao", "economia de jogo",
            "dificuldade", "feedback visual", "tutorial", "inventario", "ranking", "matchmaking",
            "acessibilidade", "automacao de abrir jogo", "overlay",
        ],
    },
    "08_Imobiliario": {
        "tag": "imobiliario",
        "themes": [
            "avaliacao de imovel", "matricula", "iptu", "itbi", "financiamento imobiliario",
            "fgts", "bairro", "preco por metro quadrado", "cap rate", "renda de aluguel",
            "documentacao", "vistoria", "contrato", "proposta", "zoneamento", "condominio",
            "liquidez", "comparativo de mercado", "planta do imovel", "visita tecnica",
        ],
    },
    "09_Corretor_Vendas": {
        "tag": "vendas",
        "themes": [
            "qualificacao de lead", "follow up", "crm", "objeção de preco", "objeção de tempo",
            "script de atendimento", "rapport", "pergunta discovery", "proposta de valor", "negociacao",
            "fechamento", "pos venda", "captacao de proprietario", "agendamento de visita", "lead frio",
            "lead quente", "whatsapp business", "pipeline", "indicacao", "taxa de conversao",
        ],
    },
    "10_Marketing_Ads": {
        "tag": "marketing",
        "themes": [
            "facebook ads", "meta ads", "google ads", "pixel", "landing page", "criativo",
            "copywriting", "funil", "remarketing", "cpl", "ctr", "conversao", "publico frio",
            "publico morno", "lead magnet", "conteudo organico", "seo local", "campanha whatsapp",
            "teste ab", "dashboard de campanha",
        ],
    },
    "11_Financas": {
        "tag": "financas",
        "themes": [
            "juros compostos", "fluxo de caixa", "orcamento", "reserva de emergencia", "risco",
            "diversificacao", "liquidez", "selic", "inflacao", "spread", "roi", "margem",
            "custo fixo", "custo variavel", "capital de giro", "preco", "receita recorrente",
            "imposto", "moeda", "cenario economico",
        ],
    },
    "12_Cannabis": {
        "tag": "cannabis",
        "themes": [
            "botanica da cannabis", "genetica", "terpenos", "canabinoides", "medicina baseada em evidencia",
            "regras locais", "reducao de danos", "equipamentos", "extracao segura", "armazenamento",
            "identificacao de variedade", "perfil aromatico", "floracao", "vegetativo", "pragas comuns",
            "nutrientes", "substrato", "registro de observacao", "qualidade da informacao", "seguranca juridica",
        ],
    },
    "13_Cultivo": {
        "tag": "cultivo",
        "themes": [
            "solo vivo", "compostagem", "micorrizas", "ppfd", "vpd", "temperatura", "umidade",
            "irrigacao", "poda", "treinamento de planta", "nutrientes", "deficiencia mineral",
            "pragas", "fungos", "calendario de cultivo", "fotoperiodo", "substrato", "drenagem",
            "bioestimulante", "registro de grow",
        ],
    },
    "14_Hidroponia": {
        "tag": "hidroponia",
        "themes": [
            "ph", "ec", "ppm", "oxigenacao", "reservatorio", "bomba", "aeroponia", "aquaponia",
            "solucao nutritiva", "temperatura da agua", "raiz", "biofilme", "algas", "troca de agua",
            "gotejamento", "nft", "dwc", "sensor", "calibracao", "limpeza do sistema",
        ],
    },
    "15_Saude": {
        "tag": "saude",
        "themes": [
            "sono", "hidratacao", "alongamento", "ergonomia", "respiracao", "caminhada",
            "alimentacao", "estresse", "pausa ativa", "luz solar", "ritmo circadiano", "postura",
            "saude mental", "habito sustentavel", "sinal de alerta", "consulta profissional",
            "medicao simples", "energia", "recuperacao", "rotina de bem-estar",
        ],
    },
    "16_Biologia": {
        "tag": "biologia",
        "themes": [
            "celula", "dna", "rna", "proteina", "enzima", "microbioma", "fungos", "bacterias",
            "ecossistema", "evolucao", "fotossintese", "respiracao celular", "homeostase",
            "hormonio vegetal", "simbiose", "cadeia alimentar", "biodiversidade", "adaptacao",
            "ciclo da agua", "solo como organismo",
        ],
    },
    "17_Receitas": {
        "tag": "receitas",
        "themes": [
            "mise en place", "calor seco", "calor umido", "fermentacao", "emulsao", "reducao",
            "marinada", "temperatura interna", "textura", "tempero", "acidez", "doçura",
            "sal", "gordura", "panela certa", "forno", "conservacao", "porcionamento",
            "lista de compras", "aproveitamento de sobras",
        ],
    },
    "18_Cultura": {
        "tag": "cultura",
        "themes": [
            "cinema", "literatura", "serie", "quadrinhos", "historia da arte", "mitologia",
            "filosofia", "sociologia", "memoria cultural", "humor", "critica", "genero narrativo",
            "personagem", "simbolo", "estetica", "movimento cultural", "jogo como cultura",
            "esporte", "comunidade", "referencia pop",
        ],
    },
    "19_Musica": {
        "tag": "musica",
        "themes": [
            "ritmo", "melodia", "harmonia", "timbre", "frequencia", "equalizacao", "compressao",
            "sintese sonora", "voz", "microfone", "spotify", "playlist", "bpm", "escala",
            "acorde", "baixo", "bateria", "mixagem", "masterizacao", "paisagem sonora",
        ],
    },
    "20_Viagens": {
        "tag": "viagem",
        "themes": [
            "roteiro", "hospedagem", "aeroporto", "bagagem", "seguro viagem", "documento",
            "moeda local", "transporte publico", "mapa offline", "restaurante", "atração",
            "clima", "fuso horario", "orçamento de viagem", "milhas", "check-in", "conexao",
            "plano b", "seguranca urbana", "memoria de viagem",
        ],
    },
    "21_Rotinas": {
        "tag": "rotina",
        "themes": [
            "checklist matinal", "revisao semanal", "planejamento diario", "limpeza digital",
            "backup", "organização de arquivos", "agenda", "alarme", "habito minimo", "gatilho",
            "recompensa", "controle de ambiente", "ciclo de estudo", "ciclo de trabalho",
            "manutencao do pc", "ritual de inicio", "ritual de fim", "fila de tarefas",
            "prioridade", "energia por horario",
        ],
    },
    "22_Dicionario": {
        "tag": "dicionario",
        "themes": [
            "prefixo", "sufixo", "etimologia", "sinonimo", "antonimo", "campo semantico",
            "termo tecnico", "traducao", "falso cognato", "neologismo", "sigla", "abreviacao",
            "exemplo de uso", "definicao operacional", "categoria gramatical", "metafora",
            "analogia", "palavra-chave", "glossario", "vocabulario ativo",
        ],
    },
    "23_Pesquisas": {
        "tag": "pesquisa",
        "themes": [
            "fonte primaria", "fonte secundaria", "citacao", "resumo", "metodologia",
            "viés", "amostra", "correlacao", "causalidade", "revisao bibliografica",
            "hipotese", "experimento", "replicabilidade", "evidencia", "incerteza",
            "comparacao", "dataset", "nota de campo", "pergunta de pesquisa", "sintese",
        ],
    },
    "24_Projetos": {
        "tag": "projetos",
        "themes": [
            "escopo", "milestone", "entrega", "teste de aceitacao", "risco do projeto",
            "dependencia", "roadmap", "backlog", "bug", "refatoracao", "documentacao",
            "release", "usuario-alvo", "metricas de sucesso", "prototipo", "feedback",
            "priorizacao", "custo de manutencao", "handoff", "retrospectiva",
        ],
    },
}


def _slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def _is_under(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved_root = root.resolve()
        return resolved == resolved_root or resolved.is_relative_to(resolved_root)
    except Exception:
        return False


def _card(card_id: int, area: str, area_tag: str, theme: str, lens: tuple[str, str]) -> str:
    lens_name, lens_text = lens
    theme_tag = _slug(theme)
    return "\n".join(
        [
            f"### ATLAS-{card_id:04d} - {theme} / {lens_name}",
            "",
            f"Informacao: em {theme}, {lens_text}.",
            f"Uso no Jarvis: quando o usuario mencionar {theme}, cruzar com a area {area}, buscar nota especifica e responder com proximo passo verificavel.",
            f"Tags: #{area_tag} #{theme_tag} #{lens_name}",
            "",
        ]
    )


def build_cards() -> dict[str, list[str]]:
    cards_by_area: dict[str, list[str]] = {}
    card_id = 1
    for area, info in AREAS.items():
        area_cards: list[str] = []
        for theme in info["themes"]:
            for lens in LENSES:
                area_cards.append(_card(card_id, area, str(info["tag"]), theme, lens))
                card_id += 1
                if len(area_cards) >= CARDS_PER_AREA:
                    break
            if len(area_cards) >= CARDS_PER_AREA:
                break
        cards_by_area[area] = area_cards
    return cards_by_area


def build_plan(root: Path = BRAIN_ROOT) -> dict[str, Any]:
    cards_by_area = build_cards()
    files = []
    for area, cards in cards_by_area.items():
        for index in range(0, len(cards), CARDS_PER_FILE):
            pack_number = index // CARDS_PER_FILE + 1
            path = root / area / f"{_slug(area)}_hub_{pack_number:02d}.md"
            files.append({
                "area": area,
                "path": str(path),
                "cards": len(cards[index : index + CARDS_PER_FILE]),
            })
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "areas": len(cards_by_area),
        "total_cards": sum(len(cards) for cards in cards_by_area.values()),
        "files": files,
    }


def _pack_text(area: str, info: dict[str, Any], pack_number: int, cards: list[str]) -> str:
    return "\n".join(
        [
            "---",
            "type: knowledge-hub-pack",
            f"area: {area}",
            f"hub: {pack_number}",
            f"cards: {len(cards)}",
            f"updated: {datetime.now().date().isoformat()}",
            "tags: [hub-5000, " + str(info["tag"]) + "]",
            "---",
            "",
            f"# Hub 5000 - {area} - parte {pack_number:02d}",
            "",
            f"Area hub: [[{area}/_index]]",
            "",
            "Este hub guarda cards atomicos de conhecimento. Ele fica dentro da area principal para parecer com o cerebro antigo, mas em arquivos compactos para manter o Obsidian e o Jarvis responsivos.",
            "",
            *cards,
        ]
    )


def _upsert_atlas_block(index_path: Path, pack_links: list[str]) -> None:
    start = "<!-- ATLAS_5000_START -->"
    end = "<!-- ATLAS_5000_END -->"
    current = index_path.read_text(encoding="utf-8", errors="ignore") if index_path.exists() else f"# {index_path.parent.name}\n"
    block = "\n".join(
        [
            start,
            "## Hubs 5000",
            "",
            "Cards diversos adicionados como hubs compactos para ampliar conhecimento geral sem criar milhares de arquivos soltos.",
            "",
            *[f"- [[{link}]]" for link in pack_links],
            end,
            "",
        ]
    )
    if start in current and end in current:
        before = current.split(start, 1)[0].rstrip()
        after = current.split(end, 1)[1].lstrip()
        text = before + "\n\n" + block + after
    else:
        text = current.rstrip() + "\n\n" + block
    index_path.write_text(text, encoding="utf-8")


def apply_plan(root: Path = BRAIN_ROOT) -> dict[str, Any]:
    if not _is_under(root, BRAIN_ROOT):
        raise ValueError(f"Unsafe root: {root}")
    cards_by_area = build_cards()
    ops: list[dict[str, Any]] = []
    for area, cards in cards_by_area.items():
        info = AREAS[area]
        area_path = root / area
        pack_links: list[str] = []
        for index in range(0, len(cards), CARDS_PER_FILE):
            pack_number = index // CARDS_PER_FILE + 1
            pack_cards = cards[index : index + CARDS_PER_FILE]
            pack_name = f"{_slug(area)}_hub_{pack_number:02d}.md"
            pack_path = area_path / pack_name
            pack_path.write_text(_pack_text(area, info, pack_number, pack_cards), encoding="utf-8")
            pack_links.append(Path(pack_name).stem)
            ops.append({"kind": "write_pack", "path": str(pack_path), "cards": len(pack_cards)})
        _upsert_atlas_block(area_path / "_index.md", pack_links)
        ops.append({"kind": "update_area_index", "path": str(area_path / "_index.md")})

    manifest_path = root / "90_Archive" / "atlas_5000_manifests" / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "applied": datetime.now().isoformat(timespec="seconds"),
        "total_cards": sum(len(cards) for cards in cards_by_area.values()),
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
    parser = argparse.ArgumentParser(description="Generate 5000 organized knowledge cards as compact Obsidian hubs.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()

    plan = build_plan()
    REPORT_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Areas: {plan['areas']}")
    print(f"Cards: {plan['total_cards']}")
    print(f"Files: {len(plan['files'])}")
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
