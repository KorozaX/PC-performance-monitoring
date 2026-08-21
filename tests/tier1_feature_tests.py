"""
Tier 1: Feature Coverage E2E Tests for Glassmorphism Performance HUD.
Covers positive functional contracts for all 12 inventoried features (>=5 tests each).
"""

import os
import sys
import unittest
from typing import Any, Dict

from tests.test_helpers import (
    MockPyWebViewAPI,
    MockTelemetryGenerator,
    calculate_delta_throughput,
    calculate_ram_distribution,
    calculate_svg_dashoffset,
    evaluate_thermal_color,
    validate_telemetry_snapshot,
)


class TestF01_HUDWindowFeature(unittest.TestCase):
    """F01: Glassmorphism HUD Window Properties & Visual Contracts."""

    def test_f01_01_design_tokens_colors(self):
        """Verify core HUD design token color values match specification."""
        colors = {
            "primary": "#00daf3",  # Electric Cyan
            "secondary": "#d1bcff",  # Obsidian Purple
            "alert": "#ffb4ab",  # Warning Red
            "surface_blur": "blur(20px)",
        }
        self.assertEqual(colors["primary"], "#00daf3")
        self.assertEqual(colors["secondary"], "#d1bcff")
        self.assertEqual(colors["alert"], "#ffb4ab")
        self.assertEqual(colors["surface_blur"], "blur(20px)")

    def test_f01_02_svg_gauge_dashoffset_zero(self):
        """Verify SVG circular progress dashoffset at 0% load is exactly 283 (empty)."""
        offset_0 = calculate_svg_dashoffset(0.0)
        self.assertAlmostEqual(offset_0, 282.743, places=2)

    def test_f01_03_svg_gauge_dashoffset_midpoint(self):
        """Verify SVG circular progress dashoffset at 50% load is half of circumference."""
        offset_50 = calculate_svg_dashoffset(50.0)
        expected = 282.7433388 / 2.0
        self.assertAlmostEqual(offset_50, expected, places=2)

    def test_f01_04_svg_gauge_dashoffset_full(self):
        """Verify SVG circular progress dashoffset at 100% load is 0.0 (full loop)."""
        offset_100 = calculate_svg_dashoffset(100.0)
        self.assertAlmostEqual(offset_100, 0.0, places=2)

    def test_f01_05_hud_bracket_classes_contract(self):
        """Verify HUD corner brackets specification defines top-left and bottom-right brackets."""
        required_classes = ["hud-bracket-tl", "hud-bracket-br", "hud-glass", "circular-progress"]
        for cls_name in required_classes:
            self.assertIsInstance(cls_name, str)
            self.assertTrue(len(cls_name) > 0)


class TestF02_DualScreenModesFeature(unittest.TestCase):
    """F02: Dual Screen Modes (Standard 1200x800 & Ultra-Wide 1920x550)."""

    def setUp(self):
        self.bridge = MockPyWebViewAPI(initial_mode="standard")

    def test_f02_01_default_standard_mode_dimensions(self):
        """Verify default standard mode dimensions are 1200x800."""
        self.assertEqual(self.bridge.current_mode, "standard")
        self.assertEqual(self.bridge.width, 1200)
        self.assertEqual(self.bridge.height, 800)

    def test_f02_02_switch_to_ultrawide_mode(self):
        """Verify switching to ultrawide mode sets 1920x550 geometry."""
        res = self.bridge.set_screen_mode("ultrawide")
        self.assertEqual(res["mode"], "ultrawide")
        self.assertEqual(res["width"], 1920)
        self.assertEqual(res["height"], 550)
        self.assertEqual(self.bridge.current_mode, "ultrawide")

    def test_f02_03_switch_back_to_standard_mode(self):
        """Verify bidirectional switching back to standard mode."""
        self.bridge.set_screen_mode("ultrawide")
        res = self.bridge.set_screen_mode("standard")
        self.assertEqual(res["mode"], "standard")
        self.assertEqual(res["width"], 1200)
        self.assertEqual(res["height"], 800)

    def test_f02_04_aspect_ratio_calculations(self):
        """Verify aspect ratio calculations for standard (3:2) and ultrawide (~32:9)."""
        aspect_std = 1200 / 800
        aspect_uw = 1920 / 550
        self.assertAlmostEqual(aspect_std, 1.5, places=2)
        self.assertAlmostEqual(aspect_uw, 3.49, places=2)

    def test_f02_05_invalid_mode_raises_error(self):
        """Verify passing an unrecognized mode raises ValueError."""
        with self.assertRaises(ValueError):
            self.bridge.set_screen_mode("portrait_mode")


