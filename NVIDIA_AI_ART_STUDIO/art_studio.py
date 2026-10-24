from __future__ import annotations

import base64
from collections import deque
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

import cv2
import numpy as np

from video_options import VIDEO_FORMATS, VIDEO_PROVIDERS, VIDEO_QUALITIES, video_settings
from hf_auth import safe_error
from hf_settings import HuggingFaceDialog
from hf_image import IMAGE_MODEL_LABEL, generate_hf_image
from studio_input_widgets import MediaInput
from studio_preferences import load_video_preferences, save_video_preferences
from dataset_panel import DatasetPanel

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QSplitter, QTabWidget, QTextEdit, QVBoxLayout, QWidget, QScrollArea,
)

ROOT = Path(__file__).resolve().parent
JARVIS_ROOT = Path(os.environ.get("JARVIS_ROOT", str(ROOT.parent))).resolve()
OUTPUTS = ROOT / "outputs"
HISTORY = ROOT / "history.jsonl"
JARVIS_KEYS = Path(os.environ.get(
    "JARVIS_API_KEYS",
    str(JARVIS_ROOT / "config" / "api_keys.json"),
))

MODELS = {
    "FLUX 2 Klein 4B (recomendado)": (
        "black-forest-labs/flux.2-klein-4b",
        "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b",
    ),
    "FLUX 1 Schnell (rapido)": (
        "black-forest-labs/flux.1-schnell",
        "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell",
    ),
}

MODELS[IMAGE_MODEL_LABEL] = ("black-forest-labs/FLUX.2-klein-4B", "")

STYLES = {
    "Sem estilo extra": "",
    "Fotografia cinematografica": "cinematic photography, filmic lighting, high dynamic range",
    "Fotorrealista": "photorealistic, realistic materials, natural lighting, professional photography",
    "Concept art": "high-end concept art, detailed environment design, dramatic composition",
    "Anime": "premium anime illustration, expressive design, clean linework, detailed color",
    "Fantasia": "epic fantasy art, intricate details, atmospheric lighting, painterly realism",
    "Produto / publicidade": "premium product photography, studio lighting, clean commercial composition",
    "Editorial": "editorial art direction, sophisticated composition, bold controlled color palette",
}

RATIOS = {
    "Quadrado 1:1": 1.0,
    "Retrato 4:5": 4 / 5,
    "Paisagem 16:9": 16 / 9,
    "Story 9:16": 9 / 16,
}

BG, PANEL, LINE = "#080b10", "#101722", "#26384a"
CYAN, PURPLE, GREEN, RED = "#42dfff", "#a77bff", "#67efad", "#ff6f7d"
TEXT, MUTED = "#e4f5fa", "#78909c"
VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"
VISION_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
AUDIO_OUTPUTS = ROOT / "audio"
_WHISPER_MODEL = None
VIDEO_OUTPUTS = ROOT / "videos"
HF_VIDEO_WORKER = ROOT / "hf_video_worker.py"
STUDIO_PYTHON = Path(sys.executable)
VIDEO_PRESETS = VIDEO_FORMATS


def nvidia_key() -> str:
    if os.environ.get("NVIDIA_API_KEY", "").strip():
        return os.environ["NVIDIA_API_KEY"].strip()
    try:
        return str(json.loads(JARVIS_KEYS.read_text(encoding="utf-8")).get("nvidia_api_key") or "").strip()
    except Exception:
        return ""


def clip_prompt(text: str, limit: int = 800) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = max(head.rfind("."), head.rfind(","), head.rfind(" "))
    if cut >= int(limit * 0.82):
        head = head[:cut]
    return head.rstrip(" ,.;:") + "."


def render_prompt(prompt: str, style: str, negative: str) -> str:
    base = re.sub(r"\s+", " ", prompt).strip().rstrip(".")
    parts = [base]
    if style and style.casefold() not in base.casefold():
        parts.append(style)
    quality = "high quality, coherent composition, no watermark"
    if "no watermark" not in base.casefold():
        parts.append(quality)
    negative = re.sub(r"\s+", " ", negative).strip().rstrip(".")
    if negative and negative.casefold() not in base.casefold():
        parts.append("Avoid: " + negative)
    return clip_prompt(". ".join(parts) + ".", 800)


def decode_image(raw: bytes, content_type: str) -> bytes:
    if content_type.startswith("image/"):
        return raw
    try:
        data = json.loads(raw.decode("utf-8"))
        artifacts = data.get("artifacts") or []
        encoded = artifacts[0].get("base64") if artifacts else None
        if not encoded:
            images = data.get("data") or []
            encoded = images[0].get("b64_json") if images else None
        if encoded:
            return base64.b64decode(encoded.split(",", 1)[-1])
    except Exception:
        pass
    raise RuntimeError(raw.decode("utf-8", errors="replace")[:1200] or "Resposta NVIDIA sem imagem.")


def generate_nvidia(prompt: str, model_name: str, seed: int) -> bytes:
    prompt = clip_prompt(prompt, 800)
    key = nvidia_key()
    if not key:
        raise RuntimeError("Chave NVIDIA nao encontrada no Jarvis: " + str(JARVIS_KEYS))
    _model_id, endpoint = MODELS[model_name]
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"prompt": prompt, "seed": seed, "steps": 4}).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            return decode_image(response.read(), response.headers.get_content_type())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"NVIDIA HTTP {exc.code}: {exc.read(1200).decode('utf-8', errors='replace')}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha de conexao NVIDIA: {exc.reason}") from exc

def _contact_sheet(frames: list[np.ndarray]) -> np.ndarray:
    prepared = []
    for index, frame in enumerate(frames[:6], 1):
        item = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_AREA)
        cv2.rectangle(item, (0, 0), (112, 30), (5, 10, 18), -1)
        cv2.putText(item, f"QUADRO {index}", (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 230, 255), 1)
        prepared.append(item)
    while len(prepared) < 6:
        prepared.append(np.zeros((240, 320, 3), dtype=np.uint8))
    return np.vstack((np.hstack(prepared[:3]), np.hstack(prepared[3:6])))


