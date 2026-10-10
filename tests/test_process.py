import unittest
from unittest.mock import patch, MagicMock, AsyncMock, call
import sys
import subprocess
import signal
import os
from bff.process import ServerProcessManager

class TestProcessManager(unittest.TestCase):
    def setUp(self):
        self.manager = ServerProcessManager()
        self.manager._wait_for_ready = MagicMock()
        
        # mock _init_temp to set temp_dir so Path() doesn't fail
        import tempfile
        real_temp = tempfile.gettempdir()
        def fake_init_temp():
            self.manager.temp_dir = real_temp
            self.manager.db_path = real_temp + "/db"
            self.manager.clock_path = real_temp + "/clock"
        self.manager._init_temp = MagicMock(side_effect=fake_init_temp)

    @patch("bff.process.sys.platform", "win32")
    @patch("bff.process.subprocess.Popen")
    @patch("bff.mcp_client.status", new_callable=AsyncMock)
    def test_start_windows_creationflags(self, mock_status, mock_popen):
        mock_status.return_value = None
        self.manager.start("flood")
        mock_popen.assert_called_once()
        kwargs = mock_popen.call_args.kwargs
        self.assertIn("creationflags", kwargs)
        self.assertEqual(kwargs["creationflags"], subprocess.CREATE_NEW_PROCESS_GROUP)

    @patch("bff.process.sys.platform", "linux")
    @patch("bff.process.subprocess.Popen")
    @patch("bff.mcp_client.status", new_callable=AsyncMock)
    def test_start_posix_start_new_session(self, mock_status, mock_popen):
        mock_status.return_value = None
        self.manager.start("flood")
        mock_popen.assert_called_once()
        kwargs = mock_popen.call_args.kwargs
        self.assertIn("start_new_session", kwargs)
        self.assertTrue(kwargs["start_new_session"])

    @patch("bff.process.sys.platform", "win32")
    @patch("bff.process.subprocess.run")
    @patch("bff.mcp_client.status", new_callable=AsyncMock)
    def test_stop_windows_taskkill(self, mock_status, mock_run):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 1234
        self.manager.proc = mock_proc
        self.manager.temp_dir = "dummy"

        mock_status.return_value = None # server down immediately

        self.manager.stop()
        mock_run.assert_called_with(["taskkill", "/PID", "1234", "/T", "/F"], capture_output=True, check=False, timeout=10)
        self.assertIsNone(self.manager.proc)
        self.assertIsNone(self.manager.temp_dir)

    @patch("bff.process.sys.platform", "linux")
    @patch("bff.process.os.killpg", create=True)
    @patch("bff.process.os.getpgid", return_value=5678, create=True)
    @patch("bff.process.time.sleep")
    @patch("bff.mcp_client.status", new_callable=AsyncMock)
    def test_stop_posix_killpg(self, mock_status, mock_sleep, mock_getpgid, mock_killpg):
        mock_proc = MagicMock()
        # First poll is None, second poll inside killpg block is None (meaning it needs SIGKILL)
        mock_proc.poll.return_value = None
        mock_proc.pid = 1234
        self.manager.proc = mock_proc
        self.manager.temp_dir = "dummy"

        mock_status.return_value = None

        self.manager.stop()
        mock_getpgid.assert_called_with(1234)
        sigterm = getattr(signal, "SIGTERM", 15)
        sigkill = getattr(signal, "SIGKILL", 9)
        mock_killpg.assert_has_calls([
            call(5678, sigterm),
            call(5678, sigkill)
        ])
        
    @patch("bff.mcp_client.status", new_callable=AsyncMock)
    def test_stop_waits_until_status_none(self, mock_status):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0 # Already dead
        self.manager.proc = mock_proc
        self.manager.temp_dir = "dummy"
        
        # Returns "ok" twice, then None
        mock_status.side_effect = ["ok", "ok", None]
        
        with patch("bff.process.time.sleep") as mock_sleep:
            self.manager.stop()
            self.assertEqual(mock_sleep.call_count, 2)
            self.assertEqual(mock_status.call_count, 3)

    @patch("bff.mcp_client.status", new_callable=AsyncMock)
    def test_stop_raises_runtimeerror_if_never_down(self, mock_status):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        self.manager.proc = mock_proc
        self.manager.temp_dir = "dummy"
        
        mock_status.return_value = "still_up"
        
        with patch("bff.process.time.sleep"), patch("bff.process.time.time", side_effect=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]):
            with self.assertRaisesRegex(RuntimeError, "Child server did not stop"):
                self.manager.stop()

    @patch("bff.mcp_client.status", new_callable=AsyncMock)
    def test_stop_idempotent(self, mock_status):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        self.manager.proc = mock_proc
        self.manager.temp_dir = "dummy"
        mock_status.return_value = None
        
        # First stop
        self.manager.stop()
        self.assertIsNone(self.manager.proc)
        self.assertIsNone(self.manager.temp_dir)
        
        # Second stop
        mock_status.reset_mock()
        self.manager.stop()
        mock_status.assert_not_called() # Should return immediately

    @patch("bff.process.tempfile.mkdtemp")
    @patch("bff.process.subprocess.Popen")
    @patch("bff.mcp_client.status", new_callable=AsyncMock)
    def test_restart_calls_stop_before_start(self, mock_status, mock_popen, mock_mkdtemp):
        import tempfile
        mock_mkdtemp.return_value = tempfile.gettempdir()
        mock_status.return_value = None
        self.manager.stop = MagicMock()
        self.manager.start = MagicMock()
        self.manager.current_scenario = "none"
        
        self.manager.restart("recorded")
        self.manager.start.assert_called_with("recorded")
        
        # In our implementation, restart calls start, and start calls stop
        # Let's verify start does call stop
        real_start = ServerProcessManager.start
        self.manager.start = real_start.__get__(self.manager)
        
        self.manager.start("recorded")
        self.manager.stop.assert_called_once()
