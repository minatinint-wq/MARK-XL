from pathlib import Path
from datetime import datetime
import threading
from PyQt6.QtCore import QUrl, pyqtSignal, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QTextEdit, QFileDialog, QMessageBox
from dataset_tools import DATASET_CATALOG, DATASET_ROOT, build_dataset
from hf_auth import safe_error


class DatasetPanel(QWidget):
    prepared = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_output = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("DATASETS PARA TREINAMENTO")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#67efad;")
        layout.addWidget(title)
        info = QLabel(
            "Organize imagens e videos para um treino separado. Os geradores publicos nao sao retreinados por anexar um dataset. "
            "Neste notebook, prepare e revise os dados; o treinamento de geradores exigira uma GPU compativel."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        self.catalog = QComboBox()
        self.catalog.addItems([d["name"] for d in DATASET_CATALOG])
        layout.addWidget(self.catalog)
        self.description = QTextEdit()
        self.description.setReadOnly(True)
        self.description.setMaximumHeight(180)
        layout.addWidget(self.description)
        self.catalog.currentIndexChanged.connect(self.show_catalog)
        link = QPushButton("ABRIR DATASET NO HUGGING FACE")
        link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DATASET_CATALOG[self.catalog.currentIndex()]["url"])))
        layout.addWidget(link)
        self.show_catalog()
        own = QLabel(
            "MEUS ARQUIVOS\n"
            "Separe uma pasta com arquivos e legendas: foto.png + foto.txt, ou clipe.mp4 + clipe.txt. "
            "A exportacao copia somente pares validos para uma pasta nova e gera metadata.jsonl. "
            "Limites por exportacao: 500 arquivos / 2 GB; clipes de ate 30 s / 50 MB."
        )
        own.setWordWrap(True)
        layout.addWidget(own)
        row = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItem("Imagens para LoRA / ajuste", "image")
        self.kind.addItem("Videos para ajuste", "video")
        self.build_button = QPushButton("PREPARAR MINHA PASTA")
        self.build_button.clicked.connect(self.build)
        row.addWidget(self.kind)
        row.addWidget(self.build_button)
        layout.addLayout(row)
        self.status = QTextEdit()
        self.status.setReadOnly(True)
        self.status.setPlaceholderText("O relatorio de pares preparados e arquivos pendentes aparecera aqui.")
        layout.addWidget(self.status, 1)
        self.open_button = QPushButton("ABRIR DATASETS LOCAIS")
        self.open_button.clicked.connect(self.open_folder)
        layout.addWidget(self.open_button)
        self.prepared.connect(self.on_prepared)
        self.failed.connect(self.on_failed)

    def show_catalog(self, *_):
        item = DATASET_CATALOG[self.catalog.currentIndex()]
        self.description.setPlainText(item["description"] + "\n\n" + item["license"] + "\n\n" + item["usage"])

    def build(self):
        source = QFileDialog.getExistingDirectory(self, "Escolha a pasta com arquivos e legendas")
        if not source:
            return
        kind = self.kind.currentData()
        destination = DATASET_ROOT / ("meus-" + kind + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        self.build_button.setEnabled(False)
        self.kind.setEnabled(False)
        self.status.setPlainText("Validando arquivos e preparando o dataset local...")
        def work():
            try:
                self.prepared.emit(build_dataset(Path(source), destination, kind))
            except Exception as exc:
                self.failed.emit(safe_error(exc))
        threading.Thread(target=work, daemon=True).start()

    def on_prepared(self, report):
        self.build_button.setEnabled(True)
        self.kind.setEnabled(True)
        self.last_output = report["destination"]
        self.status.setPlainText(
            f"Preparado: {report['examples']} exemplos.\nDestino: {self.last_output}\n"
            f"Sem legenda: {len(report['missing_captions'])}. Ignorados: {len(report['skipped'])}.\n"
            "Revise dataset_report.json. Nenhum treino foi iniciado."
        )

    def on_failed(self, message):
        self.build_button.setEnabled(True)
        self.kind.setEnabled(True)
        self.status.setPlainText(message)

    def open_folder(self):
        DATASET_ROOT.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_output or str(DATASET_ROOT)))
