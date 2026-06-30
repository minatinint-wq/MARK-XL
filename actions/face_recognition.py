import cv2 as cv
import os
import json
import time
import threading
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FACE_DIR = BASE_DIR / "memory" / "faces"
FACE_DATA = BASE_DIR / "memory" / "face_data.json"
_lock = threading.Lock()
_FACE_SIZE = 160

class FaceRecognition:
    def __init__(self, ui=None, wake_callback=None, away_timeout=30):
        self.ui = ui
        self.wake_callback = wake_callback
        self.away_timeout = away_timeout
        self._cascade = None
        self._recognizer = None
        self._model_loaded = False
        self.known_faces = {}
        self.last_known_user = None
        self._load_known_faces()

    def _get_cascade(self):
        if self._cascade is None:
            cc = cv.CascadeClassifier(
                cv.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            if not cc.empty():
                self._cascade = cc
        return self._cascade

    def _build_recognizer(self):
        r = cv.face.LBPHFaceRecognizer_create()
        images, labels = [], []
        label_map = {}
        for name in sorted(self.known_faces.keys()):
            user_dir = FACE_DIR / name
            if not user_dir.exists():
                continue
            label = len(label_map)
            for fpath in sorted(user_dir.glob("*.jpg")):
                img = cv.imread(str(fpath), cv.IMREAD_GRAYSCALE)
                if img is not None:
                    img = cv.resize(img, (_FACE_SIZE, _FACE_SIZE))
                    images.append(img)
                    labels.append(label)
            if any(True for _ in user_dir.glob("*.jpg")):
                label_map[label] = name
        if images:
            r.train(images, np.array(labels))
            for name in self.known_faces:
                for lbl, nm in label_map.items():
                    if nm == name:
                        self.known_faces[name]["label"] = lbl
                        break
            self._save_known_faces()
        return r

    def _get_recognizer(self):
        if not self._model_loaded and self.known_faces:
            try:
                self._recognizer = self._build_recognizer()
                self._model_loaded = True
            except Exception:
                self._recognizer = None
        return self._recognizer

    def _open_camera(self):
        try:
            cap = cv.VideoCapture(0, cv.CAP_DSHOW)
            if cap.isOpened():
                cap.set(cv.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv.CAP_PROP_FRAME_HEIGHT, 480)
                for _ in range(3):
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        return cap
                cap.release()
        except Exception:
            pass
        return None

    def _capture_face(self, cap):
        for _ in range(5):
            ret, frame = cap.read()
            if not ret or frame is None or frame.size == 0:
                continue
            gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
            cascade = self._get_cascade()
            if cascade is None:
                return None
            faces = cascade.detectMultiScale(gray, 1.3, 5, minSize=(80, 80))
            if len(faces) > 0:
                x, y, w, h = faces[0]
                face = gray[y:y+h, x:x+w]
                return cv.resize(face, (_FACE_SIZE, _FACE_SIZE))
        return None

    def _capture_faces_bulk(self, cap, count=20, duration=6):
        faces = []
        start = time.time()
        cascade = self._get_cascade()
        if cascade is None:
            return faces
        while time.time() - start < duration and len(faces) < count:
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
            detected = cascade.detectMultiScale(gray, 1.3, 5, minSize=(80, 80))
            for (x, y, w, h) in detected:
                face = gray[y:y+h, x:x+w]
                face = cv.resize(face, (_FACE_SIZE, _FACE_SIZE))
                faces.append(face)
                if len(faces) >= count:
                    break
            time.sleep(0.05)
        return faces[:count]

    def _load_known_faces(self):
        self.known_faces = {}
        try:
            if FACE_DATA.exists():
                with open(FACE_DATA, "r", encoding="utf-8") as f:
                    self.known_faces = json.load(f)
        except Exception:
            self.known_faces = {}
        FACE_DIR.mkdir(parents=True, exist_ok=True)

    def _save_known_faces(self):
        with _lock:
            with open(FACE_DATA, "w", encoding="utf-8") as f:
                json.dump(self.known_faces, f, indent=2, ensure_ascii=False)

    def _predict(self, face_img):
        r = self._get_recognizer()
        if r is None or not self.known_faces:
            return None, 0
        try:
            label, confidence = r.predict(face_img)
            for name, info in self.known_faces.items():
                if info.get("label") == label and isinstance(confidence, (int, float)):
                    if confidence < 85:
                        return name, confidence
                    return None, confidence
        except Exception:
            pass
        return None, 0

    def identify(self, face_img=None):
        if face_img is not None:
            return self._predict(face_img)
        cap = self._open_camera()
        if cap is None:
            return "unknown", 0
        face_img = self._capture_face(cap)
        cap.release()
        if face_img is None:
            return "unknown", 0
        return self._predict(face_img)

    def train(self, name, duration=6):
        cap = self._open_camera()
        if cap is None:
            return False, "Nenhuma camera encontrada"
        faces = self._capture_faces_bulk(cap, count=20, duration=duration)
        cap.release()

        if len(faces) < 5:
            return False, f"So {len(faces)} faces capturadas, precisa de pelo menos 5"

        user_dir = FACE_DIR / name
        user_dir.mkdir(parents=True, exist_ok=True)
        for i, face in enumerate(faces):
            fname = user_dir / f"face_{int(time.time()*1000)}_{i}.jpg"
            cv.imwrite(str(fname), face)

        label = len(self.known_faces)
        self.known_faces[name] = {
            "photos": len(faces),
            "trained_at": time.time(),
            "label": label
        }
        self._save_known_faces()
        self._model_loaded = False
        self._recognizer = None
        return True, f"{len(faces)} fotos de {name} treinadas!"

    def snapshot(self):
        cap = self._open_camera()
        if cap is None:
            return None
        result = self._capture_face(cap)
        cap.release()
        return result

    def is_registered(self):
        return len(self.known_faces) > 0

    def get_user_name(self):
        return list(self.known_faces.keys())

    def delete_user(self, name):
        if name not in self.known_faces:
            return False
        user_dir = FACE_DIR / name
        if user_dir.exists():
            import shutil
            shutil.rmtree(user_dir)
        del self.known_faces[name]
        self._save_known_faces()
        self._model_loaded = False
        self._recognizer = None
        return True

    def get_status(self):
        return {
            "known_users": list(self.known_faces.keys()),
            "total_faces_trained": len(self.known_faces)
        }

    def start(self):
        pass

    def stop(self):
        pass

    def register_first_face(self):
        print("\n" + "=" * 50)
        print("  PRIMEIRA ATIVACAO - Registro facial")
        print("=" * 50)
        name = input("\n  Digite seu nome: ").strip()
        if not name:
            name = "Usuario"
        print("\n  Olhe para a camera. Capturando 20 fotos...")
        input("  Pressione ENTER quando estiver pronto...")
        success, msg = self.train(name, duration=6)
        if success:
            print(f"\n  OK: {msg}")
            print(f"  Bem-vindo, {name}! Iniciando JARVIS...\n")
            return True, name
        print(f"\n  FALHA: {msg}")
        retry = input("  Tentar novamente? (s/n): ").strip().lower()
        if retry == "s":
            return self.register_first_face()
        return False, msg

    def boot_authenticate(self, timeout=15):
        if not self.is_registered():
            return None
        cascade = self._get_cascade()
        if cascade is None:
            return None
        cap = self._open_camera()
        if cap is None:
            return None
        print(f"  Olhe para a camera. Reconhecendo em ate {timeout}s...")
        start = time.time()
        result = None
        while time.time() - start < timeout:
            face = self._capture_face(cap)
            if face is not None:
                name, conf = self._predict(face)
                if name:
                    result = (name, conf)
                    break
            elapsed = int(time.time() - start)
            if elapsed > 0 and elapsed % 3 == 0:
                print(f"  Aguardando... ({timeout - elapsed}s restantes)")
            time.sleep(0.2)
        cap.release()
        if result:
            name, conf = result
            print(f"  Reconhecido: {name} (confianca: {100-conf:.0f}%)")
            return name
        return None
