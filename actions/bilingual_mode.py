"""MODO BILINGUE UNIVERSAL — JARVIS tradutor de QUALQUER idioma

Usa a API Gemini (ja instalada) para detectar e traduzir qualquer idioma.
Mantem cache local no vault para aprendizado continuo.

Modos:
- translate: traduz automaticamente entre qualquer par de idiomas
- learn: modo pratica - usuario fala no idioma alvo, JARVIS corrige
- teach: JARVIS ensina vocabulario/frases
"""

import re
import json
import random
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

VAULT = Path(__file__).resolve().parent.parent / "memory"
TRANSLATION_CACHE_FILE = VAULT / "data" / "translation_cache.json"
LINGUAS_DIR = VAULT / "auto_study" / "linguas"

TRANSLATION_CACHE: dict = {}
BILINGUAL_STATE: dict = {
    "active": False,
    "mode": "translate",
    "source_lang": "auto",
    "target_lang": "en-US",
    "target_display": "Ingles",
    "session_start": None,
    "words_learned": 0,
    "phrases_practiced": 0,
}

# Cache de idiomas conhecidos para display
LANG_NAMES = {
    "en": "Ingles", "pt": "Portugues", "es": "Espanhol", "fr": "Frances",
    "de": "Alemao", "it": "Italiano", "nl": "Holandes", "ru": "Russo",
    "zh": "Chines", "ja": "Japones", "ko": "Coreano", "ar": "Arabe",
    "hi": "Hindi", "sv": "Sueco", "no": "Noruegues", "da": "Dinamarques",
    "fi": "Finlandes", "pl": "Polones", "cs": "Tcheco", "hu": "Hungaro",
    "ro": "Romeno", "th": "Tailandes", "vi": "Vietnamita", "tr": "Turco",
    "el": "Grego", "he": "Hebraico", "id": "Indonesio", "ms": "Malaio",
    "la": "Latim", "eo": "Esperanto",
    "tl": "Filipino", "jw": "Javanes", "su": "Sundanes",
    "ceb": "Cebuano", "hmn": "Hmong", "haw": "Havaiano",
    "mi": "Maori", "sm": "Samoano", "to": "Tonganes",
    "mt": "Maltes", "is": "Islandes", "ga": "Irlandes",
    "cy": "Gales", "gd": "Gaelico Escoces", "lb": "Luxemburgues",
    "af": "Afrikaans", "sw": "Suaheli", "ha": "Hausa",
    "yo": "Ioruba", "ig": "Igbo", "zu": "Zulu",
    "xh": "Xhosa", "st": "Soto", "ny": "Chichewa",
    "rw": "Kinyarwanda", "sn": "Shona", "so": "Soma-li",
    "am": "Amárico", "ti": "Tigrínia", "om": "Oromo",
    "ps": "Pachto", "ku": "Curdo", "ckb": "Curdo Sorani",
    "sd": "Sindi", "pa": "Punjabi", "gu": "Gujarati",
    "mr": "Marati", "ne": "Nepales", "si": "Cingales",
    "km": "Khmer", "my": "Birmanês", "lo": "Lao",
    "mn": "Mongol", "bo": "Tibetano", "dz": "Dzonga",
    "ka": "Georgiano", "hy": "Armênio", "az": "Azeri",
    "kk": "Cazaque", "ky": "Quirguiz", "tk": "Turcomeno",
    "uz": "Uzbeque", "tg": "Tadjique", "bs": "Bosnio",
}

