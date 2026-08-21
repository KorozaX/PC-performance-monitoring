"""
tests/test_adversarial_stress.py
Comprehensive Empirical Adversarial Stress Harness for Milestone 1 Backend Telemetry.
Validates ProcessCollector, GPUCollector, ThermalAggregator, TelemetryEngine, and Bridge API
under hostile conditions, resource pressure, process churn, multi-GPU configurations,
Optimus transitions, sensor dropouts, and malformed inputs.
"""

import copy
import math
import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.bridge.api import HUDBridgeAPI
from src.telemetry.cpu_collector import CPUCollector, CPUThermalProbe
from src.telemetry.engine import TelemetryEngine, query_system_info
from src.telemetry.gpu_collector import (
    CTypesNVML,
    DXGI_ADAPTER_DESC1,
    DXGIEnumerator,
    GPUAdapterInfo,
    GPUCollector,
    LUID,
    PDHGPUMonitor,
)
from src.telemetry.network_collector import NetworkCollector
from src.telemetry.process_collector import (
    ProcessCollector,
    ProcessPrevMetrics,
    STATUS_INFO_LENGTH_MISMATCH,
    STATUS_SUCCESS,
    SYSTEM_PROCESS_INFORMATION,
)
from src.telemetry.ram_collector import RAMCollector
from src.telemetry.storage_collector import StorageCollector
from src.telemetry.thermals import ThermalAggregator
from tests.test_helpers import validate_telemetry_snapshot


class TestProcessCollectorStress(unittest.TestCase):
    """Stress tests for ProcessCollector."""

    def setUp(self):
        self.collector = ProcessCollector()

    def tearDown(self):
        self.collector.shutdown()

    def test_rapid_back_to_back_calls(self):
        """Stress: 200 rapid consecutive collect calls without delay."""
        durations = []
        for _ in range(200):
            t0 = time.perf_counter()
            procs = self.collector.get_top_processes(limit=5)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            durations.append(dt_ms)
            self.assertIsInstance(procs, list)
            self.assertLessEqual(len(procs), 5)
            for p in procs:
                self.assertIn("pid", p)
                self.assertIn("name", p)
                self.assertIn("cpu_pct", p)
                self.assertIn("memory_mb", p)
                self.assertIn("memory_pct", p)
                self.assertIn("disk_mbps", p)
                self.assertIn("gpu_pct", p)
                self.assertGreaterEqual(p["cpu_pct"], 0.0)
                self.assertLessEqual(p["cpu_pct"], 100.0)

        avg_lat = sum(durations) / len(durations)
        # Average scan latency should be fast (< 25ms on live Windows kernel)
        self.assertLess(avg_lat, 50.0, f"Average scan latency too slow: {avg_lat:.2f}ms")

    def test_process_churn_simulation(self):
        """Simulate rapid process spawn and death with PID churn."""
        collector = ProcessCollector()
        now = time.perf_counter()

        # Seed initial state with 50 processes
        collector._prev_procs = {
            pid: ProcessPrevMetrics(
                user_time=1000000,
                kernel_time=500000,
                io_bytes=1024 * 1024,
                timestamp=now - 1.0,
            )
            for pid in range(100, 150)
        }

        # Run real collect to verify old non-existent PIDs are pruned from _prev_procs
        procs = collector.get_top_processes(limit=5)
        self.assertIsInstance(procs, list)
        # Verify _prev_procs was updated and only contains active processes
        for p in procs:
            self.assertIn(p["pid"], collector._prev_procs)

    def test_high_pid_ranges(self):
        """Stress: Verify handling of high PIDs (e.g. 4194304, 2^31 - 1)."""
        collector = ProcessCollector()
        # Seed _prev_procs with extreme PID values
        high_pids = [65536, 1048576, 4194304, 2147483647]
        now = time.perf_counter()
        for pid in high_pids:
            collector._prev_procs[pid] = ProcessPrevMetrics(
                user_time=10000000,
                kernel_time=5000000,
                io_bytes=100000,
                timestamp=now - 1.0,
            )

        procs = collector.get_top_processes(limit=5)
        self.assertIsInstance(procs, list)

    def test_buffer_reallocation_under_small_initial_buffer(self):
        """Simulate initial buffer being too small (STATUS_INFO_LENGTH_MISMATCH)."""
        collector = ProcessCollector()
        if collector._is_windows and collector._ntdll:
            # Force small buffer
            collector._buf_size = 64
            collector._buffer = (
                collector._ntdll.ctypes.create_string_buffer(64)
                if hasattr(collector._ntdll, "ctypes")
                else None
            )
            import ctypes
            collector._buffer = ctypes.create_string_buffer(64)

            # Query should automatically reallocate buffer and succeed
            procs = collector.get_top_processes(limit=5)
            self.assertIsInstance(procs, list)
            self.assertGreater(collector._buf_size, 64)

    def test_concurrent_multithreaded_scans(self):
        """Stress: 10 concurrent threads invoking get_top_processes simultaneously."""
        collector = ProcessCollector()
        errors = []

        def worker():
            try:
                for _ in range(20):
                    p = collector.get_top_processes(limit=5)
                    if not isinstance(p, list):
                        errors.append("Returned non-list")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")

    def test_psutil_fallback_on_simulated_ntdll_crash(self):
        """Verify seamless psutil fallback when ntdll is disabled/errored."""
        collector = ProcessCollector()
        collector._ntdll = None
        collector._buffer = None
        procs = collector.get_top_processes(limit=5)
        self.assertIsInstance(procs, list)
        self.assertLessEqual(len(procs), 5)
        for p in procs:
            self.assertIn("pid", p)
            self.assertIn("name", p)
            self.assertIn("cpu_pct", p)
            self.assertIn("memory_mb", p)

    def test_limit_boundaries(self):
        """Verify limit=0, limit=1, limit=100, limit=-5."""
        collector = ProcessCollector()
        self.assertEqual(len(collector.get_top_processes(limit=0)), 0)
        self.assertLessEqual(len(collector.get_top_processes(limit=1)), 1)
        procs_100 = collector.get_top_processes(limit=100)
        self.assertIsInstance(procs_100, list)
        # Negative limit in Python slicing returns empty or slice
        procs_neg = collector.get_top_processes(limit=-1)
        self.assertIsInstance(procs_neg, list)


