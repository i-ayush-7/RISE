import unittest
from unittest.mock import patch, MagicMock, AsyncMock, call
import sys
import subprocess
import signal
import os
import threading
import time
from bff.process import ServerProcessManager

class TestProcessManager(unittest.TestCase):

    def tearDown(self):
        if self.manager.log_file:
            self.manager.log_file.close()
    @patch('atexit.register')
    def setUp(self, mock_atexit):

        self.manager = ServerProcessManager()
        self.manager._wait_for_ready = MagicMock()
        
        import tempfile
        real_temp = tempfile.gettempdir()
        def fake_init_temp():
            self.manager.temp_dir = real_temp
            self.manager.db_path = real_temp + "/db"
            self.manager.clock_path = real_temp + "/clock"
        self.manager._init_temp = MagicMock(side_effect=fake_init_temp)

    @patch("bff.process.sys.platform", "win32")
    @patch("bff.process.subprocess.Popen")
    @patch("bff.process.status", new_callable=AsyncMock)
    def test_start_windows_creationflags(self, mock_status, mock_popen):
        mock_status.return_value = None
        self.manager.start("flood")
        mock_popen.assert_called_once()
        kwargs = mock_popen.call_args.kwargs
        self.assertIn("creationflags", kwargs)
        self.assertEqual(kwargs["creationflags"], subprocess.CREATE_NEW_PROCESS_GROUP)

    @patch("bff.process.sys.platform", "linux")
    @patch("bff.process.subprocess.Popen")
    @patch("bff.process.status", new_callable=AsyncMock)
    def test_start_posix_start_new_session(self, mock_status, mock_popen):
        mock_status.return_value = None
        self.manager.start("flood")
        mock_popen.assert_called_once()
        kwargs = mock_popen.call_args.kwargs
        self.assertIn("start_new_session", kwargs)
        self.assertTrue(kwargs["start_new_session"])

    @patch("bff.process.sys.platform", "win32")
    @patch("bff.process.subprocess.run")
    @patch("bff.process.status", new_callable=AsyncMock)
    def test_stop_windows_taskkill(self, mock_status, mock_run):
        mock_proc = MagicMock()
        mock_proc.pid = 4242
        self.manager.proc = mock_proc
        self.manager.temp_dir = "dummy"

        mock_status.return_value = None

        self.manager.stop()
        mock_run.assert_called_with(["taskkill", "/PID", "4242", "/T", "/F"], capture_output=True, check=False, timeout=10)
        self.assertIsNone(self.manager.proc)
        self.assertIsNone(self.manager.temp_dir)

    @patch("bff.process.sys.platform", "linux")
    @patch("bff.process.os.killpg", create=True)
    @patch("bff.process.os.getpgid", return_value=5678, create=True)
    @patch("bff.process.time.sleep")
    @patch("bff.process.status", new_callable=AsyncMock)
    def test_stop_posix_killpg(self, mock_status, mock_sleep, mock_getpgid, mock_killpg):
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, None]
        mock_proc.pid = 4242
        self.manager.proc = mock_proc
        self.manager.temp_dir = "dummy"

        mock_status.return_value = None

        self.manager.stop()
        mock_getpgid.assert_called_with(4242)
        sigterm = getattr(signal, "SIGTERM", 15)
        sigkill = getattr(signal, "SIGKILL", 9)
        mock_killpg.assert_has_calls([
            call(5678, sigterm),
            call(5678, sigkill)
        ])

    @patch("bff.process.status", new_callable=AsyncMock)
    @patch("bff.process.subprocess.run")
    @patch("bff.process.sys.platform", "win32")
    def test_stop_waits_until_status_none(self, mock_run, mock_status):
        mock_proc = MagicMock()
        mock_proc.pid = 4242
        self.manager.proc = mock_proc
        self.manager.temp_dir = "dummy"
        
        mock_status.side_effect = ["ok", "ok", None]
        
        with patch("bff.process.time.sleep") as mock_sleep:
            self.manager.stop()
            self.assertEqual(mock_status.call_count, 3)

    @patch("bff.process.status", new_callable=AsyncMock)
    @patch("bff.process.subprocess.run")
    @patch("bff.process.sys.platform", "win32")
    def test_stop_raises_runtimeerror_if_never_down(self, mock_run, mock_status):
        mock_proc = MagicMock()
        mock_proc.pid = 4242
        self.manager.proc = mock_proc
        self.manager.temp_dir = "dummy"
        
        mock_status.return_value = "still_up"
        
        with patch("bff.process.time.sleep") as mock_sleep:
            with patch("bff.process.time.time", side_effect=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]):
                with self.assertLogs("bff.process", level="WARNING"):
                    with self.assertRaisesRegex(RuntimeError, "Child server did not stop"):
                        self.manager.stop()

    @patch("bff.process.status", new_callable=AsyncMock)
    def test_stop_idempotent(self, mock_status):
        mock_proc = MagicMock()
        mock_proc.pid = 4242
        self.manager.proc = mock_proc
        self.manager.temp_dir = "dummy"
        mock_status.return_value = None
        
        with patch("bff.process.subprocess.run") as mock_run:
            # First stop
            self.manager.stop()
            self.assertIsNone(self.manager.proc)
            self.assertIsNone(self.manager.temp_dir)
            
            # Second stop
            mock_status.reset_mock()
            self.manager.stop()
            mock_status.assert_not_called()

    @patch("bff.process.tempfile.mkdtemp")
    @patch("bff.process.subprocess.Popen")
    @patch("bff.process.status", new_callable=AsyncMock)
    def test_restart_calls_stop_before_start(self, mock_status, mock_popen, mock_mkdtemp):
        import tempfile
        mock_mkdtemp.return_value = tempfile.gettempdir()
        mock_status.return_value = None
        self.manager.current_scenario = "none"
        
        with patch.object(self.manager, "_stop_locked") as mock_stop:
            self.manager.restart("recorded")
            mock_stop.assert_called_once()
            
    @patch("bff.process.status", new_callable=AsyncMock)
    @patch("bff.process.subprocess.run")
    @patch("bff.process.sys.platform", "win32")
    def test_lock_serializes(self, mock_run, mock_status):
        mock_status.return_value = None
        
        # We will hold the lock and prove that stop() blocks
        self.manager.lock.acquire()
        
        def run_stop():
            self.manager.stop()
            
        t = threading.Thread(target=run_stop)
        t.start()
        
        time.sleep(0.1)
        self.assertTrue(t.is_alive())
        
        self.manager.lock.release()
        t.join(timeout=1)
        self.assertFalse(t.is_alive())
