from __future__ import annotations

import base64
import json
import re
import shutil
import threading
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from actions.cpu_acceleration import configure_cpu_acceleration, configure_opencv

configure_cpu_acceleration()
import cv2
import numpy as np

configure_opencv(cv2)


BASE_DIR = Path(__file__).resolve().parents[1]
VISION_DIR = BASE_DIR / "memory" / "vision_lab"
CATALOG_PATH = VISION_DIR / "catalog.json"
SAMPLES_DIR = VISION_DIR / "samples"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    plain = re.sub(r"[^a-zA-Z0-9_-]+", "-", plain.strip()).strip("-").lower()
    return plain or "sem-nome"


def _kind(value: str) -> str:
    value = (value or "object").lower().strip()
    return "people" if value in {"person", "people", "pessoa", "pessoas", "face", "rosto"} else "objects"


class VisionCatalog:
    """Small local visual memory based on user-confirmed camera samples."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else VISION_DIR
        self.catalog_path = self.root / "catalog.json"
        self.samples_dir = self.root / "samples"
        self._lock = threading.RLock()
        self._cache: dict[str, tuple[float, np.ndarray | None, np.ndarray | None]] = {}
        self._face_detector = cv2.CascadeClassifier(
            str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
        )
        self.data = self._load()

    def _empty(self) -> dict[str, Any]:
        return {"version": 1, "people": {}, "objects": {}, "updated_at": _now()}

    def _load(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                raw.setdefault("people", {})
                raw.setdefault("objects", {})
                return raw
        except (OSError, ValueError, TypeError):
            pass
        return self._empty()

    def _save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = _now()
        temp = self.catalog_path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.catalog_path)

    def detect_faces(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        if frame is None or frame.size == 0 or self._face_detector.empty():
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found = self._face_detector.detectMultiScale(
            gray, scaleFactor=1.12, minNeighbors=5, minSize=(60, 60)
        )
        return [tuple(map(int, box)) for box in found]

    @staticmethod
    def _person_descriptor(image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        gray = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
        gray = cv2.equalizeHist(gray)
        hog = cv2.HOGDescriptor((64, 64), (16, 16), (8, 8), (8, 8), 9)
        vector = hog.compute(gray).reshape(-1).astype(np.float32)
        return vector / (float(np.linalg.norm(vector)) + 1e-8)

    @staticmethod
    def _object_descriptor(image: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
        resized = cv2.resize(image, (192, 192), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [24, 24], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        _keypoints, descriptors = cv2.ORB_create(nfeatures=350).detectAndCompute(gray, None)
        return hist.reshape(-1).astype(np.float32), descriptors

    def _sample_data(self, path: Path) -> tuple[np.ndarray | None, np.ndarray | None]:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None, None
        key = str(path)
        cached = self._cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1], cached[2]
        image = cv2.imread(str(path))
        if image is None:
            return None, None
        hist, orb = self._object_descriptor(image)
        self._cache[key] = (mtime, hist, orb)
        return hist, orb

    def add_sample(self, kind: str, label: str, image: np.ndarray) -> dict[str, Any]:
        group = _kind(kind)
        clean_label = (label or "").strip()
        if not clean_label:
            raise ValueError("Digite um nome antes de capturar.")
        if image is None or image.size == 0:
            raise ValueError("A camera ainda nao entregou uma imagem valida.")

        sample = image.copy()
        if group == "people":
            faces = self.detect_faces(sample)
            if not faces:
                raise ValueError("Nenhum rosto foi detectado. Olhe para a camera e tente novamente.")
            x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
            margin = int(max(w, h) * 0.18)
            y1, y2 = max(0, y - margin), min(sample.shape[0], y + h + margin)
            x1, x2 = max(0, x - margin), min(sample.shape[1], x + w + margin)
            sample = sample[y1:y2, x1:x2]

        with self._lock:
            entry = self.data[group].setdefault(
                clean_label,
                {"label": clean_label, "created_at": _now(), "samples": []},
            )
            target = self.samples_dir / group / _slug(clean_label)
            target.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = target / f"{stamp}.jpg"
            if not cv2.imwrite(str(path), sample, [int(cv2.IMWRITE_JPEG_QUALITY), 92]):
                raise OSError("Nao foi possivel salvar o exemplo visual.")
            rel = path.relative_to(self.root).as_posix()
            entry["samples"].append({"path": rel, "created_at": _now()})
            while len(entry["samples"]) > 20:
                old = entry["samples"].pop(0)
                try:
                    (self.root / old["path"]).unlink(missing_ok=True)
                except OSError:
                    pass
            entry["updated_at"] = _now()
            self._save()
            learned = {"kind": group, "label": clean_label, "samples": len(entry["samples"]), "path": rel}
            try:
                from actions.affective_memory import observe_entity, remember_entity
                affective_kind = "person" if group == "people" else "object"
                remember_entity(
                    kind=affective_kind,
                    label=clean_label,
                    details=f"Identidade visual ensinada com {len(entry['samples'])} exemplo(s).",
                    importance=0.7,
                    source="vision_lab",
                )
                observe_entity(
                    kind=affective_kind,
                    label=clean_label,
                    event="novo exemplo visual ensinado",
                    confidence=1.0,
                    source="vision_lab",
                )
            except Exception:
                pass
            return learned

    def list_entries(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._lock:
            for group in ("people", "objects"):
                for label, entry in self.data[group].items():
                    rows.append({
                        "kind": group,
                        "label": label,
                        "samples": len(entry.get("samples", [])),
                        "updated_at": entry.get("updated_at") or entry.get("created_at", ""),
                    })
        return sorted(rows, key=lambda row: (row["kind"], row["label"].casefold()))

    def delete(self, kind: str, label: str) -> bool:
        group = _kind(kind)
        with self._lock:
            actual = next((name for name in self.data[group] if name.casefold() == label.casefold()), None)
            if actual is None:
                return False
            for sample in self.data[group][actual].get("samples", []):
                self._cache.pop(str(self.root / sample.get("path", "")), None)
            shutil.rmtree(self.samples_dir / group / _slug(actual), ignore_errors=True)
            del self.data[group][actual]
            self._save()
            return True

    def recognize_faces(self, frame: np.ndarray, threshold: float = 0.84) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        entries = self.data.get("people", {})
        for x, y, w, h in self.detect_faces(frame):
            margin = int(max(w, h) * 0.18)
            y1, y2 = max(0, y - margin), min(frame.shape[0], y + h + margin)
            x1, x2 = max(0, x - margin), min(frame.shape[1], x + w + margin)
            query = self._person_descriptor(frame[y1:y2, x1:x2])
            best_label, best_score = "Pessoa desconhecida", 0.0
            for label, entry in entries.items():
                for item in entry.get("samples", []):
                    image = cv2.imread(str(self.root / item.get("path", "")))
                    if image is None:
                        continue
                    score = float(np.dot(query, self._person_descriptor(image)))
                    if score > best_score:
                        best_label, best_score = label, score
            if best_score < threshold:
                best_label = "Pessoa desconhecida"
            results.append({"box": (x, y, w, h), "label": best_label, "score": best_score})
        return results

    def recognize_object(self, image: np.ndarray, threshold: float = 0.40) -> dict[str, Any] | None:
        if image is None or image.size == 0:
            return None
        query_hist, query_orb = self._object_descriptor(image)
        best_label, best_score = "", 0.0
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        for label, entry in self.data.get("objects", {}).items():
            for item in entry.get("samples", []):
                hist, orb = self._sample_data(self.root / item.get("path", ""))
                if hist is None:
                    continue
                hist_score = max(0.0, float(cv2.compareHist(query_hist, hist, cv2.HISTCMP_CORREL)))
                orb_score = 0.0
                if query_orb is not None and orb is not None and len(query_orb) >= 2 and len(orb) >= 2:
                    pairs = matcher.knnMatch(query_orb, orb, k=2)
                    good = sum(1 for pair in pairs if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance)
                    orb_score = min(1.0, good / max(8.0, len(query_orb) * 0.20))
                score = 0.58 * hist_score + 0.42 * orb_score
                if score > best_score:
                    best_label, best_score = label, score
        if not best_label or best_score < threshold:
            return None
        return {"label": best_label, "score": best_score}


def analyze_scene_ollama(frame: np.ndarray, prompt: str = "", model: str = "qwen3.5:4b") -> str:
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise ValueError("Nao foi possivel preparar a imagem para analise.")
    instruction = prompt.strip() or (
        "Descreva em portugues o que aparece nesta imagem. Liste pessoas, objetos, texto visivel "
        "e qualquer detalhe util. Seja objetivo e nao invente o que nao consegue ver."
    )
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": instruction, "images": [base64.b64encode(encoded).decode("ascii")]}],
        "stream": False,
        "think": False,
        "keep_alive": "5m",
        "options": {"temperature": 0.2, "num_predict": 220},
    }).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            answer = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"O Ollama local nao respondeu: {exc}") from exc
    text = str(answer.get("message", {}).get("content", "")).strip()
    return text or "O modelo local nao retornou uma descricao."


def vision_lab(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "open").lower().strip()
    kind = str(params.get("kind") or params.get("type") or "")
    label = str(params.get("label") or params.get("name") or "").strip()

    if action in {"status", "list", "listar", "catalog"}:
        rows = VisionCatalog().list_entries()
        if not rows:
            return "Vision Labs pronto. Ainda nao ha pessoas ou objetos ensinados."
        items = [f"{row['label']} ({'pessoa' if row['kind'] == 'people' else 'objeto'}, {row['samples']} exemplos)" for row in rows]
        return "Vision Labs aprendeu: " + "; ".join(items) + "."

    if action in {"delete", "remove", "forget", "esquecer"}:
        if not label:
            return "Informe o nome da pessoa ou objeto que deve ser removido."
        removed = VisionCatalog().delete(kind, label)
        return f"{label} removido da memoria visual." if removed else f"Nao encontrei {label} na memoria visual."

    if player is None:
        return "Vision Labs indisponivel: a interface do Jarvis nao foi encontrada."

    if action in {"close", "stop", "fechar"}:
        close = getattr(player, "close_vision_lab", None)
        if callable(close):
            close()
            return "Vision Labs fechado."
    elif action in {"toggle", "alternar"}:
        toggle = getattr(player, "toggle_vision_lab", None)
        if callable(toggle):
            toggle()
            return "Vision Labs alternado."
    else:
        open_lab = getattr(player, "open_vision_lab", None)
        if callable(open_lab):
            open_lab(kind=kind, label=label)
            return "Vision Labs aberto. A camera pode ensinar pessoas e objetos por exemplos locais."

    return "A interface atual do Jarvis nao expoe o controle do Vision Labs."