# Dados de contexto cultural e idiomatico por idioma
CULTURAL_CONTEXT = {
    "ja": {
        "script_type": "Logografico + Silabario (Kanji, Hiragana, Katakana)",
        "formality_levels": 3,
        "levels_desc": "Keigo: 1) Kudaketa (casual) — entre amigos, 2) Teinei (polido) — padrao, 3) Sonkeigo/Kenjougo (honorífico) — superiores/clientes",
        "key_etiquette": "NUNCA usar kudaketa com superiores. Usar -san, -sama, -sensei conforme hierarquia.",
        "unique_features": "3 sistemas de escrita, contexto implicito, sujeito frequentemente omitido",
        "idioms": {
            "hara ga tatsu": "Literally 'stomach stands up' = to be angry",
            "me ga mawaru": "Literally 'eyes spin' = to be dizzy/overwhelmed",
            "ude ga naru": "Literally 'arm rings out' = to be eager to do something",
            "ki ni suru": "To mind / to care about / to worry",
            "shikata ga nai": "It cannot be helped / it is what it is",
        },
        "common_mistakes": "Confundir wa/ga particles, omitir desu/masu em situacoes formais, usar anata (voce) excessivamente"
    },
    "zh": {
        "script_type": "Logografico (Hanzi Simplificado/Tradicional)",
        "formality_levels": 2,
        "levels_desc": "1) Coloquial — amigos/familia, 2) Formal — trabalho/desconhecidos",
        "key_etiquette": "Usar nin (voce respeitoso) para superiores. NUNCA apontar pessoas.",
        "unique_features": "4 tons + neutro, sem conjugacao, caracteres compartilhados com japones (kanji)",
        "idioms": {
            "yi wu suo you": "Literally 'one thing does not have' = to have nothing",
            "xin hua nu fang": "Literally 'heart flowers angrily bloom' = to be furious",
            "qi guai de shi": "The strange thing is...",
            "jian dan lai shuo": "Simply speaking...",
            "bu ke neng": "Impossible / no way"
        },
        "tonal_explanation": "ma1 (mae) = mae, ma2 (ma) = canhamo/linho, ma3 (ma) = cavalo, ma4 (ma) = xingar/praguejar, ma (neutro) = particula interrogativa"
    },
    "ar": {
        "script_type": "Abjad (da direita para esquerda)",
        "formality_levels": 2,
        "levels_desc": "1) Amiyah (dialeto coloquial) — dia a dia, 2) Fus-ha (árabe classico) — formal/midia/literatura",
        "key_etiquette": "Sempre usar 'Assalamu alaikum' antes de perguntar algo. Maos direita para cumprimentar, esquerda e considerada impura.",
        "unique_features": "Escrita da direita para esquerda, 28 letras, raizes triliteras, caligrafia como arte",
        "dialect_notes": "Egipcio, Sirio, Libanes, Magrebino (Marrocos/Argelia) sao dialetos praticamente diferentes do Fus-ha. Egipcio e o mais compreendido no mundo arabe por causa do cinema.",
        "idioms": {
            "al hamdu lillah": "Gracas a Deus (usado o tempo todo)",
            "insha'allah": "Se Deus quiser (futuro)",
            "ma sha' allah": "O que Deus quis (admiração, protege do mau-olhado)",
            "yalla": "Vamos / ande logo",
            "khalas": "Acabou / chega / pronto"
        }
    },
    "ko": {
        "script_type": "Alfabetico (Hangul + Hanja limitado)",
        "formality_levels": 7,
        "levels_desc": "7 niveis: Hasoseo-che (maximo respeito) → Hage-che (formal medio) → Hae-yo-che (polido comum) → Haera-che (formal escrito) → Hae-che (intimo) → Hae-ney (amigavel) → Hae (casual)",
        "key_etiquette": "Idade define linguagem. NUNCA usar casual com quem e mais velho que voce NUNCA.",
        "unique_features": "Alfabeto cientificamente projetado (1443), formato silabico, 7 niveis de formalidade",
        "idioms": {
            "tteok kuk meok eoss eo": "Literally 'ate rice cake soup' = how old are you? (Coreano pergunta idade perguntando quantas vezes comeu sopa de ano novo)",
            "go ta get it da": "Literally 'gas pedal' = hurry up",
            "jinjja": "Really? / seriously?",
            "daebak": "Awesome! / jackpot!",
            "aigoo": "Oh dear! / oh my! (exclamacao)"
        }
    },
    "th": {
        "script_type": "Abugida (Tailandes)",
        "formality_levels": 3,
        "levels_desc": "1) Palavra final khrap/ka conforme genero, 2) Formal rap/ka, 3) Real (para realeza)",
        "key_etiquette": "Homens terminam frases com khrap, mulheres com kha. NUNCA tocar a cabeca de alguem (sagrada). Wai (maos em prece) para cumprimentar.",
        "unique_features": "5 tons, 44 consoantes, sem espacos entre palavras, alfabeto de origem Khmer",
        "tonal_explanation": "Mai ek (tom descendente), mai tho (tom ascendente), mai tri (tom alto), mai chattawa (tom baixo), sem marca (tom medio)",
        "idioms": {
            "mai pen rai": "No problem / it's okay / never mind (filosofia tailandesa)",
            "jai yen yen": "Literally 'cool heart' = calm down / keep cool",
            "sanuk": "Fun / enjoyment (conceito central da cultura tailandesa)",
            "kreng jai": "To be considerate / not impose on others (conceito muito importante)",
            "sabai sabai": "Comfortable / relaxed / easy-going"
        }
    },
    "de": {
        "script_type": "Alfabetico latino",
        "formality_levels": 2,
        "levels_desc": "1) Du (informal) — amigos, familia, 2) Sie (formal) — estranhos, chefes, professores, pessoas mais velhas",
        "key_etiquette": "Sempre usar Sie ate a pessoa explicitamente oferecer du. Pontualidade e extrema importancia.",
        "unique_features": "3 generos gramaticais (der/die/das), 4 casos, palavras compostas gigantes, verbo sempre no final em oracoes subordinadas",
        "idioms": {
            "das ist mir wurst": "Literally 'that is sausage to me' = I don't care",
            "ich verstehe nur Bahnhof": "Literally 'I only understand train station' = I don't understand anything",
            "alles in Ordnung": "Everything is in order / okay",
            "toi toi toi": "Good luck (dizer sorte da azar, entao usa-se isso)",
            "na ja": "Well... (hesitation / mild disagreement)"
        }
    },
    "fr": {
        "script_type": "Alfabetico latino",
        "formality_levels": 2,
        "levels_desc": "1) Tu (informal) — amigos, familia, criancas, 2) Vous (formal) — estranhos, chefes, grupo",
        "key_etiquette": "Sempre dizer bonjour/madame/monsieur antes de qualquer pergunta. Tutoyer (usar tu) sem permissao e rude.",
        "unique_features": "Generos gramaticais, ligacoes (liaison), muitos homofonos, verbo + preposicao que nao traduzem diretamente",
        "idioms": {
            "c'est la vie": "That is life (aceitacao de algo ruim)",
            "avoir le cafard": "Literally 'to have the cockroach' = to feel depressed",
            "appeler un chat un chat": "To call a spade a spade",
            "faire la grasse matinee": "To sleep in late (literally 'to do the fat morning')",
            "oh la la": "Expression of surprise/disappointment (NUNCA romantico como nos filmes)"
        }
    },
    "ru": {
        "script_type": "Alfabetico cirilico",
        "formality_levels": 2,
        "levels_desc": "1) Ty (informal) — amigos, familia, 2) Vy (formal) — estranhos, chefes, multiplas pessoas",
        "key_etiquette": "Usar nome + patronimico (nome do pai) para pessoas mais velhas/chefes. Vy (plural) para uma pessoa e formal.",
        "unique_features": "6 casos gramaticais, 3 generos, aspecto verbal perfeito/imperfeito, alfabeto cirilico (33 letras)",
        "idioms": {
            "ne perevodi strelki": "Don't shift the arrows = don't change the subject / don't blame others",
            "eto ne moe": "It is not mine = it is not my problem",
            "vse budet khorosho": "Everything will be fine",
            "kak dela": "How are things",
            "u menya vse normalno": "I am fine / everything is normal"
        }
    },
    "hi": {
        "script_type": "Abugida (Devanagari)",
        "formality_levels": 2,
        "levels_desc": "1) Tum (informal) — amigos, 2) Aap (formal/respeitoso) — chefes, idosos, estranhos",
        "key_etiquette": "Usar Aap para quem e mais velho ou superior. Usar Namaste com maos em prece. Nao usar a esquerda para dar/receber objetos.",
        "unique_features": "Escrita Devanagari, generos gramaticais, ordem SOV (sujeito-objeto-verbo), palavras emprestadas do Persa/Arabe",
        "idioms": {
            "namaste": "I bow to you (saudacao universal)",
            "accha": "Okay? / really? / I see (multifuncional)",
            "kya baat hai": "What a thing! = impressive!",
            "thik hai": "Okay / fine / settled",
            "bahut achha": "Very good / very nice"
        }
    },
    "pt": {
        "script_type": "Alfabetico latino",
        "formality_levels": 2,
        "levels_desc": "1) Voce (informal) — todo uso no Brasil, 2) O senhor/A senhora (formal) — chefes, idosos, estranhos em contexto formal",
        "key_etiquette": "Brasil: 'Voce' e aceitavel universalmente. Portugal: usar 'Voce' com cautela, preferir 'O senhor/A senhora' para idosos.",
        "unique_features": "Diferenças significativas entre portugues do Brasil e de Portugal, muitos tempos verbais, contracoes obrigatorias (de+o=do, em+uma=numa)",
        "idioms": {
            "pagar o pato": "To pay the duck = to take the blame for something",
            "encher a cara": "To fill the face = to get drunk",
            "ficar a ver navios": "To be left watching ships = to be left empty-handed",
            "matar dois coelhos com uma cajadada": "Kill two rabbits with one blow = kill two birds with one stone",
            "mais vale um passaro na mao do que dois voando": "Better one bird in the hand than two flying = bird in the hand is worth two in the bush"
        }
    },
    "tr": {
        "script_type": "Alfabetico latino (moderno)",
        "formality_levels": 2,
        "levels_desc": "1) Sen (informal) — amigos, familia, 2) Siz (formal) — chefes, idosos, estranhos",
        "key_etiquette": "Usar -bey/-hanim apos primeiro nome para homens/mulheres (ex: Ahmet Bey, Ayse Hanim). Muito importante.",
        "unique_features": "Aglutinante (palavras enormes), harmonia vocalica, sem genero gramatical, ordem SOV"
    },
    "vi": {
        "script_type": "Alfabetico latino com diacriticos (Quoc Ngu)",
        "formality_levels": 3,
        "levels_desc": "Nivel de formalidade depende do pronome pessoal — ha dezenas de palavras para 'eu' e 'voce' dependendo da idade/genero/relacao",
        "key_etiquette": "NUNCA chamar alguem mais velho de 'ban' (amigo). Usar 'anh' (irmao mais velho) ou 'chi' (irma mais velha).",
        "unique_features": "6 tons, escrita latinizada por missionarios no seculo 17, pronomes pessoais complexissimos (20+ formas para 'I')"
    }
}