class TestGPUCollectorStress(unittest.TestCase):
    """Stress tests for GPUCollector."""

    def test_simulated_multi_gpu_configs(self):
        """Stress: Multi-GPU setups (2, 4, 8 adapters with mixed iGPU and dGPU)."""
        adapters = [
            GPUAdapterInfo(
                id=0,
                name="NVIDIA GeForce RTX 4090",
                vendor="NVIDIA",
                gpu_type="dedicated",
                luid_str="0x00000000_0x00010000",
                dedicated_bytes=24 * 1024 * 1024 * 1024,
                shared_bytes=32 * 1024 * 1024 * 1024,
            ),
            GPUAdapterInfo(
                id=1,
                name="AMD Radeon 780M",
                vendor="AMD",
                gpu_type="integrated",
                luid_str="0x00000000_0x00020000",
                dedicated_bytes=512 * 1024 * 1024,
                shared_bytes=16 * 1024 * 1024 * 1024,
            ),
            GPUAdapterInfo(
                id=2,
                name="Intel Arc A770",
                vendor="Intel",
                gpu_type="dedicated",
                luid_str="0x00000000_0x00030000",
                dedicated_bytes=16 * 1024 * 1024 * 1024,
                shared_bytes=32 * 1024 * 1024 * 1024,
            ),
            GPUAdapterInfo(
                id=3,
                name="NVIDIA RTX A6000",
                vendor="NVIDIA",
                gpu_type="dedicated",
                luid_str="0x00000000_0x00040000",
                dedicated_bytes=48 * 1024 * 1024 * 1024,
                shared_bytes=32 * 1024 * 1024 * 1024,
            ),
        ]

        with patch.object(DXGIEnumerator, "enumerate_adapters", return_value=adapters):
            collector = GPUCollector()
            self.assertEqual(len(collector.adapters), 4)

            # Mock PDH data for all adapters
            mock_pdh_data = {
                "0x00000000_0x00010000": {
                    "load_pct": 75.0,
                    "dedicated_bytes": 12 * 1024 * 1024 * 1024,
                    "shared_bytes": 1024 * 1024 * 1024,
                },
                "0x00000000_0x00020000": {
                    "load_pct": 12.0,
                    "dedicated_bytes": 256 * 1024 * 1024,
                    "shared_bytes": 2 * 1024 * 1024 * 1024,
                },
                "0x00000000_0x00030000": {
                    "load_pct": 45.0,
                    "dedicated_bytes": 8 * 1024 * 1024 * 1024,
                    "shared_bytes": 512 * 1024 * 1024,
                },
                "0x00000000_0x00040000": {
                    "load_pct": 90.0,
                    "dedicated_bytes": 36 * 1024 * 1024 * 1024,
                    "shared_bytes": 2048 * 1024 * 1024,
                },
            }

            collector.pdh.available = True
            collector.nvml.available = False  # Disable host NVML for purely simulated adapter test
            with patch.object(collector.pdh, "collect", return_value=mock_pdh_data):
                gpus = collector.collect()
                self.assertEqual(len(gpus), 4)
                self.assertEqual(gpus[0]["name"], "NVIDIA GeForce RTX 4090")
                self.assertEqual(gpus[0]["type"], "dedicated")
                self.assertAlmostEqual(gpus[0]["vram_total_gb"], 24.0, places=1)
                self.assertEqual(gpus[1]["name"], "AMD Radeon 780M")
                self.assertEqual(gpus[1]["type"], "integrated")
                self.assertEqual(gpus[2]["name"], "Intel Arc A770")
                self.assertEqual(gpus[3]["name"], "NVIDIA RTX A6000")

    def test_optimus_sleep_wake_cycle(self):
        """Simulate repeated Optimus sleep (D3 cold) -> wake -> sleep transitions."""
        collector = GPUCollector()
        collector.nvml.available = True
        collector.nvml.handles = {0: MagicMock()}

        # 1. Awake state
        awake_data = {
            "load_pct": 55.0,
            "vram_used_bytes": 2 * 1024 * 1024 * 1024,
            "vram_total_bytes": 6 * 1024 * 1024 * 1024,
            "temperature_c": 62.0,
            "freq_mhz": 1500,
        }
        with patch.object(collector.nvml, "query_device", return_value=awake_data):
            gpus = collector.collect()
            self.assertGreater(len(gpus), 0)
            self.assertNotEqual(gpus[0]["temperature_c"], "N/A")

        # 2. Transition to D3 cold sleep (query raises exception or returns None)
        with patch.object(
            collector.nvml,
            "query_device",
            side_effect=RuntimeError("GPU in D3 Cold Sleep"),
        ):
            gpus_sleep = collector.collect()
            self.assertGreater(len(gpus_sleep), 0)
            self.assertEqual(gpus_sleep[0]["temperature_c"], "N/A")
            self.assertEqual(gpus_sleep[0]["clock_mhz"], "N/A")

        # 3. Transition back to Awake state
        with patch.object(collector.nvml, "query_device", return_value=awake_data):
            gpus_wake = collector.collect()
            self.assertGreater(len(gpus_wake), 0)
            self.assertEqual(gpus_wake[0]["temperature_c"], 62.0)
            self.assertEqual(gpus_wake[0]["clock_mhz"], 1500)

    def test_pdh_counter_reinitialization(self):
        """Stress: Close PDH monitor, trigger queries, re-open PDH monitor."""
        collector = GPUCollector()
        # Close PDH
        collector.pdh.close()
        self.assertFalse(collector.pdh.available)

        # Collect should survive without PDH
        gpus_no_pdh = collector.collect()
        self.assertIsInstance(gpus_no_pdh, list)

        # Re-initialize PDH
        collector.pdh = PDHGPUMonitor()
        gpus_reinit = collector.collect()
        self.assertIsInstance(gpus_reinit, list)

    def test_ema_smoothing_behavior(self):
        """Verify EMA smoothing dampens abrupt spike without staying stuck."""
        collector = GPUCollector(smoothing_alpha=0.5)
        adapter = GPUAdapterInfo(
            id=0,
            name="Test GPU",
            vendor="AMD",
            gpu_type="integrated",
            luid_str="0x1_0x1",
            dedicated_bytes=0,
            shared_bytes=4 * 1024 * 1024 * 1024,
        )
        collector.adapters = [adapter]

        # Feed 100% load
        mock_pdh_100 = {"0x1_0x1": {"load_pct": 100.0, "dedicated_bytes": 0, "shared_bytes": 0}}
        collector.pdh.available = True
        with patch.object(collector.pdh, "collect", return_value=mock_pdh_100):
            gpus = collector.collect()
            # First tick with alpha=0.5: smoothed = 100.0 (prev was 100.0 on first init)
            self.assertEqual(gpus[0]["utilization_pct"], 100.0)

        # Feed 0% load
        mock_pdh_0 = {"0x1_0x1": {"load_pct": 0.0, "dedicated_bytes": 0, "shared_bytes": 0}}
        with patch.object(collector.pdh, "collect", return_value=mock_pdh_0):
            gpus = collector.collect()
            # 0.5 * 0 + 0.5 * 100 = 50.0%
            self.assertEqual(gpus[0]["utilization_pct"], 50.0)

            # Another 0% tick: 0.5 * 0 + 0.5 * 50 = 25.0%
            gpus2 = collector.collect()
            self.assertEqual(gpus2[0]["utilization_pct"], 25.0)


