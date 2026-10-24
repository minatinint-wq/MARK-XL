import json
import os
import unittest
import urllib.request
from unittest.mock import patch

from actions.remote_ai_gateway import HOST, PORT, start_gateway
from actions.voice_message_flow import VoiceMessageFlow


class RemoteAIVoiceTests(unittest.TestCase):
    def test_voice_message_requires_draft_and_confirmation(self):
        flow = VoiceMessageFlow()
        self.assertEqual(flow.accept("Jarvis enviar mensagem para João"), ("open", "João", ""))
        self.assertEqual(flow.accept("confirmar envio"), ("need_text", "João", ""))
        self.assertEqual(flow.accept("Oi, tudo bem?"), ("draft", "João", "Oi, tudo bem?"))
        self.assertEqual(flow.accept("corrigir mensagem para Oi, João!"), ("draft", "João", "Oi, João!"))
        self.assertEqual(flow.accept("confirmar envio"), ("send", "João", "Oi, João!"))
        self.assertEqual(flow.accept("cancelar mensagem"), ("cancel", "", ""))
        self.assertEqual(flow.stage, "idle")


    def test_voice_message_does_not_intercept_unrelated_speech(self):
        flow = VoiceMessageFlow()
        self.assertIsNone(flow.accept("qual é a previsão do tempo"))
        self.assertEqual(flow.accept("mandar mensagem pra Maria"), ("open", "Maria", ""))
        self.assertEqual(flow.accept("texto: Chego às oito"), ("draft", "Maria", "Chego às oito"))


    def test_gateway_health_without_calling_cloud(self):
        with patch.dict(os.environ, {"JARVIS_LEADIO_AI_KEY": "synthetic-local-only-key-000000000000000000"}):
            self.assertTrue(start_gateway())
            with urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=3) as response:
                data = json.load(response)
        self.assertEqual(data["service"], "Jarvis remote AI gateway")
        self.assertTrue(data["configured"])


if __name__ == "__main__":
    unittest.main()
