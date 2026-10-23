"""Local protected settings and an explicit, free-only voice preview."""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout,
)
from actions import fish_voice


def launch_settings():
    executable = Path(sys.executable)
    if executable.name.lower() == "python.exe" and executable.with_name("pythonw.exe").exists():
        executable = executable.with_name("pythonw.exe")
    subprocess.Popen([str(executable), str(Path(__file__).resolve())],
                     cwd=str(fish_voice.BASE_DIR), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class FishVoiceDialog(QDialog):
    preview_done = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Jarvis · Voz em português")
        self.setFont(QFont("Segoe UI", 10))
        self.setMinimumWidth(540)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._testing = False
        self.setStyleSheet("""
            QDialog { background:#0b1520; color:#e3f3ff; }
            QLabel, QCheckBox { color:#e3f3ff; font-size:14px; }
            QLineEdit, QDoubleSpinBox { background:#142637; color:white; padding:8px; border:1px solid #33576c; border-radius:5px; }
            QPushButton { background:#174a60; color:white; padding:10px; border-radius:5px; }
            QPushButton:disabled { color:#8899aa; background:#24323e; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        title = QLabel("Jarvis (UCM) — Português Brasileiro")
        title.setStyleSheet("font-size:20px; font-weight:bold; color:#67dcff;")
        layout.addWidget(title)
        info = QLabel("Voz de Rogerio Geraldo no Fish Audio.\nModelo s2.1-pro-free · sem troca automática para um modelo pago.")
        info.setWordWrap(True)
        layout.addWidget(info)
        links = QHBoxLayout()
        for label, url in [("Criar chave Fish Audio", fish_voice.API_KEYS_URL), ("Ver voz escolhida", fish_voice.VOICE_URL)]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, target=url: QDesktopServices.openUrl(QUrl(target)))
            links.addWidget(button)
        layout.addLayout(links)
        layout.addWidget(QLabel("Chave da API Fish Audio"))
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Cole aqui. Não envie a chave na conversa.")
        self.key.setClearButtonEnabled(True)
        layout.addWidget(self.key)
        protected = QLabel("A chave fica criptografada pelo Windows neste computador.\nDeixe o campo vazio para manter uma chave já salva.")
        protected.setWordWrap(True)
        protected.setStyleSheet("font-size:12px; color:#acbfcc;")
        layout.addWidget(protected)
        settings = fish_voice.read_settings()
        self.enabled = QCheckBox("Usar esta voz nas respostas do Jarvis")
        self.enabled.setChecked(settings["enabled"])
        layout.addWidget(self.enabled)
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Velocidade"))
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.5, 1.5)
        self.speed.setSingleStep(0.05)
        self.speed.setSuffix("x")
        self.speed.setValue(settings["speed"])
        speed_row.addWidget(self.speed)
        layout.addLayout(speed_row)
        disclosure = QLabel("A voz Fish começa em streaming enquanto a resposta é escrita. Se a transmissão falhar, tenta recuperar a mesma voz; Gemini só assume se as duas tentativas Fish falharem. As falas são enviadas ao Fish Audio.")
        disclosure.setWordWrap(True)
        disclosure.setStyleSheet("font-size:12px; color:#acbfcc;")
        layout.addWidget(disclosure)
        self.status = QLabel(fish_voice.voice_status())
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("Salvar configuração")
        self.save_button.clicked.connect(self.save)
        self.test_button = QPushButton("Testar voz grátis")
        self.test_button.clicked.connect(self.preview)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.test_button)
        layout.addLayout(buttons)
        test_text = QLabel(f'Teste envia somente: “{fish_voice.TEST_TEXT}”')
        test_text.setWordWrap(True)
        test_text.setStyleSheet("font-size:12px; color:#acbfcc;")
        layout.addWidget(test_text)
        self.preview_done.connect(self._preview_finished)

    def save(self, checked=False):
        try:
            if self.key.text().strip():
                fish_voice.save_key(self.key.text())
                self.key.clear()
            fish_voice.save_settings(self.enabled.isChecked(), self.speed.value())
            self.status.setText("Salvo. " + fish_voice.voice_status() + " Reinicie o Jarvis uma vez após instalar esta integração.")
            return True
        except fish_voice.FishVoiceError as exc:
            self.status.setText(str(exc))
        except Exception:
            self.status.setText("Não foi possível salvar a configuração. Confira o acesso à pasta do Jarvis.")
        return False

    def preview(self):
        if self._testing or not self.save():
            return
        key = fish_voice.read_key()
        if not key:
            self.status.setText("Crie uma chave Fish Audio e cole no campo protegido primeiro.")
            return
        self._testing = True
        speed = self.speed.value()
        self.save_button.setEnabled(False)
        self.test_button.setEnabled(False)
        self.status.setText("Gerando a frase de teste no modelo gratuito...")

        def worker():
            try:
                pcm = fish_voice.synthesize(fish_voice.TEST_TEXT, key, speed)
                import sounddevice as sd
                with sd.RawOutputStream(samplerate=fish_voice.SAMPLE_RATE, channels=1, dtype="int16") as stream:
                    stream.write(pcm)
                result = "Teste concluído. A voz PT-BR foi gerada e reproduzida."
            except fish_voice.FishVoiceError as exc:
                result = str(exc)
            except Exception:
                result = "Não foi possível reproduzir o teste. Confira a saída de som e tente novamente."
            self.preview_done.emit(result)

        threading.Thread(target=worker, daemon=True, name="FishVoicePreview").start()

    def _preview_finished(self, result):
        self._testing = False
        self.save_button.setEnabled(True)
        self.test_button.setEnabled(True)
        self.status.setText(result)

    def closeEvent(self, event):
        if self._testing:
            self.status.setText("Aguarde o teste terminar para fechar esta janela.")
            event.ignore()
        else:
            super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = FishVoiceDialog()
    dialog.show()
    sys.exit(app.exec())
