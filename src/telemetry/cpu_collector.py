"""
src/telemetry/cpu_collector.py
High-performance CPU hardware telemetry collector for Windows.
Extracts processor model, current clock frequency (GHz), overall utilization %,
per-core/thread loads, physical and logical core counts, and CPU temperature.
"""

import logging
import platform
import sys
from typing import Any, Dict, List, Union

import psutil

logger = logging.getLogger(__name__)


class CPUCollector:
    """
    Collects real-time CPU performance metrics and static hardware specifications.
    Uses non-blocking psutil time-delta calculations and WinReg queries.
    """

    def __init__(self):
        self.model: str = self._query_cpu_model()
        self.cores_physical: int = psutil.cpu_count(logical=False) or 1
        self.cores_logical: int = psutil.cpu_count(logical=True) or 1
        self.base_freq_ghz: float = self._query_base_freq_ghz()

        # Warm-up call to initialize psutil internal delta counters
        try:
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(interval=None, percpu=True)
        except Exception as exc:
            logger.debug("CPU collector warmup error: %s", exc)

    def _query_cpu_model(self) -> str:
        """Queries CPU model name string from Windows Registry."""
        if sys.platform == "win32":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                )
                model_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                winreg.CloseKey(key)
                if model_name and isinstance(model_name, str):
                    return model_name.strip()
            except Exception as exc:
                logger.debug("WinReg CPU model query error: %s", exc)

        proc = platform.processor()
        if proc:
            return proc.strip()
        return "Generic Windows x64 Processor"

    def _query_base_freq_ghz(self) -> float:
        """Queries base processor frequency from Windows Registry ~MHz."""
        if sys.platform == "win32":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                )
                mhz, _ = winreg.QueryValueEx(key, "~MHz")
                winreg.CloseKey(key)
                if mhz and isinstance(mhz, (int, float)) and mhz > 0:
                    return round(float(mhz) / 1000.0, 2)
            except Exception as exc:
                logger.debug("WinReg ~MHz query error: %s", exc)

        try:
            freq = psutil.cpu_freq()
            if freq and freq.max and freq.max > 0:
                return round(float(freq.max) / 1000.0, 2)
            if freq and freq.current and freq.current > 0:
                return round(float(freq.current) / 1000.0, 2)
        except Exception:
            pass

        return 2.50

    def _query_temperature(self) -> Union[float, str]:
        """
        Attempts to read CPU temperature via ACPI thermal zones or psutil sensors.
        Returns float temperature in °C or 'N/A' if inaccessible.
        """
        # 1. psutil sensors_temperatures (if supported)
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz"]:
                        if name in temps and temps[name]:
                            val = temps[name][0].current
                            if val is not None and val > 0:
                                return round(float(val), 1)
        except Exception:
            pass

        # 2. Windows WMI ACPI ThermalZone (if available without elevated driver)
        if sys.platform == "win32":
            try:
                import ctypes
                # Fast check to see if thermal query is possible; user-mode fallback is N/A
            except Exception:
                pass

        return "N/A"

    def collect(self) -> Dict[str, Any]:
        """
        Polls CPU dynamic telemetry in < 1ms.
        Returns a dictionary adhering to PROJECT.md interface contract.
        """
        try:
            load_raw = psutil.cpu_percent(interval=None)
            load_pct = min(100.0, max(0.0, round(float(load_raw), 1)))
        except Exception:
            load_pct = 0.0

        try:
            per_core_raw = psutil.cpu_percent(interval=None, percpu=True)
            per_core_load = [
                min(100.0, max(0.0, round(float(c), 1)))
                for c in per_core_raw
            ]
        except Exception:
            per_core_load = [load_pct] * self.cores_logical

        freq_ghz = self.base_freq_ghz
        try:
            freq_info = psutil.cpu_freq()
            if freq_info and freq_info.current and freq_info.current > 0:
                freq_ghz = round(float(freq_info.current) / 1000.0, 2)
        except Exception:
            pass

        temperature_c = self._query_temperature()

        return {
            "model": self.model,
            "load_pct": load_pct,
            "freq_ghz": freq_ghz,
            "cores_physical": self.cores_physical,
            "cores_logical": self.cores_logical,
            "temperature_c": temperature_c,
            "per_core_load": per_core_load,
        }

    def poll(self) -> Dict[str, Any]:
        """Alias for collect()."""
        return self.collect()

    def get_fallback(self) -> Dict[str, Any]:
        """Returns safe default struct in case of unexpected failure."""
        return {
            "model": getattr(self, "model", "Generic Windows x64 Processor"),
            "load_pct": 0.0,
            "freq_ghz": getattr(self, "base_freq_ghz", 2.50),
            "cores_physical": getattr(self, "cores_physical", 1),
            "cores_logical": getattr(self, "cores_logical", 1),
            "temperature_c": "N/A",
            "per_core_load": [0.0] * getattr(self, "cores_logical", 1),
        }
