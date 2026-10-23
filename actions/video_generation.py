"""Launch the shared ZeroGPU Studio with the user's duration and media inputs."""
from __future__ import annotations
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from actions.runtime_identity import APP_ROOT
from typing import Any

USER_HOME = Path.home()
STUDIO = USER_HOME / "Desktop" / "NVIDIA_AI_ART_STUDIO" / "art_studio.py"
WORKER = STUDIO.parent / "hf_video_worker.py"
BUNDLED_PYTHON = APP_ROOT / "Python" / "bin" / "python.exe"
OUTPUT_DIR = STUDIO.parent / "videos"
LOG_DIR = APP_ROOT / "logs"
LAUNCH_LOG = LOG_DIR / "video_generation.jsonl"
STUDIO_LOG = LOG_DIR / "video_studio.log"
_FORMAT_ALIASES = {
    "vertical": "vertical", "portrait": "vertical", "retrato": "vertical", "9:16": "vertical",
    "square": "square", "quadrado": "square", "1:1": "square",
    "landscape": "landscape", "paisagem": "landscape", "horizontal": "landscape", "16:9": "landscape",
}
_ASPECTS = {"landscape": "16:9 (Landscape)", "vertical": "9:16 (Portrait)", "square": "1:1 (Square)"}


def _modules():
    if str(STUDIO.parent) not in sys.path:
        sys.path.insert(0, str(STUDIO.parent))
    from video_options import VIDEO_PROVIDERS, video_settings
    from studio_preferences import load_video_preferences, save_video_preferences
    return VIDEO_PROVIDERS, video_settings, load_video_preferences, save_video_preferences


def resolve_options(params):
    models, validate, load_defaults, _ = _modules()
    defaults = load_defaults()
    raw_model = str(params.get("model") or params.get("provider") or defaults["provider"]).casefold()
    model = {"ltx-2.5": "ltx", "ltx2.5": "ltx", "minimax": "h3", "minimax h3": "h3", "zerogpu": defaults["provider"]}.get(raw_model, raw_model)
    first = str(params.get("first_image") or params.get("image_path") or "").strip()
    last = str(params.get("last_image") or "").strip()
    video = str(params.get("reference_video") or params.get("video_path") or "").strip()
    mode = str(params.get("input_mode") or ("video" if video else "frames" if last else "image" if first else "text")).casefold()
    if mode not in {"text", "image", "frames", "video"}:
        raise ValueError("Modo invalido. Use text, image, frames ou video.")
    if mode == "video" and not (params.get("model") or params.get("provider")):
        model = "h3"
    if model not in models:
        raise ValueError("Use modelo ltx ou h3.")
    raw_quality = str(params.get("quality") or defaults["quality"]).casefold()
    quality = {"economico": "economy", "econômico": "economy", "detalhado": "detail"}.get(raw_quality, raw_quality)
    default_format = next(key for key, value in _ASPECTS.items() if value == defaults["aspect_ratio"])
    raw_format = str(params.get("format") or params.get("aspect_ratio") or default_format).casefold()
    if raw_format not in _FORMAT_ALIASES:
        raise ValueError("Formato invalido. Use landscape, vertical ou square.")
    video_format = _FORMAT_ALIASES[raw_format]
    duration = float(params.get("duration", params.get("seconds", defaults["duration"])))
    validate(model, quality, _ASPECTS[video_format], duration)
    if mode == "video" and (model != "h3" or duration < 5):
        raise ValueError("Video de referencia requer H3 e duracao de 5 a 14 segundos.")
    if mode == "text" and (first or last or video):
        raise ValueError("O modo text nao usa anexos; escolha o modo correspondente.")
    if mode in {"image", "frames"} and video or mode == "video" and (first or last):
        raise ValueError("Use imagens ou video de referencia em cada geracao.")
    if mode == "image" and last:
        raise ValueError("Para usar imagem final, escolha o modo frames.")
    from media_inputs import validate_image, validate_video
    for path in (first, last):
        if path:
            validate_image(path)
    if video:
        validate_video(video)
    return {"model": model, "quality": quality, "duration": int(duration), "format": video_format,
            "input_mode": mode, "first_image": first, "last_image": last, "reference_video": video}


