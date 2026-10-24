from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox
from media_inputs import validate_image, validate_video, IMAGE_FILTER, VIDEO_FILTER


class MediaInput(QWidget):
    changed = pyqtSignal()

    def __init__(self, title, kind="image", parent=None):
        super().__init__(parent)
        self.kind = kind
        self.path = ""
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        label = QLabel(title)
        label.setStyleSheet("color:#9eb8c9;border:none;")
        layout.addWidget(label)
        row = QHBoxLayout()
        self.field = QLineEdit()
        self.field.setReadOnly(True)
        self.field.setPlaceholderText("Escolha ou arraste um arquivo aqui")
        self.field.setStyleSheet("background:#070b11;color:#e4f5fa;padding:5px;border:1px solid #26384a;")
        self.browse = QPushButton("ANEXAR")
        self.clear_button = QPushButton("X")
        self.clear_button.setToolTip("Remover anexo")
        self.clear_button.setMaximumWidth(28)
        self.browse.clicked.connect(self.select)
        self.clear_button.clicked.connect(self.clear)
        row.addWidget(self.field, 1)
        row.addWidget(self.browse)
        row.addWidget(self.clear_button)
        layout.addLayout(row)

    def set_path(self, value):
        if not value:
            self.clear()
            return
        (validate_video if self.kind == "video" else validate_image)(value)
        self.path = str(Path(value).resolve())
        self.field.setText(Path(value).name)
        self.field.setToolTip(self.path)
        self.changed.emit()

    def select(self):
        path, _ = QFileDialog.getOpenFileName(self, "Anexar " + self.kind, "",
                                              VIDEO_FILTER if self.kind == "video" else IMAGE_FILTER)
        if path:
            try:
                self.set_path(path)
            except ValueError as exc:
                QMessageBox.warning(self, "Arquivo invalido", str(exc))

    def clear(self):
        self.path = ""
        self.field.clear()
        self.field.setToolTip("")
        self.changed.emit()

    def dragEnterEvent(self, event):
        if self.isEnabled() and event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1:
            if event.mimeData().urls()[0].isLocalFile():
                event.acceptProposedAction()

    def dropEvent(self, event):
        try:
            self.set_path(event.mimeData().urls()[0].toLocalFile())
            event.acceptProposedAction()
        except ValueError as exc:
            QMessageBox.warning(self, "Arquivo invalido", str(exc))