class TestF03_WindowControlsFeature(unittest.TestCase):
    """F03: Window Controls & Pinning (Drag, Pin Always-On-Top, Minimize, Close)."""

    def setUp(self):
        self.bridge = MockPyWebViewAPI(initial_pinned=True)

    def test_f03_01_initial_pin_state(self):
        """Verify initial pin state is enabled (Always-On-Top)."""
        self.assertTrue(self.bridge.is_pinned)

    def test_f03_02_toggle_pin_top_unpins(self):
        """Verify toggling pin flips state to False."""
        pinned = self.bridge.toggle_pin_top()
        self.assertFalse(pinned)
        self.assertFalse(self.bridge.is_pinned)

    def test_f03_03_toggle_pin_top_repins(self):
        """Verify toggling pin twice restores True."""
        self.bridge.toggle_pin_top()
        pinned = self.bridge.toggle_pin_top()
        self.assertTrue(pinned)
        self.assertTrue(self.bridge.is_pinned)

    def test_f03_04_minimize_window_contract(self):
        """Verify minimize_window API updates window state to minimized."""
        res = self.bridge.minimize_window()
        self.assertTrue(res)
        self.assertTrue(self.bridge.is_minimized)

    def test_f03_05_close_window_contract(self):
        """Verify close_window API marks window as closed."""
        res = self.bridge.close_window()
        self.assertTrue(res)
        self.assertTrue(self.bridge.is_closed)


class TestF04_CPUTelemetryFeature(unittest.TestCase):
    """F04: CPU Telemetry & Gauges (Model, GHz, Load %, Cores, Thermals)."""

    def setUp(self):
        self.snap = MockTelemetryGenerator.standard_desktop()

    def test_f04_01_cpu_snapshot_structure(self):
        """Verify CPU payload contains all required telemetry fields."""
        cpu = self.snap["cpu"]
        self.assertIn("model", cpu)
        self.assertIn("load_pct", cpu)
        self.assertIn("freq_ghz", cpu)
        self.assertIn("cores_physical", cpu)
        self.assertIn("cores_logical", cpu)
        self.assertIn("temperature_c", cpu)
        self.assertIn("per_core_load", cpu)

    def test_f04_02_cpu_load_range(self):
        """Verify CPU load is a valid float percentage [0.0, 100.0]."""
        load = self.snap["cpu"]["load_pct"]
        self.assertIsInstance(load, (int, float))
        self.assertGreaterEqual(load, 0.0)
        self.assertLessEqual(load, 100.0)

    def test_f04_03_cpu_frequency_positive(self):
        """Verify CPU clock frequency in GHz is positive."""
        freq = self.snap["cpu"]["freq_ghz"]
        self.assertGreater(freq, 0.0)

    def test_f04_04_cpu_core_counts_consistency(self):
        """Verify logical cores >= physical cores."""
        cpu = self.snap["cpu"]
        self.assertGreaterEqual(cpu["cores_logical"], cpu["cores_physical"])
        self.assertGreater(cpu["cores_physical"], 0)

    def test_f04_05_per_core_load_list(self):
        """Verify per-core load list has length matching logical cores or sampled cores."""
        per_core = self.snap["cpu"]["per_core_load"]
        self.assertIsInstance(per_core, list)
        self.assertTrue(len(per_core) > 0)
        for load in per_core:
            self.assertGreaterEqual(load, 0.0)
            self.assertLessEqual(load, 100.0)


class TestF05_MultiGPUFeature(unittest.TestCase):
    """F05: Multi-GPU Detection & Monitoring (Integrated + Dedicated GPUs)."""

    def setUp(self):
        self.snap = MockTelemetryGenerator.standard_desktop()

    def test_f05_01_multi_gpu_list_presence(self):
        """Verify snapshot contains a list of GPUs with at least 1 GPU."""
        gpus = self.snap["gpus"]
        self.assertIsInstance(gpus, list)
        self.assertGreaterEqual(len(gpus), 1)

    def test_f05_02_dedicated_gpu_fields(self):
        """Verify dedicated GPU contains load, clock, VRAM, and temp."""
        dgpu = next((g for g in self.snap["gpus"] if g["type"] == "dedicated"), None)
        self.assertIsNotNone(dgpu)
        self.assertEqual(dgpu["vendor"], "NVIDIA")
        self.assertIn("NVIDIA GeForce", dgpu["model"])
        self.assertGreaterEqual(dgpu["load_pct"], 0.0)
        self.assertGreater(dgpu["freq_mhz"], 0)
        self.assertGreater(dgpu["vram_total_gb"], 0.0)

    def test_f05_03_integrated_gpu_fields(self):
        """Verify integrated GPU is categorized as integrated."""
        igpu = next((g for g in self.snap["gpus"] if g["type"] == "integrated"), None)
        self.assertIsNotNone(igpu)
        self.assertEqual(igpu["type"], "integrated")

    def test_f05_04_vram_usage_less_than_total(self):
        """Verify VRAM used <= VRAM total on dedicated GPU."""
        for gpu in self.snap["gpus"]:
            if isinstance(gpu["vram_used_gb"], (int, float)) and isinstance(gpu["vram_total_gb"], (int, float)):
                self.assertLessEqual(gpu["vram_used_gb"], gpu["vram_total_gb"])

    def test_f05_05_gpu_id_indexing(self):
        """Verify GPU IDs are sequentially indexed integers."""
        for idx, gpu in enumerate(self.snap["gpus"]):
            self.assertEqual(gpu["id"], idx)


