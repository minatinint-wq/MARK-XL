from __future__ import annotations

import threading
import time
from typing import Any

from actions.cpu_acceleration import configure_cpu_acceleration, configure_opencv

configure_cpu_acceleration()
import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from actions.vision_lab import VisionCatalog, analyze_scene_ollama

configure_opencv(cv2)


BG = "#070b12"
PANEL = "#0d1520"
CYAN = "#52e6ff"
ORANGE = "#ffad42"
GREEN = "#69f0ae"
TEXT = "#d8f7ff"
MUTED = "#78909c"


class VisionLabWindow(QMainWindow):
    analysis_done = pyqtSignal(str)
    analysis_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("J.A.R.V.I.S - Vision Labs")
        self.setMinimumSize(980, 650)
        self.resize(1180, 760)
        self.catalog = VisionCatalog()
        self.capture: cv2.VideoCapture | None = None
        self.current_frame: np.ndarray | None = None
        self._ticks = 0
        self._face_results: list[dict[str, Any]] = []
        self._object_result: dict[str, Any] | None = None
        self._analyzing = False
        self._affective_seen: dict[str, float] = {}

        central = QWidget()
        central.setStyleSheet(f"background:{BG}; color:{TEXT};")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)
        root.addWidget(self._header())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle{background:#193142;width:2px;}")
        splitter.addWidget(self._camera_panel())
        splitter.addWidget(self._control_panel())
        splitter.setSizes([760, 390])
        root.addWidget(splitter, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self.analysis_done.connect(self._finish_analysis)
        self.analysis_failed.connect(self._fail_analysis)
        self._refresh_catalog()
        QTimer.singleShot(100, self.start_camera)

    def _header(self) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("VISION LABS")
        title.setStyleSheet(f"font-size:24px;font-weight:700;letter-spacing:4px;color:{CYAN};")
        subtitle = QLabel("memoria visual local | pessoas | objetos | leitura de cena")
        subtitle.setStyleSheet(f"font-size:12px;color:{MUTED};")
        row.addWidget(title)
        row.addWidget(subtitle)
        row.addStretch()
        self.camera_state = QLabel("CAMERA: OFFLINE")
        self.camera_state.setStyleSheet(f"color:{ORANGE};font-weight:700;")
        row.addWidget(self.camera_state)
        return box

    def _camera_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid #193142;border-radius:8px;}}")
        layout = QVBoxLayout(panel)
        self.preview = QLabel("Inicializando camera...")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(640, 480)
        self.preview.setStyleSheet("background:#020509;border:1px solid #245066;color:#607d8b;")
        layout.addWidget(self.preview, 1)

        row = QHBoxLayout()
        self.camera_button = self._button("PARAR CAMERA", CYAN)
        self.camera_button.clicked.connect(self._toggle_camera)
        self.recognition = QCheckBox("RECONHECIMENTO AO VIVO")
        self.recognition.setChecked(True)
        self.recognition.setStyleSheet(f"color:{TEXT};spacing:8px;")
        row.addWidget(self.camera_button)
        row.addWidget(self.recognition)
        row.addStretch()
        layout.addLayout(row)
        return panel

    def _control_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid #193142;border-radius:8px;}}")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        label = QLabel("ENSINAR PELA CAMERA")
        label.setStyleSheet(f"color:{CYAN};font-weight:700;letter-spacing:2px;")
        layout.addWidget(label)

        self.kind = QComboBox()
        self.kind.addItem("Pessoa", "person")
        self.kind.addItem("Objeto", "object")
        self.kind.currentIndexChanged.connect(self._update_hint)
        self.kind.setStyleSheet(self._input_style())
        layout.addWidget(self.kind)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Nome: Sabrina, caneca azul, controle...")
        self.name.setStyleSheet(self._input_style())
        self.name.returnPressed.connect(self.capture_sample)
        layout.addWidget(self.name)

        self.learn_button = self._button("CAPTURAR EXEMPLO", GREEN)
        self.learn_button.clicked.connect(self.capture_sample)
        layout.addWidget(self.learn_button)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(f"color:{MUTED};font-size:11px;border:none;")
        layout.addWidget(self.hint)
        self._update_hint()

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color:#193142;")
        layout.addWidget(divider)

        scene_label = QLabel("ANALISE LOCAL DA CENA")
        scene_label.setStyleSheet(f"color:{ORANGE};font-weight:700;letter-spacing:2px;")
        layout.addWidget(scene_label)
        self.scene_prompt = QLineEdit()
        self.scene_prompt.setPlaceholderText("Opcional: o que tem sobre a mesa?")
        self.scene_prompt.setStyleSheet(self._input_style())
        layout.addWidget(self.scene_prompt)
        self.analyze_button = self._button("ANALISAR COM QWEN LOCAL", ORANGE)
        self.analyze_button.clicked.connect(self.analyze_scene)
        layout.addWidget(self.analyze_button)

        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("Resultados e descricoes aparecem aqui.")
        self.result.setStyleSheet(
            "QTextEdit{background:#050911;color:#cfeef5;border:1px solid #193142;padding:8px;}"
        )
        layout.addWidget(self.result, 1)

        catalog_label = QLabel("MEMORIA APRENDIDA")
        catalog_label.setStyleSheet(f"color:{CYAN};font-weight:700;")
        layout.addWidget(catalog_label)
        self.catalog_list = QListWidget()
        self.catalog_list.setStyleSheet(
            "QListWidget{background:#050911;color:#cfeef5;border:1px solid #193142;}"
            "QListWidget::item{padding:5px;} QListWidget::item:selected{background:#153545;}"
        )
        layout.addWidget(self.catalog_list, 1)
        delete = self._button("ESQUECER SELECIONADO", "#ff6b7a")
        delete.clicked.connect(self.delete_selected)
        layout.addWidget(delete)
        return panel

    @staticmethod
    def _input_style() -> str:
        return (
            "QLineEdit,QComboBox{background:#050911;color:#d8f7ff;border:1px solid #245066;"
            "border-radius:4px;padding:8px;} QComboBox QAbstractItemView{background:#0d1520;color:#d8f7ff;}"
        )

    @staticmethod
    def _button(text: str, color: str) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            f"QPushButton{{background:#0a111b;color:{color};border:1px solid {color};"
            "border-radius:4px;padding:9px;font-weight:700;}"
            f"QPushButton:hover{{background:{color};color:#071018;}}"
            "QPushButton:disabled{color:#52616a;border-color:#34434b;}"
        )
        return button

    def configure(self, kind: str = "", label: str = "") -> None:
        if kind:
            wanted = "person" if kind.lower() in {"person", "people", "pessoa", "rosto"} else "object"
            index = self.kind.findData(wanted)
            if index >= 0:
                self.kind.setCurrentIndex(index)
        if label:
            self.name.setText(label)

    def start_camera(self) -> None:
        if self.capture is not None and self.capture.isOpened():
            return
        capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(0)
        if not capture.isOpened():
            capture.release()
            self.capture = None
            self.preview.setText("Camera indisponivel. Verifique permissao ou outro app usando a camera.")
            self.camera_state.setText("CAMERA: INDISPONIVEL")
            self.camera_state.setStyleSheet("color:#ff6b7a;font-weight:700;")
            self.camera_button.setText("TENTAR CAMERA")
            return
        self.capture = capture
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.timer.start(66)
        self.camera_state.setText("CAMERA: ONLINE")
        self.camera_state.setStyleSheet(f"color:{GREEN};font-weight:700;")
        self.camera_button.setText("PARAR CAMERA")

    def stop_camera(self) -> None:
        self.timer.stop()
        if self.capture is not None:
            self.capture.release()
        self.capture = None
        self.current_frame = None
        self.preview.clear()
        self.preview.setText("Camera parada.")
        self.camera_state.setText("CAMERA: OFFLINE")
        self.camera_state.setStyleSheet(f"color:{ORANGE};font-weight:700;")
        self.camera_button.setText("INICIAR CAMERA")

    def _toggle_camera(self) -> None:
        if self.capture is not None and self.capture.isOpened():
            self.stop_camera()
        else:
            self.start_camera()

    @staticmethod
    def _center_roi(frame: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        height, width = frame.shape[:2]
        rw, rh = int(width * 0.48), int(height * 0.55)
        x, y = (width - rw) // 2, (height - rh) // 2
        return frame[y:y + rh, x:x + rw].copy(), (x, y, rw, rh)

    def _update_frame(self) -> None:
        if self.capture is None:
            return
        ok, frame = self.capture.read()
        if not ok:
            return
        frame = cv2.flip(frame, 1)
        self.current_frame = frame.copy()
        self._ticks += 1

        if self.recognition.isChecked() and self._ticks % 10 == 0:
            self._face_results = self.catalog.recognize_faces(frame)
            roi, _box = self._center_roi(frame)
            self._object_result = self.catalog.recognize_object(roi)
            self._remember_recognitions()

        display = frame.copy()
        _roi, (x, y, w, h) = self._center_roi(display)
        if self.kind.currentData() == "object":
            cv2.rectangle(display, (x, y), (x + w, y + h), (66, 173, 255), 2)
            cv2.putText(display, "OBJETO AQUI", (x + 10, y + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (66, 173, 255), 2)
        for item in self._face_results:
            fx, fy, fw, fh = item["box"]
            known = item["label"] != "Pessoa desconhecida"
            color = (80, 235, 160) if known else (90, 160, 255)
            cv2.rectangle(display, (fx, fy), (fx + fw, fy + fh), color, 2)
            caption = f"{item['label']} {item['score']:.0%}" if known else item["label"]
            cv2.putText(display, caption, (fx, max(24, fy - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)
        if self._object_result:
            caption = f"Objeto: {self._object_result['label']} {self._object_result['score']:.0%}"
            cv2.putText(display, caption, (18, display.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 235, 160), 2)

        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.preview.setPixmap(pixmap)

    def _remember_recognitions(self) -> None:
        recognized = []
        for item in self._face_results:
            if item.get("label") != "Pessoa desconhecida":
                recognized.append(("person", str(item["label"]), float(item.get("score") or 0.0)))
        if self._object_result:
            recognized.append(("object", str(self._object_result["label"]), float(self._object_result.get("score") or 0.0)))
        now = time.time()
        for kind, label, score in recognized:
            key = f"{kind}:{label.casefold()}"
            if now - self._affective_seen.get(key, 0.0) < 300:
                continue
            self._affective_seen[key] = now
            def save_observation(k=kind, name=label, confidence=score):
                try:
                    from actions.affective_memory import observe_entity
                    observe_entity(kind=k, label=name, event="reconhecido pela camera", confidence=confidence, source="vision_lab")
                except Exception:
                    pass
            threading.Thread(target=save_observation, daemon=True).start()

    def _update_hint(self) -> None:
        if self.kind.currentData() == "person":
            self.hint.setText("Capture de 3 a 5 exemplos olhando para a camera e variando levemente o angulo e a luz.")
        else:
            self.hint.setText("Coloque o objeto dentro do quadro laranja. Capture de 3 a 5 lados com fundo parecido ao uso real.")

    def capture_sample(self) -> None:
        if self.current_frame is None:
            self.result.setPlainText("Inicie a camera antes de ensinar.")
            return
        try:
            sample = self.current_frame
            if self.kind.currentData() == "object":
                sample, _box = self._center_roi(sample)
            learned = self.catalog.add_sample(str(self.kind.currentData()), self.name.text(), sample)
            word = "pessoa" if learned["kind"] == "people" else "objeto"
            self.result.setPlainText(
                f"Aprendido: {learned['label']} como {word}. Exemplos salvos: {learned['samples']}."
            )
            self._refresh_catalog()
        except Exception as exc:
            self.result.setPlainText(str(exc))

    def analyze_scene(self) -> None:
        if self.current_frame is None or self._analyzing:
            if self.current_frame is None:
                self.result.setPlainText("Inicie a camera antes de analisar a cena.")
            return
        self._analyzing = True
        self.analyze_button.setEnabled(False)
        self.analyze_button.setText("ANALISANDO...")
        frame = self.current_frame.copy()
        prompt = self.scene_prompt.text()

        def work() -> None:
            try:
                self.analysis_done.emit(analyze_scene_ollama(frame, prompt))
            except Exception as exc:
                self.analysis_failed.emit(str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _finish_analysis(self, text: str) -> None:
        self._analyzing = False
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("ANALISAR COM QWEN LOCAL")
        self.result.setPlainText(text)

    def _fail_analysis(self, error: str) -> None:
        self._finish_analysis(f"Falha na analise local: {error}")

    def _refresh_catalog(self) -> None:
        self.catalog_list.clear()
        for row in self.catalog.list_entries():
            kind = "PESSOA" if row["kind"] == "people" else "OBJETO"
            self.catalog_list.addItem(f"{kind} | {row['label']} | {row['samples']} exemplos")

    def delete_selected(self) -> None:
        item = self.catalog_list.currentItem()
        if item is None:
            self.result.setPlainText("Selecione uma memoria para esquecer.")
            return
        parts = [part.strip() for part in item.text().split("|")]
        if len(parts) < 2:
            return
        kind = "person" if parts[0] == "PESSOA" else "object"
        if self.catalog.delete(kind, parts[1]):
            self.result.setPlainText(f"Memoria removida: {parts[1]}.")
            self._refresh_catalog()

    def closeEvent(self, event) -> None:
        self.stop_camera()
        super().closeEvent(event)
