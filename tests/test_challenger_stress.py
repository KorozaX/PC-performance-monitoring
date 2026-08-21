"""
tests/test_challenger_stress.py
Milestone 1 Adversarial Challenger Stress & Concurrency Verification Harness.
Targeted testing for:
1. Concurrency & Startup Race Conditions during async discovery window
2. Cache corruption & invalid profile recovery (.cache/hw_profile.json)
3. HUDBridgeAPI window controls & maximize/restore toggling edge cases
"""

import concurrent.futures
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.bridge.api import HUDBridgeAPI
from src.telemetry.engine import HardwareProfileManager, TelemetryEngine
from tests.test_helpers import validate_telemetry_snapshot


class TestConcurrencyAndStartupRaces(unittest.TestCase):
    """Stress-tests concurrent snapshot queries and engine lifecycle during async discovery."""

    def test_concurrent_snapshot_queries_during_async_discovery(self):
        """
        Spawns 50 threads calling get_snapshot() and poll_once() concurrently
        while the background hardware discovery thread is actively executing.
        """
        engine = TelemetryEngine(interval_ms=50)
        num_threads = 50
        num_queries_per_thread = 20
        errors = []

        def worker_query(tid: int):
            for i in range(num_queries_per_thread):
                try:
                    # Alternating between get_snapshot() and poll_once()
                    if (tid + i) % 2 == 0:
                        snap = engine.get_snapshot()
                    else:
                        snap = engine.poll_once()
                    
                    if not isinstance(snap, dict):
                        errors.append(f"Thread {tid} got non-dict snapshot: {type(snap)}")
                        continue
                    
                    valid, err_list = validate_telemetry_snapshot(snap)
                    if not valid:
                        errors.append(f"Thread {tid} invalid snapshot: {err_list}")
                except Exception as exc:
                    errors.append(f"Thread {tid} exception: {exc}")
                time.sleep(0.005)

        threads = [threading.Thread(target=worker_query, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        engine.stop()
        self.assertEqual(len(errors), 0, f"Encountered {len(errors)} concurrency errors: {errors[:5]}")

    def test_concurrent_bridge_get_telemetry_snapshot(self):
        """
        Spawns 40 threads accessing HUDBridgeAPI.get_telemetry_snapshot() concurrently.
        """
        engine = TelemetryEngine(interval_ms=100)
        bridge = HUDBridgeAPI(engine=engine)
        num_threads = 40
        num_queries = 25
        errors = []

        def bridge_worker(tid: int):
            for _ in range(num_queries):
                try:
                    snap = bridge.get_telemetry_snapshot()
                    valid, err_list = validate_telemetry_snapshot(snap)
                    if not valid:
                        errors.append(f"Thread {tid} invalid: {err_list}")
                except Exception as exc:
                    errors.append(f"Thread {tid} exception: {exc}")
                time.sleep(0.002)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(bridge_worker, i) for i in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        engine.stop()
        self.assertEqual(len(errors), 0, f"Bridge concurrency errors: {errors[:5]}")

    def test_concurrent_subscribers_during_active_polling(self):
        """
        Validates thread-safety of subscriber list when callbacks are added and removed
        dynamically while background engine loop is rapidly polling.
        """
        engine = TelemetryEngine(interval_ms=20)
        engine.start()
        errors = []
        received_counts = [0] * 20

        def subscriber_factory(idx: int):
            def cb(snap):
                received_counts[idx] += 1
            return cb

        def subscriber_manager(idx: int):
            cb = subscriber_factory(idx)
            for _ in range(10):
                try:
                    engine.subscribe(cb)
                    time.sleep(0.01)
                    engine.unsubscribe(cb)
                    time.sleep(0.005)
                except Exception as exc:
                    errors.append(f"SubManager {idx} failed: {exc}")

        threads = [threading.Thread(target=subscriber_manager, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        engine.stop()
        self.assertEqual(len(errors), 0, f"Subscriber registration concurrency errors: {errors}")

    def test_concurrent_engine_start_stop_cycles(self):
        """Stress-tests rapid start() and stop() calls across concurrent threads."""
        engine = TelemetryEngine(interval_ms=50)
        errors = []

        def toggler(tid: int):
            for _ in range(10):
                try:
                    engine.start()
                    time.sleep(0.005)
                    engine.stop(timeout=0.5)
                except Exception as exc:
                    errors.append(f"Toggler {tid} exception: {exc}")

        threads = [threading.Thread(target=toggler, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        engine.stop()
        self.assertEqual(len(errors), 0, f"Engine start/stop lifecycle concurrency errors: {errors}")


class TestCacheCorruptionTolerance(unittest.TestCase):
    """Stress-tests hardware profile cache resilience against corrupted or malformed files."""

    def setUp(self):
        self.test_cache_dir = tempfile.mkdtemp(prefix="hud_test_cache_")
        self.orig_cache_dir = HardwareProfileManager.CACHE_DIR
        self.orig_cache_file = HardwareProfileManager.CACHE_FILE
        HardwareProfileManager.CACHE_DIR = self.test_cache_dir
        HardwareProfileManager.CACHE_FILE = os.path.join(self.test_cache_dir, "hw_profile.json")

    def tearDown(self):
        HardwareProfileManager.CACHE_DIR = self.orig_cache_dir
        HardwareProfileManager.CACHE_FILE = self.orig_cache_file
        shutil.rmtree(self.test_cache_dir, ignore_errors=True)

    def test_cache_missing_file_returns_none(self):
        """Missing cache file returns None gracefully without error."""
        if os.path.exists(HardwareProfileManager.CACHE_FILE):
            os.remove(HardwareProfileManager.CACHE_FILE)
        res = HardwareProfileManager.load_cache()
        self.assertIsNone(res)

        engine = TelemetryEngine()
        snap = engine.get_snapshot()
        valid, errs = validate_telemetry_snapshot(snap)
        self.assertTrue(valid, f"Snapshot invalid on cache miss: {errs}")
        engine.stop()

    def test_cache_empty_file_returns_none(self):
        """Zero-byte empty cache file handled gracefully."""
        with open(HardwareProfileManager.CACHE_FILE, "w", encoding="utf-8") as f:
            f.write("")
        res = HardwareProfileManager.load_cache()
        self.assertIsNone(res)

        engine = TelemetryEngine()
        snap = engine.get_snapshot()
        valid, errs = validate_telemetry_snapshot(snap)
        self.assertTrue(valid, f"Snapshot invalid on empty cache: {errs}")
        engine.stop()

    def test_cache_malformed_json_syntax(self):
        """Broken/corrupted JSON syntax returns None without raising JSONDecodeError."""
        corruptions = [
            "{",
            "{\"version\": 1, \"cpu\": {",
            "{{bad json 12345---",
            "\x00\x01\x02\xFF\xFE binary garbage data",
            "None",
            "undefined",
        ]
        for corrupt in corruptions:
            with open(HardwareProfileManager.CACHE_FILE, "w", encoding="utf-8", errors="ignore") as f:
                f.write(corrupt)
            res = HardwareProfileManager.load_cache()
            self.assertIsNone(res, f"Expected None for corruption: {corrupt}")

            engine = TelemetryEngine()
            snap = engine.get_snapshot()
            valid, errs = validate_telemetry_snapshot(snap)
            self.assertTrue(valid, f"Snapshot invalid for corruption '{corrupt}': {errs}")
            engine.stop()

    def test_cache_non_dict_json_payloads(self):
        """Valid JSON that is not a dictionary (e.g. list, int, string, null) returns None."""
        payloads = [
            "[1, 2, 3]",
            "\"just a raw string\"",
            "12345",
            "true",
            "null",
        ]
        for payload in payloads:
            with open(HardwareProfileManager.CACHE_FILE, "w", encoding="utf-8") as f:
                f.write(payload)
            res = HardwareProfileManager.load_cache()
            self.assertIsNone(res, f"Expected None for non-dict JSON: {payload}")

    def test_cache_wrong_version_number(self):
        """Mismatching or negative cache version returns None."""
        invalid_versions = [0, 2, 999, -1, "v1", None, 1.5]
        for ver in invalid_versions:
            data = {"version": ver, "cpu": {"name": "Old CPU"}}
            with open(HardwareProfileManager.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
            res = HardwareProfileManager.load_cache()
            self.assertIsNone(res, f"Expected None for version: {ver}")

    def test_cache_missing_or_corrupt_subfields(self):
        """Cache has version 1 but fields are empty or have invalid types."""
        bad_structures = [
            {"version": 1},  # completely empty payload
            {"version": 1, "cpu": "string_instead_of_dict"},
            {"version": 1, "cpu": None, "system_info": 9999},
            {"version": 1, "cpu": {"name": 12345}},  # non-string name
            {"version": 1, "gpus": "not_a_list"},
            {"version": 1, "ram": None},
        ]
        for bad_struct in bad_structures:
            with open(HardwareProfileManager.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(bad_struct, f)
            res = HardwareProfileManager.load_cache()
            self.assertIsNotNone(res)

            engine = TelemetryEngine()
            snap = engine.get_snapshot()
            valid, errs = validate_telemetry_snapshot(snap)
            self.assertTrue(valid, f"Engine snapshot invalid on bad cache subfield: {errs}")
            engine.stop()

    def test_cache_save_and_load_roundtrip(self):
        """HardwareProfileManager atomic save and load roundtrip."""
        test_profile = {
            "cpu": {"name": "Test Custom Ryzen 9", "cores_physical": 8, "cores_logical": 16},
            "gpus": [{"id": 0, "name": "Test RTX 4090"}],
            "system_info": {"os": "Windows 11 Test", "cpu_arch": "x86_64"},
        }
        saved = HardwareProfileManager.save_cache(test_profile)
        self.assertTrue(saved)
        self.assertTrue(os.path.exists(HardwareProfileManager.CACHE_FILE))

        loaded = HardwareProfileManager.load_cache()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["version"], HardwareProfileManager.CACHE_VERSION)
        self.assertEqual(loaded["cpu"]["name"], "Test Custom Ryzen 9")
        self.assertEqual(loaded["system_info"]["os"], "Windows 11 Test")

    def test_cache_save_disk_error_graceful_handling(self):
        """Simulate disk write failure during save_cache."""
        with patch("builtins.open", side_effect=PermissionError("Read-only filesystem")):
            saved = HardwareProfileManager.save_cache({"cpu": {}})
            self.assertFalse(saved)


class TestHUDBridgeAPIMaximizeRestoreEdgeCases(unittest.TestCase):
    """Stress-tests window controls, state synchronization, and maximize/restore edge cases."""

    def setUp(self):
        self.mock_engine = MagicMock(spec=TelemetryEngine)
        self.mock_engine.get_snapshot.return_value = {
            "timestamp": 1000.0,
            "cpu": {"name": "Test CPU", "model": "Test CPU", "load_pct": 25.0, "utilization_pct": 25.0},
            "gpus": [{"id": 0, "name": "Test GPU", "type": "dedicated", "utilization_pct": 10.0}],
            "ram": {"used_gb": 16.0, "total_gb": 32.0, "used_mb": 16384.0, "total_mb": 32768.0},
            "storage": {"drives": []},
            "thermals": {"cpu_c": 50.0},
        }
        self.bridge = HUDBridgeAPI(engine=self.mock_engine, initial_mode="standard", initial_pinned=True)

    def test_toggle_maximize_without_attached_window(self):
        """Toggling maximize when self.window is None updates internal state cleanly."""
        self.assertIsNone(self.bridge.window)
        self.assertFalse(self.bridge.is_maximized())

        # 1. First toggle -> Maximized
        res1 = self.bridge.toggle_maximize()
        self.assertTrue(res1)
        self.assertTrue(self.bridge.is_maximized())
        self.assertTrue(self.bridge.is_maximized_state)

        # 2. Second toggle -> Restored
        res2 = self.bridge.toggle_maximize()
        self.assertFalse(res2)
        self.assertFalse(self.bridge.is_maximized())
        self.assertFalse(self.bridge.is_maximized_state)
        self.assertEqual(self.bridge.width, 1200)
        self.assertEqual(self.bridge.height, 800)

    def test_toggle_maximize_with_mock_window(self):
        """Toggling maximize calls window.maximize() and window.restore() appropriately."""
        mock_win = MagicMock()
        self.bridge.set_window(mock_win)

        # Maximize
        self.assertTrue(self.bridge.toggle_maximize())
        mock_win.maximize.assert_called_once()
        mock_win.restore.assert_not_called()

        # Restore
        self.assertFalse(self.bridge.toggle_maximize())
        mock_win.restore.assert_called_once()

    def test_toggle_maximize_with_failing_window_methods(self):
        """If window.maximize() or window.restore() raises an exception, bridge does not crash."""
        mock_win = MagicMock()
        mock_win.maximize.side_effect = RuntimeError("COM / WebView2 maximization exception")
        mock_win.restore.side_effect = RuntimeError("COM / WebView2 restoration exception")
        self.bridge.set_window(mock_win)

        # Maximize attempt
        res1 = self.bridge.toggle_maximize()
        self.assertTrue(res1)
        self.assertTrue(self.bridge.is_maximized())

        # Restore attempt
        res2 = self.bridge.toggle_maximize()
        self.assertFalse(res2)
        self.assertFalse(self.bridge.is_maximized())

    def test_rapid_maximize_restore_cycles(self):
        """50 consecutive toggle_maximize() invocations maintain strict boolean alternation."""
        mock_win = MagicMock()
        self.bridge.set_window(mock_win)

        for i in range(50):
            is_max = self.bridge.toggle_maximize()
            expected = (i % 2 == 0)
            self.assertEqual(is_max, expected, f"Cycle {i} mismatch: got {is_max}, expected {expected}")
            self.assertEqual(self.bridge.is_maximized(), expected)

        # Final state after 50 cycles (even number) is False (restored)
        self.assertFalse(self.bridge.is_maximized())
        self.assertEqual(self.bridge.width, 1200)
        self.assertEqual(self.bridge.height, 800)

    def test_screen_mode_switch_resets_maximized_state(self):
        """Switching screen mode while maximized automatically un-maximizes and restores geometry."""
        mock_win = MagicMock()
        self.bridge.set_window(mock_win)

        # Maximize in standard mode
        self.bridge.toggle_maximize()
        self.assertTrue(self.bridge.is_maximized())

        # Switch to ultrawide
        res_uw = self.bridge.set_screen_mode("ultrawide")
        self.assertFalse(self.bridge.is_maximized())
        self.assertEqual(res_uw["mode"], "ultrawide")
        self.assertEqual(res_uw["width"], 1920)
        self.assertEqual(res_uw["height"], 550)
        mock_win.restore.assert_called()
        mock_win.resize.assert_called_with(1920, 550)

        # Maximize again in ultrawide mode
        self.bridge.toggle_maximize()
        self.assertTrue(self.bridge.is_maximized())

        # Switch back to standard
        res_std = self.bridge.set_screen_mode("standard")
        self.assertFalse(self.bridge.is_maximized())
        self.assertEqual(res_std["mode"], "standard")
        self.assertEqual(res_std["width"], 1200)
        self.assertEqual(res_std["height"], 800)

    def test_restore_window_unsets_both_minimized_and_maximized(self):
        """restore_window() clears both is_minimized and is_maximized_state."""
        mock_win = MagicMock()
        self.bridge.set_window(mock_win)

        # Maximize then restore
        self.bridge.toggle_maximize()
        self.bridge.is_minimized = True
        self.assertTrue(self.bridge.is_maximized())
        self.assertTrue(self.bridge.is_minimized)

        self.bridge.restore_window()
        self.assertFalse(self.bridge.is_maximized())
        self.assertFalse(self.bridge.is_minimized)
        mock_win.restore.assert_called()

    def test_minimize_window_preserves_state_and_calls_window_minimize(self):
        """minimize_window() sets is_minimized = True and calls window.minimize()."""
        mock_win = MagicMock()
        self.bridge.set_window(mock_win)

        self.assertFalse(self.bridge.is_minimized)
        self.assertTrue(self.bridge.minimize_window())
        self.assertTrue(self.bridge.is_minimized)
        mock_win.minimize.assert_called_once()

    def test_switch_tab_validation(self):
        """switch_tab accepts valid tabs case-insensitively and rejects invalid tab names."""
        for tab in ["MONITOR", "TELEMETRY", "SYSTEM", "monitor", "telemetry", "system"]:
            res = self.bridge.switch_tab(tab)
            self.assertEqual(res, tab.upper())
            self.assertEqual(self.bridge.active_tab, tab.upper())

        for invalid in ["INVALID", "", "SETTINGS", "DEBUG", "None", None]:
            with self.assertRaises(ValueError):
                self.bridge.switch_tab(invalid)

    def test_get_status_contains_all_fields(self):
        """get_status() returns an exhaustive dictionary reflecting live bridge state."""
        status = self.bridge.get_status()
        expected_keys = [
            "mode", "width", "height", "is_pinned",
            "is_minimized", "is_maximized", "is_closed", "active_tab"
        ]
        for k in expected_keys:
            self.assertIn(k, status)
        self.assertEqual(status["mode"], "standard")
        self.assertEqual(status["width"], 1200)
        self.assertEqual(status["height"], 800)
        self.assertTrue(status["is_pinned"])
        self.assertFalse(status["is_minimized"])
        self.assertFalse(status["is_maximized"])
        self.assertFalse(status["is_closed"])
        self.assertEqual(status["active_tab"], "MONITOR")


if __name__ == "__main__":
    unittest.main()