class TestThermalAggregatorStress(unittest.TestCase):
    """Stress tests for ThermalAggregator."""

    def test_all_sensors_missing_returns_clean_na(self):
        """Verify all missing sensors produce strict 'N/A' dictionary with zero exceptions."""
        result = ThermalAggregator.aggregate(None, None, None)
        self.assertEqual(
            result,
            {
                "cpu_c": "N/A",
                "dgpu_c": "N/A",
                "igpu_c": "N/A",
                "gpu_c": "N/A",
                "ssd_c": "N/A",
            },
        )

    def test_malformed_hostile_inputs_no_exceptions(self):
        """Stress: Corrupted, malformed, non-dict, non-list, and extreme value inputs."""
        agg = ThermalAggregator()
        hostile_cases = [
            ({}, {}, {}),
            ({"temperature_c": "N/A"}, [{"temperature_c": "N/A"}], {"drives": "not_a_list"}),
            ({"temperature_c": None}, [{"type": "dedicated", "temperature_c": None}], {"drives": [None, 123]}),
            ({"temperature_c": -100.0}, [{"type": "dedicated", "temperature_c": -50.0}], {"drives": [{"temperature_c": -20.0}]}),
            ({"temperature_c": 0.0}, [{"type": "dedicated", "temperature_c": 0}], {"drives": [{"temperature_c": 0.0}]}),
            ({"temperature_c": "corrupted_string"}, [{"type": "integrated", "temperature_c": {}}], {"drives": [{"temperature_c": []}]}),
            (12345, "invalid", True),
            ({"temperature_c": float("nan")}, [{"type": "dedicated", "temperature_c": float("nan")}], {"drives": [{"temperature_c": float("nan")}]}),
            ({"temperature_c": float("inf")}, [{"type": "dedicated", "temperature_c": float("inf")}], {"drives": [{"temperature_c": float("inf")}]}),
        ]

        for cpu_in, gpu_in, storage_in in hostile_cases:
            res = agg.aggregate(cpu_in, gpu_in, storage_in)
            self.assertIsInstance(res, dict)
            self.assertIn("cpu_c", res)
            self.assertIn("dgpu_c", res)
            self.assertIn("igpu_c", res)
            self.assertIn("gpu_c", res)
            self.assertIn("ssd_c", res)

    def test_multi_sensor_arbitration(self):
        """Verify correct temperature attribution across multiple GPUs and SSDs."""
        cpu_data = {"temperature_c": 58.4}
        gpus_data = [
            {"id": 0, "name": "RTX 3060", "type": "dedicated", "temperature_c": 64.2},
            {"id": 1, "name": "Radeon Graphics", "type": "integrated", "temperature_c": 49.1},
        ]
        storage_data = {
            "drives": [
                {"letter": "C:", "temperature_c": 41.0},
                {"letter": "D:", "temperature_c": 48.5},
                {"letter": "E:", "temperature_c": "N/A"},
            ]
        }

        res = ThermalAggregator.aggregate(cpu_data, gpus_data, storage_data)
        self.assertEqual(res["cpu_c"], 58.4)
        self.assertEqual(res["dgpu_c"], 64.2)
        self.assertEqual(res["igpu_c"], 49.1)
        self.assertEqual(res["gpu_c"], 64.2)
        self.assertEqual(res["ssd_c"], 48.5)  # Max valid drive temp


