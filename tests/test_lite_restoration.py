import unittest
from pathlib import Path
from unittest.mock import patch

from actions import dev_agent, lite_creative_ui, nvidia_camera_lab, sketchbook, spotify_reconnect, video_generation


class LiteRestorationTests(unittest.TestCase):
    def test_nvidia_status_does_not_claim_missing_studio(self):
        with patch.object(nvidia_camera_lab, "_studio_path", return_value=Path("C:/missing-lab/art_studio.py")):
            self.assertIn("não instalado", nvidia_camera_lab.nvidia_camera_lab({"action": "status"}))

    def test_nvidia_launch_uses_active_python_and_camera_tab(self):
        with patch.object(nvidia_camera_lab, "_studio_path", return_value=Path(__file__)), \
             patch.object(nvidia_camera_lab.subprocess, "Popen") as popen:
            result = nvidia_camera_lab.nvidia_camera_lab({"action": "open"})
        self.assertIn("aberto", result)
        self.assertEqual(popen.call_args.args[0][-2:], ["--tab", "camera"])
        self.assertEqual(
            popen.call_args.kwargs["env"]["JARVIS_API_KEYS"],
            str(nvidia_camera_lab.APP_ROOT / "config" / "api_keys.json"),
        )
        self.assertEqual(
            popen.call_args.kwargs["env"]["JARVIS_ROOT"],
            str(nvidia_camera_lab.APP_ROOT),
        )

    def test_nvidia_studio_is_bundled_beside_jarvis(self):
        self.assertEqual(
            nvidia_camera_lab._studio_path(),
            nvidia_camera_lab.APP_ROOT / "NVIDIA_AI_ART_STUDIO" / "art_studio.py",
        )
        self.assertIn("pronto", nvidia_camera_lab.nvidia_camera_lab({"action": "status"}))

    def test_creative_actions_share_the_bundled_studio(self):
        expected = nvidia_camera_lab.APP_ROOT / "NVIDIA_AI_ART_STUDIO" / "art_studio.py"
        self.assertEqual(sketchbook.STUDIO, expected)
        self.assertEqual(video_generation.STUDIO, expected)
        self.assertTrue(video_generation.WORKER.is_file())

    def test_spotify_connected_does_not_open_browser(self):
        client = type("Client", (), {"current_user": lambda self: {"display_name": "Teste", "product": "premium"}})()
        with patch("actions.smart_home._get_spotipy", return_value=client), \
             patch.object(spotify_reconnect.webbrowser, "open") as browser:
            result = spotify_reconnect.check_and_reconnect()
        self.assertIn("premium", result)
        browser.assert_not_called()

    def test_spotify_premium_403_does_not_repeat_oauth(self):
        error = type("PremiumError", (Exception,), {"http_status": 403})()
        def fail(_self):
            raise error
        client = type("Client", (), {"current_user": fail})()
        with patch("actions.smart_home._get_spotipy", return_value=client), \
             patch.object(spotify_reconnect.webbrowser, "open") as browser:
            result = spotify_reconnect.check_and_reconnect()
        self.assertIn("403", result)
        browser.assert_not_called()

    def test_dev_agent_rejects_path_traversal(self):
        base = Path("C:/Users/Test/Desktop/JarvisProjects/project")
        for path in ("../outside.py", "C:/Windows/system.py", ""):
            with self.subTest(path=path), self.assertRaises(ValueError):
                dev_agent._safe_project_file(base, path)
        self.assertEqual(dev_agent._safe_project_file(base, "src/main.py"), base / "src/main.py")

    def test_dev_agent_respects_user_confirmation(self):
        player = type("Player", (), {"confirm_dev_project": lambda self, _description: False})()
        with patch.object(dev_agent, "_build_project") as build:
            result = dev_agent.dev_agent({"description": "teste"}, player=player)
        self.assertIn("cancelada", result)
        build.assert_not_called()

    def test_native_webengine_failure_isolated(self):
        result = type("Result", (), {"returncode": -1073740791, "stdout": b""})()
        with patch.object(lite_creative_ui.subprocess, "run", return_value=result):
            self.assertFalse(lite_creative_ui.webengine_preflight())


if __name__ == "__main__":
    unittest.main()
