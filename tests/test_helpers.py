"""
Test Helpers, Schema Validators, and Mock Telemetry Generators for E2E Tests.
"""

import math
import time
from typing import Any, Dict, List, Optional, Tuple, Union


def calculate_svg_dashoffset(pct: float, radius: float = 45.0) -> float:
    """
    Calculate the SVG stroke-dashoffset for a circular progress gauge.
    Circumference = 2 * pi * r ≈ 282.743 (rounded to 283 in CSS).
    offset = 283 - (pct / 100.0) * 283
    """
    circumference = 2.0 * math.pi * radius
    clamped_pct = max(0.0, min(100.0, float(pct)))
    return circumference - (clamped_pct / 100.0) * circumference


def evaluate_thermal_color(temp_c: Union[float, int, str]) -> str:
    """
    Evaluate thermal color token based on temperature threshold.
    <60°C -> Electric Cyan (#00daf3)
    60°C - 79°C -> Obsidian Purple (#d1bcff)
    >=80°C -> Warning/Alert Red (#ffb4ab)
    'N/A' -> Neutral Gray (#849396)
    """
    if temp_c == "N/A" or temp_c is None:
        return "#849396"
    try:
        temp = float(temp_c)
        if temp < 60.0:
            return "#00daf3"
        elif temp < 80.0:
            return "#d1bcff"
        else:
            return "#ffb4ab"
    except (ValueError, TypeError):
        return "#849396"


def calculate_delta_throughput(
    bytes_curr: int, bytes_prev: int, time_delta_sec: float
) -> Tuple[float, float]:
    """
    Calculate delta throughput from byte counters over time_delta_sec.
    Returns (throughput_mbs, throughput_mbps).
    """
    if time_delta_sec <= 0.0:
        return 0.0, 0.0
    byte_diff = max(0, bytes_curr - bytes_prev)
    mbs = (byte_diff / (1024.0 * 1024.0)) / time_delta_sec
    mbps = (byte_diff * 8.0 / (1000.0 * 1000.0)) / time_delta_sec
    return round(mbs, 2), round(mbps, 2)


def calculate_ram_distribution(
    in_use_gb: float, cached_gb: float, free_gb: float
) -> Dict[str, int]:
    """
    Calculate integer percentage distribution for RAM segments.
    Guarantees sum equals 100%.
    """
    total = in_use_gb + cached_gb + free_gb
    if total <= 0:
        return {"in_use_pct": 0, "cached_pct": 0, "free_pct": 100}
    
    in_use_pct = int(round((in_use_gb / total) * 100))
    cached_pct = int(round((cached_gb / total) * 100))
    free_pct = 100 - in_use_pct - cached_pct
    if free_pct < 0:
        free_pct = 0
        cached_pct = 100 - in_use_pct
    return {
        "in_use_pct": in_use_pct,
        "cached_pct": cached_pct,
        "free_pct": free_pct,
    }


