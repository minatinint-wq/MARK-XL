from __future__ import annotations
import sys
import threading
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout
from hf_auth import huggingface_token, validate_token, save_token, safe_error


class HuggingFaceDialog(QDialog):
    checked = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conta Hugging Face - Jarvis")
        self.setMinimumWidth(590)
        self.busy = False
        self.setStyleSheet(
            "QDialog{background:#101722;color:#e4f5fa;} QLabel{color:#e4f5fa;}"
            "QLineEdit{background:#070b11;color:#e4f5fa;border:1px solid #42dfff;padding:10px;}"
            "QPushButton{background:#15212e;color:#67efad;border:1px solid #344b5c;padding:10px;}"
            "QPushButton:disabled{color:#78909c;}"
        )
        layout = QVBoxLayout(self)
        heading = QLabel("CONECTAR A CONTA GRATUITA")
        heading.setStyleSheet("font-size:18px;font-weight:bold;color:#67efad;padding:8px;")
        layout.addWidget(heading)
        instructions = QLabel(
            "1. Crie sua conta e confirme o e-mail.\n"
            "2. Em Access Tokens, crie um token Read (leitura) chamado Jarvis.\n"
            "3. Cole abaixo e clique em Validar e salvar.\n\n"
            "O token fica criptografado para seu usuario do Windows. "
            "Ele nao aparece em logs nem e enviado para outras pessoas."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        links = QHBoxLayout()
        for title, url in [("Criar conta", "https://huggingface.co/join"),
                           ("Criar token de leitura", "https://huggingface.co/settings/tokens")]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            links.addWidget(button)
        layout.addLayout(links)
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText("Cole aqui o token hf_... (o campo fica oculto)")
        self.token.setMaxLength(512)
        layout.addWidget(self.token)
        row = QHBoxLayout()
        self.save_button = QPushButton("VALIDAR E SALVAR")
        self.test_button = QPushButton("TESTAR CONTA SALVA")
        self.save_button.clicked.connect(lambda: self.start_check(True))
        self.test_button.clicked.connect(lambda: self.start_check(False))
        row.addWidget(self.save_button)
        row.addWidget(self.test_button)
        layout.addLayout(row)
        self.status = QLabel("Cole o token somente neste campo do aplicativo.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setMinimumHeight(65)
        layout.addWidget(self.status)
        quota = QLabel(
            "ZeroGPU: sem login, 2 min de processamento/dia; conta gratuita, 5 min/dia. "
            "A cota e compartilhada por imagens e videos. Ela nao indica a duracao do video.\n"
            "Comece com LTX, Economico, 8 a 10 s. Mais tempo depende da cota e do Space."
        )
        quota.setWordWrap(True)
        quota.setStyleSheet("color:#9caebb;")
        layout.addWidget(quota)
        self.close_button = QPushButton("FECHAR")
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button)
        self.checked.connect(self.on_checked)
        self.failed.connect(self.on_failed)

    def set_busy(self, value):
        self.busy = value
        for widget in [self.token, self.save_button, self.test_button, self.close_button]:
            widget.setEnabled(not value)

    def start_check(self, save):
        if self.busy:
            return
        token = self.token.text().strip() if save else ""
        self.token.clear()
        self.set_busy(True)
        self.status.setText("Validando com o Hugging Face. Nenhuma GPU sera usada...")
        def work():
            try:
                candidate = token if save else huggingface_token()
                if not candidate:
                    raise ValueError("Nenhuma conta salva. Cole um token de leitura primeiro.")
                account = validate_token(candidate)
                if account.get("email_verified") is False:
                    raise ValueError("Confirme seu e-mail no Hugging Face e valide novamente.")
                if save:
                    save_token(candidate)
                self.checked.emit(account)
            except Exception as exc:
                self.failed.emit(safe_error(exc))
        threading.Thread(target=work, daemon=True).start()

    def on_checked(self, account):
        self.set_busy(False)
        self.status.setText(
            "Conectado como " + account["username"] + ". Conta validada.\n"
            "O Studio usara esta conta nas proximas geracoes."
        )
        self.status.setStyleSheet("color:#67efad;")
        self.close_button.setText("PRONTO - FECHAR")

    def on_failed(self, message):
        self.set_busy(False)
        self.status.setText(message)
        self.status.setStyleSheet("color:#ff9c9c;")

    def reject(self):
        if not self.busy:
            super().reject()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
        else:
            super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = HuggingFaceDialog()
    dialog.show()
    sys.exit(app.exec())