# Conjugacao verbal para os principais idiomas
VERB_CONJUGATIONS = {
    "en": {
        "to_be": {"I am", "you are", "he/she/it is", "we are", "they are"},
        "past": {"I was", "you were", "he/she/it was", "we were", "they were"},
        "future": {"I will be", "you will be", "he/she/it will be", "we will be", "they will be"},
        "have": {"I have", "you have", "he/she/it has", "we have", "they have"}
    },
    "pt": {
        "ser": {"eu sou", "tu es", "voce e", "ele/ela e", "nos somos", "eles/elas sao"},
        "estar": {"eu estou", "voce esta", "ele/ela esta", "nos estamos", "eles/elas estao"},
        "ter": {"eu tenho", "voce tem", "ele/ela tem", "nos temos", "eles/elas tem"},
        "falar": {"eu falo", "voce fala", "ele/ela fala", "nos falamos", "eles/elas falam"}
    },
    "es": {
        "ser": {"yo soy", "tu eres", "usted es", "el/ella es", "nosotros somos", "ellos son"},
        "estar": {"yo estoy", "tu estas", "usted esta", "el/ella esta", "nosotros estamos", "ellos estan"},
        "hablar": {"yo hablo", "tu hablas", "usted habla", "nosotros hablamos", "ellos hablan"},
        "tener": {"yo tengo", "tu tienes", "usted tiene", "el/ella tiene", "nosotros tenemos", "ellos tienen"}
    },
    "fr": {
        "etre": {"je suis", "tu es", "il/elle est", "nous sommes", "vous etes", "ils/elles sont"},
        "avoir": {"j'ai", "tu as", "il/elle a", "nous avons", "vous avez", "ils/elles ont"},
        "parler": {"je parle", "tu parles", "il/elle parle", "nous parlons", "vous parlez", "ils/elles parlent"}
    }
}

