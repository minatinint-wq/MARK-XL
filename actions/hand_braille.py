from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from actions.cpu_acceleration import configure_cpu_acceleration, configure_opencv

configure_cpu_acceleration()
import numpy as np

try:
    import cv2
    configure_opencv(cv2)
    _CV2 = True
except ImportError:
    _CV2 = False


_BASE = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _BASE / "config" / "api_keys.json"

_BRAILLE_NUMBERS = {
    0: ("⠼⠚", "sinal de numero, pontos 2-4-5"),
    1: ("⠼⠁", "sinal de numero, ponto 1"),
    2: ("⠼⠃", "sinal de numero, pontos 1-2"),
    3: ("⠼⠉", "sinal de numero, pontos 1-4"),
    4: ("⠼⠙", "sinal de numero, pontos 1-4-5"),
    5: ("⠼⠑", "sinal de numero, pontos 1-5"),
}


@dataclass
class HandBrailleResult:
    detected: bool
    finger_count: Optional[int]
    braille: str
    dots: str
    confidence: float
    message: str


def wants_hand_braille(text: str) -> bool:
    query = (text or "").lower()
    return "braille" in query or "braile" in query


def braille_for_count(count: int) -> tuple[str, str]:
    count = max(0, min(int(count), 5))
    return _BRAILLE_NUMBERS[count]


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _camera_backend() -> int:
    if not _CV2:
        return 0
    os_name = str(_load_config().get("os_system", "windows")).lower()
    if os_name == "windows":
        return cv2.CAP_DSHOW
    if os_name == "mac":
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_ANY


def _camera_index(default: int = 0) -> int:
    try:
        return int(_load_config().get("camera_index", default))
    except Exception:
        return default


def open_camera_capture(camera_index: Optional[int] = None, width: int = 1280, height: int = 720):
    if not _CV2:
        raise RuntimeError("OpenCV (cv2) is not installed. Run: pip install opencv-python")

    index = _camera_index() if camera_index is None else int(camera_index)
    cap = cv2.VideoCapture(index, _camera_backend())
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Camera index {index} could not be opened.")

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
    try:
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
    except Exception:
        pass
    try:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
    except Exception:
        pass
    return cap


def capture_camera_frame(
    camera_index: Optional[int] = None,
    warmup: int = 12,
    width: int = 1280,
    height: int = 720,
):
    cap = open_camera_capture(camera_index=camera_index, width=width, height=height)
    try:
        frame = None
        best_score = -1.0
        for _ in range(max(1, warmup)):
            ret, candidate = cap.read()
            if ret and candidate is not None and candidate.size:
                score = _frame_quality_score(candidate)
                if score > best_score:
                    best_score = score
                    frame = candidate

        if frame is None:
            if (int(width), int(height)) != (640, 480):
                return capture_camera_frame(
                    camera_index=camera_index,
                    warmup=max(6, warmup),
                    width=640,
                    height=480,
                )
            raise RuntimeError("Camera returned no frame.")
        return frame
    finally:
        cap.release()


def _frame_quality_score(frame) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    exposure_balance = max(0.0, 128.0 - abs(128.0 - brightness))
    return sharpness + exposure_balance


def analyze_camera_braille(camera_index: Optional[int] = None) -> HandBrailleResult:
    frame = capture_camera_frame(camera_index=camera_index)
    return analyze_frame_for_braille(frame)


def analyze_frame_for_braille(frame) -> HandBrailleResult:
    if not _CV2:
        return _no_hand("OpenCV is not available.")
    if frame is None or not getattr(frame, "size", 0):
        return _no_hand("Camera returned an empty frame.")

    contour = _largest_hand_contour(frame)
    if contour is None:
        return _no_hand(
            "Nao consegui isolar uma mao na camera. Coloque a mao contra um fundo liso e tente de novo."
        )

    count, confidence = _count_raised_fingers(contour)
    braille, dots = braille_for_count(count)
    message = (
        f"Vejo {count} dedo{'s' if count != 1 else ''} levantado{'s' if count != 1 else ''}. "
        f"Em braille numerico: {braille}. Para falar: {dots}."
    )
    return HandBrailleResult(True, count, braille, dots, confidence, message)