def validate_telemetry_snapshot(snapshot: Any) -> Tuple[bool, List[str]]:
    """
    Strictly validate a telemetry snapshot dictionary against the PROJECT.md schema.
    Returns (is_valid, error_list).
    """
    errors: List[str] = []
    if not isinstance(snapshot, dict):
        return False, ["Snapshot must be a dictionary"]

    # 1. Timestamp
    if "timestamp" not in snapshot:
        errors.append("Missing 'timestamp' field")
    elif not isinstance(snapshot["timestamp"], (int, float)):
        errors.append(f"'timestamp' must be numeric, got {type(snapshot['timestamp'])}")

    # 2. CPU
    if "cpu" not in snapshot or not isinstance(snapshot["cpu"], dict):
        errors.append("Missing or invalid 'cpu' dictionary")
    else:
        cpu = snapshot["cpu"]
        for req_field in ["model", "load_pct", "freq_ghz", "cores_physical", "cores_logical", "temperature_c"]:
            if req_field not in cpu:
                errors.append(f"Missing CPU field: {req_field}")
        
        if "load_pct" in cpu and not isinstance(cpu["load_pct"], (int, float)):
            errors.append("CPU 'load_pct' must be numeric")
        elif "load_pct" in cpu and not (0.0 <= cpu["load_pct"] <= 100.0):
            errors.append(f"CPU 'load_pct' out of range [0, 100]: {cpu['load_pct']}")

        if "freq_ghz" in cpu and not isinstance(cpu["freq_ghz"], (int, float)):
            errors.append("CPU 'freq_ghz' must be numeric")

        if "temperature_c" in cpu:
            val = cpu["temperature_c"]
            if val != "N/A" and not isinstance(val, (int, float)):
                errors.append(f"CPU 'temperature_c' must be float, int or 'N/A', got {val}")

        if "per_core_load" in cpu:
            if not isinstance(cpu["per_core_load"], list):
                errors.append("CPU 'per_core_load' must be a list")
            else:
                for idx, core_val in enumerate(cpu["per_core_load"]):
                    if not isinstance(core_val, (int, float)) or not (0.0 <= core_val <= 100.0):
                        errors.append(f"CPU core {idx} load invalid: {core_val}")

    # 3. GPUs
    if "gpus" not in snapshot or not isinstance(snapshot["gpus"], list):
        errors.append("Missing or invalid 'gpus' list")
    else:
        for idx, gpu in enumerate(snapshot["gpus"]):
            if not isinstance(gpu, dict):
                errors.append(f"GPU[{idx}] must be a dict")
                continue
            for req in ["id", "type", "vendor", "model", "load_pct", "freq_mhz", "vram_used_gb", "vram_total_gb", "temperature_c"]:
                if req not in gpu:
                    errors.append(f"GPU[{idx}] missing field: {req}")
            
            if "type" in gpu and gpu["type"] not in ("integrated", "dedicated"):
                errors.append(f"GPU[{idx}] invalid type: {gpu['type']}")

            if "load_pct" in gpu and gpu["load_pct"] != "N/A" and not isinstance(gpu["load_pct"], (int, float)):
                errors.append(f"GPU[{idx}] invalid load_pct: {gpu['load_pct']}")

    # 4. RAM
    if "ram" not in snapshot or not isinstance(snapshot["ram"], dict):
        errors.append("Missing or invalid 'ram' dictionary")
    else:
        ram = snapshot["ram"]
        for req in ["load_pct", "used_gb", "free_gb", "total_gb", "type_badge", "distribution"]:
            if req not in ram:
                errors.append(f"RAM missing field: {req}")
        if "distribution" in ram and isinstance(ram["distribution"], dict):
            dist = ram["distribution"]
            for d_field in ["in_use_pct", "cached_pct", "free_pct"]:
                if d_field not in dist or not isinstance(dist[d_field], (int, float)):
                    errors.append(f"RAM distribution missing or invalid {d_field}")
            if all(k in dist for k in ["in_use_pct", "cached_pct", "free_pct"]):
                total_pct = dist["in_use_pct"] + dist["cached_pct"] + dist["free_pct"]
                if not (98 <= total_pct <= 102):  # allow slight rounding variance
                    errors.append(f"RAM distribution sum != 100%: {total_pct}%")

    # 5. Storage
    if "storage" not in snapshot or not isinstance(snapshot["storage"], dict):
        errors.append("Missing or invalid 'storage' dictionary")
    else:
        storage = snapshot["storage"]
        if "drives" not in storage or not isinstance(storage["drives"], list):
            errors.append("Storage missing 'drives' list")
        else:
            for idx, drive in enumerate(storage["drives"]):
                if not isinstance(drive, dict):
                    errors.append(f"Drive[{idx}] must be a dict")
                    continue
                for req in ["device", "type_badge", "used_gb", "total_gb", "load_pct", "read_mbs", "write_mbs", "temperature_c"]:
                    if req not in drive:
                        errors.append(f"Drive[{idx}] missing field: {req}")

    # 6. Network
    if "network" not in snapshot or not isinstance(snapshot["network"], dict):
        errors.append("Missing or invalid 'network' dictionary")
    else:
        net = snapshot["network"]
        for req in ["interface", "connected", "downlink_mbps", "uplink_mbps", "downlink_mbs", "uplink_mbs"]:
            if req not in net:
                errors.append(f"Network missing field: {req}")
        if "connected" in net and not isinstance(net["connected"], bool):
            errors.append("Network 'connected' must be boolean")

    # 7. Thermals
    if "thermals" not in snapshot or not isinstance(snapshot["thermals"], dict):
        errors.append("Missing or invalid 'thermals' dictionary")
    else:
        thermals = snapshot["thermals"]
        for req in ["cpu_c", "gpu_c", "ssd_c"]:
            if req not in thermals:
                errors.append(f"Thermals missing field: {req}")
            elif thermals[req] != "N/A" and not isinstance(thermals[req], (int, float)):
                errors.append(f"Thermals '{req}' must be float/int or 'N/A', got {thermals[req]}")

    return len(errors) == 0, errors


