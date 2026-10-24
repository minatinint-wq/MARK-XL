from __future__ import annotations
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit, quote
from gradio_client import Client, handle_file
from hf_auth import huggingface_token
from media_inputs import validate_image, prepare_image_file

IMAGE_SPACE = "black-forest-labs/FLUX.2-klein-4B"
IMAGE_MODEL_LABEL = "FLUX 2 Klein 4B - ZeroGPU (anexos)"


def image_request(prompt: str, seed: int, width: int, height: int, paths: list[Path]) -> dict:
    if len(paths) > 3:
        raise ValueError("Use ate 3 imagens de referencia.")
    if not prompt.strip():
        raise ValueError("Descreva a imagem ou a edicao desejada.")
    return {
        "prompt": prompt, "input_images": [{"image": handle_file(str(path)), "caption": None} for path in paths],
        "mode_choice": "Distilled (4 steps)", "seed": seed, "randomize_seed": False,
        "width": width, "height": height, "num_inference_steps": 4, "guidance_scale": 1.0,
        "prompt_upsampling": False,
    }


def generate_hf_image(prompt: str, seed: int, ratio: float, references: list[str]) -> bytes:
    # Prepare private temporary copies; source files are never edited.
    if len(references) > 3:
        raise ValueError("Use ate 3 imagens de referencia.")
    for path in references:
        validate_image(path)
    width, height = (1024, max(256, round(1024 / ratio / 8) * 8)) if ratio >= 1 else (max(256, round(1024 * ratio / 8) * 8), 1024)
    with tempfile.TemporaryDirectory(prefix="jarvis-image-") as temp:
        paths = [prepare_image_file(path, Path(temp) / f"reference-{i}.png") for i, path in enumerate(references)]
        params = image_request(prompt, seed, width, height, paths)
        client = Client(IMAGE_SPACE, token=huggingface_token() or False, verbose=False, download_files=False)
        api = client.view_api(return_format="dict", print_info=False)
        endpoint = api.get("named_endpoints", {}).get("/infer")
        if not endpoint or set(params) - {p["parameter_name"] for p in endpoint.get("parameters", [])}:
            raise RuntimeError("A API de imagens mudou ou esta indisponivel.")
        result = client.predict(api_name="/infer", **params)
        value = result[0] if isinstance(result, (tuple, list)) else result
        if isinstance(value, dict):
            url = value.get("url")
            value = urljoin(client.src + "/", url) if url else client.src.rstrip("/") + "/gradio_api/file=" + quote(str(value.get("path") or ""), safe="/")
        if not isinstance(value, str) or urlsplit(value).scheme not in {"http", "https"}:
            raise RuntimeError("A API nao retornou uma imagem para baixar.")
        with urllib.request.urlopen(value, timeout=120) as response:
            raw = response.read(25 * 1024 * 1024 + 1)
        if len(raw) > 25 * 1024 * 1024:
            raise RuntimeError("A imagem de resposta excedeu 25 MB.")
        from PIL import Image
        import io
        try:
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()
        except (OSError, ValueError) as exc:
            raise RuntimeError("O Space retornou uma imagem invalida.") from exc
        return raw
