"""Extract explicit video settings without inventing attachment paths."""
import re
import unicodedata
from pathlib import Path


def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)).casefold()


def parse_video_request(text):
    original = " ".join(str(text or "").strip().split())
    normalized = normalize(original)
    if re.search(r"\b(?:nao|nunca)\s+(?:gere|gerar|crie|criar|faca|fazer|produza|produzir|monte|montar)\b", normalized):
        return None
    if re.search(r"\b(?:configure|configurar|conectar|conecte|login)\b", normalized) and ("hugging" in normalized or "zerogpu" in normalized):
        return {"action": "hf_setup"}
    if re.search(r"\b(?:abra|abrir|abre|mostrar)\b", normalized) and "dataset" in normalized:
        return {"action": "datasets"}
    if not re.search(r"\bvideos?\b", normalized):
        return None
    opening = bool(re.search(r"\b(?:abra|abrir|abre|inicie|iniciar)\b", normalized) and re.search(r"\b(?:studio|estudio|laboratorio|lab)\b", normalized))
    creating = bool(re.search(r"\b(?:gere|gerar|gera|crie|criar|cria|faca|fazer|faz|produza|produzir|monte|montar|quero)\b", normalized))
    saving = bool(re.search(r"\b(?:salve|salvar|defina|definir)\b", normalized) and "padrao" in normalized)
    if not (opening or creating or saving):
        return None
    request = {"action": "save_defaults" if saving else "open" if opening and not creating else "generate"}
    words = {"dois": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
             "onze": 11, "doze": 12, "treze": 13, "quatorze": 14, "catorze": 14, "quinze": 15, "dezesseis": 16,
             "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20, "trinta": 30, "um": 1, "uma": 1}
    duration_match = re.search(r"\b(\d+(?:[.,]\d+)?|" + "|".join(words) + r")\s*(segundos?|segs?|s|minutos?|mins?)\b", normalized)
    if duration_match:
        value, unit = duration_match.groups()
        request["duration"] = (words[value] if value in words else float(value.replace(",", "."))) * (60 if unit.startswith("min") else 1)
    if re.search(r"\b(?:minimax|h3)\b", normalized):
        request["model"] = "h3"
    elif re.search(r"\bltx", normalized):
        request["model"] = "ltx"
    if re.search(r"\b(?:economico|economy|economica)\b", normalized):
        request["quality"] = "economy"
    elif re.search(r"\b(?:detalhado|detalhada|detail)\b", normalized):
        request["quality"] = "detail"
    if re.search(r"\b(?:vertical|retrato|portrait)\b|9\s*:\s*16", normalized):
        request["format"] = "vertical"
    elif re.search(r"\b(?:quadrado|square)\b|1\s*:\s*1", normalized):
        request["format"] = "square"
    elif re.search(r"\b(?:paisagem|horizontal|landscape)\b|16\s*:\s*9", normalized):
        request["format"] = "landscape"
    paths = re.findall(r'["\']([^"\']+\.(?:png|jpe?g|webp|bmp|mp4|mov|webm|avi|mkv))["\']', original, flags=re.I)
    image_paths, video_paths = [], []
    for path in paths:
        (video_paths if Path(path).suffix.lower() in {".mp4", ".mov", ".webm", ".avi", ".mkv"} else image_paths).append(path)
    if video_paths:
        request.update(input_mode="video", reference_video=video_paths[0])
    elif image_paths:
        request.update(input_mode="frames" if len(image_paths) > 1 else "image", first_image=image_paths[0])
        if len(image_paths) > 1:
            request["last_image"] = image_paths[1]
    elif re.search(r"\b(?:usando|use|com|a partir de)\s+(?:(?:a|esta|essa|minha|uma)\s+)?(?:imagem|foto)\b", normalized):
        request["input_mode"] = "frames" if "final" in normalized else "image"
    elif "video de referencia" in normalized or "video como referencia" in normalized:
        request["input_mode"] = "video"
    cleaned = re.sub(r"^\s*jarvis[\s,;:.-]*", "", original, flags=re.I)
    match = re.search(r"\bv[ií]deo\b", cleaned, flags=re.I)
    scene = cleaned[match.end():] if match else cleaned
    for path in paths:
        scene = scene.replace('"' + path + '"', "").replace("'" + path + "'", "")
    # Only remove the duration expression; keep the user's scene and artistic constraints.
    scene = re.sub(r"\b(?:\d+(?:[.,]\d+)?|" + "|".join(words) + r")\s*(?:segundos?|segs?|s|minutos?|mins?)\b", "", scene, flags=re.I)
    scene = re.sub(r"^\s*(?:(?:de|da|do|sobre|mostrando|com)\s+)+", "", scene, flags=re.I).strip(" ,.;:-")
    scene = re.sub(r"\s+", " ", scene)
    if request["action"] == "generate":
        if len(scene) < 4 or scene.casefold() in {"de", "do", "da"}:
            request["action"] = "open"
        else:
            request["prompt"] = scene
    return request
