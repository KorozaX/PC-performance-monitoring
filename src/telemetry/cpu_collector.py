"""
src/telemetry/cpu_collector.py
High-performance CPU hardware telemetry collector for Windows.
Extracts processor name, clock frequency (MHz/GHz), overall utilization %,
per-core/thread loads, physical/logical core counts, and multi-layered CPU thermals.
"""

import ctypes
from ctypes import wintypes
import logging
import platform
import sys
from typing import Any, Dict, List, Union

import psutil

logger = logging.getLogger(__name__)


class PDH_ITEM_DBL(ctypes.Structure):
    _fields_ = [
        ("szName", wintypes.LPWSTR),
        ("CStatus", wintypes.DWORD),
        ("doubleValue", ctypes.c_double),
    ]


class CPUThermalProbe:
    """Low-overhead multi-layer thermal probe for Intel & AMD CPUs."""

    def __init__(self):
        self.pdh_available = False
        self.hQuery = None
        self.hCounter = None
        self.pdh = None
        self._init_pdh()

    def _init_pdh(self):
        if sys.platform != "win32":
            return
        try:
            self.pdh = ctypes.windll.pdh
            h_query = wintypes.HANDLE()
            if self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(h_query)) == 0:
                h_counter = wintypes.HANDLE()
                res = self.pdh.PdhAddEnglishCounterW(
                    h_query,
                    r"\Thermal Zone Information(*)\Temperature",
                    0,
                    ctypes.byref(h_counter),
                )
                if res == 0:
                    self.hQuery = h_query
                    self.hCounter = h_counter
                    self.pdh.PdhCollectQueryData(self.hQuery)
                    self.pdh_available = True
                else:
                    self.pdh.PdhCloseQuery(h_query)
        except Exception as exc:
            logger.debug("PDH Thermal Zone init error: %s", exc)
            self.pdh_available = False

    def query(self) -> Union[float, str]:
        # Layer 1: psutil sensors_temperatures (if present on platform or mocked in tests)
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if isinstance(temps, dict):
                    if not temps:
                        return "N/A"
                    for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz", "cpu-thermal"]:
                        if name in temps and temps[name]:
                            val = temps[name][0].current
                            if val is not None and 20.0 <= val <= 115.0:
                                return round(float(val), 1)
                    for entries in temps.values():
                        if entries and getattr(entries[0], "current", None) is not None:
                            val = entries[0].current
                            if 20.0 <= val <= 115.0:
                                return round(float(val), 1)
                    return "N/A"
        except Exception:
            pass

        # Layer 2: Windows PDH Thermal Zone Information
        if self.pdh_available and self.hQuery and self.hCounter and self.pdh:
            try:
                self.pdh.PdhCollectQueryData(self.hQuery)
                buf_size = wintypes.DWORD(0)
                item_cnt = wintypes.DWORD(0)
                self.pdh.PdhGetFormattedCounterArrayW(
                    self.hCounter,
                    0x00000200,  # PDH_FMT_DOUBLE
                    ctypes.byref(buf_size),
                    ctypes.byref(item_cnt),
                    None,
                )
                if buf_size.value > 0:
                    buf = ctypes.create_string_buffer(buf_size.value)
                    if (
                        self.pdh.PdhGetFormattedCounterArrayW(
                            self.hCounter,
                            0x00000200,
                            ctypes.byref(buf_size),
                            ctypes.byref(item_cnt),
                            ctypes.cast(buf, ctypes.c_void_p),
                        )
                        == 0
                    ):
                        items = ctypes.cast(buf, ctypes.POINTER(PDH_ITEM_DBL))
                        valid_temps = []
                        for i in range(item_cnt.value):
                            kelvin = items[i].doubleValue
                            celsius = kelvin - 273.15
                            if 20.0 <= celsius <= 115.0:
                                valid_temps.append(celsius)
                        if valid_temps:
                            return round(float(max(valid_temps)), 1)
            except Exception as exc:
                logger.debug("PDH thermal query exception: %s", exc)

        # Layer 3: Graceful N/A
        return "N/A"

    def close(self):
        if self.pdh_available and self.hQuery and self.pdh:
            try:
                self.pdh.PdhCloseQuery(self.hQuery)
            except Exception:
                pass
            self.hQuery = None
            self.hCounter = None
            self.pdh_available = False


class CPUCollector:
    """
    Collects real-time CPU performance metrics and static hardware specifications.
    Uses non-blocking psutil time-delta calculations and WinReg queries.
    """

    def __init__(self):
        self.name: str = self._query_cpu_model()
        self.model: str = self.name
        self.cores_physical: int = psutil.cpu_count(logical=False) or 1
        self.cores_logical: int = psutil.cpu_count(logical=True) or 1
        self.base_freq_mhz: float = self._query_base_freq_mhz()
        self.base_freq_ghz: float = round(self.base_freq_mhz / 1000.0, 2)
        self.thermal_probe = CPUThermalProbe()

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

    def _query_base_freq_mhz(self) -> float:
        """Queries base processor frequency in MHz."""
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
                    return float(mhz)
            except Exception as exc:
                logger.debug("WinReg ~MHz query error: %s", exc)

        try:
            freq = psutil.cpu_freq()
            if freq and freq.max and freq.max > 0:
                return float(freq.max)
            if freq and freq.current and freq.current > 0:
                return float(freq.current)
        except Exception:
            pass

        return 2500.0

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
            per_core_utilization = [
                min(100.0, max(0.0, round(float(c), 1)))
                for c in per_core_raw
            ]
        except Exception:
            per_core_utilization = [load_pct] * self.cores_logical

        freq_mhz = self.base_freq_mhz
        try:
            freq_info = psutil.cpu_freq()
            if freq_info and freq_info.current and freq_info.current > 0:
                freq_mhz = round(float(freq_info.current), 1)
        except Exception:
            pass

        freq_ghz = round(freq_mhz / 1000.0, 2)
        temperature_c = self.thermal_probe.query()

        return {
            "name": self.name,
            "model": self.name,
            "cores_physical": self.cores_physical,
            "cores_logical": self.cores_logical,
            "utilization_pct": load_pct,
            "load_pct": load_pct,
            "frequency_mhz": freq_mhz,
            "freq_ghz": freq_ghz,
            "temperature_c": temperature_c,
            "per_core_utilization": per_core_utilization,
            "per_core_load": per_core_utilization,
        }

    def poll(self) -> Dict[str, Any]:
        """Alias for collect()."""
        return self.collect()

    def get_fallback(self) -> Dict[str, Any]:
        """Returns safe default struct in case of unexpected failure."""
        name = getattr(self, "name", getattr(self, "model", "Generic Windows x64 Processor"))
        freq_mhz = getattr(self, "base_freq_mhz", 2500.0)
        freq_ghz = round(freq_mhz / 1000.0, 2)
        cores_phys = getattr(self, "cores_physical", 1)
        cores_log = getattr(self, "cores_logical", 1)
        return {
            "name": name,
            "model": name,
            "cores_physical": cores_phys,
            "cores_logical": cores_log,
            "utilization_pct": 0.0,
            "load_pct": 0.0,
            "frequency_mhz": freq_mhz,
            "freq_ghz": freq_ghz,
            "temperature_c": "N/A",
            "per_core_utilization": [0.0] * cores_log,
            "per_core_load": [0.0] * cores_log,
        }

    def shutdown(self):
        """Releases thermal probe handles."""
        if hasattr(self, "thermal_probe") and self.thermal_probe:
            self.thermal_probe.close()
