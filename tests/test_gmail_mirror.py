import unittest
from unittest.mock import patch

from actions import gmail_mirror


class GmailMirrorTests(unittest.TestCase):
    def test_inbox_reads_only_metadata(self):
        calls = []

        def fake_get(path, _token):
            calls.append(path)
            if path.startswith("/messages?"):
                return {"messages": [{"id": "abcdef123456"}]}
            return {"threadId": "thread123456", "internalDate": "1700000000000",
                    "payload": {"headers": [{"name": "From", "value": "Ana <ana@example.com>"},
                                            {"name": "Subject", "value": "Reunião"}]},
                    "snippet": "never returned to Jarvis"}

        with patch.object(gmail_mirror, "_credentials", return_value=type("C", (), {"token": "synthetic"})()), \
             patch.object(gmail_mirror, "_get", side_effect=fake_get):
            rows = gmail_mirror.inbox(100)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject"], "Reunião")
        self.assertNotIn("snippet", rows[0])
        self.assertIn("maxResults=20", calls[0])
        self.assertIn("format=metadata", calls[1])
        self.assertNotIn("format=full", calls[1])

    def test_gmail_link_validates_identifier(self):
        self.assertIn("thread123456", gmail_mirror.gmail_url("thread123456"))
        with self.assertRaises(gmail_mirror.GmailMirrorError):
            gmail_mirror.gmail_url("../../other")


if __name__ == "__main__":
    unittest.main()
