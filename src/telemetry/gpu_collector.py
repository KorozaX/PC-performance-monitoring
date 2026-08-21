"""
src/telemetry/gpu_collector.py
Multi-GPU hardware telemetry collector supporting simultaneous multi-GPU discovery
via DXGI 1.1 COM interfaces and Task Manager parity WDDM PDH aggregation with EMA smoothing.
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import logging
import os
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# --- Windows / DXGI Type Definitions ---
HRESULT = ctypes.c_long
UINT = wintypes.UINT
DWORD = wintypes.DWORD
WCHAR = wintypes.WCHAR
SIZE_T = ctypes.c_size_t


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


IID_IDXGIFactory1 = GUID(
    0x770AAE78,
    0xF26F,
    0x4DBA,
    (ctypes.c_byte * 8)(0xA8, 0x29, 0x25, 0x3C, 0x83, 0xD1, 0xB3, 0x87),
)


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", DWORD), ("HighPart", wintypes.LONG)]

    def to_pdh_str(self) -> str:
        return f"0x{self.HighPart & 0xFFFFFFFF:08x}_0x{self.LowPart & 0xFFFFFFFF:08x}".lower()


class DXGI_ADAPTER_DESC1(ctypes.Structure):
    _fields_ = [
        ("Description", WCHAR * 128),
        ("VendorId", UINT),
        ("DeviceId", UINT),
        ("SubSysId", UINT),
        ("Revision", UINT),
        ("DedicatedVideoMemory", SIZE_T),
        ("DedicatedSystemMemory", SIZE_T),
        ("SharedSystemMemory", SIZE_T),
        ("AdapterLuid", LUID),
        ("Flags", UINT),
    ]


# --- NVML Structures ---
class NVML_UTILIZATION(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class NVML_MEMORY(ctypes.Structure):
    _fields_ = [("total", ctypes.c_uint64), ("free", ctypes.c_uint64), ("used", ctypes.c_uint64)]


# --- PDH Structures ---
class PDH_ITEM_DBL(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("CStatus", DWORD), ("doubleValue", ctypes.c_double)]


class PDH_ITEM_LNG(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("CStatus", DWORD), ("largeValue", ctypes.c_int64)]


PDH_FMT_DOUBLE = 0x00000200
PDH_FMT_LARGE = 0x00000400


@dataclass
class GPUAdapterInfo:
    id: int
    name: str
    vendor: str
    gpu_type: str  # "dedicated" | "integrated"
    luid_str: str
    dedicated_bytes: int
    shared_bytes: int
    model: str = ""
    dedicated_vram_gb: float = 0.0
    shared_vram_gb: float = 0.0

    def __post_init__(self):
        if not self.model:
            self.model = self.name
        if self.dedicated_vram_gb == 0.0 and self.dedicated_bytes > 0:
            self.dedicated_vram_gb = round(self.dedicated_bytes / (1024**3), 1)
        if self.shared_vram_gb == 0.0 and self.shared_bytes > 0:
            self.shared_vram_gb = round(self.shared_bytes / (1024**3), 1)


class DXGIEnumerator:
    """Discovers all physical GPUs and extracts LUIDs using DXGI 1.1 COM."""

    @staticmethod
    def enumerate_adapters() -> List[GPUAdapterInfo]:
        adapters: List[GPUAdapterInfo] = []
        if sys.platform != "win32":
            return adapters

        try:
            dxgi = ctypes.windll.dxgi
            pFactory = ctypes.c_void_p()
            hr = dxgi.CreateDXGIFactory1(ctypes.byref(IID_IDXGIFactory1), ctypes.byref(pFactory))
            if hr != 0 or not pFactory.value:
                return adapters

            f_vtbl = ctypes.cast(pFactory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            ReleaseFactory = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(f_vtbl[2])
            EnumAdapters1 = ctypes.WINFUNCTYPE(
                HRESULT, ctypes.c_void_p, UINT, ctypes.POINTER(ctypes.c_void_p)
            )(f_vtbl[12])

            GetDesc1_proto = ctypes.WINFUNCTYPE(
                HRESULT, ctypes.c_void_p, ctypes.POINTER(DXGI_ADAPTER_DESC1)
            )
            ReleaseAdapter_proto = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)

            idx = 0
            while True:
                pAdapter = ctypes.c_void_p()
                hr_enum = EnumAdapters1(pFactory, idx, ctypes.byref(pAdapter))
                if hr_enum != 0 or not pAdapter.value:
                    break

                a_vtbl = ctypes.cast(
                    pAdapter, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
                ).contents
                GetDesc1 = GetDesc1_proto(a_vtbl[10])
                ReleaseAdapter = ReleaseAdapter_proto(a_vtbl[2])

                desc = DXGI_ADAPTER_DESC1()
                if GetDesc1(pAdapter, ctypes.byref(desc)) == 0:
                    is_sw = (desc.Flags & 2) != 0 or desc.VendorId == 0x1414
                    if not is_sw:
                        vendor_map = {
                            0x10DE: "NVIDIA",
                            0x1002: "AMD",
                            0x8086: "Intel",
                            0x5143: "Qualcomm",
                        }
                        vendor = vendor_map.get(desc.VendorId, f"Unknown (0x{desc.VendorId:04X})")
                        is_dedicated = (desc.VendorId == 0x10DE) or (
                            desc.DedicatedVideoMemory >= 1024 * 1024 * 1024
                        )
                        gpu_type = "dedicated" if is_dedicated else "integrated"
                        adapter_name = desc.Description.strip()

                        adapters.append(
                            GPUAdapterInfo(
                                id=len(adapters),
                                name=adapter_name,
                                vendor=vendor,
                                gpu_type=gpu_type,
                                luid_str=desc.AdapterLuid.to_pdh_str(),
                                dedicated_bytes=int(desc.DedicatedVideoMemory),
                                shared_bytes=int(desc.SharedSystemMemory),
                                model=adapter_name,
                                dedicated_vram_gb=round(desc.DedicatedVideoMemory / (1024**3), 1),
                                shared_vram_gb=round(desc.SharedSystemMemory / (1024**3), 1),
                            )
                        )

                ReleaseAdapter(pAdapter)
                idx += 1

            ReleaseFactory(pFactory)
        except Exception as exc:
            logger.debug("DXGI enumeration error: %s", exc)

        return adapters


class CTypesNVML:
    """Pure ctypes wrapper for NVIDIA NVML with Optimus D3 sleep guards."""

    def __init__(self):
        self.available = False
        self.dll = None
        self.handles: Dict[int, ctypes.c_void_p] = {}
        self._init_dll()

    def _init_dll(self):
        if sys.platform != "win32":
            return
        candidates = [
            "nvml.dll",
            os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "nvml.dll"),
            os.path.join(
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                "NVIDIA Corporation",
                "NVSMI",
                "nvml.dll",
            ),
        ]
        for c in candidates:
            try:
                self.dll = ctypes.CDLL(c)
                break
            except Exception:
                continue

        if not self.dll:
            return

        try:
            init_fn = getattr(self.dll, "nvmlInit_v2", getattr(self.dll, "nvmlInit", None))
            if init_fn and init_fn() == 0:
                self.available = True
        except Exception as exc:
            logger.debug("NVML init failed: %s", exc)
            self.available = False

    def map_adapters(self, adapters: List[GPUAdapterInfo]):
        if not self.available or not self.dll:
            return
        try:
            get_count = getattr(
                self.dll, "nvmlDeviceGetCount_v2", getattr(self.dll, "nvmlDeviceGetCount", None)
            )
            get_handle = getattr(
                self.dll,
                "nvmlDeviceGetHandleByIndex_v2",
                getattr(self.dll, "nvmlDeviceGetHandleByIndex", None),
            )
            if not get_count or not get_handle:
                return

            count = ctypes.c_uint(0)
            if get_count(ctypes.byref(count)) == 0:
                for i in range(count.value):
                    h = ctypes.c_void_p()
                    if get_handle(ctypes.c_uint(i), ctypes.byref(h)) == 0:
                        for a in adapters:
                            if a.vendor == "NVIDIA" and a.id not in self.handles:
                                self.handles[a.id] = h
                                break
        except Exception as exc:
            logger.debug("NVML handle mapping error: %s", exc)

    def query_device(self, gpu_id: int) -> Optional[Dict[str, Any]]:
        if not self.available or gpu_id not in self.handles:
            return None

        h = self.handles[gpu_id]
        res: Dict[str, Any] = {
            "load_pct": None,
            "vram_used_bytes": None,
            "vram_total_bytes": None,
            "temperature_c": None,
            "freq_mhz": None,
        }

        try:
            get_util = getattr(self.dll, "nvmlDeviceGetUtilizationRates", None)
            if get_util:
                u = NVML_UTILIZATION()
                if get_util(h, ctypes.byref(u)) == 0:
                    res["load_pct"] = float(u.gpu)

            get_mem = getattr(self.dll, "nvmlDeviceGetMemoryInfo", None)
            if get_mem:
                m = NVML_MEMORY()
                if get_mem(h, ctypes.byref(m)) == 0:
                    res["vram_used_bytes"] = int(m.used)
                    res["vram_total_bytes"] = int(m.total)

            get_temp = getattr(self.dll, "nvmlDeviceGetTemperature", None)
            if get_temp:
                t = ctypes.c_uint(0)
                if get_temp(h, 0, ctypes.byref(t)) == 0:
                    res["temperature_c"] = float(t.value)

            get_clock = getattr(self.dll, "nvmlDeviceGetClockInfo", None)
            if get_clock:
                c = ctypes.c_uint(0)
                if get_clock(h, 0, ctypes.byref(c)) == 0:
                    res["freq_mhz"] = int(c.value)

        except Exception as exc:
            logger.debug("NVML query exception: %s", exc)

        return res

    def shutdown(self):
        if self.available and self.dll:
            try:
                shutdown_fn = getattr(self.dll, "nvmlShutdown", None)
                if shutdown_fn:
                    shutdown_fn()
            except Exception:
                pass
            self.available = False


class PDHGPUMonitor:
    """Monitors GPU Engine and Adapter Memory counters across Intel, AMD, NVIDIA via PDH."""

    def __init__(self):
        self.available = False
        self.hQuery = None
        self.hCounterGpu = None
        self.hCounterMem = None
        self.hCounterSMem = None
        self.re_luid = re.compile(r"luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+)")
        self._init_pdh()

    def _init_pdh(self):
        if sys.platform != "win32":
            return
        try:
            self.pdh = ctypes.windll.pdh
            self.hQuery = wintypes.HANDLE()
            if self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.hQuery)) == 0:
                self.hCounterGpu = wintypes.HANDLE()
                self.pdh.PdhAddEnglishCounterW(
                    self.hQuery,
                    r"\GPU Engine(*)\Utilization Percentage",
                    0,
                    ctypes.byref(self.hCounterGpu),
                )

                self.hCounterMem = wintypes.HANDLE()
                self.pdh.PdhAddEnglishCounterW(
                    self.hQuery,
                    r"\GPU Adapter Memory(*)\Dedicated Usage",
                    0,
                    ctypes.byref(self.hCounterMem),
                )

                self.hCounterSMem = wintypes.HANDLE()
                self.pdh.PdhAddEnglishCounterW(
                    self.hQuery,
                    r"\GPU Adapter Memory(*)\Shared Usage",
                    0,
                    ctypes.byref(self.hCounterSMem),
                )

                self.pdh.PdhCollectQueryData(self.hQuery)
                self.available = True
        except Exception as exc:
            logger.debug("PDH GPU Monitor init error: %s", exc)
            self.available = False

    def collect(self) -> Dict[str, Dict[str, Any]]:
        data_by_luid: Dict[str, Dict[str, Any]] = {}
        if not self.available or not self.hQuery:
            return data_by_luid

        try:
            self.pdh.PdhCollectQueryData(self.hQuery)

            # 1. Utilization
            buf_size = wintypes.DWORD(0)
            item_cnt = wintypes.DWORD(0)
            self.pdh.PdhGetFormattedCounterArrayW(
                self.hCounterGpu,
                PDH_FMT_DOUBLE,
                ctypes.byref(buf_size),
                ctypes.byref(item_cnt),
                None,
            )
            if buf_size.value > 0:
                buf = ctypes.create_string_buffer(buf_size.value)
                if (
                    self.pdh.PdhGetFormattedCounterArrayW(
                        self.hCounterGpu,
                        PDH_FMT_DOUBLE,
                        ctypes.byref(buf_size),
                        ctypes.byref(item_cnt),
                        ctypes.cast(buf, ctypes.c_void_p),
                    )
                    == 0
                ):
                    items = ctypes.cast(buf, ctypes.POINTER(PDH_ITEM_DBL))
                    for k in range(item_cnt.value):
                        name = items[k].szName
                        if name:
                            m = self.re_luid.search(name)
                            if m:
                                lkey = m.group(1).lower()
                                if lkey not in data_by_luid:
                                    data_by_luid[lkey] = {
                                        "load_pct": 0.0,
                                        "dedicated_bytes": 0,
                                        "shared_bytes": 0,
                                    }
                                data_by_luid[lkey]["load_pct"] += items[k].doubleValue

            # 2. Dedicated Memory
            buf_size_m = wintypes.DWORD(0)
            item_cnt_m = wintypes.DWORD(0)
            self.pdh.PdhGetFormattedCounterArrayW(
                self.hCounterMem,
                PDH_FMT_LARGE,
                ctypes.byref(buf_size_m),
                ctypes.byref(item_cnt_m),
                None,
            )
            if buf_size_m.value > 0:
                buf_m = ctypes.create_string_buffer(buf_size_m.value)
                if (
                    self.pdh.PdhGetFormattedCounterArrayW(
                        self.hCounterMem,
                        PDH_FMT_LARGE,
                        ctypes.byref(buf_size_m),
                        ctypes.byref(item_cnt_m),
                        ctypes.cast(buf_m, ctypes.c_void_p),
                    )
                    == 0
                ):
                    items_m = ctypes.cast(buf_m, ctypes.POINTER(PDH_ITEM_LNG))
                    for k in range(item_cnt_m.value):
                        name = items_m[k].szName
                        if name:
                            m = self.re_luid.search(name)
                            if m:
                                lkey = m.group(1).lower()
                                if lkey not in data_by_luid:
                                    data_by_luid[lkey] = {
                                        "load_pct": 0.0,
                                        "dedicated_bytes": 0,
                                        "shared_bytes": 0,
                                    }
                                data_by_luid[lkey]["dedicated_bytes"] = items_m[k].largeValue

            # 3. Shared Memory
            buf_size_s = wintypes.DWORD(0)
            item_cnt_s = wintypes.DWORD(0)
            self.pdh.PdhGetFormattedCounterArrayW(
                self.hCounterSMem,
                PDH_FMT_LARGE,
                ctypes.byref(buf_size_s),
                ctypes.byref(item_cnt_s),
                None,
            )
            if buf_size_s.value > 0:
                buf_s = ctypes.create_string_buffer(buf_size_s.value)
                if (
                    self.pdh.PdhGetFormattedCounterArrayW(
                        self.hCounterSMem,
                        PDH_FMT_LARGE,
                        ctypes.byref(buf_size_s),
                        ctypes.byref(item_cnt_s),
                        ctypes.cast(buf_s, ctypes.c_void_p),
                    )
                    == 0
                ):
                    items_s = ctypes.cast(buf_s, ctypes.POINTER(PDH_ITEM_LNG))
                    for k in range(item_cnt_s.value):
                        name = items_s[k].szName
                        if name:
                            m = self.re_luid.search(name)
                            if m:
                                lkey = m.group(1).lower()
                                if lkey not in data_by_luid:
                                    data_by_luid[lkey] = {
                                        "load_pct": 0.0,
                                        "dedicated_bytes": 0,
                                        "shared_bytes": 0,
                                    }
                                data_by_luid[lkey]["shared_bytes"] = items_s[k].largeValue

        except Exception as exc:
            logger.debug("PDH collect error: %s", exc)

        return data_by_luid

    def close(self):
        if self.available and self.hQuery:
            try:
                self.pdh.PdhCloseQuery(self.hQuery)
            except Exception:
                pass
            self.hQuery = None
            self.available = False


class GPUCollector:
    """
    Unified Multi-GPU Telemetry Coordinator.
    Performs DXGI 1.1 discovery, WDDM PDH aggregation, and EMA smoothing.
    """

    def __init__(self, smoothing_alpha: float = 0.5):
        self._lock = threading.Lock()
        self.alpha = smoothing_alpha
        self.adapters: List[GPUAdapterInfo] = DXGIEnumerator.enumerate_adapters()
        self._smoothed_loads: Dict[int, float] = {}

        if not self.adapters:
            self.adapters = [
                GPUAdapterInfo(
                    id=0,
                    name="Generic Display Adapter",
                    vendor="Unknown",
                    gpu_type="integrated",
                    luid_str="0x00000000_0x00000000",
                    dedicated_bytes=0,
                    shared_bytes=0,
                    model="Generic Display Adapter",
                    dedicated_vram_gb=0.0,
                    shared_vram_gb=0.0,
                )
            ]

        self.nvml = CTypesNVML()
        self.nvml.map_adapters(self.adapters)
        self.pdh = PDHGPUMonitor()

    def collect(self) -> List[Dict[str, Any]]:
        with self._lock:
            pdh_data = self.pdh.collect() if getattr(self.pdh, "available", False) else {}
            gpu_list = []

            for adapter in self.adapters:
                lkey = adapter.luid_str
                pdh_entry = pdh_data.get(
                    lkey, {"load_pct": 0.0, "dedicated_bytes": 0, "shared_bytes": 0}
                )

                nvml_entry = None
                if adapter.vendor == "NVIDIA":
                    try:
                        nvml_entry = self.nvml.query_device(adapter.id)
                    except Exception as exc:
                        logger.debug("NVML query error on GPU %d: %s", adapter.id, exc)

                # 1. Utilization & EMA Smoothing
                raw_load = 0.0
                if pdh_entry["load_pct"] > 0:
                    raw_load = float(pdh_entry["load_pct"])
                elif nvml_entry and nvml_entry["load_pct"] is not None:
                    raw_load = float(nvml_entry["load_pct"])

                raw_load = min(100.0, max(0.0, raw_load))

                prev_smooth = self._smoothed_loads.get(adapter.id, raw_load)
                smoothed_load = self.alpha * raw_load + (1.0 - self.alpha) * prev_smooth
                if smoothed_load < 0.5:
                    smoothed_load = 0.0
                self._smoothed_loads[adapter.id] = smoothed_load
                load_pct = round(min(100.0, max(0.0, smoothed_load)), 1)

                # 2. Clocks & Temperature
                if nvml_entry and nvml_entry["freq_mhz"] is not None:
                    clock_mhz: Union[int, str] = int(nvml_entry["freq_mhz"])
                else:
                    clock_mhz = "N/A"

                if nvml_entry and nvml_entry["temperature_c"] is not None:
                    temp_c: Union[float, str] = round(float(nvml_entry["temperature_c"]), 1)
                else:
                    temp_c = "N/A"

                # 3. VRAM (MB and GB Dual Metrics)
                if (
                    nvml_entry
                    and nvml_entry.get("vram_used_bytes") is not None
                    and nvml_entry.get("vram_total_bytes") is not None
                ):
                    used_b = nvml_entry["vram_used_bytes"]
                    tot_b = nvml_entry["vram_total_bytes"]
                else:
                    if adapter.dedicated_bytes > 0:
                        used_b = pdh_entry["dedicated_bytes"]
                        tot_b = adapter.dedicated_bytes
                    else:
                        used_b = pdh_entry["shared_bytes"]
                        tot_b = adapter.shared_bytes

                vram_used_gb = round(used_b / (1024**3), 1)
                vram_used_mb = round(used_b / (1024**2), 1)

                if tot_b > 0:
                    vram_total_gb: Union[float, str] = round(tot_b / (1024**3), 1)
                    vram_total_mb: Union[float, str] = round(tot_b / (1024**2), 1)
                else:
                    vram_total_gb = "N/A"
                    vram_total_mb = "N/A"

                gpu_dict = {
                    "id": adapter.id,
                    "name": adapter.name,
                    "model": adapter.model,
                    "vendor": adapter.vendor,
                    "type": adapter.gpu_type,
                    "utilization_pct": load_pct,
                    "load_pct": load_pct,
                    "clock_mhz": clock_mhz,
                    "freq_mhz": clock_mhz,
                    "vram_used_gb": vram_used_gb,
                    "vram_total_gb": vram_total_gb,
                    "vram_used_mb": vram_used_mb,
                    "vram_total_mb": vram_total_mb,
                    "temperature_c": temp_c,
                }
                gpu_list.append(gpu_dict)

            return gpu_list

    def poll(self) -> List[Dict[str, Any]]:
        return self.collect()

    def get_gpus(self) -> List[Dict[str, Any]]:
        return self.collect()

    def get_fallback(self) -> List[Dict[str, Any]]:
        fallback_list = []
        for adapter in getattr(self, "adapters", []):
            tot_gb = (
                round(adapter.dedicated_bytes / (1024**3), 1)
                if adapter.dedicated_bytes > 0
                else "N/A"
            )
            tot_mb = (
                round(adapter.dedicated_bytes / (1024**2), 1)
                if adapter.dedicated_bytes > 0
                else "N/A"
            )
            fallback_list.append(
                {
                    "id": adapter.id,
                    "name": adapter.name,
                    "model": adapter.model,
                    "vendor": adapter.vendor,
                    "type": adapter.gpu_type,
                    "utilization_pct": 0.0,
                    "load_pct": 0.0,
                    "clock_mhz": "N/A",
                    "freq_mhz": "N/A",
                    "vram_used_gb": 0.0,
                    "vram_total_gb": tot_gb,
                    "vram_used_mb": 0.0,
                    "vram_total_mb": tot_mb,
                    "temperature_c": "N/A",
                }
            )
        if not fallback_list:
            fallback_list.append(
                {
                    "id": 0,
                    "name": "Generic Display Adapter",
                    "model": "Generic Display Adapter",
                    "vendor": "Unknown",
                    "type": "integrated",
                    "utilization_pct": 0.0,
                    "load_pct": 0.0,
                    "clock_mhz": "N/A",
                    "freq_mhz": "N/A",
                    "vram_used_gb": 0.0,
                    "vram_total_gb": "N/A",
                    "vram_used_mb": 0.0,
                    "vram_total_mb": "N/A",
                    "temperature_c": "N/A",
                }
            )
        return fallback_list

    def shutdown(self):
        with self._lock:
            if self.pdh:
                self.pdh.close()
            if self.nvml:
                self.nvml.shutdown()
