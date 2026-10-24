from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import dataclass
from typing import Optional

try:
    import cv2
    import numpy as np
    _CV2 = True
except Exception:
    cv2 = None
    np = None
    _CV2 = False

from actions.hand_braille import braille_for_count, open_camera_capture


@dataclass
class _HandTrack:
    detected: bool
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    center: tuple[int, int] = (0, 0)
    area: float = 0.0
    confidence: float = 0.0
    finger_count: int = 0
    fingertips: tuple[tuple[int, int], ...] = ()
    braille: str = ""
    dots: str = ""


class _CameraHandOverlay:
    def __init__(
        self,
        camera_index: Optional[int] = None,
        width: int = 1280,
        height: int = 720,
        mirror: bool = True,
        squares: int = 28,
        window_name: str = "JARVIS CAMERA HAND UI",
        braille_mode: bool = True,
        mode: str = "braille",
    ):
        self.camera_index = camera_index
        self.width = int(width)
        self.height = int(height)
        self.mirror = bool(mirror)
        self.squares = max(8, min(int(squares), 64))
        self.window_name = window_name
        self.mode = _normalize_mode(mode)
        self.braille_mode = bool(braille_mode) or self.mode == "braille"
        self.running = False
        self.thread: threading.Thread | None = None
        self._cap = None
        self.error: str | None = None
        self._stop_event = threading.Event()
        self._center: tuple[float, float] | None = None
        self._bbox: tuple[float, float, float, float] | None = None
        self._trail: list[tuple[int, int, float]] = []
        self._draw_points: list[tuple[int, int]] = []
        self._drawing_enabled = True

    def start(self) -> str:
        if self.running:
            return "Camera hand UI ja esta aberta."
        if self.thread and self.thread.is_alive():
            return "Camera hand UI ainda esta fechando. Tente novamente em alguns segundos."
        self._stop_event.clear()
        self.running = True
        self.error = None
        self.thread = threading.Thread(target=self._loop, daemon=True, name="CameraHandOverlay")
        self.thread.start()
        return "UI de camera com rastreamento de mao iniciada. Aperte Q, ESC ou feche a janela para encerrar."

    def stop(self) -> str:
        thread_alive = bool(self.thread and self.thread.is_alive())
        if not self.running and not thread_alive:
            self._force_close_windows()
            return "Camera hand UI ja esta parada."
        self._stop_event.set()
        self.running = False
        self._release_capture()
        self._force_close_windows()
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=1.8)
        self._release_capture()
        self._force_close_windows()
        if self.thread and self.thread.is_alive():
            return "Comando de fechar enviado para a UI de camera."
        return "UI de camera fechada."

    def status(self) -> str:
        if self.running:
            return "Camera hand UI ativa."
        if self.error:
            return f"Camera hand UI parada: {self.error}"
        return "Camera hand UI parada."

    def run_blocking(self) -> str:
        self._stop_event.clear()
        self.running = True
        self.error = None
        self._loop()
        return self.status()

    def _loop(self) -> None:
        if not _CV2:
            self.error = "OpenCV nao esta instalado. Rode: pip install opencv-python"
            self.running = False
            return

        cap = None
        try:
            cap = open_camera_capture(camera_index=self.camera_index, width=self.width, height=self.height)
            self._cap = cap
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.window_name, min(self.width, 1280), min(self.height, 760))

            frame_index = 0
            while self.running and not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.02)
                    continue
                if self.mirror:
                    frame = cv2.flip(frame, 1)

                track = _detect_hand(frame)
                frame = self._draw(frame, track, frame_index)
                cv2.imshow(self.window_name, frame)
                if self._window_was_closed():
                    self.running = False
                    break
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q"), ord("Q")):
                    self.running = False
                    self._stop_event.set()
                    break
                if key in (ord("c"), ord("C")):
                    self._draw_points.clear()
                elif key in (ord("d"), ord("D")):
                    self.mode = "draw"
                elif key in (ord("b"), ord("B")):
                    self.mode = "braille"
                    self.braille_mode = True
                elif key in (ord("h"), ord("H")):
                    self.mode = "hand"
                frame_index += 1
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.running = False
            self._stop_event.set()
            self._release_capture()
            self._force_close_windows()

    def _release_capture(self) -> None:
        cap = self._cap
        self._cap = None
        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass

    def _window_was_closed(self) -> bool:
        try:
            return cv2.getWindowProperty(self.window_name, cv2.WND_PROP_VISIBLE) < 1
        except Exception:
            return False

    def _force_close_windows(self) -> None:
        if not _CV2:
            return
        try:
            cv2.destroyWindow(self.window_name)
        except Exception:
            pass
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    def _draw(self, frame, track: _HandTrack, frame_index: int):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 16, 24), -1)
        frame = cv2.addWeighted(overlay, 0.16, frame, 0.84, 0)
        _draw_scan_grid(frame, frame_index)

        now = time.time()
        self._trail = [(x, y, ts) for x, y, ts in self._trail if now - ts < 0.85]

        if track.detected:
            x, y, bw, bh = track.bbox
            cx, cy = track.center
            if self._center is None:
                self._center = (float(cx), float(cy))
            else:
                self._center = (
                    self._center[0] * 0.72 + cx * 0.28,
                    self._center[1] * 0.72 + cy * 0.28,
                )
            if self._bbox is None:
                self._bbox = tuple(map(float, track.bbox))
            else:
                bx, by, bb_w, bb_h = self._bbox
                self._bbox = (
                    bx * 0.7 + x * 0.3,
                    by * 0.7 + y * 0.3,
                    bb_w * 0.7 + bw * 0.3,
                    bb_h * 0.7 + bh * 0.3,
                )
            sx, sy = int(self._center[0]), int(self._center[1])
            self._trail.append((sx, sy, now))
            _draw_hand_lock(frame, tuple(int(v) for v in self._bbox), (sx, sy), track.confidence, frame_index, self.squares)
            if self.mode == "draw":
                self._update_drawing(track)
            if self.mode == "braille":
                _draw_braille_alignment(frame, track, (sx, sy), frame_index)
        else:
            self._center = None
            self._bbox = None
            _draw_idle(frame, frame_index)

        if self.mode == "draw":
            _draw_drawing_layer(frame, self._draw_points, track)
            _draw_drawing_help(frame)
        _draw_trail(frame, self._trail, now)
        _draw_header(frame, track, self.mode)
        return frame

    def _update_drawing(self, track: _HandTrack) -> None:
        if not track.fingertips:
            return
        cursor = min(track.fingertips, key=lambda p: p[1])
        if not self._draw_points:
            self._draw_points.append(cursor)
            return
        last = self._draw_points[-1]
        if math.dist(last, cursor) > 9:
            self._draw_points.append(cursor)
        if len(self._draw_points) > 2200:
            self._draw_points = self._draw_points[-1800:]


