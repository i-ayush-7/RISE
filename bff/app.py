import json
import logging
import mimetypes
import time
from pathlib import Path
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("image/jpeg", ".jpg")
mimetypes.add_type("image/jpeg", ".jpeg")
mimetypes.add_type("image/png", ".png")
mimetypes.add_type("application/json", ".json")

from bff.config import config
from bff.process import manager, SCENARIOS
from bff.mcp_client import call_tool, status
from bff.activity import activity_log

logger = logging.getLogger(__name__)

async def get_status(request: Request):
    proto = await status()
    server_state = "up" if proto else "down"
    return JSONResponse({
        "server": server_state,
        "protocol_version": proto,
        "scenario": manager.current_scenario,
        "demo_mode": True,
        "clock_offset_minutes": manager.get_offset(),
        "bff": "ok"
    })

async def run_tool(name, arguments):
    start_t = time.time()
    ok, res_payload, _ = await call_tool(name, arguments)
    ms = int((time.time() - start_t) * 1000)
    activity_log.add(name, arguments, ok, ms, res_payload)
    return ok, res_payload, ms

async def post_tool(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)
        
    name = body.get("name")
    arguments = body.get("arguments", {})
    if not name:
        return JSONResponse({"ok": False, "error": "Missing tool name"}, status_code=400)
        
    ok, res_payload, ms = await run_tool(name, arguments)
    
    if ok:
        return JSONResponse({"ok": True, "result": res_payload, "ms": ms})
    else:
        if res_payload in ("Tool " + name + " not in allowlist", "Arguments must be a JSON object", "Too many arguments (max 20)") or (isinstance(res_payload, str) and res_payload.startswith("Argument ") and "too long" in res_payload):
            return JSONResponse({"ok": False, "error": res_payload}, status_code=400)
        return JSONResponse({"ok": False, "error": res_payload}, status_code=200)

async def get_activity(request: Request):
    try:
        after = int(request.query_params.get("after", "0"))
    except ValueError:
        after = 0
    entries = activity_log.get_since(after)
    return JSONResponse(entries)

async def post_scenario(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)
        
    scenario = body.get("scenario")
    if scenario not in SCENARIOS:
        return JSONResponse({"ok": False, "error": "Unknown scenario"}, status_code=400)
        
    import asyncio
    await asyncio.to_thread(manager.restart, scenario)
    return JSONResponse({"scenario": scenario})

async def post_reset(request: Request):
    import asyncio
    await asyncio.to_thread(manager.reset)
    return JSONResponse({"ok": True})

async def post_skip_time(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)
        
    minutes = body.get("minutes")
    if not isinstance(minutes, int) or minutes < 1 or minutes > 60:
        return JSONResponse({"ok": False, "error": "minutes must be integer 1..60"}, status_code=400)
        
    new_val = manager.add_offset(minutes)
    return JSONResponse({"clock_offset_minutes": new_val})


async def post_chat(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)
        
    text = body.get("text")
    if not isinstance(text, str):
        return JSONResponse({"ok": False, "error": "text must be a string"}, status_code=400)
        
    import unicodedata
    import re
    chars = []
    for c in text:
        cat = unicodedata.category(c)
        if cat in ("Cc", "Cf"):
            if c in ("\n", "\r", "\t"):
                chars.append(" ")
        else:
            chars.append(c)
            
    cleaned = "".join(chars)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    if len(cleaned) > 200:
        return JSONResponse({"ok": False, "error": "Please type a short message (up to 200 characters)."}, status_code=400)

    from bff.chat import handle_chat
    res = await handle_chat(text, run_tool)
    if res.get("intent") == "invalid":
        return JSONResponse({"ok": False, "error": res["reply"]}, status_code=400)
        
    # Chat tool calls appear in the activity log like any other. 
    # But wait, run_tool inside handle_chat logs the tool calls!
    # Does post_chat log anything itself?
    # "Chat tool calls appear in the activity log like any other."
    # Since handle_chat calls run_tool, run_tool will log each tool it calls.
    # What about the chat itself? The prompt says "Chat tool calls appear in the activity log like any other." This might mean the *tools called during chat* appear, which they do via run_tool.
        
    return JSONResponse(res)

class BFFSecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        host = ""
        origin = None
        content_type = ""
        content_length = None
        
        for k, v in scope.get("headers", []):
            kl = k.lower()
            if kl == b"host":
                host = v.decode("utf-8", "ignore")
            elif kl == b"origin":
                origin = v.decode("utf-8", "ignore")
            elif kl == b"content-type":
                content_type = v.decode("utf-8", "ignore")
            elif kl == b"content-length":
                try:
                    content_length = int(v.decode("utf-8", "ignore"))
                except ValueError:
                    content_length = -1
                    
        valid_hosts = [
            f"localhost:{config['bff_port']}", f"127.0.0.1:{config['bff_port']}",
            "localhost", "127.0.0.1"
        ]
        if host not in valid_hosts:
            logger.warning("Rejected request due to bad Host header")
            await self._send_plain(send, 403, "Forbidden")
            return
            
        if scope["method"] == "POST":
            if origin:
                valid_origins = [
                    f"http://localhost:{config['bff_port']}", f"http://127.0.0.1:{config['bff_port']}"
                ]
                if origin not in valid_origins:
                    logger.warning("Rejected request due to bad Origin header")
                    await self._send_plain(send, 403, "Forbidden")
                    return
                    
            if not content_type.startswith("application/json"):
                logger.warning("Rejected request due to bad Content-Type")
                await self._send_plain(send, 415, "Unsupported Media Type")
                return
                
            if content_length is not None:
                if content_length == -1:
                    logger.warning("Rejected request due to invalid Content-Length")
                    await self._send_plain(send, 400, "Bad Request")
                    return
                if content_length > 16384:
                    logger.warning("Rejected request due to oversize body")
                    await self._send_plain(send, 413, "Payload Too Large")
                    return
                    
        body_size = 0
        body_too_large = False
        response_started = False
        class PayloadTooLarge(BaseException): pass

        async def wrapped_receive():
            nonlocal body_size, body_too_large
            message = await receive()
            if message["type"] == "http.request":
                body_size += len(message.get("body", b""))
                if body_size > 16384:
                    body_too_large = True
                    raise PayloadTooLarge()
            return message

        async def wrapped_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = list(message.get("headers", []))
                headers.append((b"content-security-policy", b"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"referrer-policy", b"no-referrer"))
                if scope["path"].startswith("/api/"):
                    headers.append((b"cache-control", b"no-store"))
                else:
                    headers.append((b"cache-control", b"no-cache"))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        except BaseException as e:
            if e.__class__.__name__ == 'PayloadTooLarge':
                logger.warning('Rejected request due to oversize body (chunked)')
                if not response_started:
                    await self._send_plain(send, 413, 'Payload Too Large')
            else:
                raise
            logger.warning("Rejected request due to oversize body (chunked)")
            if not response_started:
                await self._send_plain(send, 413, "Payload Too Large")
        except Exception:
            raise

    async def _send_plain(self, send, status, text):
        body = text.encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"text/plain"),
                (b"content-length", str(len(body)).encode("utf-8")),
                (b"content-security-policy", b"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
                (b"x-content-type-options", b"nosniff"),
                (b"referrer-policy", b"no-referrer")
            ]
        })
        await send({
            "type": "http.response.body",
            "body": body
        })

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    yield
    import asyncio
    await asyncio.to_thread(manager.stop)

routes = [
    Route("/api/status", get_status),
    Route("/api/tool", post_tool, methods=["POST"]),
    Route("/api/activity", get_activity),
    Route("/api/scenario", post_scenario, methods=["POST"]),
    Route("/api/reset", post_reset, methods=["POST"]),
    Route("/api/demo/skip-time", post_skip_time, methods=["POST"]),
    Route("/api/chat", post_chat, methods=["POST"]),
    Mount("/", app=StaticFiles(directory=str(Path(__file__).parent.parent / "web"), html=True), name="static")
]

app_starlette = Starlette(routes=routes, middleware=[], lifespan=lifespan)
app = BFFSecurityMiddleware(app_starlette)
