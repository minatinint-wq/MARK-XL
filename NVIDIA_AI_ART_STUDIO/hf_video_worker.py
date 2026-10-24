from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

from gradio_client import Client, handle_file
from hf_auth import huggingface_token, safe_error
from media_inputs import validate_image, validate_video, image_data_uri
from video_options import H3_CANVASES, H3_GENERATION_PRESETS, VIDEO_PROVIDERS, video_settings

DEFAULT_KEYS = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
_active_job = None


def emit(event: str, **data: Any) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=True), flush=True)


def stop_handler(_signum, _frame) -> None:
    global _active_job
    if _active_job is not None:
        try:
            _active_job.cancel()
        except Exception:
            pass
    emit("error", message="Geracao cancelada.")
    raise SystemExit(130)


def result_video_url(result: Any, provider: str = "ltx", source: str = "") -> str:
    if provider == "ltx":
        if not isinstance(result, dict):
            raise RuntimeError("O Space devolveu uma resposta inesperada.")
        if result.get("status") != "completed":
            error = result.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(message or f"Tarefa terminou com status {result.get('status')}.")
        videos = (result.get("result") or {}).get("videos") or []
        if not videos:
            raise RuntimeError("A tarefa terminou sem um arquivo de video.")
        value = videos[0]
    else:
        # The H3 API returns [FileData, timing report, refined prompt].
        value = result[0] if isinstance(result, (list, tuple)) and result else result
    if isinstance(value, dict) and "video" in value:
        value = value["video"]
    if isinstance(value, dict):
        url = value.get("url")
        if url:
            value = urljoin(source, str(url))
        elif value.get("path") and source:
            value = source.rstrip("/") + "/gradio_api/file=" + quote(str(value["path"]), safe="/")
        else:
            raise RuntimeError("O Space nao informou o endereco do video.")
    if not isinstance(value, str) or urlsplit(value).scheme not in {"https", "http"}:
        raise RuntimeError("O Space nao devolveu uma URL valida para baixar o video.")
    return value


def download(url: str, output: Path) -> None:
    emit("downloading")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Jarvis-Video-Studio/2.0"})
        with urllib.request.urlopen(request, timeout=300) as response, temporary.open("wb") as target:
            shutil.copyfileobj(response, target)
        if temporary.stat().st_size < 1024:
            raise RuntimeError("O arquivo de video recebido esta vazio ou incompleto.")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def video_metadata(output: Path) -> dict:
    import cv2
    capture = cv2.VideoCapture(str(output))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        readable, _ = capture.read()
    finally:
        capture.release()
    if not readable or fps <= 0 or frames <= 0:
        raise RuntimeError("O arquivo recebido nao pode ser reproduzido como video.")
    return {"video_seconds": round(frames / fps, 2), "output_fps": fps}


def validate_inputs(args: argparse.Namespace) -> None:
    mode = args.input_mode
    if mode == "text":
        if args.first_image or args.last_image or args.reference_video:
            raise ValueError("Escolha o modo de entrada correspondente aos arquivos anexados.")
        return
    if mode in {"image", "frames"}:
        if not args.first_image:
            raise ValueError("Anexe a imagem inicial.")
        validate_image(args.first_image)
        if mode == "frames":
            if not args.last_image:
                raise ValueError("Anexe tambem a imagem final.")
            validate_image(args.last_image)
        elif args.last_image:
            raise ValueError("Escolha Imagens inicial e final para usar os dois arquivos.")
        if args.reference_video:
            raise ValueError("Use imagens ou video de referencia em cada geracao.")
    elif mode == "video":
        if args.provider != "h3":
            raise ValueError("Video de referencia e aceito pelo MiniMax H3. Selecione esse modelo.")
        if not args.reference_video:
            raise ValueError("Anexe um video de referencia.")
        validate_video(args.reference_video)
        if args.duration < 5:
            raise ValueError("Com video de referencia, escolha pelo menos 5 segundos de saida.")
        if args.first_image or args.last_image:
            raise ValueError("Use imagens ou video de referencia em cada geracao.")


def request_spec(args: argparse.Namespace) -> tuple[str, dict]:
    validate_inputs(args)
    settings = video_settings(args.provider, args.quality, args.aspect_ratio, args.duration)
    width = args.width if args.width is not None else settings["width"]
    height = args.height if args.height is not None else settings["height"]
    if width <= 0 or height <= 0 or width % 32 or height % 32:
        raise ValueError("As dimensoes precisam ser positivas e multiplas de 32.")
    if args.provider == "ltx":
        gpu_duration = args.gpu_duration if args.gpu_duration is not None else settings["gpu_duration"]
        if not 1 <= gpu_duration <= 120:
            raise ValueError("A reserva de GPU deve ficar entre 1 e 120 segundos.")
        params = {
            "task_type": {"text": "t2v", "image": "i2v", "frames": "flf2v"}[args.input_mode], "prompt": args.prompt,
            "negative_prompt": args.negative_prompt,
            "resolution": args.resolution or settings["resolution"],
            "aspect_ratio": args.aspect_ratio, "width": width, "height": height,
            "duration": args.duration, "fps": "24fps", "seed": args.seed,
            "use_spatial_upscaler": False, "use_temporal_upscaler": False,
            "zero_gpu_duration": gpu_duration,
        }
        if args.first_image:
            params["start_image"] = image_data_uri(args.first_image)
        if args.last_image:
            params["end_image"] = image_data_uri(args.last_image)
        return "/run", {"json_params": json.dumps(params)}
    if (width, height) not in H3_CANVASES:
        raise ValueError("Esse tamanho nao e aceito pelo Space do MiniMax H3.")
    return "/generate", {
        "prompt": args.prompt,
        "image_path": handle_file(str(args.first_image)) if args.first_image else None,
        "last_image_path": handle_file(str(args.last_image)) if args.last_image else None,
        "references": [handle_file(str(args.reference_video))] if args.reference_video else None,
        "canvas": H3_CANVASES[(width, height)], "duration": args.duration,
        "steps": 8 if args.quality == "economy" and args.input_mode != "video" else 28, "seed": args.seed,
        "upsample": False,
        "generation_preset": H3_GENERATION_PRESETS["detail" if args.input_mode == "video" else args.quality],
    }


