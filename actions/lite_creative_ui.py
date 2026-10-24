"""Load the original Sketchbook, instruments and Libras scene only on demand."""
import subprocess
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout


class LiteCreativeDialog(QDialog):
    COMMANDS = {"sketch": "openSketch", "music": "openMusic", "libras": "openLibras"}

    def __init__(self, mode: str, submit, parent=None):
        super().__init__(parent)
        from actions.reactor_view import ReactorView

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Jarvis · Sketchbook, instrumentos e Libras")
        self.resize(940, 720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._desired_mode = mode
        self.reactor = ReactorView(self)
        self.reactor.textSubmitted.connect(submit)
        self.reactor.ready.connect(lambda: self.open_mode(self._desired_mode))
        layout.addWidget(self.reactor)
        self.reactor.set_status(state="LISTENING", speaking=False, muted=False, mode="normal")

    def open_mode(self, mode: str) -> None:
        if mode not in self.COMMANDS:
            raise ValueError("Modo criativo desconhecido")
        self._desired_mode = mode
        if self.reactor._ready:
            self.reactor._bridge.command.emit(self.COMMANDS[mode])
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        self.reactor.shutdown()
        super().closeEvent(event)


def webengine_preflight() -> bool:
    """A native Qt crash must not take the voice assistant down with it."""
    script = (
        "from PyQt6.QtWidgets import QApplication; "
        "from PyQt6.QtWebEngineCore import QWebEngineProfile; "
        "app=QApplication([]); profile=QWebEngineProfile(); "
        "print('ready')"
    )
    try:
        check = subprocess.run(
            [sys.executable, "-c", script], capture_output=True,
            timeout=15, check=False,
        )
        return check.returncode == 0 and b"ready" in check.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