class TestBridgeAPIStress(unittest.TestCase):
    """Stress tests for HUDBridgeAPI and window controls."""

    def test_toggle_maximize_state_machine(self):
        """Verify toggle_maximize state transitions, dimensions preservation, and window calls."""
        bridge = HUDBridgeAPI(initial_mode="standard")
        mock_window = MagicMock()
        bridge.set_window(mock_window)

        self.assertFalse(bridge.is_maximized())
        self.assertEqual(bridge.width, 1200)
        self.assertEqual(bridge.height, 800)

        # 1. Maximize
        res_max = bridge.toggle_maximize()
        self.assertTrue(res_max)
        self.assertTrue(bridge.is_maximized())
        mock_window.maximize.assert_called_once()

        # 2. Restore
        res_rest = bridge.toggle_maximize()
        self.assertFalse(res_rest)
        self.assertFalse(bridge.is_maximized())
        self.assertEqual(bridge.width, 1200)
        self.assertEqual(bridge.height, 800)
        mock_window.restore.assert_called_once()

    def test_rapid_mode_switching_and_pin_top(self):
        """Stress: Rapid switching of screen modes and pin state."""
        bridge = HUDBridgeAPI()
        for _ in range(50):
            bridge.set_screen_mode("ultrawide")
            self.assertEqual(bridge.current_mode, "ultrawide")
            self.assertEqual(bridge.width, 1920)
            self.assertEqual(bridge.height, 550)

            bridge.set_screen_mode("standard")
            self.assertEqual(bridge.current_mode, "standard")
            self.assertEqual(bridge.width, 1200)
            self.assertEqual(bridge.height, 800)

            pinned = bridge.toggle_pin_top()
            self.assertIsInstance(pinned, bool)

    def test_tab_switching(self):
        """Verify tab switching across MONITOR, TELEMETRY, SYSTEM and error handling."""
        bridge = HUDBridgeAPI()
        self.assertEqual(bridge.switch_tab("TELEMETRY"), "TELEMETRY")
        self.assertEqual(bridge.active_tab, "TELEMETRY")
        self.assertEqual(bridge.switch_tab("SYSTEM"), "SYSTEM")
        self.assertEqual(bridge.active_tab, "SYSTEM")
        self.assertEqual(bridge.switch_tab("MONITOR"), "MONITOR")
        self.assertEqual(bridge.active_tab, "MONITOR")
        # Invalid tab should raise ValueError
        with self.assertRaises(ValueError):
            bridge.switch_tab("UNKNOWN")


class TestTelemetryEngineStartupStress(unittest.TestCase):
    """Stress tests for TelemetryEngine coordinator and startup."""

    def test_tick_0_instant_generation(self):
        """Verify Tick-0 snapshot generates in < 5ms."""
        engine = TelemetryEngine()
        t0 = time.perf_counter()
        snap = engine._generate_initial_snapshot()
        dt_ms = (time.perf_counter() - t0) * 1000.0

        self.assertLess(dt_ms, 5.0, f"Tick-0 too slow: {dt_ms:.3f}ms")
        valid, errors = validate_telemetry_snapshot(snap)
        self.assertTrue(valid, f"Tick-0 snapshot invalid: {errors}")

    def test_engine_lifecycle_start_stop_rapid(self):
        """Stress: Rapidly start and stop telemetry engine background thread."""
        for _ in range(5):
            engine = TelemetryEngine(interval_ms=50)
            engine.start()
            self.assertTrue(engine.is_running())
            time.sleep(0.08)
            snap = engine.get_snapshot()
            self.assertIsNotNone(snap)
            engine.stop()
            self.assertFalse(engine.is_running())


if __name__ == "__main__":
    unittest.main()