# Transcricao fonetica por tipo de script
PHONETIC_INFO = {
    "hiragana": {
        "description": "Silabario japones para palavras nativas e gramatica",
        "total": 46,
        "chart": "a i u e o / ka ki ku ke ko / sa shi su se so / ta chi tsu te to / na ni nu ne no / ha hi fu he ho / ma mi mu me mo / ya yu yo / ra ri ru re ro / wa wo n"
    },
    "katakana": {
        "description": "Silabario japones para palavras estrangeiras e onomatopeias",
        "total": 46,
        "chart": "a i u e o / ka ki ku ke ko / sa shi su se so / ta chi tsu te to / na ni nu ne no / ha hi fu he ho / ma mi mu me mo / ya yu yo / ra ri ru re ro / wa wo n"
    },
    "hangul": {
        "description": "Alfabeto coreano cientifico (1443)",
        "consonants": 14,
        "vowels": 10,
        "blocks": "Silabas compostas por 2-4 letras em bloco"
    },
    "devanagari": {
        "description": "Escrita do Hindi, Sânscrito, Marati, Nepalês",
        "consonants": 33,
        "vowels": 11,
        "note": "Abugida: cada consoante tem vogal inerente 'a'"
    }
}

_SUPPORTED_LANGUAGES = """af, sq, am, ar, hy, as, ay, az, bm, eu, be, bn, bho, bs, bg, ca, ceb, zh, co, hr, cs, da, dv, doi, nl, en, eo, et, ee, fil, fi, fr, fy, gl, ka, de, el, gn, gu, ha, haw, he, hi, hmn, hu, hr, is, ig, ilo, id, ga, it, ja, jv, kn, kk, km, rw, gom, ko, kri, ku, ckb, ky, lo, la, lv, ln, lt, lg, lb, mk, mai, mg, ms, ml, mt, mi, mr, mni-Mtei, lus, mn, my, ne, no, ny, or, om, ps, fa, pl, pt, pa, qu, ro, ru, sm, sa, gd, nso, sr, st, sn, sd, si, sk, sl, so, es, su, sw, sv, tl, tg, ta, tt, te, th, ti, ts, tr, tk, ak, uk, ur, ug, uz, vi, cy, xh, yi, yo, zu"""