def analyze_nvidia_camera(frames: list[np.ndarray], mode: str, question: str = "") -> str:
    if not frames:
        raise RuntimeError("Nenhum quadro da camera foi capturado.")
    key = nvidia_key()
    if not key:
        raise RuntimeError("Chave NVIDIA nao encontrada no Jarvis.")
    if mode == "Libras / gestos":
        image = _contact_sheet(frames)
        instruction = (
            "Os seis quadros estao em ordem temporal e mostram um gesto com as maos. "
            "Analise a sequencia e tente interpretar se ha um sinal de Libras. Diga o significado provavel, "
            "descreva o movimento observado e informe claramente quando estiver incerto. Nao invente."
        )
    else:
        image = frames[-1]
        if mode == "Pessoas":
            instruction = (
                "Analise as pessoas visiveis: quantidade, posicao, roupa, postura e acao aparente. "
                "Nao tente descobrir identidade nem atributos que nao estejam visiveis."
            )
        else:
            instruction = (
                "Reconheca os principais objetos e o ambiente. Liste o objeto, sua posicao aproximada "
                "e o que parece estar acontecendo na cena."
            )
    if question.strip():
        instruction += " Pergunta adicional: " + question.strip()
    instruction += " Responda somente em portugues brasileiro, de forma objetiva."
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 84])
    if not ok:
        raise RuntimeError("Nao foi possivel preparar a imagem da camera.")
    image_url = "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": "Voce e um analisador visual. Responda sempre em portugues brasileiro e sinalize incertezas."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": instruction},
            ]},
        ],
        "max_tokens": 420,
        "temperature": 0.15,
        "top_p": 0.7,
        "stream": False,
    }
    request = urllib.request.Request(
        VISION_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"NVIDIA Vision HTTP {exc.code}: {exc.read(1200).decode('utf-8', errors='replace')}") from exc
    text = str(data.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
    if not text:
        raise RuntimeError("O modelo visual NVIDIA nao retornou uma descricao.")
    return text


def transcribe_local_audio(path: str | Path, language: str = "auto") -> dict[str, str]:
    global _WHISPER_MODEL
    from faster_whisper import WhisperModel
    source = Path(path)
    if not source.exists():
        raise RuntimeError("Arquivo de audio nao encontrado.")
    if _WHISPER_MODEL is None:
        _WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8", local_files_only=True)
    options = {"beam_size": 3, "vad_filter": True}
    if language != "auto":
        options["language"] = language
    segments, info = _WHISPER_MODEL.transcribe(str(source), **options)
    transcript = " ".join(x.text.strip() for x in segments if x.text.strip()).strip()
    if not transcript:
        raise RuntimeError("Nenhuma fala foi detectada no audio.")
    return {"text": transcript, "language": str(getattr(info, "language", "") or ""), "path": str(source)}


def record_microphone(duration: int = 5, sample_rate: int = 16000) -> Path:
    import sounddevice as sd
    AUDIO_OUTPUTS.mkdir(parents=True, exist_ok=True)
    path = AUDIO_OUTPUTS / f"gravacao-{time.strftime('%Y%m%d-%H%M%S')}.wav"
    audio = sd.rec(duration * sample_rate, samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(audio.tobytes())
    return path


def save_image(raw: bytes, ratio_name: str, prompt: str) -> Path:
    image = QImage.fromData(raw)
    if image.isNull():
        raise RuntimeError("A NVIDIA retornou uma imagem invalida.")
    ratio = RATIOS[ratio_name]
    current = image.width() / max(1, image.height())
    if current > ratio:
        width = int(image.height() * ratio)
        image = image.copy((image.width() - width) // 2, 0, width, image.height())
    elif current < ratio:
        height = int(image.width() / ratio)
        image = image.copy(0, (image.height() - height) // 2, image.width(), height)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", prompt)[:42].strip("-").lower() or "arte"
    path = OUTPUTS / f"art-{time.strftime('%Y%m%d-%H%M%S')}-{slug}.png"
    if not image.save(str(path), "PNG", 96):
        raise RuntimeError("Nao foi possivel salvar a arte.")
    return path


def add_history(row: dict) -> None:
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def history_rows() -> list[dict]:
    if not HISTORY.exists():
        return []
    rows = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if Path(row.get("path", "")).exists():
                rows.append(row)
        except Exception:
            pass
    return rows[-100:][::-1]


class NvidiaCameraLab(QWidget):
    analyzed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.capture = None
        self.current_frame = None
        self.frames = deque(maxlen=6)
        self.ticks = 0
        self.busy = False
        self.detector = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 8, 4, 4)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self.camera_panel())
        split.addWidget(self.analysis_panel())
        split.setSizes([760, 400])
        root.addWidget(split, 1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.analyzed.connect(self.analysis_done)
        self.failed.connect(self.analysis_failed)

    def camera_panel(self):
        box = QFrame()
        box.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid {LINE};border-radius:8px;}}")
        lay = QVBoxLayout(box)
        self.preview = QLabel("Abra a aba para iniciar a camera")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(620, 500)
        self.preview.setStyleSheet("background:#030507;color:#546e7a;border:1px solid #1d2b38;font-size:15px;")
        lay.addWidget(self.preview, 1)
        row = QHBoxLayout()
        self.camera_button = self.button("INICIAR CAMERA", CYAN)
        self.camera_button.clicked.connect(self.toggle_camera)
        self.camera_status = QLabel("CAMERA: OFFLINE")
        self.camera_status.setStyleSheet(f"color:{MUTED};font-weight:800;border:none;")
        row.addWidget(self.camera_button)
        row.addWidget(self.camera_status)
        row.addStretch()
        lay.addLayout(row)
        return box

    def analysis_panel(self):
        box = QFrame()
        box.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid {LINE};border-radius:8px;}}")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 14, 14, 14)
        title = QLabel("NVIDIA CAMERA LAB")
        title.setStyleSheet(f"color:{CYAN};font-weight:800;letter-spacing:2px;border:none;")
        lay.addWidget(title)
        info = QLabel("Llama 3.2 Vision 11B hospedado pela NVIDIA")
        info.setStyleSheet(f"color:{MUTED};border:none;")
        lay.addWidget(info)
        self.mode = QComboBox()
        self.mode.addItems(["Objetos e cena", "Pessoas", "Libras / gestos"])
        self.mode.setStyleSheet(self.input_css())
        self.mode.currentTextChanged.connect(self.mode_changed)
        lay.addWidget(self.mode)
        self.question = QLineEdit()
        self.question.setPlaceholderText("Pergunta opcional sobre o que a camera ve...")
        self.question.setStyleSheet(self.input_css())
        self.question.returnPressed.connect(self.analyze)
        lay.addWidget(self.question)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(f"color:{MUTED};font-size:11px;border:none;")
        lay.addWidget(self.hint)
        self.mode_changed(self.mode.currentText())
        self.go = self.button("ANALISAR COM NVIDIA", PURPLE)
        self.go.setMinimumHeight(44)
        self.go.clicked.connect(self.analyze)
        lay.addWidget(self.go)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        lay.addWidget(self.progress)
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("O reconhecimento aparece aqui.")
        self.result.setStyleSheet("QTextEdit{background:#070b11;color:#e4f5fa;border:1px solid #26384a;padding:9px;}")
        lay.addWidget(self.result, 1)
        note = QLabel("Libras e experimental: o modelo interpreta 6 quadros em ordem e deve indicar quando estiver incerto.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
        lay.addWidget(note)
        return box

    @staticmethod
    def input_css():
        return "QLineEdit,QComboBox{background:#070b11;color:#e4f5fa;border:1px solid #26384a;border-radius:4px;padding:8px;}QComboBox QAbstractItemView{background:#101722;color:#e4f5fa;}"

    @staticmethod
    def button(text, color):
        widget = QPushButton(text)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setStyleSheet(f"QPushButton{{background:#090e16;color:{color};border:1px solid {color};border-radius:4px;padding:9px;font-weight:800;}}QPushButton:hover{{background:{color};color:#071018;}}QPushButton:disabled{{color:#58656c;border-color:#34434b;}}")
        return widget

    def mode_changed(self, mode):
        if mode == "Libras / gestos":
            self.hint.setText("Mantenha o sinal visivel por 3 segundos. A aba guarda 6 quadros temporarios para analisar o movimento.")
        elif mode == "Pessoas":
            self.hint.setText("Detecta quantidade, posicao, roupa, postura e acao aparente. Nao tenta adivinhar identidade.")
        else:
            self.hint.setText("Reconhece objetos, posicoes aproximadas e o contexto da cena.")

    def start_camera(self):
        if self.capture is not None and self.capture.isOpened():
            return

        self.preview.setText("Procurando cameras disponiveis...")
        self.camera_status.setText("CAMERA: PROCURANDO")
        self.camera_status.setStyleSheet(f"color:{CYAN};font-weight:800;border:none;")
        QApplication.processEvents()

        cap = None
        selected_index = None
        backend_names = (
            (getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY), "DirectShow"),
            (getattr(cv2, "CAP_MSMF", cv2.CAP_ANY), "Media Foundation"),
            (cv2.CAP_ANY, "automatico"),
        )
        tried = set()
        for index in range(6):
            for backend, backend_name in backend_names:
                key = (index, backend)
                if key in tried:
                    continue
                tried.add(key)
                candidate = cv2.VideoCapture(index, backend)
                if not candidate.isOpened():
                    candidate.release()
                    continue
                candidate.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                ok, frame = candidate.read()
                if ok and frame is not None and frame.size:
                    cap = candidate
                    selected_index = index
                    self.camera_backend = backend_name
                    break
                candidate.release()
            if cap is not None:
                break

        if cap is None:
            self.preview.setText(
                "Nenhuma camera disponivel.\n\n"
                "Feche Discord, navegador, OBS ou outro app usando a webcam; "
                "confira a permissao de Camera do Windows e clique em INICIAR CAMERA."
            )
            self.camera_status.setText("CAMERA: NAO ENCONTRADA")
            self.camera_status.setStyleSheet(f"color:{RED};font-weight:800;border:none;")
            self.camera_button.setText("TENTAR NOVAMENTE")
            return

        self.capture = cap
        self.camera_index = selected_index
        self.frames.clear()
        self.timer.start(70)
        self.camera_button.setText("PARAR CAMERA")
        self.camera_status.setText(f"CAMERA: ONLINE #{selected_index} ({self.camera_backend})")
        self.camera_status.setStyleSheet(f"color:{GREEN};font-weight:800;border:none;")

    def stop_camera(self):
        self.timer.stop()
        if self.capture is not None:
            self.capture.release()
        self.capture = None
        self.current_frame = None
        self.frames.clear()
        self.preview.clear()
        self.preview.setText("Camera parada")
        self.camera_button.setText("INICIAR CAMERA")
        self.camera_status.setText("CAMERA: OFFLINE")
        self.camera_status.setStyleSheet(f"color:{MUTED};font-weight:800;border:none;")

    def toggle_camera(self):
        if self.capture is not None and self.capture.isOpened():
            self.stop_camera()
        else:
            self.start_camera()

    def update_frame(self):
        if self.capture is None:
            return
        ok, frame = self.capture.read()
        if not ok:
            return
        frame = cv2.flip(frame, 1)
        self.current_frame = frame.copy()
        self.ticks += 1
        if self.ticks % 8 == 0:
            self.frames.append(frame.copy())
        display = frame.copy()
        if not self.detector.empty():
            gray = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)
            for x, y, w, h in self.detector.detectMultiScale(gray, 1.15, 5, minSize=(60, 60)):
                cv2.rectangle(display, (x, y), (x + w, y + h), (82, 223, 255), 2)
                cv2.putText(display, "PESSOA", (x, max(24, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (82, 223, 255), 2)
        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy()
        pix = QPixmap.fromImage(image).scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.preview.setPixmap(pix)

    def analyze(self):
        if self.current_frame is None:
            self.result.setPlainText("Inicie a camera e aguarde a imagem aparecer.")
            return
        if self.busy:
            return
        mode = self.mode.currentText()
        frames = list(self.frames) if mode == "Libras / gestos" else [self.current_frame.copy()]
        if mode == "Libras / gestos" and len(frames) < 3:
            self.result.setPlainText("Aguarde cerca de 3 segundos para capturar a sequencia do gesto.")
            return
        self.busy = True
        self.go.setEnabled(False)
        self.go.setText("ANALISANDO...")
        self.progress.setRange(0, 0)
        self.result.setPlainText("Enviando somente os quadros selecionados para a API NVIDIA...")
        question = self.question.text()
        def worker():
            try:
                self.analyzed.emit(analyze_nvidia_camera(frames, mode, question))
            except Exception as exc:
                self.failed.emit(str(exc))
        threading.Thread(target=worker, daemon=True).start()

    def reset_busy(self):
        self.busy = False
        self.go.setEnabled(True)
        self.go.setText("ANALISAR COM NVIDIA")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

    def analysis_done(self, text):
        self.reset_busy()
        self.result.setPlainText(text)

    def analysis_failed(self, text):
        self.reset_busy()
        self.result.setPlainText("Falha: " + text)



class WhisperAudioLab(QWidget):
    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.current_path = None
        self.busy = False
        self.completed.connect(self.done)
        self.failed.connect(self.error)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        title = QLabel("WHISPER AUDIO LAB")
        title.setStyleSheet(f"font-size:20px;font-weight:900;letter-spacing:3px;color:{PURPLE};")
        root.addWidget(title)
        info = QLabel("Grave ou abra um audio. Faster Whisper roda localmente e nao envia o audio para a NVIDIA.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{MUTED};padding-bottom:8px;")
        root.addWidget(info)

        panel = QFrame()
        panel.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid {LINE};border-radius:8px;}}")
        layout = QVBoxLayout(panel)
        options = QHBoxLayout()
        self.duration = QSpinBox()
        self.duration.setRange(2, 30)
        self.duration.setValue(5)
        self.duration.setSuffix(" segundos")
        self.language = QComboBox()
        for label, code in (("Detectar idioma","auto"),("Portugues","pt"),("Ingles","en"),("Espanhol","es")):
            self.language.addItem(label, code)
        self.duration.setStyleSheet(Studio.input_css())
        self.language.setStyleSheet(Studio.input_css())
        options.addWidget(QLabel("DURACAO:"))
        options.addWidget(self.duration)
        options.addSpacing(18)
        options.addWidget(QLabel("IDIOMA:"))
        options.addWidget(self.language, 1)
        layout.addLayout(options)

        buttons = QHBoxLayout()
        self.record_btn = Studio.button("GRAVAR E TRANSCREVER", CYAN)
        self.open_btn = Studio.button("ABRIR AUDIO", PURPLE)
        self.run_btn = Studio.button("TRANSCREVER ARQUIVO", GREEN)
        self.run_btn.setEnabled(False)
        self.record_btn.clicked.connect(self.record)
        self.open_btn.clicked.connect(self.open_audio)
        self.run_btn.clicked.connect(self.transcribe)
        buttons.addWidget(self.record_btn)
        buttons.addWidget(self.open_btn)
        buttons.addWidget(self.run_btn)
        layout.addLayout(buttons)
        self.file_label = QLabel("Nenhum audio selecionado.")
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet(f"color:{MUTED};border:none;padding:5px;")
        layout.addWidget(self.file_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        root.addWidget(panel)

        self.text = QTextEdit()
        self.text.setPlaceholderText("A transcricao aparece aqui e pode ser editada.")
        self.text.setStyleSheet(Studio.input_css())
        root.addWidget(self.text, 1)
        actions = QHBoxLayout()
        copy_btn = Studio.button("COPIAR TEXTO", CYAN)
        save_btn = Studio.button("SALVAR TXT", GREEN)
        folder_btn = Studio.button("ABRIR PASTA DE AUDIO", PURPLE)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))
        save_btn.clicked.connect(self.save)
        folder_btn.clicked.connect(self.open_folder)
        actions.addWidget(copy_btn)
        actions.addWidget(save_btn)
        actions.addWidget(folder_btn)
        root.addLayout(actions)
        self.status = QLabel("Modelo local: Faster Whisper Base | CPU INT8")
        self.status.setStyleSheet(f"color:{MUTED};")
        root.addWidget(self.status)

    def set_busy(self, value, message):
        self.busy = value
        self.record_btn.setEnabled(not value)
        self.open_btn.setEnabled(not value)
        self.run_btn.setEnabled(not value and self.current_path is not None)
        self.progress.setRange(0, 0 if value else 1)
        if not value:
            self.progress.setValue(0)
        self.status.setText(message)

    def open_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir audio", str(Path.home()), "Audio (*.wav *.mp3 *.m4a *.mp4 *.ogg *.flac *.aac);;Todos (*)")
        if path:
            self.current_path = Path(path)
            self.file_label.setText(path)
            self.run_btn.setEnabled(True)
            self.status.setText("Audio carregado.")

    def record(self):
        if self.busy:
            return
        duration = self.duration.value()
        language = str(self.language.currentData())
        self.set_busy(True, f"Gravando por {duration} segundos...")
        def work():
            try:
                path = record_microphone(duration)
                self.completed.emit(transcribe_local_audio(path, language))
            except Exception as exc:
                self.failed.emit(str(exc))
        threading.Thread(target=work, daemon=True).start()

    def transcribe(self):
        if self.busy or self.current_path is None:
            return
        path = self.current_path
        language = str(self.language.currentData())
        self.set_busy(True, "Transcrevendo localmente...")
        def work():
            try:
                self.completed.emit(transcribe_local_audio(path, language))
            except Exception as exc:
                self.failed.emit(str(exc))
        threading.Thread(target=work, daemon=True).start()

    def done(self, result):
        self.current_path = Path(result["path"])
        self.file_label.setText(str(self.current_path))
        self.text.setPlainText(result["text"])
        self.set_busy(False, "Concluido | idioma: " + (result.get("language") or "desconhecido"))

    def error(self, message):
        self.set_busy(False, "Falha: " + message)
        QMessageBox.critical(self, "Falha no Whisper", message)

    def save(self):
        transcript = self.text.toPlainText().strip()
        if not transcript:
            QMessageBox.information(self, "Sem texto", "Transcreva ou escreva algum texto primeiro.")
            return
        AUDIO_OUTPUTS.mkdir(parents=True, exist_ok=True)
        default = AUDIO_OUTPUTS / f"transcricao-{time.strftime('%Y%m%d-%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Salvar transcricao", str(default), "Texto (*.txt)")
        if path:
            Path(path).write_text(transcript, encoding="utf-8")
            self.status.setText("Salvo em: " + path)

    @staticmethod
    def open_folder():
        AUDIO_OUTPUTS.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(AUDIO_OUTPUTS)))