class MockTelemetryGenerator:
    """Generates schema-compliant telemetry snapshots for testing various system conditions."""

    @staticmethod
    def standard_desktop(timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Baseline standard desktop workload."""
        return {
            "timestamp": timestamp or time.time(),
            "cpu": {
                "model": "AMD Ryzen 9 6900HX with Radeon Graphics",
                "load_pct": 18.5,
                "freq_ghz": 3.30,
                "cores_physical": 8,
                "cores_logical": 16,
                "temperature_c": 52.0,
                "per_core_load": [15.0, 22.0, 10.0, 18.0, 12.0, 30.0, 14.0, 25.0],
            },
            "gpus": [
                {
                    "id": 0,
                    "type": "dedicated",
                    "vendor": "NVIDIA",
                    "model": "NVIDIA GeForce RTX 3060 Laptop GPU",
                    "load_pct": 28.0,
                    "freq_mhz": 1425,
                    "vram_used_gb": 2.1,
                    "vram_total_gb": 6.0,
                    "temperature_c": 55.0,
                },
                {
                    "id": 1,
                    "type": "integrated",
                    "vendor": "AMD",
                    "model": "AMD Radeon(TM) Graphics",
                    "load_pct": 4.0,
                    "freq_mhz": 400,
                    "vram_used_gb": 0.5,
                    "vram_total_gb": 2.0,
                    "temperature_c": 48.0,
                },
            ],
            "ram": {
                "load_pct": 42.5,
                "used_gb": 27.2,
                "free_gb": 36.8,
                "total_gb": 64.0,
                "type_badge": "DDR5-4800",
                "distribution": {
                    "in_use_pct": 43,
                    "cached_pct": 18,
                    "free_pct": 39,
                },
            },
            "storage": {
                "drives": [
                    {
                        "device": "C:",
                        "type_badge": "NVMe Gen4",
                        "used_gb": 420.5,
                        "total_gb": 1024.0,
                        "load_pct": 8.0,
                        "read_mbs": 45.2,
                        "write_mbs": 12.8,
                        "temperature_c": 42.0,
                    }
                ]
            },
            "network": {
                "interface": "Wi-Fi 2",
                "connected": True,
                "downlink_mbps": 85.4,
                "uplink_mbps": 12.3,
                "downlink_mbs": 10.67,
                "uplink_mbs": 1.54,
            },
            "thermals": {
                "cpu_c": 52.0,
                "gpu_c": 55.0,
                "ssd_c": 42.0,
            },
        }

    @staticmethod
    def gaming_high_load(timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Intense gaming session simulation with dGPU saturation."""
        return {
            "timestamp": timestamp or time.time(),
            "cpu": {
                "model": "13th Gen Intel(R) Core(TM) i9-13900HX",
                "load_pct": 88.0,
                "freq_ghz": 5.20,
                "cores_physical": 24,
                "cores_logical": 32,
                "temperature_c": 86.5,
                "per_core_load": [85.0] * 32,
            },
            "gpus": [
                {
                    "id": 0,
                    "type": "dedicated",
                    "vendor": "NVIDIA",
                    "model": "NVIDIA GeForce RTX 4080 Laptop GPU",
                    "load_pct": 98.5,
                    "freq_mhz": 2100,
                    "vram_used_gb": 11.2,
                    "vram_total_gb": 12.0,
                    "temperature_c": 84.0,
                },
                {
                    "id": 1,
                    "type": "integrated",
                    "vendor": "Intel",
                    "model": "Intel(R) UHD Graphics",
                    "load_pct": 2.0,
                    "freq_mhz": "N/A",
                    "vram_used_gb": 0.3,
                    "vram_total_gb": "N/A",
                    "temperature_c": "N/A",
                },
            ],
            "ram": {
                "load_pct": 78.0,
                "used_gb": 49.9,
                "free_gb": 14.1,
                "total_gb": 64.0,
                "type_badge": "DDR5-6000",
                "distribution": {
                    "in_use_pct": 78,
                    "cached_pct": 12,
                    "free_pct": 10,
                },
            },
            "storage": {
                "drives": [
                    {
                        "device": "C:",
                        "type_badge": "NVMe Gen4",
                        "used_gb": 850.0,
                        "total_gb": 2048.0,
                        "load_pct": 65.0,
                        "read_mbs": 1250.0,
                        "write_mbs": 450.0,
                        "temperature_c": 68.0,
                    }
                ]
            },
            "network": {
                "interface": "Ethernet",
                "connected": True,
                "downlink_mbps": 450.0,
                "uplink_mbps": 65.0,
                "downlink_mbs": 56.25,
                "uplink_mbs": 8.12,
            },
            "thermals": {
                "cpu_c": 86.5,
                "gpu_c": 84.0,
                "ssd_c": 68.0,
            },
        }

    @staticmethod
    def missing_sensors_fallback(timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Unprivileged environment with fallback values for unexposed sensors."""
        return {
            "timestamp": timestamp or time.time(),
            "cpu": {
                "model": "Generic Intel Processor",
                "load_pct": 10.0,
                "freq_ghz": 2.40,
                "cores_physical": 4,
                "cores_logical": 8,
                "temperature_c": "N/A",
                "per_core_load": [10.0] * 8,
            },
            "gpus": [
                {
                    "id": 0,
                    "type": "integrated",
                    "vendor": "Intel",
                    "model": "Intel HD Graphics",
                    "load_pct": 15.0,
                    "freq_mhz": "N/A",
                    "vram_used_gb": 0.4,
                    "vram_total_gb": "N/A",
                    "temperature_c": "N/A",
                }
            ],
            "ram": {
                "load_pct": 50.0,
                "used_gb": 8.0,
                "free_gb": 8.0,
                "total_gb": 16.0,
                "type_badge": "DDR4",
                "distribution": {
                    "in_use_pct": 50,
                    "cached_pct": 20,
                    "free_pct": 30,
                },
            },
            "storage": {
                "drives": [
                    {
                        "device": "C:",
                        "type_badge": "SATA SSD",
                        "used_gb": 200.0,
                        "total_gb": 500.0,
                        "load_pct": 0.0,
                        "read_mbs": 0.0,
                        "write_mbs": 0.0,
                        "temperature_c": "N/A",
                    }
                ]
            },
            "network": {
                "interface": "No Active Adapter",
                "connected": False,
                "downlink_mbps": 0.0,
                "uplink_mbps": 0.0,
                "downlink_mbs": 0.0,
                "uplink_mbs": 0.0,
            },
            "thermals": {
                "cpu_c": "N/A",
                "gpu_c": "N/A",
                "ssd_c": "N/A",
            },
        }


class MockPyWebViewAPI:
    """Mock implementation of the JS-Python bridge window.pywebview.api."""

    def __init__(self, initial_mode: str = "standard", initial_pinned: bool = True):
        self.current_mode: str = initial_mode
        self.width: int = 1200 if initial_mode == "standard" else 1920
        self.height: int = 800 if initial_mode == "standard" else 550
        self.is_pinned: bool = initial_pinned
        self.is_minimized: bool = False
        self.is_closed: bool = False
        self.latest_snapshot: Dict[str, Any] = MockTelemetryGenerator.standard_desktop()

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        return self.latest_snapshot

    def set_screen_mode(self, mode_name: str) -> Dict[str, Any]:
        if mode_name == "ultrawide":
            self.current_mode = "ultrawide"
            self.width, self.height = 1920, 550
        elif mode_name == "standard":
            self.current_mode = "standard"
            self.width, self.height = 1200, 800
        else:
            raise ValueError(f"Unknown screen mode: {mode_name}")
        return {
            "mode": self.current_mode,
            "width": self.width,
            "height": self.height,
        }

    def toggle_pin_top(self) -> bool:
        self.is_pinned = not self.is_pinned
        return self.is_pinned

    def minimize_window(self) -> bool:
        self.is_minimized = True
        return True

    def restore_window(self) -> bool:
        self.is_minimized = False
        return True

    def close_window(self) -> bool:
        self.is_closed = True
        return True
