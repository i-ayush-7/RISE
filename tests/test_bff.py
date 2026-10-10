import unittest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock

class TestBFF(unittest.TestCase):
    def test_config_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            from bff.config import load_config
            cfg = load_config()
            self.assertEqual(cfg["bff_port"], 8080)
            self.assertEqual(cfg["mcp_port"], 8000)
            self.assertEqual(len(cfg["token"]), 43)  # urlsafe 32 bytes is ~43 chars
            self.assertEqual(cfg["nws_point"], "34.0522,-118.2437")

    def test_process_env(self):
        from unittest.mock import patch, MagicMock, AsyncMock
        from bff.process import ServerProcessManager
        import subprocess
        with patch('atexit.register'):
              mgr = ServerProcessManager()
        
        with patch("subprocess.Popen") as mock_popen, patch("subprocess.run"):
            mock_popen.return_value = MagicMock()
            mock_popen.return_value.poll.return_value = None
            
            with patch("time.sleep"), patch("bff.process.ServerProcessManager._wait_for_ready"):
                with patch.dict(os.environ, {"RISE_ALLOW_NO_AUTH": "1", "RISE_ALLOWED_HOSTS": "*"}):
                    mgr.start("flood")
                    
        args, kwargs = mock_popen.call_args
        env = kwargs["env"]
        self.assertNotIn("RISE_ALLOW_NO_AUTH", env)
        self.assertNotIn("RISE_ALLOWED_HOSTS", env)
        self.assertEqual(env["RISE_DEMO_MODE"], "1")
        self.assertTrue(os.path.isabs(env["RISE_DEMO_CLOCK_FILE"]))
        self.assertEqual(env["RISE_ALERT_SOURCE"], "fixture")
        self.assertEqual(env["RISE_FIXTURE_SCENARIO"], "flood_warning")
        
        if mgr.log_file:
            mgr.log_file.close()
            mgr.log_file = None
        from unittest.mock import patch, AsyncMock
        with patch("bff.process.status", new_callable=AsyncMock) as mock_status, patch("time.sleep"):
            mock_status.return_value = None
            mgr.stop()
        
    def test_client_allowlist(self):
        from bff.mcp_client import call_tool
        import asyncio
        ok, res, proto = asyncio.run(call_tool("remove_member", {}))
        self.assertFalse(ok)
        self.assertIn("not in allowlist", res)
        
        ok, res, proto = asyncio.run(call_tool("ping", {"a": "1"*1001}))
        self.assertFalse(ok)
        self.assertIn("too long", res)
        
        ok, res, proto = asyncio.run(call_tool("ping", {str(i): i for i in range(21)}))
        self.assertFalse(ok)
        self.assertIn("Too many", res)
        
        ok, res, proto = asyncio.run(call_tool("ping", "not-a-dict"))
        self.assertFalse(ok)
        self.assertIn("must be a JSON object", res)

    def test_activity_log(self):
        from bff.activity import ActivityLog
        log = ActivityLog(capacity=100)
        
        for i in range(110):
            log.add("tool", {"val": i}, True, 10, "res")
            
        entries = log.get_since(0)
        self.assertEqual(len(entries), 100)
        self.assertEqual(entries[-1]["arguments"]["val"], 109)
        
        long_res = "A" * 2500
        log.add("tool", {}, True, 5, long_res)
        entries = log.get_since(0)
        self.assertTrue(len(entries[-1]["result"]) < 2500)
        self.assertTrue(entries[-1]["result"].endswith("..."))

    async def run_asgi(self, app, scope, body=b""):
        responses = []
        
        async def receive():
            return {"type": "http.request", "body": body}
            
        async def send(message):
            responses.append(message)
            
        await app(scope, receive, send)
        
        start = [r for r in responses if r["type"] == "http.response.start"][0]
        body_msg = [r for r in responses if r["type"] == "http.response.body"][0]
        return start, body_msg

    def test_app_middleware(self):
        import asyncio
        from bff.app import app
        
        # Test bad host -> 403
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/status",
            "headers": [(b"host", b"evil.com")]
        }
        start, body = asyncio.run(self.run_asgi(app, scope))
        self.assertEqual(start["status"], 403)
        
        # Test missing host -> 403
        scope["headers"] = []
        start, body = asyncio.run(self.run_asgi(app, scope))
        self.assertEqual(start["status"], 403)
        
        # Test good host
        scope["headers"] = [(b"host", b"127.0.0.1:8080")]
        start, body = asyncio.run(self.run_asgi(app, scope))
        self.assertEqual(start["status"], 200)
        
        # POST good origin
        scope["method"] = "POST"
        scope["path"] = "/api/tool"
        scope["headers"] = [(b"host", b"127.0.0.1:8080"), (b"origin", b"http://127.0.0.1:8080"), (b"content-type", b"application/json")]
        with patch("bff.app.manager.reset"):
            start, body = asyncio.run(self.run_asgi(app, scope, b'{"name": "ping"}'))
            self.assertEqual(start["status"], 200)
            
        # POST bad origin
        scope["headers"] = [(b"host", b"127.0.0.1:8080"), (b"origin", b"http://evil.com"), (b"content-type", b"application/json")]
        start, body = asyncio.run(self.run_asgi(app, scope, b'{"name": "ping"}'))
        self.assertEqual(start["status"], 403)
        
        # POST bad content type
        scope["headers"] = [(b"host", b"127.0.0.1:8080"), (b"content-type", b"text/plain")]
        start, body = asyncio.run(self.run_asgi(app, scope, b'{"name": "ping"}'))
        self.assertEqual(start["status"], 415)
        
        # POST oversize
        scope["headers"] = [(b"host", b"127.0.0.1:8080"), (b"content-type", b"application/json"), (b"content-length", b"20000")]
        start, body = asyncio.run(self.run_asgi(app, scope, b'{"name": "ping"}'))
        self.assertEqual(start["status"], 413)

    def test_app_status(self):
        import asyncio
        from bff.app import app
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/status",
            "headers": [(b"host", b"127.0.0.1:8080")]
        }
        
        with patch("bff.app.status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = "2025"
            start, body = asyncio.run(self.run_asgi(app, scope))
            self.assertEqual(start["status"], 200)
            res = json.loads(body["body"])
            self.assertEqual(res["server"], "up")
            self.assertNotIn("token", res)
            self.assertNotIn("path", res)
            self.assertNotIn("pid", res)
            
            headers = dict(start["headers"])
            self.assertIn(b"cache-control", headers)
            self.assertEqual(headers[b"cache-control"], b"no-store")
            
    def test_static_files(self):
        import asyncio
        from bff.app import app
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"host", b"127.0.0.1:8080")]
        }
        
        start, body = asyncio.run(self.run_asgi(app, scope))
        self.assertEqual(start["status"], 200)
        
        scope["path"] = "/assets/house-rain.jpg"
        start, body = asyncio.run(self.run_asgi(app, scope))
        self.assertEqual(start["status"], 200)
        headers = dict(start["headers"])
        self.assertEqual(headers[b"content-type"], b"image/jpeg")
        
        scope["path"] = "/../README.md"
        start, body = asyncio.run(self.run_asgi(app, scope))
        self.assertTrue(start["status"] in (403, 404))
        
    def test_source_checks(self):
        import ast
        from pathlib import Path
        
        base = Path(__file__).parent.parent / "bff"
        
        for py_file in base.rglob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn("0.0.0.0", content)
                
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        if node.func.attr in ("debug", "info", "warning", "error", "critical", "exception"):
                            # check args
                            for arg in node.args:
                                if isinstance(arg, ast.Name) and arg.id == "token":
                                    self.fail(f"Token passed to logging in {py_file}")
                                if isinstance(arg, ast.JoinedStr):
                                    for v in arg.values:
                                        if isinstance(v, ast.FormattedValue):
                                            if isinstance(v.value, ast.Name) and v.value.id == "token":
                                                self.fail(f"Token passed to logging in {py_file}")
                                                
        from bff.config import config
        self.assertNotIn("token", config["token"]) # just sanity checking no literal "token" is the token


    def test_chunked_under_limit(self):
        import asyncio
        from bff.app import app
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/tool",
            "headers": [(b"host", b"127.0.0.1:8080"), (b"origin", b"http://127.0.0.1:8080"), (b"content-type", b"application/json")]
        }
        with patch("bff.app.manager.reset"):
            start, body = asyncio.run(self.run_asgi(app, scope, b'{"name": "ping"}'))
            self.assertEqual(start["status"], 200)

    def test_chunked_over_limit(self):
        import asyncio
        from bff.app import app
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/tool",
            "headers": [(b"host", b"127.0.0.1:8080"), (b"origin", b"http://127.0.0.1:8080"), (b"content-type", b"application/json")]
        }
        # oversize payload without content-length
        large_body = b"{" + b'"a":"' + b"A"*17000 + b'"}'
        start, body = asyncio.run(self.run_asgi(app, scope, large_body))
        self.assertEqual(start["status"], 413)



    def test_chat_validation(self):
        import asyncio
        from bff.app import app
        import json
        
        # bad Origin
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/chat",
            "headers": [(b"host", b"127.0.0.1:8080"), (b"origin", b"http://evil.com"), (b"content-type", b"application/json")]
        }
        start, body = asyncio.run(self.run_asgi(app, scope, b"{}"))
        self.assertEqual(start["status"], 403)
        
        # bad content-type
        scope["headers"] = [(b"host", b"127.0.0.1:8080"), (b"origin", b"http://127.0.0.1:8080"), (b"content-type", b"text/plain")]
        start, body = asyncio.run(self.run_asgi(app, scope, b'{"text": "hello"}'))
        self.assertEqual(start["status"], 415)
        
        # missing text
        scope["headers"] = [(b"host", b"127.0.0.1:8080"), (b"origin", b"http://127.0.0.1:8080"), (b"content-type", b"application/json")]
        start, body = asyncio.run(self.run_asgi(app, scope, b'{}'))
        self.assertEqual(start["status"], 400)
        
        # text too long
        long_body = b'{"text": "' + b'A' * 201 + b'"}'
        start, body = asyncio.run(self.run_asgi(app, scope, long_body))
        self.assertEqual(start["status"], 400)
        
        # 200 shape
        from unittest.mock import patch
        with patch("bff.chat.handle_chat") as mock_handle:
            async def fake_handle(*args):
                return {"reply": "Hi", "intent": "help", "tools": [], "refresh": []}
            mock_handle.side_effect = fake_handle
            start, body = asyncio.run(self.run_asgi(app, scope, b'{"text": "hello"}'))
            self.assertEqual(start["status"], 200)


if __name__ == "__main__":
    unittest.main()
