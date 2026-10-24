"""On-demand, lightweight local WhatsApp setup for Jarvis (no WebEngine)."""
from __future__ import annotations

import threading

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)

from actions import bird_local


class BirdLocalDialog(QDialog):
    result_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Jarvis · WhatsApp pela Bird local")
        self.setMinimumWidth(480)
        self.setStyleSheet("background:#06141c;color:#d1eff7;")
        settings = bird_local.load_settings()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("A API Bird precisa estar ativa neste PC. Nenhuma mensagem é enviada automaticamente."))

        connection = QFormLayout()
        self.base_url = QLineEdit(settings.get("base_url") or "http://127.0.0.1:8787")
        self.instance_id = QLineEdit(settings.get("instance_id") or "")
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("bird_live_... (deixe vazio para manter a chave salva)")
        connection.addRow("API local", self.base_url)
        connection.addRow("Instância", self.instance_id)
        connection.addRow("Chave", self.key)
        layout.addLayout(connection)
        save_connection = QPushButton("Salvar conexão local")
        save_connection.clicked.connect(self._save_connection)
        layout.addWidget(save_connection)
        check_connection = QPushButton("Ver status da instância")
        check_connection.clicked.connect(self._check_connection)
        layout.addWidget(check_connection)

        contact = QFormLayout()
        self.name = QLineEdit()
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("DDI + DDD + número, apenas dígitos")
        self.consent = QCheckBox("Este contato autorizou mensagens por este canal")
        contact.addRow("Contato", self.name)
        contact.addRow("Número", self.phone)
        contact.addRow("", self.consent)
        layout.addLayout(contact)
        save_contact = QPushButton("Salvar contato autorizado")
        save_contact.clicked.connect(self._save_contact)
        layout.addWidget(save_contact)

        layout.addWidget(QLabel("Mensagem para o contato acima"))
        self.message = QTextEdit()
        self.message.setMaximumHeight(100)
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        self.send_button = QPushButton("Revisar e enviar")
        self.send_button.clicked.connect(self._send)
        actions.addWidget(self.send_button)
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.close)
        actions.addWidget(close_button)
        layout.addLayout(actions)
        self.status = QLabel("Envios são enfileirados; isso não confirma entrega no WhatsApp.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.result_ready.connect(self._finish_send)

    def _save_connection(self):
        try:
            bird_local.save_settings(self.base_url.text(), self.instance_id.text())
            if self.key.text().strip():
                bird_local.save_key(self.key.text())
                self.key.clear()
            self.status.setText("Conexão local salva neste usuário do Windows.")
        except Exception as exc:
            self.status.setText(str(exc))

    def _save_contact(self):
        try:
            bird_local.save_contact(self.name.text(), self.phone.text(), consent=self.consent.isChecked())
            self.status.setText("Contato autorizado salvo localmente.")
        except Exception as exc:
            self.status.setText(str(exc))

    def _check_connection(self):
        self.status.setText("Consultando a Bird local...")

        def work():
            try:
                result = bird_local.instance_status()
            except Exception as exc:
                result = str(exc)
            self.result_ready.emit(result)

        threading.Thread(target=work, name="JarvisBirdLocalStatus", daemon=True).start()

    def _send(self):
        receiver, message = self.name.text().strip(), self.message.toPlainText().strip()
        if not receiver or not message:
            self.status.setText("Informe um contato cadastrado e uma mensagem.")
            return
        answer = QMessageBox.question(
            self, "Confirmar WhatsApp", f"Enviar para {receiver}?\n\n{message[:500]}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.send_button.setEnabled(False)
        self.status.setText("Enviando pedido à Bird local...")

        def work():
            try:
                result = bird_local.send_text(receiver, message, confirmed=True)
            except Exception as exc:
                result = str(exc)
            self.result_ready.emit(result)

        threading.Thread(target=work, name="JarvisBirdLocalSend", daemon=True).start()

    def _finish_send(self, result: str):
        self.status.setText(result)
        self.send_button.setEnabled(True)

    def show_draft(self, receiver: str, message: str = "") -> None:
        self.name.setText(receiver)
        self.message.setPlainText(message)
        self.show()
        self.raise_()
        self.activateWindow()
        (self.message if message else self.name).setFocus()
