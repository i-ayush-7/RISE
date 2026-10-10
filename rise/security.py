import logging
import hmac
import hashlib
import re
from typing import Callable, Awaitable, Dict, Any, List

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    def __init__(
        self,
        app: Callable[[Dict[str, Any], Callable, Callable], Awaitable[None]],
        token: str,
        allowed_hosts: List[str],
        allowed_origins: List[str],
        max_body_bytes: int = 65536
    ):
        self.app = app
        self.token = token
        self.allowed_hosts = set(allowed_hosts)
        self.allowed_origins = set(allowed_origins)
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
            
        headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])}
        client_addr = scope.get("client", ("unknown", 0))[0]
        
        # 1. Host check
        host = headers.get("host", "")
        host_no_port = host.split(":")[0].lower()
        if host_no_port not in self.allowed_hosts:
            logger.warning(f"Rejected request: 403 from {client_addr}")
            await self._send_plain(send, 403, b"Forbidden")
            return
            
        # 2. Origin check
        if "origin" in headers:
            origin = headers["origin"].lower()
            if origin not in self.allowed_origins:
                logger.warning(f"Rejected request: 403 from {client_addr}")
                await self._send_plain(send, 403, b"Forbidden")
                return
                
        # 3. Authorization check
        if self.token is not None:
            auth = headers.get("authorization", "")
            prefix = "Bearer "
            if not auth.startswith(prefix):
                logger.warning(f"Rejected request: 401 from {client_addr}")
                await self._send_401(send)
                return
                
            provided_token = auth[len(prefix):]
            expected_hash = hashlib.sha256(self.token.encode("utf-8")).digest()
            provided_hash = hashlib.sha256(provided_token.encode("utf-8")).digest()
            if not hmac.compare_digest(expected_hash, provided_hash):
                logger.warning(f"Rejected request: 401 from {client_addr}")
                await self._send_401(send)
                return
                
        # 4. Body size check (Content-Length header)
        if "content-length" in headers:
            try:
                cl = int(headers["content-length"])
                if cl > self.max_body_bytes:
                    logger.warning(f"Rejected request: 413 from {client_addr}")
                    await self._send_plain(send, 413, b"Payload Too Large")
                    return
            except ValueError:
                pass
                
        # 4. Body size check (wrapped receive)
        body_read = 0
        async def wrapped_receive() -> Dict[str, Any]:
            nonlocal body_read
            message = await receive()
            if message["type"] == "http.request":
                chunk_len = len(message.get("body", b""))
                body_read += chunk_len
                if body_read > self.max_body_bytes:
                    logger.warning(f"Rejected request: 413 from {client_addr}")
                    raise RuntimeError("Payload Too Large")
            return message
            
        try:
            return await self.app(scope, wrapped_receive, send)
        except RuntimeError as e:
            if str(e) == "Payload Too Large":
                await self._send_plain(send, 413, b"Payload Too Large")
                return
            raise

    async def _send_plain(self, send: Callable, status: int, body: bytes) -> None:
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"text/plain"), (b"content-length", str(len(body)).encode("ascii"))]
        })
        await send({
            "type": "http.response.body",
            "body": body
        })
        
    async def _send_401(self, send: Callable) -> None:
        body = b"Unauthorized"
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"text/plain"), (b"content-length", str(len(body)).encode("ascii")), (b"www-authenticate", b"Bearer")]
        })
        await send({
            "type": "http.response.body",
            "body": body
        })


def load_security_config(environ: Dict[str, str]) -> Dict[str, Any]:
    allow_no_auth = environ.get("RISE_ALLOW_NO_AUTH", "") == "1"
    token = environ.get("RISE_AUTH_TOKEN", "")
    demo_mode = environ.get("RISE_DEMO_MODE") == "1"
    
    if demo_mode:
        import os
        clock_file = environ.get("RISE_DEMO_CLOCK_FILE", "")
        if not clock_file or not os.path.isabs(clock_file):
            raise ValueError("RISE_DEMO_CLOCK_FILE must be an absolute path when RISE_DEMO_MODE=1")
    
    if not allow_no_auth and len(token) < 32:
        raise ValueError("RISE_AUTH_TOKEN is required (at least 32 characters). Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\" ")
        
    if allow_no_auth:
        token = None
        logger.warning("AUTH DISABLED: local development only")
        hosts = ["localhost", "127.0.0.1"]
    else:
        hosts = ["localhost", "127.0.0.1"]
        extra_hosts = environ.get("RISE_ALLOWED_HOSTS", "")
        if extra_hosts:
            if demo_mode:
                raise ValueError("Demo mode is local only: remove extra hosts from RISE_ALLOWED_HOSTS")
            for h in extra_hosts.split(","):
                h = h.strip().lower()
                if not h: continue
                if h == "*" or not re.match(r"^[a-z0-9.-]+$", h):
                    raise ValueError(f"Invalid host in RISE_ALLOWED_HOSTS: {h}")
                hosts.append(h)
                
    origins = []
    extra_origins = environ.get("RISE_ALLOWED_ORIGINS", "")
    if extra_origins:
        for o in extra_origins.split(","):
            o = o.strip().lower()
            if o:
                origins.append(o)
                
    return {
        "token": token,
        "allowed_hosts": hosts,
        "allowed_origins": origins,
        "demo_mode": demo_mode
    }