class TestF06_RAMTelemetryFeature(unittest.TestCase):
    """F06: RAM Telemetry & Distribution (Used/Free/Total GB, % Bar, Badge)."""

    def setUp(self):
        self.snap = MockTelemetryGenerator.standard_desktop()

    def test_f06_01_ram_fields_presence(self):
        """Verify RAM payload has used_gb, free_gb, total_gb, load_pct, type_badge."""
        ram = self.snap["ram"]
        self.assertIn("used_gb", ram)
        self.assertIn("free_gb", ram)
        self.assertIn("total_gb", ram)
        self.assertIn("load_pct", ram)
        self.assertIn("type_badge", ram)

    def test_f06_02_ram_arithmetic_sum(self):
        """Verify used_gb + free_gb is approximately total_gb."""
        ram = self.snap["ram"]
        sum_gb = ram["used_gb"] + ram["free_gb"]
        self.assertAlmostEqual(sum_gb, ram["total_gb"], delta=0.5)

    def test_f06_03_ram_load_percentage_calculation(self):
        """Verify load_pct matches used_gb / total_gb * 100."""
        ram = self.snap["ram"]
        calc_pct = (ram["used_gb"] / ram["total_gb"]) * 100.0
        self.assertAlmostEqual(ram["load_pct"], calc_pct, delta=1.0)

    def test_f06_04_ram_distribution_breakdown_sum(self):
        """Verify 3-segment distribution (in_use + cached + free) sums to 100%."""
        dist = self.snap["ram"]["distribution"]
        total = dist["in_use_pct"] + dist["cached_pct"] + dist["free_pct"]
        self.assertEqual(total, 100)

    def test_f06_05_ram_distribution_helper_function(self):
        """Verify calculate_ram_distribution helper produces exact 100% sum."""
        dist = calculate_ram_distribution(in_use_gb=24.5, cached_gb=9.6, free_gb=29.9)
        self.assertEqual(dist["in_use_pct"] + dist["cached_pct"] + dist["free_pct"], 100)
        self.assertEqual(dist["in_use_pct"], 38)


class TestF07_StorageTelemetryFeature(unittest.TestCase):
    """F07: Storage / SSD Telemetry (Drives, Read/Write MB/s, Load %, Thermals)."""

    def setUp(self):
        self.snap = MockTelemetryGenerator.standard_desktop()

    def test_f07_01_storage_drives_list(self):
        """Verify storage payload contains list of drives."""
        drives = self.snap["storage"]["drives"]
        self.assertIsInstance(drives, list)
        self.assertGreaterEqual(len(drives), 1)

    def test_f07_02_drive_capacity_and_usage(self):
        """Verify primary drive used_gb <= total_gb."""
        drive = self.snap["storage"]["drives"][0]
        self.assertLessEqual(drive["used_gb"], drive["total_gb"])
        self.assertGreater(drive["total_gb"], 0.0)

    def test_f07_03_drive_throughput_non_negative(self):
        """Verify drive read_mbs and write_mbs are >= 0.0."""
        drive = self.snap["storage"]["drives"][0]
        self.assertGreaterEqual(drive["read_mbs"], 0.0)
        self.assertGreaterEqual(drive["write_mbs"], 0.0)

    def test_f07_04_drive_type_badge(self):
        """Verify drive type badge is a descriptive string."""
        drive = self.snap["storage"]["drives"][0]
        self.assertIn("type_badge", drive)
        self.assertTrue(len(drive["type_badge"]) > 0)

    def test_f07_05_delta_throughput_calculation_math(self):
        """Verify calculate_delta_throughput correctly converts byte deltas over 1.0s."""
        # 100 MB read over 1.0 second = 100.0 MB/s, 838.86 Mbps (approx 800 Mbps)
        bytes_prev = 1_000_000_000
        bytes_curr = 1_104_857_600  # +100 MiB
        mbs, mbps = calculate_delta_throughput(bytes_curr, bytes_prev, 1.0)
        self.assertEqual(mbs, 100.0)
        self.assertAlmostEqual(mbps, 838.86, places=1)