class VideoGenerationLab(QWidget):
    event_received = pyqtSignal(dict)
    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.process = None
        self.cancel_requested = False
        self.busy = False
        self.started_at = None
        self.last_output = None
        self.event_received.connect(self.on_event)
        self.completed.connect(self.done)
        self.failed.connect(self.error)

        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self.update_elapsed)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        title = QLabel("ZEROGPU VIDEO LAB")
        title.setStyleSheet(f"font-size:20px;font-weight:900;letter-spacing:3px;color:{GREEN};")
        root.addWidget(title)
        info = QLabel(
            "LTX-2.5 e MiniMax H3 em GPU remota do Hugging Face. "
            "Escolha modelo, duracao e qualidade; o Studio acompanha a fila e baixa o video com audio."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{MUTED};padding-bottom:8px;")
        root.addWidget(info)

        split = QSplitter(Qt.Orientation.Horizontal)
        controls = QFrame()
        controls.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid {LINE};border-radius:8px;}}")
        form = QVBoxLayout(controls)
        form.addWidget(Studio.label("MODELO DE VIDEO", GREEN))
        self.provider = QComboBox()
        for provider_id, provider_info in VIDEO_PROVIDERS.items():
            self.provider.addItem(provider_info["label"], provider_id)
        self.provider.setCurrentIndex(0)
        self.provider.setStyleSheet(Studio.input_css())
        form.addWidget(self.provider)
        self.input_mode = QComboBox()
        for label, value in [("Texto para video", "text"), ("Imagem inicial", "image"),
                             ("Imagens inicial e final", "frames"), ("Video de referencia (H3)", "video")]:
            self.input_mode.addItem(label, value)
        self.input_mode.setStyleSheet(Studio.input_css())
        form.addWidget(self.input_mode)
        self.first_image = MediaInput("IMAGEM INICIAL")
        self.last_image = MediaInput("IMAGEM FINAL")
        self.reference_video = MediaInput("VIDEO DE REFERENCIA", "video")
        for widget in (self.first_image, self.last_image, self.reference_video):
            form.addWidget(widget)

        settings_row = QHBoxLayout()
        self.quality = QComboBox()
        for label, quality_id in VIDEO_QUALITIES.items():
            self.quality.addItem(label, quality_id)
        self.quality.setStyleSheet(Studio.input_css())
        self.duration = QSpinBox()
        self.duration.setRange(2, 20)
        self.duration.setValue(8)
        self.duration.setPrefix("Duracao: ")
        self.duration.setSuffix(" s")
        self.duration.setStyleSheet(Studio.input_css())
        settings_row.addWidget(self.quality)
        settings_row.addWidget(self.duration)
        form.addLayout(settings_row)
        self.save_defaults = Studio.button("USAR COMO PADRAO NO JARVIS", GREEN)
        self.save_defaults.clicked.connect(self.save_video_defaults)
        form.addWidget(self.save_defaults)
        form.addWidget(Studio.label("DESCREVA O VIDEO", CYAN))
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText(
            "Ex.: Um aviao de papel vermelho voa sobre o oceano, movimento cinematografico..."
        )
        self.prompt.setFixedHeight(105)
        self.prompt.setStyleSheet(Studio.input_css())
        form.addWidget(self.prompt)

        form.addWidget(Studio.label("EVITAR", PURPLE))
        self.negative = QLineEdit()
        self.negative.setText("blurry, low quality, distorted, static shot, watermark, text")
        self.negative.setStyleSheet(Studio.input_css())
        form.addWidget(self.negative)

        row = QHBoxLayout()
        self.preset = QComboBox()
        self.preset.addItems(VIDEO_PRESETS)
        self.preset.setCurrentIndex(0)
        self.preset.setStyleSheet(Studio.input_css())
        self.seed = QSpinBox()
        self.seed.setRange(0, 2147483647)
        self.seed.setValue(random.randint(1, 999999999))
        self.seed.setPrefix("Seed: ")
        self.seed.setStyleSheet(Studio.input_css())
        row.addWidget(self.preset, 2)
        row.addWidget(self.seed, 1)
        form.addLayout(row)

        self.video_note = QLabel()
        self.video_note.setWordWrap(True)
        self.video_note.setStyleSheet(f"color:{MUTED};border:none;padding:6px 0;")
        form.addWidget(self.video_note)

        buttons = QHBoxLayout()
        self.generate_btn = Studio.button("GERAR VIDEO ZEROGPU", GREEN)
        self.cancel_btn = Studio.button("CANCELAR", RED)
        self.cancel_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self.generate)
        self.cancel_btn.clicked.connect(self.cancel)
        buttons.addWidget(self.generate_btn, 1)
        buttons.addWidget(self.cancel_btn)
        form.addLayout(buttons)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Pronto")
        self.progress.setTextVisible(True)
        self.progress.setStyleSheet(
            "QProgressBar{background:#070b11;color:#e4f5fa;border:1px solid #26384a;"
            "border-radius:4px;text-align:center;min-height:24px;}"
            "QProgressBar::chunk{background:#35c98b;border-radius:3px;}"
        )
        form.addWidget(self.progress)

        self.stage = QLabel("Pronto para gerar.")
        self.stage.setWordWrap(True)
        self.stage.setStyleSheet(f"color:{MUTED};border:none;padding:5px;")
        form.addWidget(self.stage)
        form.addStretch()

        action_row = QHBoxLayout()
        self.open_btn = Studio.button("ABRIR VIDEO", CYAN)
        self.open_btn.setEnabled(False)
        folder_btn = Studio.button("ABRIR PASTA", PURPLE)
        self.open_btn.clicked.connect(self.open_video)
        folder_btn.clicked.connect(self.open_folder)
        action_row.addWidget(self.open_btn)
        action_row.addWidget(folder_btn)
        form.addLayout(action_row)

        preview_panel = QFrame()
        preview_panel.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid {LINE};border-radius:8px;}}")
        preview_layout = QVBoxLayout(preview_panel)
        self.preview = QLabel("A pre-visualizacao do video aparece aqui")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(560, 315)
        self.preview.setStyleSheet(
            "background:#030507;color:#546e7a;border:1px solid #1d2b38;font-size:16px;"
        )
        preview_layout.addWidget(self.preview, 1)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setStyleSheet(f"color:{MUTED};border:none;padding:6px;")
        preview_layout.addWidget(self.details)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setMinimumWidth(380)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        split.addWidget(scroll)
        split.addWidget(preview_panel)
        split.setSizes([470, 720])
        root.addWidget(split, 1)
        defaults = load_video_preferences()
        self.provider.setCurrentIndex(self.provider.findData(defaults["provider"]))
        self.quality.setCurrentIndex(self.quality.findData(defaults["quality"]))
        self.preset.setCurrentIndex(list(VIDEO_PRESETS.values()).index(defaults["aspect_ratio"]))
        self.duration.setValue(int(defaults["duration"]))
        self.input_mode.currentIndexChanged.connect(self.input_mode_changed)
        self.provider.currentIndexChanged.connect(self.video_options_changed)
        self.quality.currentIndexChanged.connect(self.video_options_changed)
        self.preset.currentIndexChanged.connect(self.video_options_changed)
        self.duration.valueChanged.connect(self.video_options_changed)
        self.video_options_changed()

    def input_mode_changed(self, *_args):
        if self.input_mode.currentData() == "video":
            self.provider.setCurrentIndex(self.provider.findData("h3"))
        self.video_options_changed()

    def save_video_defaults(self, *_args):
        try:
            save_video_preferences(
                self.provider.currentData(), self.quality.currentData(), self.duration.value(),
                VIDEO_PRESETS[self.preset.currentText()],
            )
            QMessageBox.information(self, "Padrao salvo", "O Studio e o Jarvis usarao estas opcoes quando voce nao informar outras.")
        except Exception as exc:
            QMessageBox.warning(self, "Falha ao salvar", safe_error(exc))

    def video_options_changed(self, *_args) -> None:
        provider = self.provider.currentData()
        model = VIDEO_PROVIDERS[provider]
        self.duration.blockSignals(True)
        mode = self.input_mode.currentData()
        self.first_image.setVisible(mode in {"image", "frames"})
        self.last_image.setVisible(mode == "frames")
        self.reference_video.setVisible(mode == "video")
        self.duration.setRange(5 if mode == "video" else model["min_duration"], model["max_duration"])
        self.duration.blockSignals(False)
        self.negative.setEnabled(provider == "ltx" and not self.busy)
        self.negative.setToolTip(
            "O Space do MiniMax H3 nao possui campo de prompt negativo." if provider == "h3" else ""
        )
        settings = video_settings(
            provider, self.quality.currentData(),
            VIDEO_PRESETS[self.preset.currentText()], self.duration.value(),
        )
        width, height = settings["width"], settings["height"]
        self.video_note.setText(
            f'Ate {model["max_duration"]}s neste modo. Economico reduz resolucao e, no H3, usa geracao acelerada. '
            "Videos mais longos ou detalhados exigem mais GPU e podem exceder a cota. "
            "Conta gratuita: 5 min de GPU/dia; sem login: 2 min. "
            + ("Video de referencia requer H3 e usa 28 passos, inclusive no Economico; pode exceder a cota gratuita."
               if mode == "video" else "Os anexos serao enviados ao Space ao clicar em Gerar." if mode != "text" else "")
        )
        if not self.busy:
            self.details.setText(
                f'{model["label"]} | {width}x{height} | cerca de {self.duration.value()} s | 24 FPS | audio | ZeroGPU'
            )

    def set_busy(self, value: bool) -> None:
        self.busy = value
        self.generate_btn.setEnabled(not value)
        self.cancel_btn.setEnabled(value)
        self.preset.setEnabled(not value)
        self.seed.setEnabled(not value)
        self.provider.setEnabled(not value)
        self.quality.setEnabled(not value)
        self.duration.setEnabled(not value)
        for widget in (self.input_mode, self.first_image, self.last_image, self.reference_video, self.save_defaults):
            widget.setEnabled(not value)
        self.negative.setEnabled(not value and self.provider.currentData() == "ltx")
        if value:
            self.started_at = time.time()
            self.clock.start()
        else:
            self.clock.stop()

    def update_elapsed(self) -> None:
        if self.started_at:
            elapsed = int(time.time() - self.started_at)
            minutes, seconds = divmod(elapsed, 60)
            base = self.stage.property("base_text") or self.stage.text().split(" | tempo:")[0]
            self.stage.setText(f"{base} | tempo: {minutes:02d}:{seconds:02d}")

    def set_stage(self, text: str) -> None:
        self.stage.setProperty("base_text", text)
        self.stage.setText(text)
        self.update_elapsed()

    def generate(self) -> None:
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "Prompt vazio", "Descreva o video que voce quer gerar.")
            return
        if self.busy:
            return
        if not HF_VIDEO_WORKER.exists():
            QMessageBox.critical(self, "Integracao ausente", f"Worker nao encontrado em:\n{HF_VIDEO_WORKER}")
            return

        provider = self.provider.currentData()
        quality = self.quality.currentData()
        duration = self.duration.value()
        aspect = VIDEO_PRESETS[self.preset.currentText()]
        mode = self.input_mode.currentData()
        attachments = []
        if mode in {"image", "frames"}:
            if not self.first_image.path or (mode == "frames" and not self.last_image.path):
                QMessageBox.warning(self, "Anexe os arquivos", "Escolha as imagens exigidas pelo modo selecionado.")
                return
            attachments += ["--first-image", self.first_image.path]
            if mode == "frames":
                attachments += ["--last-image", self.last_image.path]
        if mode == "video":
            if provider != "h3" or not self.reference_video.path:
                QMessageBox.warning(self, "Video de referencia", "Selecione MiniMax H3 e anexe o video de referencia.")
                return
            attachments += ["--reference-video", self.reference_video.path]
        VIDEO_OUTPUTS.mkdir(parents=True, exist_ok=True)
        output = VIDEO_OUTPUTS / f"{provider}-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1000000:06d}.mp4"
        command = [
            str(STUDIO_PYTHON), str(HF_VIDEO_WORKER),
            "--prompt", prompt,
            "--negative-prompt", self.negative.text().strip() if provider == "ltx" else "",
            "--output", str(output),
            "--seed", str(self.seed.value()),
            "--provider", provider,
            "--quality", quality,
            "--aspect-ratio", aspect,
            "--duration", str(duration), "--input-mode", mode,
        ] + attachments
        self.cancel_requested = False
        self.last_output = output
        self.open_btn.setEnabled(False)
        self.set_busy(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Conectando ao ZeroGPU...")
        self.set_stage("CONECTANDO AO HUGGING FACE")
        self.details.setText("Saida planejada: " + str(output))

        def worker():
            complete_event = None
            error_message = None
            recent = []
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=flags,
                )
                assert self.process.stdout is not None
                for raw in self.process.stdout:
                    line = raw.strip()
                    if not line:
                        continue
                    print(f"[VIDEO WORKER] {line}", flush=True)
                    recent.append(line)
                    recent = recent[-8:]
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(event, dict) or "event" not in event:
                        continue
                    self.event_received.emit(event)
                    if event["event"] == "complete":
                        complete_event = event
                    elif event["event"] == "error":
                        error_message = str(event.get("message") or "Falha desconhecida.")
                code = self.process.wait()
                if self.cancel_requested:
                    self.failed.emit("Geracao cancelada.")
                elif code == 0 and complete_event:
                    self.completed.emit(complete_event)
                else:
                    self.failed.emit(error_message or "\n".join(recent) or f"O processo terminou com codigo {code}.")
            except Exception as exc:
                self.failed.emit(str(exc))
            finally:
                self.process = None

        threading.Thread(target=worker, daemon=True).start()

    def on_event(self, event: dict) -> None:
        name = event.get("event")
        if name == "connecting":
            self.progress.setRange(0, 0)
            self.progress.setFormat("Conectando ao Space ZeroGPU...")
            self.set_stage("CONECTANDO AO ZEROGPU")
        elif name == "queued":
            self.progress.setRange(0, 0)
            rank = event.get("rank")
            eta = event.get("eta")
            queue_text = f"Posicao na fila: {rank}" if rank is not None else "Aguardando GPU gratuita"
            if eta:
                queue_text += f" | estimativa: {int(float(eta))}s"
            self.progress.setFormat(queue_text)
            self.set_stage("AGUARDANDO GPU GRATUITA")
        elif name == "downloading":
            self.progress.setRange(0, 0)
            self.progress.setFormat("Baixando MP4...")
            self.set_stage("BAIXANDO RESULTADO")
        elif name == "generating":
            self.progress.setRange(0, 0)
            self.progress.setFormat("Gerando video na GPU remota...")
            self.set_stage("GERANDO VIDEO")
        elif name == "step":
            current = int(event.get("current") or 0)
            total = max(int(event.get("total") or 1), 1)
            self.progress.setRange(0, total)
            self.progress.setValue(current)
            self.progress.setFormat(f"Gerando passo {current}/{total}")
            self.set_stage(f"GERANDO PASSO {current}/{total}")
        elif name == "decoding":
            self.progress.setRange(0, 0)
            self.progress.setFormat("Decodificando quadros...")
            self.set_stage("DECODIFICANDO QUADROS")
        elif name == "encoding_base":
            self.progress.setRange(0, 0)
            self.progress.setFormat("Montando video base...")
            self.set_stage("MONTANDO VIDEO BASE")
        elif name == "interpolating":
            source = int(event.get("source_frames") or 0)
            target = int(event.get("target_frames") or 0)
            fps = int(event.get("output_fps") or 24)
            self.progress.setRange(0, 0)
            self.progress.setFormat(f"Interpolando {source} -> {target} quadros...")
            self.set_stage(f"RIFE: INTERPOLANDO PARA {fps} FPS")
        elif name == "encoding":
            self.progress.setRange(0, 0)
            self.progress.setFormat("Salvando MP4 em 24 FPS...")
            self.set_stage("SALVANDO MP4 EM 24 FPS")

    def cancel(self) -> None:
        if self.process is not None:
            self.cancel_requested = True
            self.set_stage("CANCELANDO")
            self.process.terminate()
            self.cancel_btn.setEnabled(False)

    def stop_process(self) -> None:
        if self.process is not None:
            self.cancel_requested = True
            self.process.terminate()

    def done(self, event: dict) -> None:
        self.set_busy(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat("Concluido")
        output = Path(str(event.get("output") or self.last_output))
        self.last_output = output
        self.open_btn.setEnabled(output.exists())
        seconds = float(event.get("seconds") or 0)
        self.set_stage(f"CONCLUIDO EM {seconds / 60:.1f} MIN")
        model = str(event.get("model") or VIDEO_PROVIDERS[self.provider.currentData()]["label"])
        actual_duration = event.get("video_seconds")
        duration_text = f" | {actual_duration:g} s" if actual_duration is not None else ""
        self.details.setText(f"{model}{duration_text}\nVideo salvo em:\n{output}")
        self.show_preview(output)
        QApplication.alert(self.window(), 6000)
        QMessageBox.information(
            self,
            "Video concluido",
            f"{model} terminou a geracao{duration_text}.\n\nArquivo salvo em:\n{output}",
        )

    def error(self, message: str) -> None:
        self.set_busy(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Falha")
        self.set_stage("FALHA")
        self.details.setText(message)
        print(f"[VIDEO ERROR] {message}", flush=True)
        if message != "Geracao cancelada.":
            QMessageBox.critical(self, "Falha no video", message)

    def show_preview(self, path: Path) -> None:
        capture = cv2.VideoCapture(str(path))
        ok, frame = capture.read()
        capture.release()
        if not ok:
            self.preview.setText("Video concluido; nao foi possivel ler a miniatura.")
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888).copy()
        pix = QPixmap.fromImage(image)
        self.preview.setPixmap(
            pix.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )

    def open_video(self) -> None:
        if self.last_output and Path(self.last_output).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output)))

    @staticmethod
    def open_folder() -> None:
        VIDEO_OUTPUTS.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(VIDEO_OUTPUTS)))