_SESSION: _CameraHandOverlay | None = None


def _session_is_alive(session: _CameraHandOverlay | None) -> bool:
    return bool(session and (session.running or (session.thread and session.thread.is_alive())))


def camera_hand_ui(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = _normalize_action(params.get("action", "start"))

    if _normalize_mode(params.get("mode")) == "libras":
        if player is None or not hasattr(player, 'set_libras_mode'):
            return 'Abra o modo Libras pelo botão Libras na interface principal.'
        closing = action in {'stop','close','fechar','sair','encerrar'}
        player.set_libras_mode(not closing)
        return 'Modo Libras fechado.' if closing else 'Modo Libras aberto. Interprete o gesto e revise o texto antes de enviar.'

    global _SESSION
    if action in {
        "stop",
        "close",
        "parar",
        "fechar",
        "fecha",
        "sair",
        "exit",
        "quit",
        "encerrar",
        "shutdown",
        "force_stop",
        "forcar_parada",
        "parar_braille",
        "fechar_braille",
        "stop_braille",
        "close_braille",
    }:
        if _SESSION is None:
            return "Camera hand UI nao estava ativa."
        result = _SESSION.stop()
        if not _session_is_alive(_SESSION):
            _SESSION = None
        return result

    if action in {"status", "estado"}:
        if _SESSION is None:
            return "Camera hand UI parada."
        result = _SESSION.status()
        if not _session_is_alive(_SESSION):
            _SESSION = None
        return result

    if action in {"start", "open", "abrir", "run", "executar"}:
        if _SESSION is not None and not _SESSION.running and _SESSION.thread and _SESSION.thread.is_alive():
            return "Camera hand UI ainda esta fechando. Tente novamente em alguns segundos."
        if _SESSION is not None and _SESSION.running:
            mode = _normalize_mode(params.get("mode", _SESSION.mode))
            _SESSION.mode = mode
            _SESSION.braille_mode = mode == "braille"
            return f"Camera hand UI ativa em modo {mode}."
        if _SESSION is None or not _SESSION.running:
            _SESSION = _CameraHandOverlay(
                camera_index=params.get("camera_index"),
                width=int(params.get("width", 1280)),
                height=int(params.get("height", 720)),
                mirror=bool(params.get("mirror", True)),
                squares=int(params.get("squares", 28)),
                braille_mode=bool(params.get("braille_mode", True)),
                mode=str(params.get("mode", "braille")),
            )
        if action in {"run", "executar"}:
            return _SESSION.run_blocking()
        return _SESSION.start()

    return "Acao invalida. Use start, stop, close ou status."


def _normalize_mode(mode: str) -> str:
    mode = str(mode or "braille").lower().strip()
    aliases = {
        "desenho": "draw",
        "draw": "draw",
        "drawing": "draw",
        "braile": "braille",
        "braille": "braille",
        "mao": "hand",
        "mão": "hand",
        "hand": "hand",
        "libras": "libras",
    }
    for token in re.split(r"[/|,;]+", mode):
        token = token.strip()
        if token in aliases:
            return aliases[token]
    return aliases.get(mode, "braille")


def _normalize_action(value: object) -> str:
    aliases = {
        "open": "start", "abrir": "start", "iniciar": "start",
        "run": "run", "executar": "run", "start": "start",
        "close": "stop", "fechar": "stop", "fecha": "stop",
        "parar": "stop", "sair": "stop", "encerrar": "stop", "stop": "stop",
        "status": "status", "estado": "status",
    }
    raw = str(value or "start").lower().strip()
    for token in re.split(r"[/|,;]+", raw):
        token = token.strip()
        if token in aliases:
            return aliases[token]
    return raw


def _detect_hand(frame) -> _HandTrack:
    h, w = frame.shape[:2]
    work = frame
    scale = 1.0
    if w > 760:
        scale = 760 / float(w)
        work = cv2.resize(frame, (760, int(h * scale)))

    blurred = cv2.GaussianBlur(work, (7, 7), 0)
    ycrcb = cv2.cvtColor(blurred, cv2.COLOR_BGR2YCrCb)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    skin_ycrcb = cv2.inRange(ycrcb, np.array([0, 132, 76]), np.array([255, 178, 132]))
    skin_hsv = cv2.inRange(hsv, np.array([0, 18, 38]), np.array([34, 230, 255]))
    mask = cv2.bitwise_or(skin_ycrcb, skin_hsv)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    mask = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return _HandTrack(False)
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    min_area = max(2600.0, mask.shape[0] * mask.shape[1] * 0.012)
    if area < min_area:
        return _HandTrack(False)

    x, y, bw, bh = cv2.boundingRect(contour)
    inv = 1.0 / scale
    x, y, bw, bh = int(x * inv), int(y * inv), int(bw * inv), int(bh * inv)
    cx, cy = x + bw // 2, y + bh // 2
    confidence = min(0.99, max(0.25, area / float(mask.shape[0] * mask.shape[1]) * 8.0))
    fingertips = _finger_tips_from_contour(contour, scale, x, y, bw, bh)
    finger_count = len(fingertips)
    if finger_count == 0:
        finger_count = _estimate_fingers_from_shape(contour, bw, bh)
    finger_count = max(0, min(5, int(finger_count)))
    braille, dots = braille_for_count(finger_count)
    confidence = max(confidence, min(0.98, 0.42 + finger_count * 0.08))
    return _HandTrack(True, (x, y, bw, bh), (cx, cy), area, confidence, finger_count, tuple(fingertips[:5]), braille, dots)


def _finger_tips_from_contour(contour, scale: float, x: int, y: int, w: int, h: int) -> list[tuple[int, int]]:
    hull = cv2.convexHull(contour, returnPoints=True)
    if hull is None or len(hull) < 3:
        return []
    points = hull.reshape(-1, 2)
    top_limit = int((y + h * 0.68) * scale)
    min_gap = max(16, int(w * scale * 0.1))
    candidates = [tuple(map(int, p)) for p in points if int(p[1]) < top_limit]
    if not candidates:
        return []
    candidates.sort(key=lambda p: (p[0], p[1]))
    clusters: list[list[tuple[int, int]]] = []
    for p in candidates:
        if not clusters or abs(p[0] - clusters[-1][-1][0]) > min_gap:
            clusters.append([p])
        else:
            clusters[-1].append(p)
    tips = []
    inv = 1.0 / scale
    for cluster in clusters:
        px, py = min(cluster, key=lambda p: p[1])
        if py < int((y + h * 0.62) * scale):
            tips.append((int(px * inv), int(py * inv)))
    tips.sort(key=lambda p: p[0])
    return tips[:5]


def _estimate_fingers_from_shape(contour, w: int, h: int) -> int:
    hull_indices = cv2.convexHull(contour, returnPoints=False)
    if hull_indices is None or len(hull_indices) < 4:
        return 0
    defects = cv2.convexityDefects(contour, hull_indices)
    if defects is None:
        return 0
    count = 0
    min_depth = max(10.0, h * 0.035)
    for i in range(defects.shape[0]):
        _start, _end, _far, depth_raw = defects[i, 0]
        if depth_raw / 256.0 >= min_depth:
            count += 1
    if count <= 0 and h > w * 1.25:
        return 1
    return min(5, count + 1 if count else 0)


def _draw_scan_grid(frame, frame_index: int) -> None:
    h, w = frame.shape[:2]
    color = (30, 95, 110)
    step = 54
    offset = frame_index % step
    for x in range(-step + offset, w, step):
        cv2.line(frame, (x, 0), (x, h), color, 1, cv2.LINE_AA)
    for y in range(-step + offset, h, step):
        cv2.line(frame, (0, y), (w, y), color, 1, cv2.LINE_AA)


def _draw_header(frame, track: _HandTrack, mode: str = "braille") -> None:
    if mode == "draw":
        status = "DRAW MODE" if track.detected else "DRAW MODE / SEARCHING"
    else:
        status = "BRAILLE FOUND" if track.detected and track.braille else ("HAND LOCK" if track.detected else "SEARCHING HAND")
    conf = int(track.confidence * 100) if track.detected else 0
    cv2.rectangle(frame, (18, 16), (450, 96), (0, 18, 28), -1)
    cv2.rectangle(frame, (18, 16), (450, 96), (0, 210, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "JARVIS CAMERA UI", (32, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 230, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{status}  CONF {conf:02d}%", (32, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (120, 255, 210), 1, cv2.LINE_AA)
    if track.detected:
        if mode == "draw":
            cv2.putText(frame, f"FINGER CURSOR ACTIVE  POINTS {track.finger_count}", (32, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 230, 80), 1, cv2.LINE_AA)
        else:
            cv2.putText(frame, f"FINGERS {track.finger_count}  BRAILLE {track.braille or '--'}", (32, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 230, 80), 1, cv2.LINE_AA)


def _draw_idle(frame, frame_index: int) -> None:
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    radius = 70 + int(math.sin(frame_index * 0.08) * 12)
    cv2.circle(frame, (cx, cy), radius, (0, 150, 220), 1, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), radius // 2, (0, 90, 150), 1, cv2.LINE_AA)
    cv2.putText(frame, "SHOW HAND", (cx - 70, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 230, 255), 1, cv2.LINE_AA)


def _draw_hand_lock(frame, bbox: tuple[int, int, int, int], center: tuple[int, int], confidence: float, frame_index: int, squares: int) -> None:
    x, y, w, h = bbox
    cx, cy = center
    x = max(0, x)
    y = max(0, y)
    pad = 22
    color = (0, 235, 255)
    alt = (0, 255, 140)
    _corner_box(frame, x - pad, y - pad, w + pad * 2, h + pad * 2, color)
    cv2.drawMarker(frame, (cx, cy), alt, cv2.MARKER_CROSS, 24, 1, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), max(12, min(w, h) // 7), color, 1, cv2.LINE_AA)

    radius_x = max(80, w // 2 + 46)
    radius_y = max(70, h // 2 + 42)
    for i in range(squares):
        angle = (i / squares) * math.tau + frame_index * 0.028
        jitter = math.sin(frame_index * 0.07 + i) * 9
        sx = int(cx + math.cos(angle) * (radius_x + jitter))
        sy = int(cy + math.sin(angle) * (radius_y - jitter))
        size = 7 + int((math.sin(frame_index * 0.11 + i * 1.7) + 1) * 4)
        sq_color = alt if i % 4 == 0 else color
        cv2.rectangle(frame, (sx - size, sy - size), (sx + size, sy + size), sq_color, 1, cv2.LINE_AA)
        if i % 5 == 0:
            cv2.line(frame, (cx, cy), (sx, sy), (0, 90, 110), 1, cv2.LINE_AA)

    bar_w = 160
    pct = max(0.0, min(1.0, confidence))
    cv2.rectangle(frame, (x, max(0, y - 42)), (x + bar_w, max(0, y - 30)), (0, 40, 50), -1)
    cv2.rectangle(frame, (x, max(0, y - 42)), (x + int(bar_w * pct), max(0, y - 30)), alt, -1)
    cv2.putText(frame, "TRACKING", (x, max(14, y - 50)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)


def _draw_braille_alignment(frame, track: _HandTrack, center: tuple[int, int], frame_index: int) -> None:
    x, y, w, h = track.bbox
    cx, cy = center
    bone = (0, 255, 140)
    joint = (255, 230, 80)
    tech = (0, 230, 255)

    palm_y = int(y + h * 0.68)
    wrist = (cx, min(frame.shape[0] - 1, y + h + 24))
    cv2.line(frame, wrist, (cx, palm_y), (0, 120, 140), 2, cv2.LINE_AA)
    cv2.circle(frame, wrist, 7, (0, 170, 180), 1, cv2.LINE_AA)
    cv2.circle(frame, (cx, palm_y), 10, bone, 1, cv2.LINE_AA)

    tips = list(track.fingertips)
    if not tips and track.finger_count:
        spacing = max(24, w // 6)
        base_x = cx - spacing * (track.finger_count - 1) // 2
        tips = [(base_x + i * spacing, y + int(h * 0.16)) for i in range(track.finger_count)]

    for index, tip in enumerate(tips[:5], start=1):
        tx, ty = tip
        knuckle = (int((tx + cx) / 2), int((ty + palm_y) / 2))
        cv2.line(frame, (cx, palm_y), knuckle, bone, 2, cv2.LINE_AA)
        cv2.line(frame, knuckle, (tx, ty), tech, 2, cv2.LINE_AA)
        cv2.circle(frame, knuckle, 6, joint, 1, cv2.LINE_AA)
        pulse = 9 + int(math.sin(frame_index * 0.15 + index) * 3)
        cv2.rectangle(frame, (tx - pulse, ty - pulse), (tx + pulse, ty + pulse), tech, 2, cv2.LINE_AA)
        cv2.putText(frame, str(index), (tx + 12, ty - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.46, joint, 1, cv2.LINE_AA)

    _draw_braille_panel(frame, track)


def _draw_braille_panel(frame, track: _HandTrack) -> None:
    h, w = frame.shape[:2]
    panel_w, panel_h = 360, 118
    x = max(12, w - panel_w - 18)
    y = 18
    cv2.rectangle(frame, (x, y), (x + panel_w, y + panel_h), (0, 12, 20), -1)
    cv2.rectangle(frame, (x, y), (x + panel_w, y + panel_h), (0, 230, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "BRAILLE TRANSLATOR", (x + 16, y + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 230, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, f"SIGNAL: {track.braille or '--'}", (x + 16, y + 58), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 230, 80), 2, cv2.LINE_AA)
    cv2.putText(frame, f"FINGERS: {track.finger_count}  {track.dots[:34]}", (x + 16, y + 84), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (120, 255, 210), 1, cv2.LINE_AA)
    cv2.putText(frame, "STATUS: ALIGNED BONES / FINGER POINTS", (x + 16, y + 106), cv2.FONT_HERSHEY_SIMPLEX, 0.39, (90, 170, 190), 1, cv2.LINE_AA)


def _draw_drawing_layer(frame, points: list[tuple[int, int]], track: _HandTrack) -> None:
    if len(points) >= 2:
        for idx in range(1, len(points)):
            p1 = points[idx - 1]
            p2 = points[idx]
            age = idx / max(1, len(points))
            color = (0, int(150 + 90 * age), int(180 + 75 * age))
            thickness = 2 if idx < len(points) - 12 else 4
            cv2.line(frame, p1, p2, color, thickness, cv2.LINE_AA)
        for p in points[-24::4]:
            cv2.circle(frame, p, 5, (255, 230, 80), 1, cv2.LINE_AA)

    if track.fingertips:
        cursor = min(track.fingertips, key=lambda p: p[1])
        x, y = cursor
        cv2.circle(frame, (x, y), 18, (0, 255, 140), 2, cv2.LINE_AA)
        cv2.circle(frame, (x, y), 5, (255, 230, 80), -1, cv2.LINE_AA)
        cv2.putText(frame, "DRAW TIP", (x + 22, y - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 255, 140), 1, cv2.LINE_AA)


def _draw_drawing_help(frame) -> None:
    h, w = frame.shape[:2]
    panel_w, panel_h = 430, 156
    x = 18
    y = max(110, h - panel_h - 18)
    cv2.rectangle(frame, (x, y), (x + panel_w, y + panel_h), (0, 12, 20), -1)
    cv2.rectangle(frame, (x, y), (x + panel_w, y + panel_h), (0, 230, 255), 1, cv2.LINE_AA)
    lines = [
        "MODO DESENHO",
        "Levante o dedo indicador e mova para desenhar.",
        "Abra a mao para estabilizar o cursor.",
        "Teclas: C limpa | B braille | H mao | D desenho | Q fecha",
        "Dica: use fundo liso e boa luz para o traço ficar limpo.",
    ]
    for i, line in enumerate(lines):
        color = (255, 230, 80) if i == 0 else ((120, 255, 210) if i < 3 else (90, 170, 190))
        scale = 0.58 if i == 0 else 0.43
        cv2.putText(frame, line, (x + 16, y + 28 + i * 25), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def _corner_box(frame, x: int, y: int, w: int, h: int, color) -> None:
    x2, y2 = x + w, y + h
    length = max(18, min(w, h) // 4)
    points = [
        ((x, y), (x + length, y)), ((x, y), (x, y + length)),
        ((x2, y), (x2 - length, y)), ((x2, y), (x2, y + length)),
        ((x, y2), (x + length, y2)), ((x, y2), (x, y2 - length)),
        ((x2, y2), (x2 - length, y2)), ((x2, y2), (x2, y2 - length)),
    ]
    for p1, p2 in points:
        cv2.line(frame, p1, p2, color, 2, cv2.LINE_AA)


def _draw_trail(frame, trail: list[tuple[int, int, float]], now: float) -> None:
    for x, y, ts in trail:
        age = now - ts
        alpha = max(0.0, 1.0 - age / 0.85)
        size = int(6 + alpha * 12)
        color = (0, int(120 + 120 * alpha), int(150 + 105 * alpha))
        cv2.rectangle(frame, (x - size, y - size), (x + size, y + size), color, 1, cv2.LINE_AA)


if __name__ == "__main__":
    print(camera_hand_ui({"action": "run"}))