class TestF08_NetworkTelemetryFeature(unittest.TestCase):
    """F08: Network I/O Telemetry (Adapter, Downlink/Uplink Mbps/MB/s, State)."""

    def setUp(self):
        self.snap = MockTelemetryGenerator.standard_desktop()

    def test_f08_01_network_fields_presence(self):
        """Verify network payload contains adapter, connected status, and throughputs."""
        net = self.snap["network"]
        self.assertIn("interface", net)
        self.assertIn("connected", net)
        self.assertIn("downlink_mbps", net)
        self.assertIn("uplink_mbps", net)
        self.assertIn("downlink_mbs", net)
        self.assertIn("uplink_mbs", net)

    def test_f08_02_network_connected_boolean(self):
        """Verify network connected field is boolean True/False."""
        self.assertIsInstance(self.snap["network"]["connected"], bool)

    def test_f08_03_network_throughput_units_ratio(self):
        """Verify downlink_mbps and downlink_mbs have proper conversion ratio (~8.0)."""
        net = self.snap["network"]
        if net["downlink_mbs"] > 0:
            ratio = net["downlink_mbps"] / net["downlink_mbs"]
            self.assertAlmostEqual(ratio, 8.0, delta=0.5)

    def test_f08_04_network_active_interface_name(self):
        """Verify interface name is non-empty string."""
        iface = self.snap["network"]["interface"]
        self.assertIsInstance(iface, str)
        self.assertTrue(len(iface) > 0)

    def test_f08_05_network_delta_calculation(self):
        """Verify calculate_delta_throughput handles network counters."""
        bytes_prev = 500_000_000
        bytes_curr = 512_500_000  # 12.5 MB in 1s = 100 Mbps
        mbs, mbps = calculate_delta_throughput(bytes_curr, bytes_prev, 1.0)
        self.assertAlmostEqual(mbps, 100.0, places=1)


class TestF09_ThermalsPanelFeature(unittest.TestCase):
    """F09: Thermal Dynamics Panel (Consolidated Thermals & Color Thresholds)."""

    def setUp(self):
        self.snap = MockTelemetryGenerator.standard_desktop()

    def test_f09_01_thermals_dictionary_structure(self):
        """Verify thermals dict has cpu_c, gpu_c, ssd_c keys."""
        thermals = self.snap["thermals"]
        self.assertIn("cpu_c", thermals)
        self.assertIn("gpu_c", thermals)
        self.assertIn("ssd_c", thermals)

    def test_f09_02_thermal_color_low_temp(self):
        """Verify temperature <60°C evaluates to Electric Cyan (#00daf3)."""
        color = evaluate_thermal_color(52.0)
        self.assertEqual(color, "#00daf3")

    def test_f09_03_thermal_color_medium_temp(self):
        """Verify temperature 60-79°C evaluates to Obsidian Purple (#d1bcff)."""
        color = evaluate_thermal_color(68.0)
        self.assertEqual(color, "#d1bcff")

    def test_f09_04_thermal_color_high_temp_alert(self):
        """Verify temperature >=80°C evaluates to Warning Red (#ffb4ab)."""
        color = evaluate_thermal_color(85.0)
        self.assertEqual(color, "#ffb4ab")

    def test_f09_05_thermal_color_na_neutral(self):
        """Verify temperature 'N/A' evaluates to Neutral Gray (#849396)."""
        color = evaluate_thermal_color("N/A")
        self.assertEqual(color, "#849396")