def check_api(client: Client, api_name: str, params: dict) -> None:
    api = client.view_api(return_format="dict", print_info=False)
    endpoint = api.get("named_endpoints", {}).get(api_name)
    if endpoint is None:
        raise RuntimeError(f"A API {api_name} nao esta disponivel neste Space.")
    available = {item.get("parameter_name") for item in endpoint.get("parameters", [])}
    missing = set(params) - available
    if missing:
        raise RuntimeError("A API do Space mudou; parametros ausentes: " + ", ".join(sorted(missing)))


def run(args: argparse.Namespace) -> Path | None:
    global _active_job
    api_name, params = request_spec(args)
    token = huggingface_token()
    model = VIDEO_PROVIDERS[args.provider]
    space = args.space or model["space"]
    emit("connecting", space=space, model=model["label"], authenticated=bool(token))
    # Keep the token inside the client; downloads use the public Space output URL.
    client = Client(space, token=token or False, verbose=False, download_files=False)
    check_api(client, api_name, params)
    if args.check:
        return None
    try:
        _active_job = client.submit(api_name=api_name, **params)
        last_signature = None
        while not _active_job.done():
            status = _active_job.status()
            code = getattr(getattr(status, "code", None), "value", None) or str(getattr(status, "code", ""))
            rank, eta = getattr(status, "rank", None), getattr(status, "eta", None)
            signature = (code, rank, int(eta or 0))
            if signature != last_signature:
                if code in {"PROCESSING", "LOG", "ITERATING", "GENERATING"}:
                    emit("generating", code=code)
                else:
                    emit("queued", code=code, rank=rank, eta=eta)
                last_signature = signature
            time.sleep(1.5)
        result = _active_job.result()
    finally:
        _active_job = None
    url = result_video_url(result, args.provider, client.src)
    download(url, args.output)
    return args.output


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jarvis video worker: LTX-2.5 / MiniMax H3 via ZeroGPU")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--provider", choices=VIDEO_PROVIDERS, default="ltx")
    parser.add_argument("--quality", choices=("economy", "detail"), default="detail")
    parser.add_argument("--input-mode", choices=("text", "image", "frames", "video"), default="text")
    parser.add_argument("--first-image", type=Path)
    parser.add_argument("--last-image", type=Path)
    parser.add_argument("--reference-video", type=Path)
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--space", default=None)
    parser.add_argument("--resolution", default=None)
    parser.add_argument("--aspect-ratio", default="16:9 (Landscape)")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--gpu-duration", type=int, default=None)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if not args.check and (not args.prompt.strip() or args.output is None):
        parser.error("--prompt e --output sao obrigatorios para gerar um video")
    return args


def main() -> int:
    args = parse_args()
    signal.signal(signal.SIGINT, stop_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop_handler)
    started = time.time()
    try:
        output = run(args)
        metadata = video_metadata(output) if output else {}
        if output and metadata["video_seconds"] < args.duration - 1:
            raise RuntimeError(
                f'O Space devolveu {metadata["video_seconds"]}s, mas foram pedidos {args.duration:g}s. '
                f'O arquivo foi salvo em {output}.'
            )
        emit("complete", output=str(output) if output else "", seconds=round(time.time() - started, 2),
             provider="huggingface-zerogpu", model=VIDEO_PROVIDERS[args.provider]["label"],
             requested_seconds=args.duration, check=args.check, **metadata)
        return 0
    except Exception as exc:
        message = safe_error(exc)
        if "larger than the maximum allowed" in message.casefold():
            # Keep the free route: do not pass through the provider's subscription upsell.
            message = (
                "O Space pediu mais tempo de GPU do que sua conta permite. "
                "Use o modo Economico, reduza a duracao ou escolha LTX-2.5. "
                "Se estiver sem login, configure um token de conta gratuita Hugging Face no Jarvis."
            )
        elif any(term in message.casefold() for term in ("402", "429", "quota")):
            message += " | A cota do ZeroGPU pode ter acabado. Aguarde a renovacao ou tente uma duracao menor."
        elif any(term in message.casefold() for term in ("timeout", "timed out", "gpu task aborted")):
            message += " | Tente o modo Economico ou um video mais curto."
        emit("error", message=message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
