"""
Test Helpers, Schema Validators, and Mock Telemetry Generators for E2E Tests.
Provides comprehensive mock generators, SVG/thermal calculation helpers,
and strict schema validation matching PROJECT.md § Interface Contracts.
"""

import copy
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union


def calculate_svg_dashoffset(pct: float, radius: float = 45.0) -> float:
    """
    Calculate the SVG stroke-dashoffset for a circular progress gauge.
    Circumference = 2 * pi * r ≈ 282.743 (rounded to 283 in CSS for r=45).
    offset = Circumference * (1.0 - (clamped_pct / 100.0))
    """
    if radius <= 0.0:
        return 0.0
    circumference = 2.0 * math.pi * radius
    clamped_pct = max(0.0, min(100.0, float(pct)))
    return circumference * (1.0 - (clamped_pct / 100.0))


def evaluate_thermal_color(temp_c: Union[float, int, str, None]) -> str:
    """
    Evaluate thermal color token based on temperature threshold.
    <60°C -> Electric Cyan (#00daf3)
    60°C - 79.9°C -> Obsidian Purple (#d1bcff)
    >=80°C -> Warning/Alert Red (#ffb4ab)
    'N/A' or invalid -> Neutral Gray (#849396)
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
    Strictly validate a telemetry snapshot dictionary against PROJECT.md § Interface Contracts.
    Accepts both standard and legacy field names for flexible compatibility.
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
        # Model / Name
        name_val = cpu.get("name") or cpu.get("model")
        if not name_val or not isinstance(name_val, str):
            errors.append("Missing CPU name or model string")

        # Load / Utilization
        load_val = cpu.get("utilization_pct") if "utilization_pct" in cpu else cpu.get("load_pct")
        if load_val is None or not isinstance(load_val, (int, float)):
            errors.append("Missing or invalid CPU utilization_pct / load_pct")
        elif not (0.0 <= load_val <= 100.0):
            errors.append(f"CPU utilization out of range [0, 100]: {load_val}")

        # Frequency
        freq_val = cpu.get("frequency_mhz") if "frequency_mhz" in cpu else cpu.get("freq_ghz")
        if freq_val is None or (freq_val != "N/A" and not isinstance(freq_val, (int, float))):
            errors.append(f"CPU frequency must be numeric or 'N/A', got {freq_val}")

        # Cores
        if "cores_physical" in cpu and not isinstance(cpu["cores_physical"], int):
            errors.append("CPU 'cores_physical' must be integer")
        if "cores_logical" in cpu and not isinstance(cpu["cores_logical"], int):
            errors.append("CPU 'cores_logical' must be integer")

        # Temperature
        if "temperature_c" in cpu:
            val = cpu["temperature_c"]
            if val != "N/A" and not isinstance(val, (int, float)):
                errors.append(f"CPU 'temperature_c' must be float, int or 'N/A', got {val}")

        # Per core load
        per_core = cpu.get("per_core_utilization") or cpu.get("per_core_load")
        if per_core is not None:
            if not isinstance(per_core, list):
                errors.append("CPU per-core load must be a list")
            else:
                for idx, core_val in enumerate(per_core):
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
            gpu_name = gpu.get("name") or gpu.get("model")
            if not gpu_name:
                errors.append(f"GPU[{idx}] missing name/model")

            gpu_type = gpu.get("type")
            if gpu_type not in ("integrated", "dedicated"):
                errors.append(f"GPU[{idx}] invalid type: {gpu_type}")

            gpu_load = gpu.get("utilization_pct") if "utilization_pct" in gpu else gpu.get("load_pct")
            if gpu_load is not None and gpu_load != "N/A" and not isinstance(gpu_load, (int, float)):
                errors.append(f"GPU[{idx}] invalid load: {gpu_load}")

    # 4. RAM
    if "ram" not in snapshot or not isinstance(snapshot["ram"], dict):
        errors.append("Missing or invalid 'ram' dictionary")
    else:
        ram = snapshot["ram"]
        for req in ["used_gb", "total_gb"]:
            if req not in ram:
                errors.append(f"RAM missing field: {req}")

        # Check numeric MB fields if present
        for mb_field in ["used_mb", "total_mb", "free_mb", "available_mb", "committed_mb"]:
            if mb_field in ram and not isinstance(ram[mb_field], (int, float)):
                errors.append(f"RAM field '{mb_field}' must be numeric")

    # 5. Processes (Optional or Schema validated)
    if "processes" in snapshot:
        if not isinstance(snapshot["processes"], list):
            errors.append("'processes' must be a list")
        else:
            for p_idx, proc in enumerate(snapshot["processes"]):
                if not isinstance(proc, dict):
                    errors.append(f"Process[{p_idx}] must be a dict")
                    continue
                if "pid" not in proc or not isinstance(proc["pid"], int):
                    errors.append(f"Process[{p_idx}] missing or invalid pid")
                if "name" not in proc or not isinstance(proc["name"], str):
                    errors.append(f"Process[{p_idx}] missing or invalid name")

    # 6. Storage
    if "storage" not in snapshot or not isinstance(snapshot["storage"], dict):
        errors.append("Missing or invalid 'storage' dictionary")
    else:
        storage = snapshot["storage"]
        if "drives" not in storage or not isinstance(storage["drives"], list):
            errors.append("Storage missing 'drives' list")

    # 7. Thermals
    if "thermals" not in snapshot or not isinstance(snapshot["thermals"], dict):
        errors.append("Missing or invalid 'thermals' dictionary")
    else:
        thermals = snapshot["thermals"]
        for req in ["cpu_c"]:
            if req not in thermals:
                errors.append(f"Thermals missing field: {req}")
            elif thermals[req] != "N/A" and not isinstance(thermals[req], (int, float)):
                errors.append(f"Thermals '{req}' must be float/int or 'N/A', got {thermals[req]}")

    # 8. Network
    if "network" in snapshot and not isinstance(snapshot["network"], dict):
        errors.append("'network' must be a dictionary")

    # 9. System Info (Optional in some payloads, but if present must be dict)
    if "system_info" in snapshot and not isinstance(snapshot["system_info"], dict):
        errors.append("'system_info' must be a dictionary")

    return len(errors) == 0, errors


class MockTelemetryGenerator:
    """Generates schema-compliant telemetry snapshots for testing various system conditions."""

    @staticmethod
    def standard_desktop(timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Baseline standard desktop workload with dual GPU, RAM in MB/GB, top processes."""
        ts = time.time() if timestamp is None else timestamp
        return {
            "timestamp": ts,
            "cpu": {
                "name": "AMD Ryzen 9 6900HX with Radeon Graphics",
                "model": "AMD Ryzen 9 6900HX with Radeon Graphics",
                "cores_physical": 8,
                "cores_logical": 16,
                "utilization_pct": 18.5,
                "load_pct": 18.5,
                "frequency_mhz": 3300.0,
                "freq_ghz": 3.30,
                "temperature_c": 52.0,
                "per_core_utilization": [15.0, 22.0, 10.0, 18.0, 12.0, 30.0, 14.0, 25.0],
                "per_core_load": [15.0, 22.0, 10.0, 18.0, 12.0, 30.0, 14.0, 25.0],
            },
            "gpus": [
                {
                    "id": 0,
                    "name": "NVIDIA GeForce RTX 3060 Laptop GPU",
                    "model": "NVIDIA GeForce RTX 3060 Laptop GPU",
                    "type": "dedicated",
                    "vendor": "NVIDIA",
                    "utilization_pct": 28.0,
                    "load_pct": 28.0,
                    "vram_used_gb": 2.1,
                    "vram_total_gb": 6.0,
                    "vram_used_mb": 2150.4,
                    "vram_total_mb": 6144.0,
                    "clock_mhz": 1425,
                    "freq_mhz": 1425,
                    "temperature_c": 55.0,
                },
                {
                    "id": 1,
                    "name": "AMD Radeon(TM) Graphics",
                    "model": "AMD Radeon(TM) Graphics",
                    "type": "integrated",
                    "vendor": "AMD",
                    "utilization_pct": 4.0,
                    "load_pct": 4.0,
                    "vram_used_gb": 0.5,
                    "vram_total_gb": 2.0,
                    "vram_used_mb": 512.0,
                    "vram_total_mb": 2048.0,
                    "clock_mhz": 400,
                    "freq_mhz": 400,
                    "temperature_c": 48.0,
                },
            ],
            "ram": {
                "used_gb": 22.6,
                "total_gb": 64.0,
                "free_gb": 41.4,
                "used_mb": 23142.4,
                "total_mb": 65536.0,
                "free_mb": 42393.6,
                "available_mb": 42500.0,
                "committed_mb": 26000.0,
                "commit_limit_mb": 70000.0,
                "utilization_pct": 35.3,
                "load_pct": 35.3,
                "memory_type": "DDR5",
                "type_badge": "DDR5-4800",
                "speed_mhz": 4800,
                "distribution": {
                    "in_use_pct": 35,
                    "cached_pct": 20,
                    "free_pct": 45,
                },
            },
            "processes": [
                {
                    "pid": 1248,
                    "name": "chrome.exe",
                    "cpu_pct": 6.2,
                    "memory_mb": 842.5,
                    "memory_pct": 1.3,
                    "disk_mbps": 1.2,
                    "gpu_pct": 4.5,
                },
                {
                    "pid": 4512,
                    "name": "Code.exe",
                    "cpu_pct": 4.8,
                    "memory_mb": 620.0,
                    "memory_pct": 0.9,
                    "disk_mbps": 0.4,
                    "gpu_pct": 2.1,
                },
                {
                    "pid": 7890,
                    "name": "Spotify.exe",
                    "cpu_pct": 1.5,
                    "memory_mb": 210.0,
                    "memory_pct": 0.3,
                    "disk_mbps": 0.0,
                    "gpu_pct": 0.8,
                },
                {
                    "pid": 2304,
                    "name": "explorer.exe",
                    "cpu_pct": 0.8,
                    "memory_mb": 180.0,
                    "memory_pct": 0.2,
                    "disk_mbps": 0.1,
                    "gpu_pct": 0.5,
                },
                {
                    "pid": 9812,
                    "name": "Discord.exe",
                    "cpu_pct": 0.5,
                    "memory_mb": 150.0,
                    "memory_pct": 0.2,
                    "disk_mbps": 0.0,
                    "gpu_pct": 0.2,
                },
            ],
            "storage": {
                "drives": [
                    {
                        "device": "C:",
                        "letter": "C:",
                        "type": "NVMe Gen4",
                        "type_badge": "NVMe Gen4",
                        "used_gb": 420.5,
                        "total_gb": 1024.0,
                        "free_gb": 603.5,
                        "utilization_pct": 41.1,
                        "load_pct": 8.0,
                        "read_mbs": 45.2,
                        "write_mbs": 12.8,
                        "read_mbps": 45.2,
                        "write_mbps": 12.8,
                        "temperature_c": 42.0,
                    }
                ]
            },
            "network": {
                "interface": "Wi-Fi 2",
                "adapter_name": "Wi-Fi 2",
                "connected": True,
                "downlink_mbps": 85.4,
                "uplink_mbps": 12.3,
                "download_mbps": 85.4,
                "upload_mbps": 12.3,
                "downlink_mbs": 10.67,
                "uplink_mbs": 1.54,
            },
            "thermals": {
                "cpu_c": 52.0,
                "gpu_c": 55.0,
                "dgpu_c": 55.0,
                "igpu_c": 48.0,
                "ssd_c": 42.0,
            },
            "system_info": {
                "os": "Windows 11 Home 23H2 (Build 22631)",
                "cpu_arch": "x86_64",
                "motherboard": "Standard OEM",
                "bios_version": "1.04",
            },
        }

    @staticmethod
    def gaming_high_load(timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Intense gaming session simulation with dGPU saturation."""
        ts = time.time() if timestamp is None else timestamp
        return {
            "timestamp": ts,
            "cpu": {
                "name": "13th Gen Intel(R) Core(TM) i9-13900HX",
                "model": "13th Gen Intel(R) Core(TM) i9-13900HX",
                "cores_physical": 24,
                "cores_logical": 32,
                "utilization_pct": 88.0,
                "load_pct": 88.0,
                "frequency_mhz": 5200.0,
                "freq_ghz": 5.20,
                "temperature_c": 86.5,
                "per_core_utilization": [85.0] * 32,
                "per_core_load": [85.0] * 32,
            },
            "gpus": [
                {
                    "id": 0,
                    "name": "NVIDIA GeForce RTX 4080 Laptop GPU",
                    "model": "NVIDIA GeForce RTX 4080 Laptop GPU",
                    "type": "dedicated",
                    "vendor": "NVIDIA",
                    "utilization_pct": 98.5,
                    "load_pct": 98.5,
                    "vram_used_gb": 11.2,
                    "vram_total_gb": 12.0,
                    "vram_used_mb": 11468.8,
                    "vram_total_mb": 12288.0,
                    "clock_mhz": 2100,
                    "freq_mhz": 2100,
                    "temperature_c": 84.0,
                },
                {
                    "id": 1,
                    "name": "Intel(R) UHD Graphics",
                    "model": "Intel(R) UHD Graphics",
                    "type": "integrated",
                    "vendor": "Intel",
                    "utilization_pct": 2.0,
                    "load_pct": 2.0,
                    "vram_used_gb": 0.3,
                    "vram_total_gb": "N/A",
                    "vram_used_mb": 307.2,
                    "vram_total_mb": "N/A",
                    "clock_mhz": "N/A",
                    "freq_mhz": "N/A",
                    "temperature_c": "N/A",
                },
            ],
            "ram": {
                "used_gb": 49.9,
                "total_gb": 64.0,
                "free_gb": 14.1,
                "used_mb": 51097.6,
                "total_mb": 65536.0,
                "free_mb": 14438.4,
                "available_mb": 14500.0,
                "committed_mb": 56000.0,
                "commit_limit_mb": 70000.0,
                "utilization_pct": 78.0,
                "load_pct": 78.0,
                "memory_type": "DDR5",
                "type_badge": "DDR5-6000",
                "speed_mhz": 6000,
                "distribution": {
                    "in_use_pct": 78,
                    "cached_pct": 12,
                    "free_pct": 10,
                },
            },
            "processes": [
                {
                    "pid": 5832,
                    "name": "Cyberpunk2077.exe",
                    "cpu_pct": 65.4,
                    "memory_mb": 14500.0,
                    "memory_pct": 22.1,
                    "disk_mbps": 120.5,
                    "gpu_pct": 92.0,
                },
                {
                    "pid": 9104,
                    "name": "OBS64.exe",
                    "cpu_pct": 12.1,
                    "memory_mb": 1200.0,
                    "memory_pct": 1.8,
                    "disk_mbps": 45.0,
                    "gpu_pct": 5.0,
                },
                {
                    "pid": 1120,
                    "name": "Discord.exe",
                    "cpu_pct": 2.3,
                    "memory_mb": 450.0,
                    "memory_pct": 0.7,
                    "disk_mbps": 0.1,
                    "gpu_pct": 0.5,
                },
                {
                    "pid": 3310,
                    "name": "Steam.exe",
                    "cpu_pct": 1.1,
                    "memory_mb": 310.0,
                    "memory_pct": 0.5,
                    "disk_mbps": 0.5,
                    "gpu_pct": 0.2,
                },
                {
                    "pid": 4412,
                    "name": "chrome.exe",
                    "cpu_pct": 0.9,
                    "memory_mb": 850.0,
                    "memory_pct": 1.3,
                    "disk_mbps": 0.0,
                    "gpu_pct": 0.3,
                },
            ],
            "storage": {
                "drives": [
                    {
                        "device": "C:",
                        "letter": "C:",
                        "type": "NVMe Gen4",
                        "type_badge": "NVMe Gen4",
                        "used_gb": 850.0,
                        "total_gb": 2048.0,
                        "free_gb": 1198.0,
                        "utilization_pct": 41.5,
                        "load_pct": 65.0,
                        "read_mbs": 1250.0,
                        "write_mbs": 450.0,
                        "read_mbps": 1250.0,
                        "write_mbps": 450.0,
                        "temperature_c": 68.0,
                    }
                ]
            },
            "network": {
                "interface": "Ethernet",
                "adapter_name": "Ethernet",
                "connected": True,
                "downlink_mbps": 450.0,
                "uplink_mbps": 65.0,
                "download_mbps": 450.0,
                "upload_mbps": 65.0,
                "downlink_mbs": 56.25,
                "uplink_mbs": 8.12,
            },
            "thermals": {
                "cpu_c": 86.5,
                "gpu_c": 84.0,
                "dgpu_c": 84.0,
                "igpu_c": "N/A",
                "ssd_c": 68.0,
            },
            "system_info": {
                "os": "Windows 11 Pro 23H2 (Build 22631)",
                "cpu_arch": "x86_64",
                "motherboard": "ROG Strix SCAR 18",
                "bios_version": "3.12",
            },
        }

    @staticmethod
    def missing_sensors_fallback(timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Unprivileged environment with fallback values for unexposed sensors."""
        ts = time.time() if timestamp is None else timestamp
        return {
            "timestamp": ts,
            "cpu": {
                "name": "Generic Intel Processor",
                "model": "Generic Intel Processor",
                "cores_physical": 4,
                "cores_logical": 8,
                "utilization_pct": 10.0,
                "load_pct": 10.0,
                "frequency_mhz": 2400.0,
                "freq_ghz": 2.40,
                "temperature_c": "N/A",
                "per_core_utilization": [10.0] * 8,
                "per_core_load": [10.0] * 8,
            },
            "gpus": [
                {
                    "id": 0,
                    "name": "Intel HD Graphics",
                    "model": "Intel HD Graphics",
                    "type": "integrated",
                    "vendor": "Intel",
                    "utilization_pct": 15.0,
                    "load_pct": 15.0,
                    "vram_used_gb": 0.4,
                    "vram_total_gb": "N/A",
                    "vram_used_mb": 409.6,
                    "vram_total_mb": "N/A",
                    "clock_mhz": "N/A",
                    "freq_mhz": "N/A",
                    "temperature_c": "N/A",
                }
            ],
            "ram": {
                "used_gb": 8.0,
                "total_gb": 16.0,
                "free_gb": 8.0,
                "used_mb": 8192.0,
                "total_mb": 16384.0,
                "free_mb": 8192.0,
                "available_mb": 8192.0,
                "committed_mb": 9000.0,
                "commit_limit_mb": 18000.0,
                "utilization_pct": 50.0,
                "load_pct": 50.0,
                "memory_type": "DDR4",
                "type_badge": "DDR4",
                "speed_mhz": 2400,
                "distribution": {
                    "in_use_pct": 50,
                    "cached_pct": 20,
                    "free_pct": 30,
                },
            },
            "processes": [],
            "storage": {
                "drives": [
                    {
                        "device": "C:",
                        "letter": "C:",
                        "type": "SATA SSD",
                        "type_badge": "SATA SSD",
                        "used_gb": 200.0,
                        "total_gb": 500.0,
                        "free_gb": 300.0,
                        "utilization_pct": 40.0,
                        "load_pct": 0.0,
                        "read_mbs": 0.0,
                        "write_mbs": 0.0,
                        "read_mbps": 0.0,
                        "write_mbps": 0.0,
                        "temperature_c": "N/A",
                    }
                ]
            },
            "network": {
                "interface": "No Active Adapter",
                "adapter_name": "No Active Adapter",
                "connected": False,
                "downlink_mbps": 0.0,
                "uplink_mbps": 0.0,
                "download_mbps": 0.0,
                "upload_mbps": 0.0,
                "downlink_mbs": 0.0,
                "uplink_mbs": 0.0,
            },
            "thermals": {
                "cpu_c": "N/A",
                "gpu_c": "N/A",
                "dgpu_c": "N/A",
                "igpu_c": "N/A",
                "ssd_c": "N/A",
            },
            "system_info": {
                "os": "Windows 10 Pro 22H2",
                "cpu_arch": "x86_64",
                "motherboard": "Generic Board",
                "bios_version": "N/A",
            },
        }


class MockPyWebViewAPI:
    """Mock implementation of the JS-Python bridge window.pywebview.api."""

    def __init__(self, initial_mode: str = "standard", initial_pinned: bool = True):
        self.current_mode: str = initial_mode
        self.width: int = 1200 if initial_mode == "standard" else 1920
        self.height: int = 800 if initial_mode == "standard" else 550
        self.prev_width: int = 1200
        self.prev_height: int = 800
        self.is_pinned: bool = initial_pinned
        self.is_minimized: bool = False
        self.is_maximized_state: bool = False
        self.is_closed: bool = False
        self.active_tab: str = "MONITOR"
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

    def toggle_maximize(self) -> bool:
        """Toggles maximize state, stores previous geometry before maximize and restores."""
        if not self.is_maximized_state:
            self.prev_width = self.width
            self.prev_height = self.height
            self.width = 1920
            self.height = 1080
            self.is_maximized_state = True
        else:
            self.width = self.prev_width
            self.height = self.prev_height
            self.is_maximized_state = False
        return self.is_maximized_state

    def is_maximized(self) -> bool:
        return self.is_maximized_state

    def minimize_window(self) -> bool:
        self.is_minimized = True
        return True

    def restore_window(self) -> bool:
        self.is_minimized = False
        return True

    def close_window(self) -> bool:
        self.is_closed = True
        return True

    def switch_tab(self, tab_name: str) -> str:
        valid_tabs = ["MONITOR", "TELEMETRY", "SYSTEM"]
        if tab_name.upper() not in valid_tabs:
            raise ValueError(f"Invalid tab: {tab_name}. Expected one of {valid_tabs}")
        self.active_tab = tab_name.upper()
        return self.active_tab

    def get_status(self) -> Dict[str, Any]:
        return {
            "mode": self.current_mode,
            "width": self.width,
            "height": self.height,
            "is_pinned": self.is_pinned,
            "is_minimized": self.is_minimized,
            "is_maximized": self.is_maximized_state,
            "is_closed": self.is_closed,
            "active_tab": self.active_tab,
        }
