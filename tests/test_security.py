import unittest
import os
import io
import asyncio
from typing import Dict, Any, List
from rise.security import SecurityMiddleware, load_security_config

class DummyApp:
    def __init__(self):
        self.called = False
    async def __call__(self, scope, receive, send):
        self.called = True
        if scope.get("type") == "http":
            try:
                await receive()
            except Exception:
                raise
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"OK"})

async def mock_receive(body=b""):
    return {"type": "http.request", "body": body}
    
class MockSend:
    def __init__(self):
        self.messages = []
    async def __call__(self, msg):
        self.messages.append(msg)
        
class TestSecurity(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = DummyApp()
        self.token = "A" * 32
        self.middleware = SecurityMiddleware(self.app, self.token, ["localhost"], ["https://ui.example.com"])
        self.scope = {
            "type": "http",
            "headers": [
                (b"host", b"localhost"),
                (b"authorization", f"Bearer {self.token}".encode("latin1"))
            ],
            "client": ("127.0.0.1", 12345)
        }
        
    async def test_auth_correct_token(self):
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertTrue(self.app.called)
        self.assertEqual(send.messages[0]["status"], 200)
        
    async def test_auth_missing_header(self):
        self.scope["headers"] = [(b"host", b"localhost")]
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertFalse(self.app.called)
        self.assertEqual(send.messages[0]["status"], 401)
        self.assertIn((b"www-authenticate", b"Bearer"), send.messages[0]["headers"])
        self.assertEqual(send.messages[1]["body"], b"Unauthorized")
        
    async def test_auth_wrong_token(self):
        self.scope["headers"] = [(b"host", b"localhost"), (b"authorization", b"Bearer wrong")]
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertFalse(self.app.called)
        self.assertEqual(send.messages[0]["status"], 401)
        
    async def test_auth_token_different_case(self):
        self.scope["headers"] = [(b"host", b"localhost"), (b"authorization", f"Bearer {self.token.lower()}".encode("latin1"))]
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertFalse(self.app.called)
        self.assertEqual(send.messages[0]["status"], 401)
        
    async def test_auth_basic(self):
        self.scope["headers"] = [(b"host", b"localhost"), (b"authorization", b"Basic token")]
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 401)
        
    async def test_auth_bearer_with_nothing(self):
        self.scope["headers"] = [(b"host", b"localhost"), (b"authorization", b"Bearer")]
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 401)
        
    async def test_auth_token_different_length(self):
        self.scope["headers"] = [(b"host", b"localhost"), (b"authorization", f"Bearer {self.token}A".encode("latin1"))]
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 401)
        
    async def test_host_allowed_with_and_without_port(self):
        for host_val in [b"localhost", b"localhost:8000"]:
            self.scope["headers"] = [(b"host", host_val), (b"authorization", f"Bearer {self.token}".encode("latin1"))]
            app = DummyApp()
            mw = SecurityMiddleware(app, self.token, ["localhost"], [])
            send = MockSend()
            await mw(self.scope, mock_receive, send)
            self.assertTrue(app.called)
            
    async def test_host_evil(self):
        self.scope["headers"] = [(b"host", b"evil.example.com"), (b"authorization", f"Bearer {self.token}".encode("latin1"))]
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 403)
        self.assertEqual(send.messages[1]["body"], b"Forbidden")
        
    async def test_host_missing(self):
        self.scope["headers"] = [(b"authorization", f"Bearer {self.token}".encode("latin1"))]
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 403)
        
    async def test_host_extra_host_passes(self):
        self.scope["headers"] = [(b"host", b"my.domain.com")]
        mw = SecurityMiddleware(DummyApp(), None, ["localhost", "my.domain.com"], [])
        send = MockSend()
        await mw(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 200)
        
    async def test_origin_absent_passes(self):
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 200)
        
    async def test_origin_allowed_passes(self):
        self.scope["headers"].append((b"origin", b"https://ui.example.com"))
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 200)
        
    async def test_origin_other_fails(self):
        self.scope["headers"].append((b"origin", b"http://evil.com"))
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 403)
        
    async def test_origin_null_fails(self):
        self.scope["headers"].append((b"origin", b"null"))
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 403)
        
    async def test_body_content_length_exceeded(self):
        self.scope["headers"].append((b"content-length", b"65537"))
        send = MockSend()
        await self.middleware(self.scope, mock_receive, send)
        self.assertEqual(send.messages[0]["status"], 413)
        self.assertFalse(self.app.called)
        
    async def test_body_chunked_grows_past_limit(self):
        async def mock_receive_chunked():
            return {"type": "http.request", "body": b"A" * 65537}
            
        send = MockSend()
        await self.middleware(self.scope, mock_receive_chunked, send)
        self.assertEqual(send.messages[0]["status"], 413)
        
    async def test_body_exactly_at_limit(self):
        async def mock_receive_exact():
            return {"type": "http.request", "body": b"A" * 65536}
            
        send = MockSend()
        await self.middleware(self.scope, mock_receive_exact, send)
        self.assertTrue(self.app.called)
        
    async def test_order_and_no_leaks(self):
        # wrong host and wrong token -> 403
        self.scope["headers"] = [(b"host", b"evil.com"), (b"authorization", b"Bearer wrong")]
        send = MockSend()
        with self.assertLogs('rise.security', level='WARNING') as cm:
            await self.middleware(self.scope, mock_receive, send)
            
        self.assertEqual(send.messages[0]["status"], 403)
        body_text = send.messages[1]["body"].decode()
        self.assertNotIn("token", body_text.lower())
        self.assertNotIn("host", body_text.lower())
        self.assertNotIn("origin", body_text.lower())
        
        # Check logs for token
        for log in cm.output:
            self.assertNotIn(self.token, log)
            self.assertNotIn("wrong", log)
            
    async def test_non_http_scopes(self):
        scope = {"type": "lifespan"}
        send = MockSend()
        await self.middleware(scope, mock_receive, send)
        self.assertTrue(self.app.called)
        
    def test_config_missing_token(self):
        with self.assertRaisesRegex(ValueError, "RISE_AUTH_TOKEN is required"):
            load_security_config({})
            
    def test_config_31_char_token(self):
        with self.assertRaisesRegex(ValueError, "RISE_AUTH_TOKEN is required"):
            load_security_config({"RISE_AUTH_TOKEN": "A" * 31})
            
    def test_config_32_char_token(self):
        cfg = load_security_config({"RISE_AUTH_TOKEN": "A" * 32})
        self.assertEqual(cfg["token"], "A" * 32)
        
    def test_config_allow_no_auth(self):
        cfg = load_security_config({"RISE_ALLOW_NO_AUTH": "1", "RISE_ALLOWED_HOSTS": "test.com"})
        self.assertIsNone(cfg["token"])
        self.assertEqual(cfg["allowed_hosts"], ["localhost", "127.0.0.1"])
        
    def test_config_invalid_host(self):
        with self.assertRaisesRegex(ValueError, "Invalid host"):
            load_security_config({"RISE_AUTH_TOKEN": "A" * 32, "RISE_ALLOWED_HOSTS": "*"})
            
        with self.assertRaisesRegex(ValueError, "Invalid host"):
            load_security_config({"RISE_AUTH_TOKEN": "A" * 32, "RISE_ALLOWED_HOSTS": "evil_host"})
            
    def test_config_demo_relative_clock_path(self):
        with self.assertRaisesRegex(ValueError, "RISE_DEMO_CLOCK_FILE must be an absolute path when RISE_DEMO_MODE=1"):
            load_security_config({"RISE_AUTH_TOKEN": "A" * 32, "RISE_DEMO_MODE": "1", "RISE_DEMO_CLOCK_FILE": "relative/path"})

    def test_config_demo_extra_host(self):
        with self.assertRaisesRegex(ValueError, "Demo mode is local only: remove extra hosts from RISE_ALLOWED_HOSTS"):
            load_security_config({"RISE_AUTH_TOKEN": "A" * 32, "RISE_DEMO_MODE": "1", "RISE_DEMO_CLOCK_FILE": "C:/abs/path", "RISE_ALLOWED_HOSTS": "example.com"})

    def test_config_demo_valid(self):
        cfg = load_security_config({"RISE_AUTH_TOKEN": "A" * 32, "RISE_DEMO_MODE": "1", "RISE_DEMO_CLOCK_FILE": "C:/abs/path"})
        self.assertTrue(cfg["demo_mode"])

    def test_config_demo_invalid(self):
        cfg = load_security_config({"RISE_AUTH_TOKEN": "A" * 32})
        self.assertFalse(cfg["demo_mode"])
            
    def test_source_checks(self):
        # 18. Source checks: server.py contains no "0.0.0.0"
        server_py = os.path.join(os.path.dirname(__file__), "..", "server.py")
        content = open(server_py, "r", encoding="utf-8").read()
        self.assertNotIn("0.0.0.0", content)
        self.assertIn("DEMO MODE", content)
        
        # No file in the repo contains a hard-coded token-like string of 32 or more URL-safe characters assigned to a variable named token
        import glob
        for f in glob.glob(os.path.join(os.path.dirname(__file__), "..", "**", "*.py"), recursive=True):
            if "venv" in f or "test_security.py" in f:
                continue
            f_content = open(f, "r", encoding="utf-8").read()
            # simple check for token = "..."
            import re
            m = re.search(r'token\s*=\s*["\']([a-zA-Z0-9_-]{32,})["\']', f_content)
            self.assertIsNone(m, f"Found hardcoded token in {f}")

if __name__ == "__main__":
    unittest.main()
