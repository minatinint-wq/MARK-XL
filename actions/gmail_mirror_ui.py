"""Small, on-demand Gmail metadata panel. No message body is fetched."""
from __future__ import annotations

import threading
import webbrowser

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout

from actions import gmail_mirror


class GmailMirrorDialog(QDialog):
    result_ready = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Jarvis · Gmail somente leitura")
        self.setMinimumSize(620, 400)
        self.setStyleSheet("background:#06141c;color:#d1eff7;")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Remetente, assunto e data da caixa de entrada. Nenhum corpo ou anexo é baixado."))
        controls = QHBoxLayout()
        self.connect_button = QPushButton("Conectar Gmail")
        self.connect_button.clicked.connect(self._connect)
        controls.addWidget(self.connect_button)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self._refresh)
        controls.addWidget(self.refresh_button)
        self.open_button = QPushButton("Abrir selecionado no Gmail")
        self.open_button.clicked.connect(self._open_selected)
        controls.addWidget(self.open_button)
        layout.addLayout(controls)
        self.items = QListWidget()
        self.items.itemDoubleClicked.connect(lambda _item: self._open_selected())
        layout.addWidget(self.items)
        self.status = QLabel("Conecte sua conta Google uma vez e atualize quando quiser.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.result_ready.connect(self._show_result)

    def _run(self, action: str):
        self.connect_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.status.setText("Conectando ao Gmail..." if action == "connect" else "Buscando somente cabeçalhos...")

        def worker():
            try:
                if action == "connect":
                    gmail_mirror.connect()
                rows = gmail_mirror.inbox()
                self.result_ready.emit({"rows": rows})
            except Exception as exc:
                self.result_ready.emit({"error": str(exc) if isinstance(exc, gmail_mirror.GmailMirrorError) else "Falha ao consultar Gmail."})

        threading.Thread(target=worker, name="JarvisGmailMetadata", daemon=True).start()

    def _connect(self):
        self._run("connect")

    def _refresh(self):
        self._run("refresh")

    def _show_result(self, result: dict):
        self.connect_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        if result.get("error"):
            self.status.setText(result["error"])
            return
        self.items.clear()
        for row in result.get("rows", []):
            item = QListWidgetItem(f"{row['when']}   {row['from']}  —  {row['subject']}")
            item.setData(Qt.ItemDataRole.UserRole, row["thread_id"])
            self.items.addItem(item)
        self.status.setText(f"{self.items.count()} mensagens listadas. Só metadados; sem sincronização em segundo plano.")

    def _open_selected(self):
        item = self.items.currentItem()
        if item is None:
            self.status.setText("Selecione uma mensagem para abrir no Gmail.")
            return
        try:
            webbrowser.open(gmail_mirror.gmail_url(item.data(Qt.ItemDataRole.UserRole)))
        except gmail_mirror.GmailMirrorError as exc:
            self.status.setText(str(exc))