def _launch(prompt="", options=None, generate=False, account=False, datasets=False):
    python = BUNDLED_PYTHON if BUNDLED_PYTHON.exists() else Path(sys.executable)
    args = [str(python), str(STUDIO), "--tab", "datasets" if datasets else "video"]
    if account:
        args.append("--hf-setup")
    if prompt:
        args += ["--video-prompt", prompt]
    if options:
        for key, flag in [("model", "--video-model"), ("quality", "--video-quality"),
                          ("duration", "--video-duration"), ("format", "--video-format"),
                          ("input_mode", "--video-input-mode"), ("first_image", "--first-image"),
                          ("last_image", "--last-image"), ("reference_video", "--reference-video")]:
            if options.get(key) not in (None, ""):
                args += [flag, str(options[key])]
    if generate:
        args.append("--generate-video")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LAUNCH_LOG.open("a", encoding="utf-8") as history:
        history.write(json.dumps({"created_at": datetime.now().isoformat(timespec="seconds"),
                                  "prompt": prompt, "options": options, "generate": generate}, ensure_ascii=False) + "\n")
    with STUDIO_LOG.open("a", encoding="utf-8") as log:
        subprocess.Popen(args, cwd=str(STUDIO.parent), stdout=log, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0))


def video_generation(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    prompt = str(params.get("prompt") or "").strip()
    action = str(params.get("action") or ("generate" if prompt else "open")).casefold()
    if action.startswith("cpu_"):
        from actions.animation_cpu import animation_cpu
        return animation_cpu(params)
    if not STUDIO.exists() or not WORKER.exists():
        return "NVIDIA Studio nao encontrado."
    if action in {"hf_setup", "huggingface", "login", "account"}:
        _launch(account=True)
        return "Abri a configuracao protegida do Hugging Face no Studio. Cole o token la."
    if action in {"datasets", "dataset"}:
        _launch(datasets=True)
        return "Abri a area de datasets para preparar arquivos de treinamento."
    try:
        options = resolve_options(params)
        models, _, load_defaults, save_defaults = _modules()
        if action in {"status", "config", "providers"}:
            return (f"ZeroGPU pronto. Padrao: {models[options['model']]['label']}, {options['duration']} segundos, "
                    f"{options['quality']}. LTX: 2 a 20s; H3: 2 a 14s (referencia de video: 5 a 14s). "
                    "A duracao depende da cota de GPU. A conta e os anexos sao configurados no Studio.")
        if action in {"save_defaults", "defaults"}:
            save_defaults(options["model"], options["quality"], options["duration"], _ASPECTS[options["format"]])
            return f"Padrao compartilhado salvo: {options['model']}, {options['duration']} segundos, {options['quality']}."
        if action not in {"generate", "create", "criar", "open", "abrir", "studio"}:
            return "Use generate, open, status, save_defaults, hf_setup ou datasets."
        mode = options["input_mode"]
        missing = (mode in {"image", "frames"} and not options["first_image"]) or (mode == "frames" and not options["last_image"]) or (mode == "video" and not options["reference_video"])
        generate = action in {"generate", "create", "criar"} and bool(prompt) and not missing
        _launch(prompt[:1800], options, generate)
        if missing:
            return f"Abri o Studio com {options['duration']} segundos. Anexe os arquivos solicitados e clique em Gerar."
        if not generate:
            return f"Abri o Studio com {models[options['model']]['label']} e {options['duration']} segundos."
        return (f"Iniciei a geracao com {models[options['model']]['label']}, {options['duration']} segundos, "
                f"modo {mode}, formato {options['format']}. O Studio acompanha a fila e salva o MP4.")
    except (ValueError, TypeError, OSError) as exc:
        return "Nao iniciei a geracao: " + str(exc)
