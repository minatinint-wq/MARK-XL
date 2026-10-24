import ast
import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from actions.noise_suppression import NoiseSuppressor


camera = importlib.import_module("actions.camera_hand_ui")


def _playback_gate_from_source():
    # main.py initializes the desktop singleton at import time. Compile only
    # this pure function so the test cannot launch or interrupt the desktop app.
    source = Path(__file__).resolve().parents[1] / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "_playback_should_release")
    namespace = {"SPEECH_TAIL_SECONDS": 0.30}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[function.name]


class MicCameraRegressions(unittest.TestCase):
    def test_missing_live_turn_complete_cannot_block_microphone_forever(self):
        release = _playback_gate_from_source()
        self.assertFalse(release(10.5, 10.0, True, False, False, False))
        self.assertTrue(release(11.3, 10.0, True, False, False, False))
        self.assertFalse(release(20.0, 10.0, False, False, False, False))
        self.assertFalse(release(12.0, 10.0, True, False, True, False))
        self.assertTrue(release(16.1, 10.0, True, False, True, False))

    def test_slash_delimited_camera_values_are_normalized(self):
        self.assertEqual(camera._normalize_action("start/open/abrir"), "start")
        self.assertEqual(camera._normalize_action("stop/close/fechar"), "stop")
        self.assertEqual(camera._normalize_mode("draw/desenho"), "draw")

    def test_camera_starts_with_model_generated_aliases(self):
        fake = type("FakeOverlay", (), {"running": False, "thread": None,
                                          "start": lambda self: "started"})()
        with patch.object(camera, "_SESSION", None), \
             patch.object(camera, "_CameraHandOverlay", return_value=fake) as overlay:
            result = camera.camera_hand_ui({"action": "start/open/abrir", "mode": "draw/desenho"})
        self.assertEqual(result, "started")
        self.assertEqual(overlay.call_args.kwargs["mode"], "draw/desenho")

    def test_raw_mic_option_bypasses_noise_filter(self):
        sample = b"\x01\x00" * 160
        with patch.dict(os.environ, {"MARK_XL_MIC_RAW": "1"}):
            suppressor = NoiseSuppressor()
        self.assertFalse(suppressor.active)
        self.assertEqual(suppressor.process(sample), sample)


if __name__ == "__main__":
    unittest.main()