class Studio(QMainWindow):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NVIDIA AI ART STUDIO")
        self.setMinimumSize(1080, 680)
        self.resize(1280, 790)
        self.busy = False
        central = QWidget()
        central.setStyleSheet(f"background:{BG};color:{TEXT};")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 14)
        header = QHBoxLayout()
        title = QLabel("NVIDIA AI ART STUDIO")
        title.setStyleSheet(f"font-size:24px;font-weight:800;letter-spacing:3px;color:{CYAN};")
        status = QLabel("KEY DO JARVIS: CONECTADA" if nvidia_key() else "KEY DO JARVIS: NAO ENCONTRADA")
        status.setStyleSheet(f"color:{GREEN if nvidia_key() else RED};font-weight:800;")
        header.addWidget(title); header.addStretch()
        account_button = self.button("CONTA HUGGING FACE", GREEN)
        account_button.clicked.connect(lambda: HuggingFaceDialog(self).exec())
        header.addWidget(account_button)
        header.addWidget(status)
        root.addLayout(header)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane{border:1px solid #26384a;background:#080b10;}"
            "QTabBar::tab{background:#101722;color:#78909c;padding:10px 20px;border:1px solid #26384a;}"
            "QTabBar::tab:selected{color:#42dfff;background:#15212e;}"
        )
        art_tab = QWidget()
        art_layout = QVBoxLayout(art_tab)
        art_layout.setContentsMargins(4, 8, 4, 4)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self.controls()); split.addWidget(self.preview_panel()); split.setSizes([430, 820])
        art_layout.addWidget(split, 1)
        self.tabs.addTab(art_tab, "01  GERAR ARTE")
        self.camera_lab = NvidiaCameraLab()
        self.tabs.addTab(self.camera_lab, "02  CAMERA IA")
        self.audio_lab = WhisperAudioLab()
        self.tabs.addTab(self.audio_lab, "03  WHISPER AUDIO")
        self.video_lab = VideoGenerationLab()
        self.tabs.addTab(self.video_lab, "04  VIDEO IA")
        self.dataset_panel = DatasetPanel()
        self.tabs.addTab(self.dataset_panel, "05  DATASETS")
        self.tabs.currentChanged.connect(self.tab_changed)
        root.addWidget(self.tabs, 1)
        self.done.connect(self.finished)
        self.failed.connect(self.failure)
        self.reload_history()

    def tab_changed(self, index: int):
        if index == 1:
            QTimer.singleShot(100, self.camera_lab.start_camera)
        else:
            self.camera_lab.stop_camera()

    def closeEvent(self, event):
        self.camera_lab.stop_camera()
        self.video_lab.stop_process()
        super().closeEvent(event)

    def frame(self) -> QFrame:
        box = QFrame(); box.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid {LINE};border-radius:8px;}}")
        return box

    def controls(self) -> QWidget:
        box = self.frame(); lay = QVBoxLayout(box); lay.setContentsMargins(14, 14, 14, 14)
        lay.addWidget(self.label("IDEIA DA ARTE", CYAN))
        self.prompt = QTextEdit(); self.prompt.setMinimumHeight(130)
        self.prompt.setPlaceholderText("Descreva a imagem que voce quer criar..."); self.prompt.setStyleSheet(self.input_css())
        lay.addWidget(self.prompt)
        lay.addWidget(self.label("DIRECAO VISUAL", PURPLE))
        self.style = QComboBox(); self.style.addItems(STYLES); self.style.setStyleSheet(self.input_css()); lay.addWidget(self.style)
        self.ratio = QComboBox(); self.ratio.addItems(RATIOS); self.ratio.setStyleSheet(self.input_css()); lay.addWidget(self.ratio)
        self.model = QComboBox(); self.model.addItems(MODELS); self.model.setStyleSheet(self.input_css()); lay.addWidget(self.model)
        self.art_mode = QComboBox()
        self.art_mode.addItems(["Criar imagem a partir de texto", "Editar / combinar imagens (ZeroGPU)"])
        self.art_mode.setStyleSheet(self.input_css())
        lay.addWidget(self.art_mode)
        self.art_references = [MediaInput("IMAGEM DE REFERENCIA " + str(i+1)) for i in range(3)]
        for entry in self.art_references:
            lay.addWidget(entry)
            entry.setVisible(False)
        self.art_mode.currentIndexChanged.connect(self.art_mode_changed)
        row = QHBoxLayout(); self.seed = QSpinBox(); self.seed.setRange(0, 2147483647); self.seed.setPrefix("Seed: ")
        self.seed.setValue(random.randint(1, 999999999)); self.seed.setStyleSheet(self.input_css())
        seed_btn = self.button("NOVA SEED", PURPLE); seed_btn.clicked.connect(lambda: self.seed.setValue(random.randint(1, 2147483647)))
        row.addWidget(self.seed, 1); row.addWidget(seed_btn); lay.addLayout(row)
        self.negative = QLineEdit(); self.negative.setPlaceholderText("Evitar: texto, baixa qualidade...")
        self.negative.setStyleSheet(self.input_css()); lay.addWidget(self.negative)
        self.go = self.button("GERAR ARTE", CYAN); self.go.setMinimumHeight(46); self.go.clicked.connect(self.generate); lay.addWidget(self.go)
        self.progress = QProgressBar(); self.progress.setRange(0, 1); self.progress.setValue(0); self.progress.setTextVisible(False); lay.addWidget(self.progress)
        lay.addWidget(self.label("HISTORICO", CYAN))
        self.history = QListWidget(); self.history.setStyleSheet("QListWidget{background:#070b11;color:#d9eef4;border:1px solid #26384a;}QListWidget::item{padding:7px;}QListWidget::item:selected{background:#173341;}")
        self.history.currentRowChanged.connect(self.show_history); lay.addWidget(self.history, 1)
        folder = self.button("ABRIR PASTA DAS ARTES", GREEN); folder.clicked.connect(self.open_outputs); lay.addWidget(folder)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        scroll.setMinimumWidth(375)
        return scroll

    def art_mode_changed(self, *_args):
        editing = self.art_mode.currentIndex() == 1
        for entry in self.art_references:
            entry.setVisible(editing)
        if editing:
            self.model.setCurrentText(IMAGE_MODEL_LABEL)
        self.model.setEnabled(not editing and not self.busy)

    def preview_panel(self) -> QWidget:
        box = self.frame(); lay = QVBoxLayout(box)
        self.preview = QLabel("Sua proxima arte aparece aqui"); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(580, 520); self.preview.setStyleSheet("background:#030507;color:#546e7a;border:1px solid #1d2b38;font-size:16px;")
        self.status = QLabel("Pronto para criar."); self.status.setWordWrap(True); self.status.setStyleSheet(f"color:{MUTED};border:none;padding:6px;")
        lay.addWidget(self.preview, 1); lay.addWidget(self.status); return box

    @staticmethod
    def label(text: str, color: str) -> QLabel:
        widget = QLabel(text); widget.setStyleSheet(f"color:{color};font-weight:800;letter-spacing:2px;border:none;"); return widget

    @staticmethod
    def input_css() -> str:
        return "QTextEdit,QLineEdit,QComboBox,QSpinBox{background:#070b11;color:#e4f5fa;border:1px solid #26384a;border-radius:4px;padding:8px;}QComboBox QAbstractItemView{background:#101722;color:#e4f5fa;}"

    @staticmethod
    def button(text: str, color: str) -> QPushButton:
        widget = QPushButton(text); widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setStyleSheet(f"QPushButton{{background:#090e16;color:{color};border:1px solid {color};border-radius:4px;padding:9px;font-weight:800;}}QPushButton:hover{{background:{color};color:#071018;}}QPushButton:disabled{{color:#58656c;border-color:#34434b;}}")
        return widget

    def generate(self) -> None:
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "Prompt vazio", "Descreva a arte que voce quer criar."); return
        if self.busy: return
        style, ratio, model, seed = self.style.currentText(), self.ratio.currentText(), self.model.currentText(), self.seed.value()
        references = [entry.path for entry in self.art_references if entry.path] if self.art_mode.currentIndex() == 1 else []
        if self.art_mode.currentIndex() == 1 and not references:
            QMessageBox.warning(self, "Anexe uma imagem", "Escolha ao menos uma imagem de referencia.")
            return
        uses_hf = bool(references) or model == IMAGE_MODEL_LABEL
        if references:
            model = IMAGE_MODEL_LABEL
        final_prompt = render_prompt(prompt, STYLES[style], self.negative.text())
        self.busy = True; self.go.setEnabled(False); self.go.setText("CRIANDO..."); self.progress.setRange(0, 0)
        for widget in [self.art_mode, self.model, *self.art_references]:
            widget.setEnabled(False)
        self.status.setText("Hugging Face ZeroGPU: enviando referencias e aguardando a geracao..." if uses_hf else f"A NVIDIA esta renderizando sua arte... Prompt: {len(final_prompt)}/800 caracteres.")
        def worker():
            try:
                start = time.time()
                raw = generate_hf_image(final_prompt, seed, RATIOS[ratio], references) if uses_hf else generate_nvidia(final_prompt, model, seed)
                path = save_image(raw, ratio, prompt)
                row = {"created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "prompt": prompt, "render_prompt": final_prompt, "model": MODELS[model][0], "seed": seed, "ratio": ratio, "seconds": round(time.time()-start, 2), "path": str(path)}
                add_history(row); self.done.emit(row)
            except Exception as exc: self.failed.emit(safe_error(exc))
        threading.Thread(target=worker, daemon=True).start()

    def reset(self):
        for widget in [self.art_mode, *self.art_references]:
            widget.setEnabled(True)
        self.model.setEnabled(self.art_mode.currentIndex() == 0)
        self.busy = False; self.go.setEnabled(True); self.go.setText("GERAR ARTE"); self.progress.setRange(0, 1); self.progress.setValue(0)

    def display(self, path: Path):
        pix = QPixmap(str(path))
        self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def finished(self, row: dict):
        self.reset(); self.display(Path(row["path"])); self.status.setText(f"Criada em {row['seconds']}s | seed {row['seed']}\n{row['path']}"); self.reload_history()

    def failure(self, message: str):
        self.reset(); self.status.setText("Falha: " + message); QMessageBox.critical(self, "Falha na geracao", message)

    def reload_history(self):
        self.rows = history_rows(); self.history.clear()
        for row in self.rows: self.history.addItem(f"{row.get('created_at','')} | {row.get('prompt','')[:46]}")

    def show_history(self, index: int):
        if 0 <= index < len(self.rows):
            row = self.rows[index]; self.display(Path(row["path"])); self.status.setText(f"{row.get('model','')} | seed {row.get('seed','')}\n{row.get('prompt','')}")

    def open_outputs(self):
        OUTPUTS.mkdir(parents=True, exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(OUTPUTS)))


