import unittest
import sys
import types


if "curl_cffi" not in sys.modules:
    curl_cffi = types.ModuleType("curl_cffi")

    class DummySession:
        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            pass

    curl_cffi.requests = types.SimpleNamespace(Session=DummySession)
    sys.modules["curl_cffi"] = curl_cffi

from services.register import mail_provider


class MailProviderTests(unittest.TestCase):
    def test_parse_received_at_accepts_moemail_millisecond_timestamp(self) -> None:
        expected = "2024-01-01T12:00:00+00:00"

        self.assertEqual(mail_provider._parse_received_at(1704110400000).isoformat(), expected)
        self.assertEqual(mail_provider._parse_received_at("1704110400000").isoformat(), expected)

    def test_moemail_wait_for_code_uses_new_unseen_message(self) -> None:
        provider = mail_provider.MoEmailProvider(
            {"api_key": "test-key", "domain": ["moemail.app"], "provider_ref": "moemail#1"},
            {"request_timeout": 1, "wait_timeout": 1, "wait_interval": 0.2, "user_agent": "test"},
        )
        mailbox = {"address": "box@moemail.app", "email_id": "mailbox-id"}
        state = {
            "items": [
                {"id": "old", "subject": "Old code", "received_at": 1704110400000},
            ],
            "details": {
                "old": {"message": {"id": "old", "subject": "Old code", "content": "Verification code: 111111", "received_at": 1704110400000}},
                "new": {"message": {"id": "new", "subject": "New code", "content": "Verification code: 222222", "received_at": 1704110460000}},
            },
        }

        def fake_request(method, path, params=None, payload=None, expected=(200,)):
            if method == "GET" and path == "/api/emails/mailbox-id":
                return {"messages": list(state["items"])}
            if method == "GET" and path.startswith("/api/emails/mailbox-id/"):
                return state["details"][path.rsplit("/", 1)[-1]]
            raise AssertionError(f"unexpected request: {method} {path}")

        provider._request = fake_request
        try:
            self.assertEqual(provider.wait_for_code(mailbox), "111111")

            state["items"] = [
                {"id": "old", "subject": "Old code", "received_at": 1704110400000},
                {"id": "new", "subject": "New code", "received_at": 1704110460000},
            ]

            self.assertEqual(provider.wait_for_code(mailbox), "222222")
        finally:
            provider.close()


if __name__ == "__main__":
    unittest.main()
