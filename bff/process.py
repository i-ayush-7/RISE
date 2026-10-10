import os
import sys
import subprocess
import time
import tempfile
import shutil
import atexit
from pathlib import Path
from typing import Optional
from bff.config import config

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
        atexit.register(self.stop)

    def _init_temp(self):
        if not self.temp_dir:
            self.temp_dir = tempfile.mkdtemp()
            self.db_path = Path(self.temp_dir) / "rise.db"
            self.clock_path = Path(self.temp_dir) / "clock.txt"
            self.clock_path.write_text("0", encoding="utf-8")
            
            # seed the database
            env = os.environ.copy()
            env["RISE_DB_PATH"] = str(self.db_path)
            subprocess.run([sys.executable, "-m", "rise.seed"], env=env, cwd=str(Path(__file__).parent.parent), capture_output=True, check=True)

    def _wait_for_ready(self):
        from bff.mcp_client import status
        import asyncio
        start_t = time.time()
        while time.time() - start_t < 15:
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError("Server process exited prematurely")
            try:
                res = asyncio.run(status())
                if res is not None:
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("Timed out waiting for MCP server")

    def start(self, scenario: str = "flood"):
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")
            
        self.stop()
        self.current_scenario = scenario
        self._init_temp()
        
        env = os.environ.copy()
        # Remove unwanted vars
        for k in ["RISE_ALLOW_NO_AUTH", "RISE_ALLOWED_HOSTS"]:
            if k in env:
                del env[k]
                
        env["RISE_AUTH_TOKEN"] = config["token"]
        env["RISE_DB_PATH"] = str(self.db_path)
        env["RISE_DEMO_MODE"] = "1"
        env["RISE_DEMO_CLOCK_FILE"] = str(self.clock_path)
        
        for k, v in SCENARIOS[scenario].items():
            env[k] = v
            
        log_path = Path(self.temp_dir) / "server.log"
        self.log_file = open(log_path, "w")
        
        self.proc = subprocess.Popen(
            [sys.executable, "server.py"],
            env=env,
            cwd=str(Path(__file__).parent.parent),
            stdout=self.log_file,
            stderr=subprocess.STDOUT
        )
        self._wait_for_ready()

    def restart(self, scenario: Optional[str] = None):
        if scenario is None:
            scenario = self.current_scenario
        self.start(scenario)
        
    def reset(self):
        self.stop()
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir = None
        self.start(self.current_scenario)

    def stop(self):
        if self.proc:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], capture_output=True)
                    else:
                        self.proc.kill()
            self.proc = None
        if self.log_file:
            self.log_file.close()
            self.log_file = None

    def cleanup(self):
        self.stop()
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