def test_generation() -> int:
    prompt = "A futuristic artificial intelligence art studio, cyan lights, cinematic concept art"
    start = time.time(); raw = generate_nvidia(prompt, "FLUX 2 Klein 4B (recomendado)", 424242)
    path = save_image(raw, "Quadrado 1:1", "teste-inicial")
    add_history({"created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "prompt": prompt, "render_prompt": prompt, "model": MODELS["FLUX 2 Klein 4B (recomendado)"][0], "seed": 424242, "ratio": "Quadrado 1:1", "seconds": round(time.time()-start, 2), "path": str(path)})
    print("OK\n" + str(path)); return 0


def main() -> int:
    if "--check" in sys.argv:
        print("NVIDIA key found in Jarvis." if nvidia_key() else "NVIDIA key not found.")
        return 0 if nvidia_key() else 1
    if "--test" in sys.argv:
        return test_generation()
    argv = list(sys.argv)
    def take_option(name):
        if name not in argv:
            return ""
        index = argv.index(name)
        if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
            raise ValueError("Falta valor para " + name)
        value = argv[index + 1]
        del argv[index:index + 2]
        return value
    requested_tab = take_option("--tab").strip().casefold()
    video_prompt = take_option("--video-prompt").strip()
    provider = take_option("--video-model")
    duration = take_option("--video-duration")
    quality = take_option("--video-quality")
    video_format = take_option("--video-format")
    input_mode = take_option("--video-input-mode")
    first_image = take_option("--first-image")
    last_image = take_option("--last-image")
    reference_video = take_option("--reference-video")
    if not input_mode:
        input_mode = "video" if reference_video else "frames" if last_image else "image" if first_image else "text"
    art_prompt = take_option("--image-prompt")
    art_model = take_option("--image-model")
    art_edit = "--image-edit" in argv
    art_references = []
    while "--image-reference" in argv:
        art_references.append(take_option("--image-reference"))
    auto_video = "--generate-video" in argv
    auto_art = "--generate-image" in argv
    setup_account = "--hf-setup" in argv
    app = QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    if setup_account:
        HuggingFaceDialog().exec()
        return 0
    window = Studio()
    tab_indexes = {"art": 0, "image": 0, "camera": 1, "audio": 2, "whisper": 2, "video": 3, "datasets": 4}
    if requested_tab in tab_indexes:
        window.tabs.setCurrentIndex(tab_indexes[requested_tab])
    lab = window.video_lab
    if video_prompt:
        lab.prompt.setPlainText(video_prompt)
    try:
        if input_mode:
            index = lab.input_mode.findData(input_mode)
            if index < 0:
                raise ValueError("Modo de entrada desconhecido.")
            lab.input_mode.setCurrentIndex(index)
        if input_mode == "text" and (first_image or last_image or reference_video):
            raise ValueError("Escolha o modo de entrada correspondente aos anexos.")
        if provider:
            if provider not in VIDEO_PROVIDERS:
                raise ValueError("Modelo de video desconhecido.")
            lab.provider.setCurrentIndex(lab.provider.findData(provider))
        if quality:
            if quality not in VIDEO_QUALITIES.values():
                raise ValueError("Qualidade de video desconhecida.")
            lab.quality.setCurrentIndex(lab.quality.findData(quality))
        if duration:
            requested = float(duration)
            if not requested.is_integer() or not lab.duration.minimum() <= requested <= lab.duration.maximum():
                raise ValueError(f"Escolha uma duracao entre {lab.duration.minimum()} e {lab.duration.maximum()} segundos.")
            lab.duration.setValue(int(requested))
        if video_format:
            format_indexes = {"landscape": 0, "paisagem": 0, "horizontal": 0, "16:9": 0, "vertical": 1, "portrait": 1, "9:16": 1, "square": 2, "quadrado": 2, "1:1": 2}
            if video_format not in format_indexes:
                raise ValueError("Formato de video desconhecido.")
            lab.preset.setCurrentIndex(format_indexes[video_format])
        for entry, path in [(lab.first_image, first_image), (lab.last_image, last_image), (lab.reference_video, reference_video)]:
            if path:
                entry.set_path(path)
        if art_prompt:
            window.prompt.setPlainText(art_prompt)
        if len(art_references) > 3:
            raise ValueError("Use ate 3 imagens de referencia.")
        if art_model == "hf":
            window.model.setCurrentText(IMAGE_MODEL_LABEL)
        if art_edit or art_references:
            window.art_mode.setCurrentIndex(1)
            for entry, path in zip(window.art_references, art_references):
                entry.set_path(path)
    except (ValueError, OSError) as exc:
        auto_video = auto_art = False
        QMessageBox.warning(window, "Opcoes invalidas", safe_error(exc))
    window.show()
    if auto_video and video_prompt:
        QTimer.singleShot(500, lab.generate)
    if auto_art and art_prompt:
        QTimer.singleShot(500, window.generate)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