def _no_hand(message: str) -> HandBrailleResult:
    return HandBrailleResult(False, None, "", "", 0.0, message)


def _largest_hand_contour(frame):
    height, width = frame.shape[:2]
    if width > 720:
        scale = 720 / float(width)
        frame = cv2.resize(frame, (720, int(height * scale)))

    blurred = cv2.GaussianBlur(frame, (7, 7), 0)
    ycrcb = cv2.cvtColor(blurred, cv2.COLOR_BGR2YCrCb)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    skin_ycrcb = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 173, 127]))
    skin_hsv = cv2.inRange(hsv, np.array([0, 25, 45]), np.array([28, 210, 255]))
    mask = cv2.bitwise_or(skin_ycrcb, skin_hsv)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    mask = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    frame_area = frame.shape[0] * frame.shape[1]
    if area < max(3500, frame_area * 0.015):
        return None
    return contour


def _count_raised_fingers(contour) -> tuple[int, float]:
    x, y, w, h = cv2.boundingRect(contour)
    area = max(cv2.contourArea(contour), 1.0)
    hull_points = cv2.convexHull(contour, returnPoints=True)
    hull_area = max(cv2.contourArea(hull_points), 1.0)
    solidity = area / hull_area

    defects_count = _count_convexity_defects(contour, h)
    peaks_count = _count_hull_peaks(hull_points.reshape(-1, 2), x, y, w, h)

    if defects_count > 0:
        count = defects_count + 1
    else:
        count = peaks_count

    # A closed fist usually has a compact contour and no deep valleys.
    if count <= 1 and solidity > 0.82 and h <= w * 1.25:
        count = 0

    count = max(0, min(int(count), 5))
    confidence = max(0.2, min(0.95, 0.45 + (0.08 * max(defects_count, peaks_count)) + (1.0 - solidity) * 0.25))
    return count, round(confidence, 2)


def _count_convexity_defects(contour, hand_height: int) -> int:
    hull_indices = cv2.convexHull(contour, returnPoints=False)
    if hull_indices is None or len(hull_indices) < 4:
        return 0

    defects = cv2.convexityDefects(contour, hull_indices)
    if defects is None:
        return 0

    count = 0
    min_depth = max(10.0, hand_height * 0.035)
    for i in range(defects.shape[0]):
        start_idx, end_idx, far_idx, depth_raw = defects[i, 0]
        start = contour[start_idx][0]
        end = contour[end_idx][0]
        far = contour[far_idx][0]
        depth = depth_raw / 256.0
        if depth < min_depth:
            continue

        angle = _angle_between(start, far, end)
        if angle < 92:
            count += 1

    return min(count, 4)


def _count_hull_peaks(points: np.ndarray, x: int, y: int, w: int, h: int) -> int:
    if points.size == 0:
        return 0

    top_limit = y + int(h * 0.62)
    candidates = [tuple(p) for p in points if p[1] < top_limit]
    if not candidates:
        return 0

    candidates.sort(key=lambda p: p[0])
    gap = max(18, int(w * 0.12))
    clusters: list[list[tuple[int, int]]] = []
    for point in candidates:
        if not clusters or abs(point[0] - clusters[-1][-1][0]) > gap:
            clusters.append([point])
        else:
            clusters[-1].append(point)

    peaks = []
    for cluster in clusters:
        peak = min(cluster, key=lambda p: p[1])
        if peak[1] < y + int(h * 0.58):
            peaks.append(peak)

    return min(len(peaks), 5)


def _angle_between(a, b, c) -> float:
    ab = math.dist(a, b)
    cb = math.dist(c, b)
    ac = math.dist(a, c)
    if ab == 0 or cb == 0:
        return 180.0
    cosine = (ab * ab + cb * cb - ac * ac) / (2 * ab * cb)
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))
