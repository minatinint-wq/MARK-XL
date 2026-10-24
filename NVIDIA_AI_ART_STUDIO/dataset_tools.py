from __future__ import annotations
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from media_inputs import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, validate_image, validate_video

DATASET_CATALOG = [
    {
        "name": "DiffusionDB - imagens sinteticas e prompts",
        "url": "https://huggingface.co/datasets/poloclub/diffusiondb",
        "description": "Pares de imagens sinteticas e prompts. Util para estudar condicionamento por texto e selecionar um subconjunto de treino. O conjunto completo ocupa terabytes.",
        "license": "CC0 declarada na ficha. Revise a origem e o conteudo do subconjunto.",
        "usage": "Selecione um subconjunto no site. Nao e um LoRA pronto nem melhora automaticamente o gerador.",
    },
    {
        "name": "FineVideo - videos com anotacoes",
        "url": "https://huggingface.co/datasets/HuggingFaceFV/finevideo",
        "description": "Videos com descricoes temporais, cenas e perguntas/respostas. Voltado a compreensao de video; treino de geracao exige recortar e legendar os clipes.",
        "license": "Creative Commons conforme cada video; preserve atribuicao e proveniencia. Acesso exige aceitar os termos no site.",
        "usage": "Use apenas o subconjunto necessario e acompanhe as atualizacoes dos mantenedores. O conjunto completo tem centenas de GB.",
    },
]

DATASET_ROOT = Path(__file__).resolve().parent / "datasets"


def build_dataset(source: Path, destination: Path, kind: str) -> dict:
    source = source.resolve()
    if not source.is_dir():
        raise ValueError("Escolha uma pasta de imagens ou videos.")
    if kind not in {"image", "video"}:
        raise ValueError("Tipo de dataset invalido.")
    if destination.exists():
        raise ValueError("O destino ja existe. Escolha uma pasta nova.")
    extensions = IMAGE_EXTENSIONS if kind == "image" else VIDEO_EXTENSIONS
    files = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in extensions)
    if not files:
        raise ValueError("Nenhum arquivo compativel encontrado na pasta escolhida.")
    if len(files) > 500:
        raise ValueError("Prepare um subconjunto de ate 500 arquivos por vez.")
    if sum(p.stat().st_size for p in files) > 2 * 1024**3:
        raise ValueError("Selecione um subconjunto de ate 2 GB.")
    records, pending, skipped = [], [], []
    for file in files:
        caption_file = file.with_suffix(".txt")
        caption = ""
        if caption_file.exists():
            if caption_file.stat().st_size > 65536:
                skipped.append({"file": file.name, "reason": "Legenda TXT maior que 64 KB."})
                continue
            caption = caption_file.read_text(encoding="utf-8-sig").strip()
        if not caption:
            pending.append(file.name)
            continue
        try:
            info = (validate_image if kind == "image" else validate_video)(file)
            records.append((file, caption, info))
        except ValueError as exc:
            skipped.append({"file": file.name, "reason": str(exc)})
    if not records:
        raise ValueError("Nenhum par valido. Coloque uma legenda ao lado de cada arquivo: foto.png + foto.txt ou clipe.mp4 + clipe.txt.")
    destination.mkdir(parents=True)
    train_rows = []
    try:
        media = destination / "train"
        media.mkdir()
        seen = set()
        for file, caption, info in records:
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            if digest in seen:
                skipped.append({"file": file.name, "reason": "Arquivo duplicado."})
                continue
            seen.add(digest)
            # Stable safe names avoid collisions between JPG/PNG with the same stem.
            name = digest[:16] + file.suffix.lower()
            shutil.copy2(file, media / name)
            (media / (Path(name).stem + ".txt")).write_text(caption, encoding="utf-8")
            train_rows.append({"file_name": name, "text": caption})
        (media / "metadata.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in train_rows), encoding="utf-8")
        manifest = {
            "kind": kind, "examples": len(train_rows), "missing_captions": pending, "skipped": skipped,
            "created_at": datetime.now().isoformat(timespec="seconds"), "training_started": False,
            "format": "imagefolder" if kind == "image" else "video files + TXT captions + metadata.jsonl",
        }
        (destination / "dataset_report.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        (destination / "README.txt").write_text(
            "DATASET LOCAL PARA TREINAMENTO\n\n"
            "Cada exemplo tem um arquivo de midia e uma legenda TXT. metadata.jsonl contem file_name e text.\n"
            "Imagens: compativel com o formato ImageFolder do Hugging Face.\n"
            "Videos: adapte o manifesto ao trainer escolhido; mantenha os pares MP4/TXT.\n"
            "Revise as legendas e reserve exemplos de validacao antes de treinar.\n"
            "Os arquivos originais foram preservados. A proveniencia e a permissao de uso devem acompanhar o treino.\n"
            "Nenhum treino foi iniciado. O Space publico do ZeroGPU nao recebe este dataset automaticamente.\n"
            "Para LoRA ou ajuste de um gerador de video, escolha primeiro o modelo e um ambiente com GPU compativel.\n",
            encoding="utf-8",
        )
        return {"destination": str(destination), **manifest}
    except Exception:
        # Keep partial material for diagnosis; never report it as a completed dataset.
        (destination / "INCOMPLETE.txt").write_text("Exportacao interrompida; nao use este conjunto para treino.", encoding="utf-8")
        raise
