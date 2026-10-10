import os
import sys
import subprocess
import time
import tempfile
import shutil
import atexit
import signal
import threading
import asyncio
from pathlib import Path
from typing import Optional
import logging
from bff.config import config
from bff.mcp_client import status

logger = logging.getLogger(__name__)

SCENARIOS = {
    "flood": {"RISE_ALERT_SOURCE": "fixture", "RISE_FIXTURE_SCENARIO": "flood_warning"},
    "heatwave": {"RISE_ALERT_SOURCE": "fixture", "RISE_FIXTURE_SCENARIO": "heatwave_warning"},
    "none": {"RISE_ALERT_SOURCE": "fixture", "RISE_FIXTURE_SCENARIO": "none"},
    "recorded": {"RISE_ALERT_SOURCE": "nws_recorded", "RISE_NWS_RECORDING": "sample"},
    "live": {"RISE_ALERT_SOURCE": "nws", "RISE_NWS_POINT": config["nws_point"]}
}

class ServerProcessManager:
    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self.temp_dir: Optional[str] = None
        self.db_path: Optional[Path] = None
        self.clock_path: Optional[Path] = None
        self.current_scenario = "flood"
        self.log_file = None
        self.lock = threading.Lock()
        atexit.register(self.stop)

    def _init_temp(self):
        if not self.temp_dir:
            self.temp_dir = tempfile.mkdtemp()
            self.db_path = Path(self.temp_dir) / "rise.db"
            self.clock_path = Path(self.temp_dir) / "clock.txt"
            self.clock_path.write_text("0", encoding="utf-8")
            
            env = os.environ.copy()
            env["RISE_DB_PATH"] = str(self.db_path)
            subprocess.run([sys.executable, "-m", "rise.seed"], env=env, cwd=str(Path(__file__).parent.parent), capture_output=True, check=True)

    def _wait_for_ready(self):
        start_t = time.time()
        while time.time() - start_t < 15:
            if self.proc and self.proc.poll() is not None:
                log_content = ""
                if self.temp_dir:
                    p = Path(self.temp_dir) / "server.log"
                    if p.exists():
                        log_content = p.read_text()
                raise RuntimeError(f"Server process exited prematurely: {log_content}")
            
            res = asyncio.run(status())
            if res is not None:
                return
            time.sleep(0.5)
        raise RuntimeError("Timed out waiting for MCP server")

    def start(self, scenario: str = "flood"):
        with self.lock:
            self._start_locked(scenario)
            
    def _start_locked(self, scenario: str):
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")
            
        self._stop_locked()
        self.current_scenario = scenario
        self._init_temp()
        
        env = os.environ.copy()
        for k in ["RISE_ALLOW_NO_AUTH", "RISE_ALLOWED_HOSTS"]:
            if k in env:
                del env[k]
                
        env["RISE_AUTH_TOKEN"] = config["token"]
        env["RISE_DB_PATH"] = str(self.db_path)
        env["RISE_DEMO_MODE"] = "1"
        env["RISE_DEMO_CLOCK_FILE"] = str(self.clock_path)
        env["RISE_MCP_PORT"] = str(config["mcp_port"])
        
        for k, v in SCENARIOS[scenario].items():
            env[k] = v
            
        log_path = Path(self.temp_dir) / "server.log"
        self.log_file = open(log_path, "w")
        
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        try:
            self.proc = subprocess.Popen(
                [sys.executable, "server.py"],
                env=env,
                cwd=str(Path(__file__).parent.parent),
                stdout=self.log_file,
                stderr=subprocess.STDOUT,
                **kwargs
            )
            self._wait_for_ready()
        except Exception:
            if self.log_file:
                self.log_file.close()
                self.log_file = None
            raise

    def restart(self, scenario: Optional[str] = None):
        with self.lock:
            if scenario is None:
                scenario = self.current_scenario
            self._start_locked(scenario)
        
    def reset(self):
        with self.lock:
            self._start_locked(self.current_scenario)

    def stop(self):
        with self.lock:
            self._stop_locked()

    def _stop_locked(self):
        if not self.proc and not self.temp_dir:
            return
            
        if self.proc:
            pid = self.proc.pid
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False, timeout=10)
            else:
                try:
                    pgid = os.getpgid(pid)
                    sigterm = getattr(signal, "SIGTERM", 15)
                    sigkill = getattr(signal, "SIGKILL", 9)
                    os.killpg(pgid, sigterm)
                    time.sleep(3)
                    if self.proc.poll() is None:
                        os.killpg(pgid, sigkill)
                except Exception:
                    pass

            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            self.proc = None

        start_t = time.time()
        while time.time() - start_t < 5:
            res = asyncio.run(status())
            if res is None:
                break
            time.sleep(0.5)
        else:
            logger.warning("Server still reachable after stop")
            raise RuntimeError("Child server did not stop")

        if self.log_file:
            self.log_file.close()
            self.log_file = None

        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir = None
            
    def get_offset(self) -> int:
        if not self.clock_path or not self.clock_path.exists():
            return 0
        try:
            return int(self.clock_path.read_text(encoding="utf-8").strip())
        except Exception:
            return 0
            
    def add_offset(self, minutes: int):
        if not isinstance(minutes, int) or minutes < 1 or minutes > 60:
            raise ValueError("Offset must be an integer between 1 and 60")
        current = self.get_offset()
        new_val = min(1440, current + minutes)
        if self.clock_path:
            self.clock_path.write_text(str(new_val), encoding="utf-8")
        return new_val

manager = ServerProcessManager()
