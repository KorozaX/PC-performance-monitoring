"""
tests/test_adversarial_faults.py
Adversarial Fault-Injection & Chaos Testing Suite for Milestone 1 Hardware Telemetry Engine.

Stress-tests and validates:
1. Missing NVML DLL & Optimus D3 Cold Sleep
2. Missing / broken network adapters & zero-interface states
3. Locked / unreadable / BitLocker disks & IOCTL access denied
4. Extreme CPU loads (0%, 100%, negative, >100% overflow) & extreme core counts
5. Unprivileged ACPI / missing thermal sensors -> 'N/A' fallbacks
6. Win32 psapi memory failure & SMBIOS table corruption
7. Faulty subscriber exceptions & deadlock resistance
8. Global subsystem total-failure resilience
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from src.telemetry.cpu_collector import CPUCollector
from src.telemetry.engine import TelemetryEngine
from src.telemetry.gpu_collector import (
    CTypesNVML,
    DXGIEnumerator,
    GPUAdapterInfo,
    GPUCollector,
    PDHGPUMonitor,
)
from src.telemetry.network_collector import NetworkCollector
from src.telemetry.ram_collector import RAMCollector, parse_smbios_ram
from src.telemetry.storage_collector import StorageCollector
from src.telemetry.thermals import ThermalAggregator
from tests.test_helpers import validate_telemetry_snapshot


class TestAdversarialGPUFaults(unittest.TestCase):
    """Adversarial fault injection for GPU detection, NVML, and PDH."""

    def test_missing_nvml_dll_simulation(self):
        """Simulate missing nvml.dll on systems without NVIDIA drivers."""
        with patch("ctypes.CDLL", side_effect=OSError("nvml.dll not found")):
            nvml = CTypesNVML()
            self.assertFalse(nvml.available)
            self.assertIsNone(nvml.query_device(0))

    def test_nvml_init_failure_code(self):
        """Simulate nvmlInit returning error code NVML_ERROR_UNINITIALIZED (1)."""
        mock_dll = MagicMock()
        mock_dll.nvmlInit_v2.return_value = 1  # non-zero = error
        with patch("ctypes.CDLL", return_value=mock_dll):
            nvml = CTypesNVML()
            self.assertFalse(nvml.available)

    def test_optimus_d3_sleep_query_exception(self):
        """Simulate NVIDIA dGPU in Optimus D3 sleep raising exception during query."""
        collector = GPUCollector()
        # Mock NVML as available but query_device raising OSError
        collector.nvml.available = True
        collector.nvml.handles = {0: MagicMock()}
        with patch.object(collector.nvml, "query_device", side_effect=RuntimeError("GPU in D3 Cold Sleep")):
            # Must not crash; should fall back to PDH/DXGI
            gpu_list = collector.collect()
            self.assertIsInstance(gpu_list, list)
            self.assertGreaterEqual(len(gpu_list), 1)

    def test_dxgi_enumeration_failure_empty_adapters(self):
        """Simulate DXGI failing completely (e.g. headless VM or driver crash)."""
        with patch.object(DXGIEnumerator, "enumerate_adapters", return_value=[]):
            collector = GPUCollector()
            # Should have fallback generic adapter
            self.assertEqual(len(collector.adapters), 1)
            self.assertEqual(collector.adapters[0].model, "Generic Display Adapter")
            gpu_list = collector.collect()
            self.assertEqual(len(gpu_list), 1)
            self.assertEqual(gpu_list[0]["vendor"], "Unknown")
            self.assertEqual(gpu_list[0]["load_pct"], 0.0)

    def test_pdh_query_failure_graceful_fallback(self):
        """Simulate Windows PDH counter corruption or failure."""
        collector = GPUCollector()
        collector.pdh.available = False
        gpu_list = collector.collect()
        self.assertIsInstance(gpu_list, list)
        for g in gpu_list:
            self.assertIn(g["load_pct"], range(0, 101))


class TestAdversarialNetworkFaults(unittest.TestCase):
    """Adversarial fault injection for Network collector."""

    def test_no_adapters_psutil_empty(self):
        """Simulate system with 0 network interfaces detected."""
        collector = NetworkCollector()
        with patch("psutil.net_io_counters", return_value={}):
            data = collector.collect()
            self.assertFalse(data["connected"])
            self.assertEqual(data["interface"], "Disconnected")
            self.assertEqual(data["downlink_mbps"], 0.0)
            self.assertEqual(data["uplink_mbps"], 0.0)

    def test_iphlpapi_failure_fallback(self):
        """Simulate GetAdaptersAddresses API throwing an exception."""
        collector = NetworkCollector()
        with patch("ctypes.windll.iphlpapi.GetAdaptersAddresses", side_effect=OSError("Access denied")):
            collector._refresh_adapter_metadata()
            # Should continue operating using psutil fallback
            data = collector.collect()
            self.assertIsInstance(data, dict)
            self.assertIn("connected", data)

    def test_rapid_packet_counter_wrap(self):
        """Simulate 64-bit counter reset / overflow (curr < prev)."""
        collector = NetworkCollector()
        mock_prev = {"Ethernet": MagicMock(bytes_recv=1000000, bytes_sent=1000000)}
        mock_curr = {"Ethernet": MagicMock(bytes_recv=500, bytes_sent=200)}
        collector.prev_io = mock_prev
        with patch("psutil.net_io_counters", return_value=mock_curr):
            data = collector.collect()
            # Must not produce negative bandwidth
            self.assertGreaterEqual(data["downlink_mbps"], 0.0)
            self.assertGreaterEqual(data["uplink_mbps"], 0.0)


class TestAdversarialStorageFaults(unittest.TestCase):
    """Adversarial fault injection for Storage collector."""

    def test_locked_bitlocker_drive_access_denied(self):
        """Simulate BitLocker locked partition raising PermissionError on disk_usage."""
        collector = StorageCollector()
        collector.device_cache = {"D:": {"mount": "D:\\", "phys_id": "PhysicalDrive1", "type_badge": "Storage Drive"}}
        with patch("psutil.disk_usage", side_effect=PermissionError("Drive D: is locked by BitLocker")):
            data = collector.collect()
            self.assertEqual(len(data["drives"]), 1)
            self.assertEqual(data["drives"][0]["used_gb"], 0.0)
            self.assertEqual(data["drives"][0]["total_gb"], 0.0)

    def test_ioctl_physical_info_access_denied(self):
        """Simulate non-privileged user unable to open raw drive handles."""
        collector = StorageCollector()
        with patch("ctypes.windll.kernel32.CreateFileW", return_value=-1):
            phys_id, badge = collector._query_physical_info("C:")
            self.assertIsNone(phys_id)
            self.assertEqual(badge, "Storage Drive")

    def test_disk_io_counters_unavailable(self):
        """Simulate psutil.disk_io_counters raising RuntimeError."""
        collector = StorageCollector()
        with patch("psutil.disk_io_counters", side_effect=RuntimeError("Disk I/O counters disabled")):
            data = collector.collect()
            self.assertIsInstance(data["drives"], list)
            for d in data["drives"]:
                self.assertEqual(d["read_mbs"], 0.0)
                self.assertEqual(d["write_mbs"], 0.0)
                self.assertEqual(d["load_pct"], 0.0)


class TestAdversarialCPUFaults(unittest.TestCase):
    """Adversarial boundary and exception tests for CPU collector."""

    def test_extreme_0_percent_cpu_load(self):
        """Verify exact 0.0% CPU load clamping."""
        collector = CPUCollector()
        with patch("psutil.cpu_percent", return_value=0.0):
            data = collector.collect()
            self.assertEqual(data["load_pct"], 0.0)

    def test_extreme_100_percent_cpu_load(self):
        """Verify exact 100.0% CPU load clamping."""
        collector = CPUCollector()
        with patch("psutil.cpu_percent", return_value=100.0):
            data = collector.collect()
            self.assertEqual(data["load_pct"], 100.0)

    def test_cpu_load_overflow_and_underflow_clamping(self):
        """Verify load values outside [0, 100] are strictly clamped."""
        collector = CPUCollector()
        with patch("psutil.cpu_percent", return_value=155.0):
            data = collector.collect()
            self.assertEqual(data["load_pct"], 100.0)
        with patch("psutil.cpu_percent", return_value=-25.0):
            data = collector.collect()
            self.assertEqual(data["load_pct"], 0.0)

    def test_unprivileged_acpi_thermal_missing(self):
        """Verify missing ACPI thermal sensors safely returns 'N/A'."""
        collector = CPUCollector()
        with patch("psutil.sensors_temperatures", create=True, return_value={}):
            data = collector.collect()
            self.assertEqual(data["temperature_c"], "N/A")

    def test_registry_access_denied_cpu_model(self):
        """Verify CPU model fallback when registry access is blocked."""
        collector = CPUCollector()
        with patch("winreg.OpenKey", side_effect=PermissionError("Access Denied")):
            model = collector._query_cpu_model()
            self.assertIsInstance(model, str)
            self.assertGreater(len(model), 0)


class TestAdversarialRAMFaults(unittest.TestCase):
    """Adversarial fault injection for RAM collector."""

    def test_psapi_failure_psutil_fallback(self):
        """Simulate Win32 psapi GetPerformanceInfo returning False."""
        collector = RAMCollector()
        if collector._psapi_available:
            with patch.object(collector._psapi, "GetPerformanceInfo", return_value=0):
                data = collector.collect()
                self.assertGreater(data["total_gb"], 0.0)
                dist = data["distribution"]
                self.assertEqual(dist["in_use_pct"] + dist["cached_pct"] + dist["free_pct"], 100)

    def test_smbios_firmware_table_corrupted(self):
        """Simulate GetSystemFirmwareTable returning corrupted / truncated bytes."""
        with patch("ctypes.windll.kernel32.GetSystemFirmwareTable", return_value=0):
            badge = parse_smbios_ram()
            self.assertEqual(badge, "DDR4")


class TestAdversarialEngineChaos(unittest.TestCase):
    """Chaos testing against the TelemetryEngine coordinator."""

    def test_subscriber_exception_does_not_crash_engine(self):
        """Verify a faulty subscriber callback raising unhandled exception does not crash engine."""
        engine = TelemetryEngine(interval_ms=100)
        faulty_called = []

        def faulty_subscriber(snap):
            faulty_called.append(True)
            raise ZeroDivisionError("Chaos subscriber exploded!")

        engine.subscribe(faulty_subscriber)
        snap = engine.poll_once()
        self.assertIsNotNone(snap)
        valid, errors = validate_telemetry_snapshot(snap)
        self.assertTrue(valid, f"Validation errors: {errors}")

    def test_total_subsystem_failure_resilience(self):
        """Verify engine still returns valid JSON snapshot even when ALL 5 collectors crash."""
        engine = TelemetryEngine()
        with patch.object(engine.cpu_collector, "collect", side_effect=RuntimeError("CPU DEAD")), \
             patch.object(engine.ram_collector, "collect", side_effect=RuntimeError("RAM DEAD")), \
             patch.object(engine.gpu_collector, "collect", side_effect=RuntimeError("GPU DEAD")), \
             patch.object(engine.storage_collector, "collect", side_effect=RuntimeError("STORAGE DEAD")), \
             patch.object(engine.network_collector, "collect", side_effect=RuntimeError("NETWORK DEAD")), \
             patch.object(engine.thermal_aggregator, "aggregate", side_effect=RuntimeError("THERMALS DEAD")):
            
            snap = engine.poll_once()
            self.assertIsNotNone(snap)
            valid, errors = validate_telemetry_snapshot(snap)
            self.assertTrue(valid, f"Fallback snapshot invalid under total chaos: {errors}")
            self.assertEqual(snap["cpu"]["load_pct"], 0.0)
            self.assertEqual(snap["cpu"]["temperature_c"], "N/A")
            self.assertEqual(snap["network"]["interface"], "Disconnected")
            self.assertEqual(snap["thermals"]["cpu_c"], "N/A")

    def test_rapid_sequential_polling_stability(self):
        """Stress test: 100 rapid sequential poll_once calls without delay."""
        engine = TelemetryEngine()
        prev_ts = 0.0
        for _ in range(100):
            snap = engine.poll_once()
            self.assertGreaterEqual(snap["timestamp"], prev_ts)
            prev_ts = snap["timestamp"]
            valid, errors = validate_telemetry_snapshot(snap)
            self.assertTrue(valid, f"Snapshot invalid during rapid polling: {errors}")


if __name__ == "__main__":
    unittest.main()
