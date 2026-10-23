"""Local 3D viewport; explicit Libras interpretation can send camera sequences to Gemini."""
from __future__ import annotations
import functools
import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from actions.graphics_runtime import GRAPHICS_MODE
from PyQt6.QtCore import QObject, QTimer, QUrl, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QDialog
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEnginePermission, QWebEngineUrlRequestInterceptor
from PyQt6.QtWebEngineWidgets import QWebEngineView

class _AssetHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".cjs": "text/javascript", ".mjs": "text/javascript", ".wasm": "application/wasm", ".glb": "model/gltf-binary"}
    def log_message(self, *args): pass
    def list_directory(self, path):
        self.send_error(403)
        return None
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        super().end_headers()
    def do_GET(self):
        # Only the model's static directory is served, never the app/config directory.
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            self.send_error(403)
            return
        super().do_GET()

class _LocalRequests(QWebEngineUrlRequestInterceptor):
    def __init__(self, port, parent):
        super().__init__(parent)
        self.port = port
    def interceptRequest(self, info):
        url = info.requestUrl()
        allowed = url.scheme() in {'qrc', 'data', 'blob', 'about'} or (
            url.scheme() == 'http' and url.host() == '127.0.0.1' and url.port() == self.port
        )
        if not allowed:
            info.block(True)

class _Page(QWebEnginePage):
    def __init__(self, profile, parent):
        super().__init__(profile, parent)
        self.console_errors = []
    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.console_errors.append((message[:300], line, source.rsplit('/', 1)[-1]))
            self.console_errors = self.console_errors[-20:]

