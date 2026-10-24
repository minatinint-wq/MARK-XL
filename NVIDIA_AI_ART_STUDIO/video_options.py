from __future__ import annotations

# Public Space contracts checked on 2026-09-09.
VIDEO_PROVIDERS = {
    "ltx": {"label": "LTX-2.5", "space": "RioShiina/LTX-2.5", "min_duration": 2, "max_duration": 20},
    "h3": {"label": "MiniMax H3", "space": "mrfakename/minimax-h3-ultra-fast", "min_duration": 2, "max_duration": 14},
}
VIDEO_FORMATS = {
    "Paisagem 16:9": "16:9 (Landscape)",
    "Vertical 9:16": "9:16 (Portrait)",
    "Quadrado 1:1": "1:1 (Square)",
}
VIDEO_QUALITIES = {"Economico": "economy", "Detalhado": "detail"}
DIMENSIONS = {
    "economy": {"16:9": (960, 544), "9:16": (544, 960), "1:1": (544, 544)},
    "detail": {"16:9": (1344, 768), "9:16": (768, 1344), "1:1": (1024, 1024)},
}
H3_CANVASES = {
    (960, 544): "960x544 · 16:9 fast",
    (544, 960): "544x960 · 9:16 fast",
    (544, 544): "544x544 · 1:1 fast",
    (1344, 768): "1344x768 · 16:9 full",
    (768, 1344): "768x1344 · 9:16 full",
    (1024, 1024): "1024x1024 · 1:1 max",
}
H3_GENERATION_PRESETS = {
    "economy": "Turbo 8-step — faster, cleaner",
    "detail": "Balanced — best overall (recommended)",
}


def video_settings(provider: str, quality: str, aspect_ratio: str, duration: float) -> dict:
    if provider not in VIDEO_PROVIDERS:
        raise ValueError("Modelo de video desconhecido.")
    if quality not in DIMENSIONS:
        raise ValueError("Modo de qualidade desconhecido.")
    model = VIDEO_PROVIDERS[provider]
    if not model["min_duration"] <= duration <= model["max_duration"] or not float(duration).is_integer():
        raise ValueError(
            f'{model["label"]}: escolha uma duracao inteira entre '
            f'{model["min_duration"]} e {model["max_duration"]} segundos.'
        )
    ratio = aspect_ratio.split()[0]
    if ratio not in DIMENSIONS[quality]:
        raise ValueError("Formato de video nao suportado.")
    width, height = DIMENSIONS[quality][ratio]
    return {
        "width": width, "height": height,
        "resolution": "544p" if quality == "economy" else "768p",
        "canvas": H3_CANVASES[(width, height)],
        # Reservation time is not the video's duration or a guarantee of completion.
        "gpu_duration": min(120, max(60, round(duration * 12 * width * height / (1344 * 768)))),
    }