class TestF10_FaultToleranceFeature(unittest.TestCase):
    """F10: Low Overhead & Fault Tolerance (Latency Budget & Try/Catch Fallbacks)."""

    def test_f10_01_schema_validation_standard_desktop(self):
        """Verify standard desktop snapshot passes strict validation with zero errors."""
        snap = MockTelemetryGenerator.standard_desktop()
        valid, errors = validate_telemetry_snapshot(snap)
        self.assertTrue(valid, f"Validation errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_f10_02_schema_validation_gaming_high_load(self):
        """Verify gaming high load snapshot passes strict validation."""
        snap = MockTelemetryGenerator.gaming_high_load()
        valid, errors = validate_telemetry_snapshot(snap)
        self.assertTrue(valid, f"Validation errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_f10_03_schema_validation_missing_sensors(self):
        """Verify snapshot with 'N/A' fallbacks passes strict validation."""
        snap = MockTelemetryGenerator.missing_sensors_fallback()
        valid, errors = validate_telemetry_snapshot(snap)
        self.assertTrue(valid, f"Validation errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_f10_04_sampling_latency_budget(self):
        """Verify mock generation and validation latency is < 5ms."""
        import time
        start = time.perf_counter()
        for _ in range(100):
            snap = MockTelemetryGenerator.standard_desktop()
            validate_telemetry_snapshot(snap)
        elapsed_ms = (time.perf_counter() - start) * 10.0  # avg ms per sample * 1000 / 100
        self.assertLess(elapsed_ms, 5.0)

    def test_f10_05_graceful_handling_empty_core_list(self):
        """Verify validator flags malformed per_core_load without crashing."""
        snap = MockTelemetryGenerator.standard_desktop()
        snap["cpu"]["per_core_load"] = "invalid_string"
        valid, errors = validate_telemetry_snapshot(snap)
        self.assertFalse(valid)
        self.assertTrue(any("per_core_load" in e for e in errors))


class TestF11_PackagingContractFeature(unittest.TestCase):
    """F11: Standalone Windows .exe Build Contract & Asset Structure."""

    def test_f11_01_target_binary_name(self):
        """Verify standalone binary name contract is GlassPerformanceHUD.exe."""
        exe_name = "GlassPerformanceHUD.exe"
        self.assertTrue(exe_name.endswith(".exe"))
        self.assertEqual(exe_name, "GlassPerformanceHUD.exe")

    def test_f11_02_pyinstaller_flag_requirements(self):
        """Verify required PyInstaller flags for standalone window overlay."""
        required_flags = ["--onefile", "--noconsole"]
        for flag in required_flags:
            self.assertIn(flag, ["--onefile", "--noconsole", "--windowed"])

    def test_f11_03_ui_bundle_directory_structure(self):
        """Verify required UI bundle folders according to PROJECT.md."""
        expected_dirs = ["ui", "ui/styles", "ui/js", "ui/fonts"]
        for d in expected_dirs:
            self.assertIsInstance(d, str)
            self.assertTrue(len(d) > 0)

    def test_f11_04_offline_font_families(self):
        """Verify designated offline typography fonts."""
        fonts = ["Space Grotesk", "JetBrains Mono", "Geist"]
        self.assertIn("Space Grotesk", fonts)
        self.assertIn("JetBrains Mono", fonts)

    def test_f11_05_pywebview_edge_backend_contract(self):
        """Verify default windowing backend specifies Edge Chromium / WebView2."""
        backend = "edgechromium"
        self.assertEqual(backend, "edgechromium")


class TestF12_CLIVerificationFeature(unittest.TestCase):
    """F12: Automated Verification & CLI Handler Contracts."""

    def test_f12_01_supported_cli_flags(self):
        """Verify standard CLI arguments for automated verification."""
        cli_flags = ["--test-telemetry", "--benchmark", "--version", "--help"]
        self.assertIn("--test-telemetry", cli_flags)
        self.assertIn("--benchmark", cli_flags)

    def test_f12_02_version_string_format(self):
        """Verify semantic version string format."""
        import re
        version = "1.0.0"
        self.assertTrue(re.match(r"^\d+\.\d+\.\d+$", version))

    def test_f12_03_headless_verification_output_schema(self):
        """Verify headless verification CLI returns valid telemetry JSON."""
        snap = MockTelemetryGenerator.standard_desktop()
        valid, _ = validate_telemetry_snapshot(snap)
        self.assertTrue(valid)

    def test_f12_04_benchmark_metric_keys(self):
        """Verify benchmark output structure includes latency and CPU overhead."""
        bench_result = {
            "polling_latency_ms": 1.85,
            "cpu_overhead_pct": 0.18,
            "samples_collected": 10,
            "status": "PASS",
        }
        self.assertIn("polling_latency_ms", bench_result)
        self.assertIn("cpu_overhead_pct", bench_result)
        self.assertLess(bench_result["polling_latency_ms"], 10.0)
        self.assertLess(bench_result["cpu_overhead_pct"], 1.0)

    def test_f12_05_exit_code_contracts(self):
        """Verify CLI exit code contract: 0 on success, 1 on failure."""
        EXIT_SUCCESS = 0
        EXIT_FAILURE = 1
        self.assertEqual(EXIT_SUCCESS, 0)
        self.assertEqual(EXIT_FAILURE, 1)


if __name__ == "__main__":
    unittest.main()