class _Bridge(QObject):
    sketchResult = pyqtSignal(str)
    librasResult = pyqtSignal(str)
    statusChanged = pyqtSignal(str)
    metricsChanged = pyqtSignal(str)
    visibilityChanged = pyqtSignal(bool)
    command = pyqtSignal(str)
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self._sketch_analyzing = False
        self._sketch_last_analysis = 0.0
        self._libras_busy = False
        self._libras_last = 0.0
    @pyqtSlot()
    def ready(self):
        self.view._ready = True
        self.view._load_timer.stop()
        self.statusChanged.emit(json.dumps(self.view._status))
        self.view.ready.emit()
    @pyqtSlot(str)
    def reportError(self, message):
        self.view._fail(message)
    @pyqtSlot(result=bool)
    def armCamera(self):
        # Called exclusively by the explicit camera button in the local page.
        self.view._camera_armed_until = time.monotonic() + 35
        return True
    @pyqtSlot()
    def disarmCamera(self):
        self.view._camera_armed_until = 0
    @pyqtSlot(str, str, str)
    def sketchRequest(self, request_id, action, raw):
        if action not in {'list','load','save','generate','analyze'} or len(raw) > 9_000_000 or len(request_id) > 80:
            return
        def reply(result):
            try:
                self.sketchResult.emit(json.dumps({'requestId':request_id, **result}, ensure_ascii=False))
            except RuntimeError:
                pass  # Window closed while an in-flight request finished.
        if action == 'analyze':
            if self._sketch_analyzing or time.monotonic() - self._sketch_last_analysis < 4:
                reply({'ok':False,'message':'Aguarde a analise atual terminar.'})
                return
            self._sketch_analyzing = True
            self._sketch_last_analysis = time.monotonic()
        def work():
            try:
                from actions.sketchbook import list_templates, load_template, save_template, generate_from_sketch, interpret_sketch
                payload = json.loads(raw)
                if not isinstance(payload,dict):
                    raise ValueError('Pedido invalido.')
                if action == 'list': result = list_templates()
                elif action == 'load': result = load_template(payload.get('key'))
                elif action == 'save': result = save_template(payload)
                elif action == 'generate': result = generate_from_sketch(payload)
                else: result = interpret_sketch(payload)
                reply(result)
            except Exception:
                message = 'IA indisponivel no momento. Confira a conexao e a chave Gemini.' if action == 'analyze' else 'Nao foi possivel concluir. Confira o desenho e tente novamente.'
                reply({'ok':False,'message':message})
            finally:
                if action == 'analyze': self._sketch_analyzing = False
        threading.Thread(target=work,name='JarvisSketch-'+action,daemon=True).start()

    @pyqtSlot(str)
    def librasSubmit(self, text):
        if self.view._status.get('state') != 'SLEEPING' and text.strip() and len(text) <= 1200:
            self.view.textSubmitted.emit(text.strip())

    @pyqtSlot(str, str, str)
    def librasRequest(self, request_id, action, raw):
        if len(raw) > 6_000_000 or len(request_id) > 80 or self.view._status.get('state') == 'SLEEPING':
            return
        def reply(value):
            try: self.librasResult.emit(json.dumps({'requestId':request_id, **value}, ensure_ascii=False))
            except RuntimeError: pass
        if action == 'reference':
            try:
                source = json.loads(raw).get('source')
                url = {'ines':'https://manuario.ines.gov.br/','ufsc':'https://signbank.libras.ufsc.br/'}[source]
                from PyQt6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl(url))
            except (ValueError, KeyError, AttributeError): pass
            return
        if action != 'analyze': return
        if self._libras_busy or time.monotonic() - self._libras_last < 2:
            reply({'ok':False,'message':'Aguarde a interpretação atual terminar.'}); return
        self._libras_busy = True
        self._libras_last = time.monotonic()
        def work():
            try:
                from actions.libras import interpret_libras
                payload = json.loads(raw)
                if not isinstance(payload, dict): raise ValueError('Pedido inválido.')
                reply(interpret_libras(payload))
            except Exception:
                reply({'ok':False,'message':'Não consegui interpretar agora. Confira a câmera, a conexão e a cota Gemini.'})
            finally: self._libras_busy = False
        threading.Thread(target=work,name='JarvisLibras',daemon=True).start()

    @pyqtSlot()
    def toggleExpanded(self):
        self.view.toggle_expanded()

    @pyqtSlot(str)
    def requestBriefing(self, scope):
        """Forward an explicit, privacy-preserving local briefing request to Jarvis."""
        if self.view._status.get('state') == 'SLEEPING' or scope != 'daily':
            return
        self.view.textSubmitted.emit("__JARVIS_DAILY_BRIEFING__")

class _Expanded(QDialog):
    def __init__(self, owner):
        super().__init__(owner.window())
        self.owner = owner
        self.setWindowTitle('Jarvis · Armadura 3D e gestos')
        self.resize(1040, 880)
        self.setMinimumSize(540, 600)
        self.setStyleSheet('background:#02080d;')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(owner.web)
    def closeEvent(self, event):
        self.owner._bridge.command.emit('stopCamera')
        self.owner.layout().addWidget(self.owner.web)
        self.owner._dialog = None
        event.accept()
        self.deleteLater()

