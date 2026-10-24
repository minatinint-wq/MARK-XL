import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions import bird_local
from actions import send_message as send_message_module


class _Response:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"id":"job_test","status":"queued"}'


class BirdLocalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.patches = [
            patch.object(bird_local, "SETTINGS", root / "bird_local.json"),
            patch.object(bird_local, "PENDING", root / "pending.json"),
            patch.object(bird_local, "KEY_FILE", root / "key.dpapi"),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        bird_local.save_settings("http://127.0.0.1:8787", "wa_test")
        bird_local.save_contact("Ana", "5511999999999", consent=True)
        bird_local.save_key("bird_live_test")

    def test_key_is_protected_for_current_windows_user(self):
        self.assertNotIn(b"bird_live_test", bird_local.KEY_FILE.read_bytes())
        with patch.dict("os.environ", {"JARVIS_BIRD_API_KEY": ""}):
            self.assertEqual(bird_local._load_key(), "bird_live_test")

    def test_loopback_only_and_consent(self):
        with self.assertRaises(bird_local.BirdLocalError):
            bird_local.save_settings("http://192.168.0.5:8787", "wa_test")
        with self.assertRaises(bird_local.BirdLocalError):
            bird_local.save_contact("Bia", "5511888888888", consent=False)
        with self.assertRaises(bird_local.BirdLocalError):
            bird_local.send_text("Ana", "Oi")

    def test_send_has_confirmation_and_stable_idempotency(self):
        requests = []

        def fake_urlopen(request, timeout):
            requests.append(request)
            return _Response()

        with patch.object(bird_local, "_open", side_effect=fake_urlopen):
            first = bird_local.send_text("Ana", "Oi", confirmed=True)
            second = bird_local.send_text("Ana", "Oi", confirmed=True)
        self.assertIn("enfileirada", first)
        self.assertIn("job_test", second)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].get_header("Idempotency-key"), requests[1].get_header("Idempotency-key"))
        self.assertEqual(json.loads(requests[0].data), {"to": "5511999999999", "text": "Oi", "consent": True})
        self.assertEqual(requests[0].full_url, "http://127.0.0.1:8787/v1/instances/wa_test/messages")

    def test_lite_whatsapp_never_uses_browser_fallback(self):
        class Player:
            def confirm_bird_message(self, receiver, message):
                return receiver == "Ana" and message == "Oi"

            def write_log(self, _text):
                pass

        with patch.dict("os.environ", {"MARK_XL_GLOW_ONLY": "1"}), \
             patch.object(bird_local, "send_text", return_value="enfileirada") as local_send, \
             patch.object(send_message_module, "_send_whatsapp") as browser_send:
            result = send_message_module.send_message(
                {"platform": "WhatsApp", "receiver": "Ana", "message_text": "Oi"}, player=Player()
            )
        self.assertEqual(result, "enfileirada")
        local_send.assert_called_once_with("Ana", "Oi", confirmed=True)
        browser_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