def _load_cache():
    global TRANSLATION_CACHE
    try:
        if TRANSLATION_CACHE_FILE.exists():
            data = json.loads(TRANSLATION_CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                TRANSLATION_CACHE = data
                print(f"[Bilingual] Cache carregado: {len(data)} traducoes")
    except Exception as e:
        print(f"[Bilingual] Erro cache: {e}")


def _save_cache():
    try:
        TRANSLATION_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRANSLATION_CACHE_FILE.write_text(
            json.dumps(TRANSLATION_CACHE, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[Bilingual] Erro salvando cache: {e}")


def _cache_key(text: str, source: str, target: str) -> str:
    raw = f"{text}||{source}||{target}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _detect_lang(text: str) -> str:
    """Detect language using script blocks + normalized word scoring."""
    text_lower = text.lower().strip()

    # Script-based detection (deterministic)
    CJK = r"[\u4E00-\u9FFF]"
    if re.search(CJK, text_lower):
        return "zh" if not re.search(r"[\u3040-\u309F\u30A0-\u30FF]", text_lower) else "ja"
    if re.search(r"[\uAC00-\uD7AF]", text_lower): return "ko"
    if re.search(r"[\u0400-\u04FF]", text_lower): return "ru"
    if re.search(r"[\u0600-\u06FF]", text_lower): return "ar"
    if re.search(r"[\u0590-\u05FF]", text_lower): return "he"
    if re.search(r"[\u0900-\u097F]", text_lower): return "hi"
    if re.search(r"[\u0E00-\u0E7F]", text_lower): return "th"
    if re.search(r"[\u0370-\u03FF]", text_lower): return "el"

    # Romaji detection (Japanese romanized)
    ja_indicators = r"\b(konnichiwa|konbanwa|ohayo|sayonara|arigato|sumimasen|gomen|hai|iie|kudasai|onegai|daijobu|kawaii|sugoi|mata|nani|desu|masu|kimasu|shimasu|tabemasu|ikimasu|imasu|masen|masho)\b"
    if re.search(ja_indicators, text_lower, re.IGNORECASE):
        return "ja"

    # Latin-script: normalized word scoring (match / total_words)
    words = [w for w in re.split(r"\s+", text_lower) if len(w) > 1]
    n_words = len(words) or 1

    patterns = {
        "en": r"\b(the|is|are|you|I|we|they|he|she|it|and|to|of|in|that|have|with|for|this|not|on|will|can|do|my|at|by|or|from|was|be|get|would|could|should|does|did|been|had|then|than|there|their|your|our|its|hello|thanks|please|sorry|excuse|what|why|when|where|how)\b",
        "pt": r"\b(voce|obrigado|obrigada|tambem|ainda|sobre|seus|suas|meu|minha|teu|dele|dela|nosso|entao|depois|sempre|coisa|gente|gosta|ficar|achar|disse|tinha|estava|muito|ja|bem|aqui|ali|la|coisa|melhor|pior|maior|menor|primeiro|ultimo|novo|velho|bom|mau|visto|feito|dito)\b",
        "es": r"\b(hola|gracias|adios|hasta|tambien|pero|porque|quien|donde|cuando|siempre|nunca|puede|tiene|hace|dice|estoy|estas|estamos|ellos|ellas|ustedes|nosotros|chica|mucho|nada|algo|senor|senora|chico|entonces|todavia|ano|anos|hombre|mujer|nino|trabajo|noche|semana|vez|solo|despues|antes|ahora|aqui|alla|muy|poco|cada|entre|jamas|incluso|quizas|aunque|segun|gustaria|tengo|tienes|quiero|puedo|sabes|sabe|creo|penso|debe|deberia|podria|seria|estaria|habria|nuevo|nueva|bueno|buena|malo|mala|mejor|peor|primero|ultimo|mismo|propio|gran|sin|durante|mediante)\b",
        "fr": r"\b(bonjour|merci|tres|aussi|donc|alors|peut|fait|doit|etre|avoir|nous|vous|elles|ils|cette|cet|leurs|quelle|quel|comment|pourquoi|parce|toujours|jamais|trop|bonsoir|madame|monsieur|aujourd|travail|maison|homme|femme|enfant|monde|grand|petit|chaque|entre|pendant|depuis|parmi|voici|voila|beaucoup|peu|enfin|puis|cependant|pourtant)\b",
        "de": r"\b(guten|tag|und|die|der|das|ist|nicht|ein|eine|mit|auch|auf|fur|sich|werden|haben|oder|von|aus|bei|nach|um|durch|uber|aber|dann|doch|noch|schon|sehr|immer|heute|morgen|bitte|danke|hallo|tschuss|gut|schlecht|gross|klein|schnell|langsam|schon|alt|jung|neu|frei|offen|wichtig|moglich)\b",
        "it": r"\b(che|per|con|una|piu|ma|come|lei|suo|questo|quello|molto|ancora|tra|puo|deve|grazie|anche|dove|quando|sempre|mai|bene|qui|allora|dunque|proprio|sono|stato|stata|buongiorno|buonasera|arrivederci|prego|scusa|certo|forse|subito|adesso|ora|oggi|ieri|domani|settimana|mese|anno|volta|cosa|vita|casa|amico|lavoro|mondo|uomo|donna|bambino|questi|quelli)\b",
        "nl": r"\b(de|het|een|is|niet|met|ook|voor|op|aan|in|uit|bij|naar|door|over|van|die|dat|dit|was|zijn|hebben|worden|zullen|maar|ook|nog|al|dan|wel|hij|zij|hun|haar|hallo|dag|goed|slecht|mooi|nieuw|oud|groot|klein|snel|langzaam|belangrijk|mogelijk)\b",
    }

    scores = {}
    for lang, pattern in patterns.items():
        matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
        if matches > 0:
            scores[lang] = matches / n_words

    if scores:
        best = max(scores, key=scores.get)
        best_score = scores[best]
        # If top score is tied or very close, pick by language specificity
        contenders = [(k, v) for k, v in scores.items() if v >= best_score * 0.8]
        if len(contenders) > 1:
            # Prefer romance language with most unique indicators
            for lang, _ in contenders:
                unique_words = len(re.findall(patterns[lang], text_lower, re.IGNORECASE))
                if unique_words >= 3:
                    return lang
            return contenders[0][0]
        return best

    # Ultimate fallback: first word heuristic
    first = text_lower.split()[0] if text_lower.split() else ""
    if first.rstrip(",.!?") in {"hello","hi","hey","good","what","how","why","when","where","the","i","my","please","thanks","sorry"}:
        return "en"
    # Spanish/Portuguese last resort
    if re.search(r"\b(ola|como|voce|obrigado)\b", text_lower, re.IGNORECASE):
        return "pt"
    return "en"


def _save_to_vault(text: str, translation: str, source: str, target: str):
    """Save translation pair to vault for brain learning."""
    try:
        LINGUAS_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        filepath = LINGUAS_DIR / f"traducoes-{today}.md"

        if not filepath.exists():
            filepath.write_text(
                f"# Traducoes do Dia - {today}\n\n"
                f"Registro de traducoes realizadas pelo JARVIS.\n\n",
                encoding="utf-8"
            )

        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"- `{ts}` **{source}** → **{target}**: _{text}_ → _{translation}_\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"[Bilingual] Erro salvando nota: {e}")


def _get_api_key() -> str:
    """Read API key from config JSON (same as main.py)."""
    try:
        api_config = Path(__file__).parent.parent / "config" / "api_keys.json"
        if api_config.exists():
            import json as _json
            data = _json.loads(api_config.read_text(encoding="utf-8"))
            key = data.get("gemini_api_key", "")
            if key:
                return key
        # Try smart manager
        try:
            from tools.api_key_manager import get_api_manager
            mgr = get_api_manager()
            if mgr.current_key:
                return mgr.current_key
        except Exception:
            pass
    except Exception:
        pass
    # Last resort: env var
    import os
    return os.environ.get("OD_GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))


def _translate_via_gemini(text: str, source: str, target: str) -> dict:
    """Translate using Gemini API (free, 100+ languages)."""
    try:
        from google import genai
        client = genai.Client(api_key=_get_api_key())

        source_display = source if source != "auto" else _detect_lang(text)
        lang_names = LANG_NAMES

        src_name = lang_names.get(source_display.split("-")[0], source_display)
        tgt_name = lang_names.get(target.split("-")[0], target)

        prompt = (
            f"Translate the following text from {src_name} to {tgt_name}. "
            f"Return ONLY the translation, no explanations, no quotes.\n\n"
            f"Text: {text}"
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={
                "temperature": 0.1,
                "max_output_tokens": 500,
            }
        )

        translation = response.text.strip()
        if translation.startswith('"') and translation.endswith('"'):
            translation = translation[1:-1]

        return {
            "translation": translation,
            "detected_source": source_display,
            "success": True
        }
    except Exception as e:
        print(f"[Bilingual] Gemini error: {e}")
        return {"translation": None, "detected_source": source, "success": False}


def auto_translate(text: str, source: str = "auto", target: str = "en-US") -> dict:
    """Translate any text between any language pair."""
    text_clean = text.strip()

    _load_cache()

    # Detect language if auto
    detected = _detect_lang(text_clean) if source == "auto" else source.split("-")[0]

    # Check cache
    ck = _cache_key(text_clean, detected, target)
    if ck in TRANSLATION_CACHE:
        cached = TRANSLATION_CACHE[ck]
        return {
            "original": text_clean,
            "translation": cached,
            "confidence": "cached",
            "source": "cache",
            "detected": detected
        }

    # Try Gemini
    result = _translate_via_gemini(text_clean, detected, target)
    if result["success"] and result["translation"]:
        TRANSLATION_CACHE[ck] = result["translation"]
        _save_cache()
        _save_to_vault(text_clean, result["translation"], detected, target)

        return {
            "original": text_clean,
            "translation": result["translation"],
            "confidence": "high",
            "source": "gemini",
            "detected": detected
        }

    # Fallback
    return {
        "original": text_clean,
        "translation": f"[{detected} → {target}] {text_clean}",
        "confidence": "fallback",
        "source": "untranslated",
        "detected": detected
    }


def detect_and_translate(text: str, target: str = "en-US") -> dict:
    """Detect source language and translate to target."""
    return auto_translate(text, "auto", target)


def process_user_input(user_text: str, mode: str = "translate",
                       source: str = "auto", target: str = "en-US") -> dict:
    """Process user speech through bilingual mode."""
    result = {
        "original": user_text,
        "translation": None,
        "hints": [],
        "correction": None,
        "lesson": None,
        "response_text": "",
        "detected_lang": None,
        "target_display": LANG_NAMES.get(target.split("-")[0], target)
    }

    if mode == "translate":
        t = detect_and_translate(user_text, target)
        result["translation"] = t
        result["detected_lang"] = t.get("detected", source)
        src_display = LANG_NAMES.get(t.get("detected", "?"), t.get("detected", "?"))
        tgt_display = LANG_NAMES.get(target.split("-")[0], target)

        result["response_text"] = (
            f"💬 [{src_display}] *{user_text}*\n"
            f"   → [{tgt_display}] **{t['translation']}**"
        )
        if t.get("detected") != target.split("-")[0]:
            result["response_text"] += f"\n🌍 Detected: {src_display}"

    elif mode == "learn":
        t = detect_and_translate(user_text, source)
        result["translation"] = t
        result["detected_lang"] = t.get("detected", source)
        tgt_display = LANG_NAMES.get(target.split("-")[0], target)

        result["response_text"] = (
            f"🗣️ Voce disse: *{user_text}*\n"
            f"💡 Traducao: **{t['translation']}**\n"
            f"✅ Continue praticando {tgt_display}!"
        )

    elif mode == "teach":
        lesson = generate_lesson(target)
        result["lesson"] = lesson
        tgt_display = LANG_NAMES.get(target.split("-")[0], target)
        result["response_text"] = f"📚 **Hora de aprender {tgt_display}!**\n{lesson.get('formatted', '')}"

    return result


def generate_lesson(target: str = "en-US") -> dict:
    """Generate a mini-lesson using Gemini."""
    from google import genai

    tgt_display = LANG_NAMES.get(target.split("-")[0], target)

    prompt = (
        f"Create a mini language lesson for a Portuguese speaker learning {tgt_display}. "
        f"Generate 5 useful everyday phrases in {tgt_display} with their Portuguese translation, "
        f"a breakdown of each word, and a grammar tip. "
        f"Format the response as JSON with keys: 'category', 'phrases' (array of objects each with "
        f"'phrase', 'translation', 'breakdown', 'grammar_tip'). "
        f"Keep it beginner-friendly and practical."
    )

    try:
        client = genai.Client(api_key=_get_api_key())
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"temperature": 0.7, "max_output_tokens": 800}
        )
        text = response.text.strip()
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"\s*```", "", text)
        data = json.loads(text)

        formatted_lines = [f"## {data.get('category', 'Pratico')}"]
        for p in data.get("phrases", [])[:5]:
            formatted_lines.append(f"\n**{p['phrase']}**")
            formatted_lines.append(f"_Traducao:_ {p['translation']}")
            formatted_lines.append(f"_Detalhamento:_ {p['breakdown']}")
            if p.get("grammar_tip"):
                formatted_lines.append(f"_Dica:_ {p['grammar_tip']}")

        return {
            "category": data.get("category", "Frases Uteis"),
            "phrases": data.get("phrases", []),
            "formatted": "\n".join(formatted_lines)
        }
    except Exception as e:
        print(f"[Bilingual] Erro aula: {e}")
        return {
            "category": f"Frases em {tgt_display}",
            "phrases": [],
            "formatted": f"Tente dizer algo em {tgt_display} e eu ajudo com a traducao!"
        }


def activate(mode: str = "translate", source: str = "auto", target: str = "en-US",
             target_display: str = None) -> str:
    """Activate bilingual mode for ANY language pair."""
    global BILINGUAL_STATE

    if not target_display:
        tgt = target.split("-")[0]
        target_display = LANG_NAMES.get(tgt, tgt.upper())

    BILINGUAL_STATE["active"] = True
    BILINGUAL_STATE["mode"] = mode
    BILINGUAL_STATE["source_lang"] = source
    BILINGUAL_STATE["target_lang"] = target
    BILINGUAL_STATE["target_display"] = target_display
    BILINGUAL_STATE["session_start"] = datetime.now().isoformat()
    BILINGUAL_STATE["words_learned"] = 0
    BILINGUAL_STATE["phrases_practiced"] = 0

    _load_cache()

    mode_names = {"translate": "Traducao Automatica", "learn": "Pratica de Idioma", "teach": "Professor"}
    mode_name = mode_names.get(mode, mode)
    src_label = source if source != "auto" else "Deteccao Automatica"
    tgt_label = target_display

    return (
        f"🌐 Modo Bilingue Universal ATIVADO — {mode_name}\n"
        f"{src_label} → {tgt_label} ({target})\n"
        f"100+ idiomas suportados. Cache local ativo."
    )


def deactivate() -> str:
    """Deactivate bilingual mode."""
    global BILINGUAL_STATE
    _save_cache()

    elapsed = 0
    if BILINGUAL_STATE["session_start"]:
        try:
            start = datetime.fromisoformat(BILINGUAL_STATE["session_start"])
            elapsed = int((datetime.now() - start).total_seconds() / 60)
        except:
            pass

    stats = (
        f"📊 Sessao: {elapsed} min | "
        f"{BILINGUAL_STATE['words_learned']} palavras | "
        f"{BILINGUAL_STATE['phrases_practiced']} frases | "
        f"{len(TRANSLATION_CACHE)} traducoes em cache"
    )
    BILINGUAL_STATE["active"] = False
    BILINGUAL_STATE["session_start"] = None
    return f"🌐 Modo Bilingue DESATIVADO.\n{stats}"


def get_cultural_context(lang_code: str) -> dict:
    """Return cultural context for a language, including idioms and etiquette."""
    ctx = CULTURAL_CONTEXT.get(lang_code, {})
    if not ctx:
        return {"available": False, "message": f"Cultural context for {lang_code} not yet loaded"}
    return {"available": True, "context": ctx}


def get_idiom(lang_code: str, idiom_key: str = None) -> dict:
    """Look up an idiom in a specific language, or list all."""
    ctx = CULTURAL_CONTEXT.get(lang_code, {})
    idioms = ctx.get("idioms", {})
    if idiom_key:
        meaning = idioms.get(idiom_key, f"Idiom '{idiom_key}' not found in {lang_code}")
        return {"language": lang_code, "idiom": idiom_key, "meaning": meaning}
    return {"language": lang_code, "idiom_count": len(idioms), "idioms": idioms}


def get_conjugation(lang_code: str, verb: str = None) -> dict:
    """Return verb conjugation table for a language."""
    conjugations = VERB_CONJUGATIONS.get(lang_code, {})
    if not conjugations:
        return {"available": False, "message": f"Conjugation data for {lang_code} not loaded"}
    if verb:
        v = conjugations.get(verb, None)
        if v:
            return {"language": lang_code, "verb": verb, "forms": v}
        return {"language": lang_code, "message": f"Verb '{verb}' not found. Available: {list(conjugations.keys())}"}
    return {"language": lang_code, "available_verbs": list(conjugations.keys()), "full_data": conjugations}


def get_phonetic_info(script_type: str = None) -> dict:
    """Return phonetic/script information for a writing system."""
    if script_type:
        info = PHONETIC_INFO.get(script_type, {})
        if info:
            return {"script": script_type, "info": info}
        return {"available": False, "message": f"Info for '{script_type}' not found"}
    return {"available_scripts": list(PHONETIC_INFO.keys()), "all": PHONETIC_INFO}


def translate_with_context(text: str, target: str = "en-US") -> dict:
    """Translate AND return cultural context for the target language."""
    tgt_code = target.split("-")[0]
    trans = auto_translate(text, "auto", target)
    ctx = get_cultural_context(tgt_code)
    trans["cultural_context"] = ctx
    return trans


def bilingual_status() -> dict:
    """Return current bilingual state."""
    s = BILINGUAL_STATE
    return {
        "active": s["active"],
        "mode": s["mode"],
        "from": s["source_lang"],
        "to": s["target_lang"],
        "display": s["target_display"],
        "words_learned": s["words_learned"],
        "phrases_practiced": s["phrases_practiced"],
        "cache_size": len(TRANSLATION_CACHE),
        "session_start": s["session_start"]
    }