class ReactorView(QWidget):
    textSubmitted = pyqtSignal(str)
    ready = pyqtSignal()
    failed = pyqtSignal(str)
    def __init__(self, parent=None, assets_dir=None):
        super().__init__(parent)
        self._closed = False
        self._ready = False
        self._dialog = None
        self._camera_armed_until = 0
        from actions.runtime_identity import MARK_NAME
        self._status = {'protocol': MARK_NAME, 'state': 'INITIALISING', 'speaking': False, 'muted': False, 'mode': 'normal'}
        assets = Path(assets_dir) if assets_dir else Path(__file__).resolve().parents[1] / 'assets' / 'reactor_lab'
        if not (assets / 'armor.glb').is_file() or not (assets / 'reactor.glb').is_file():
            raise FileNotFoundError('Modelos 3D do Jarvis não encontrados')
        handler = functools.partial(_AssetHandler, directory=str(assets.resolve()))
        self._server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, name='JarvisReactorAssets', daemon=True).start()
        self._port = self._server.server_port
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.web = QWebEngineView(self)
        self._profile = QWebEngineProfile(self)
        # The viewport only loads local, immutable-on-session assets (GLB/texture/JS).
        # Keeping Chromium's HTTP cache in RAM duplicates those large resources beside
        # the WebGL buffers, which is especially costly on machines running Discord and
        # a browser at the same time.  NoCache keeps the scene resident while it is open,
        # but releases the redundant response cache instead of retaining it in memory.
        self._profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
        self._profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        self._interceptor = _LocalRequests(self._port, self._profile)
        self._profile.setUrlRequestInterceptor(self._interceptor)
        self.page = _Page(self._profile, self.web)
        self.page.setBackgroundColor(QColor('#02080d'))
        self.page.permissionRequested.connect(self._permission)
        self.page.renderProcessTerminated.connect(lambda *args: self._fail('O processo gráfico foi interrompido'))
        self.web.setPage(self.page)
        self._channel = QWebChannel(self.page)
        self._bridge = _Bridge(self)
        self._channel.registerObject('reactorBridge', self._bridge)
        self.page.setWebChannel(self._channel)
        layout.addWidget(self.web)
        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.timeout.connect(lambda: self._fail('O visual 3D não iniciou'))
        self._load_timer.start(25000)
        self.web.load(QUrl(f'http://127.0.0.1:{self._port}/index.html?graphics={GRAPHICS_MODE}'))
    def _permission(self, permission):
        origin = permission.origin()
        allowed = (
            not self._closed and time.monotonic() < self._camera_armed_until
            and origin.scheme() == 'http' and origin.host() == '127.0.0.1' and origin.port() == self._port
            and permission.permissionType() == QWebEnginePermission.PermissionType.MediaVideoCapture
        )
        permission.grant() if allowed else permission.deny()
    def _fail(self, message):
        if self._closed: return
        self._load_timer.stop()
        self.failed.emit(message)
    def set_status(self, *, state, speaking, muted, mode):
        payload = dict(state=state, speaking=bool(speaking), muted=bool(muted), mode=mode)
        if payload != self._status:
            self._status = payload
            if self._ready and not self._closed: self._bridge.statusChanged.emit(json.dumps(payload))
    def set_voice_metrics(self, payload):
        if self._ready and not self._closed:
            # Only amplitude/bands are bridged; no text, audio files, keys or recordings.
            safe = {key: payload.get(key) for key in ('source', 'level', 'bands')}
            self._bridge.metricsChanged.emit(json.dumps(safe))
    def control_model(self, payload, callback):
        if self._closed or not self._ready:
            callback({"ok": False, "message": "Aguarde o modelo 3D carregar."})
            return
        self.page.runJavaScript(
            "window.JarvisReactor?.control3D(" + json.dumps(payload, allow_nan=False) + ")", callback
        )

    def toggle_expanded(self):
        if self._closed: return
        if self._dialog:
            self._dialog.close()
        else:
            self._dialog = _Expanded(self)
            self._dialog.show()
            self._dialog.raise_()
    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, '_bridge'): self._bridge.visibilityChanged.emit(True)
    def hideEvent(self, event):
        super().hideEvent(event)
        if not self._dialog and hasattr(self, '_bridge'): self._bridge.visibilityChanged.emit(False)
    def shutdown(self):
        if self._closed: return
        self._closed = True
        self._load_timer.stop()
        if self._dialog: self._dialog.close()
        self._bridge.command.emit('stopCamera')
        self.page.runJavaScript('window.JarvisReactor?.dispose()')
        self.web.setUrl(QUrl('about:blank'))
        threading.Thread(target=self._stop_server, name='JarvisReactorStop', daemon=True).start()
    def _stop_server(self):
        self._server.shutdown()
        self._server.server_close()
    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
