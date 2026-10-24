from __future__ import annotations
import base64
import io
import math
from pathlib import Path
from PIL import Image, ImageOps

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
IMAGE_FILTER = "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)"
VIDEO_FILTER = "Videos (*.mp4 *.mov *.webm *.avi *.mkv)"


def validate_image(path: str | Path) -> dict:
    source = Path(path)
    if not source.is_file() or source.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Selecione uma imagem PNG, JPG, WEBP ou BMP existente.")
    if source.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("A imagem deve ter no maximo 20 MB.")
    try:
        with Image.open(source) as image:
            if image.width * image.height > 25_000_000:
                raise ValueError("A imagem deve ter no maximo 25 megapixels.")
            if image.width < 32 or image.height < 32:
                raise ValueError("A imagem deve ter ao menos 32 pixels em cada lado.")
            image.verify()
            return {"width": image.width, "height": image.height}
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Nao foi possivel abrir esta imagem.") from exc


def prepared_image(path: str | Path) -> Image.Image:
    validate_image(path)
    with Image.open(path) as image:
        result = ImageOps.exif_transpose(image).convert("RGB")
        result.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
        return result


def image_data_uri(path: str | Path) -> str:
    buffer = io.BytesIO()
    prepared_image(path).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def prepare_image_file(path: str | Path, target: Path) -> Path:
    prepared_image(path).save(target, format="PNG")
    return target


def validate_video(path: str | Path) -> dict:
    import cv2
    source = Path(path)
    if not source.is_file() or source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("Selecione um video MP4, MOV, WEBM, AVI ou MKV existente.")
    if source.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("A referencia deve ter no maximo 50 MB.")
    capture = cv2.VideoCapture(str(source))
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        ok, _ = capture.read()
        seconds = frames / fps if fps > 0 else 0
        if not ok or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("Nao foi possivel ler este video.")
        if seconds > 30.1:
            raise ValueError("Use um trecho de ate 30 segundos como referencia.")
        return {"duration": seconds, "fps": fps, "frames": int(frames)}
    finally:
        capture.release()
