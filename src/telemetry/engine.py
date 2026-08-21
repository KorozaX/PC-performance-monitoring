"""
src/telemetry/engine.py
Hardware Telemetry Coordinator Daemon.
Polls all hardware telemetry subsystems at ~1000ms intervals with drift compensation,
manages asynchronous hardware discovery, hydrates Tick-0 instant snapshots from local cache,
caches the latest immutable snapshot under a thread-safe lock, and broadcasts snapshots to subscribers.
"""

import copy
import json
import logging
import os
import platform
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from src.telemetry.cpu_collector import CPUCollector
from src.telemetry.gpu_collector import GPUCollector
from src.telemetry.network_collector import NetworkCollector
from src.telemetry.process_collector import ProcessCollector
from src.telemetry.ram_collector import RAMCollector
from src.telemetry.storage_collector import StorageCollector
from src.telemetry.thermals import ThermalAggregator

logger = logging.getLogger(__name__)


def query_system_info() -> Dict[str, str]:
    """Queries static OS version, architecture, motherboard, and BIOS version in < 1ms."""
    cpu_arch = platform.machine()
    if cpu_arch.upper() in ("AMD64", "X86_64", "EM64T"):
        cpu_arch = "x86_64"

    info: Dict[str, str] = {
        "os": f"Windows {platform.version()}",
        "cpu_arch": cpu_arch,
        "motherboard": "Standard OEM",
        "bios_version": "N/A",
    }

    if sys.platform == "win32":
        try:
            import winreg

            k = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
            )
            pname, _ = winreg.QueryValueEx(k, "ProductName")
            disp, _ = winreg.QueryValueEx(k, "DisplayVersion")
            build, _ = winreg.QueryValueEx(k, "CurrentBuild")
            info["os"] = f"{pname} {disp} (Build {build})"
            winreg.CloseKey(k)
        except Exception as exc:
            logger.debug("WinReg OS version query error: %s", exc)

        try:
            import winreg

            k = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\BIOS",
            )
            try:
                mfg, _ = winreg.QueryValueEx(k, "BaseBoardManufacturer")
                prod, _ = winreg.QueryValueEx(k, "BaseBoardProduct")
                mb = f"{mfg} {prod}".strip()
                if mb:
                    info["motherboard"] = mb
            except Exception:
                pass
            try:
                bios, _ = winreg.QueryValueEx(k, "BIOSVersion")
                if bios:
                    info["bios_version"] = str(bios).strip()
            except Exception:
                pass
            winreg.CloseKey(k)
        except Exception as exc:
            logger.debug("WinReg BIOS query error: %s", exc)

    return info


class HardwareProfileManager:
    """Manages atomic caching of hardware discovery profiles in .cache/hw_profile.json."""

    CACHE_VERSION = 1
    CACHE_DIR = os.path.abspath(
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".cache")
    )
    CACHE_FILE = os.path.join(CACHE_DIR, "hw_profile.json")

    @classmethod
    def load_cache(cls) -> Optional[Dict[str, Any]]:
        """Loads cached hardware profile in < 2ms. Returns None on miss or invalid format."""
        try:
            if not os.path.exists(cls.CACHE_FILE):
                return None
            with open(cls.CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("version") == cls.CACHE_VERSION:
                return data
        except Exception as exc:
            logger.debug("Failed to read hw_profile cache: %s", exc)
        return None

    @classmethod
    def save_cache(cls, profile: Dict[str, Any]) -> bool:
        """Atomically writes hardware profile to prevent corrupt file reads."""
        try:
            os.makedirs(cls.CACHE_DIR, exist_ok=True)
            tmp_path = cls.CACHE_FILE + ".tmp"
            payload = {
                "version": cls.CACHE_VERSION,
                "timestamp": time.time(),
                **profile,
            }
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, cls.CACHE_FILE)
            return True
        except Exception as exc:
            logger.debug("Failed to save hw_profile cache: %s", exc)
            return False


class TelemetryEngine:
    """
    Coordinates hardware telemetry gathering across CPU, RAM, Multi-GPU, Processes, Storage, and Network.
    Executes in a background daemon thread with drift-compensated interval timing.
    """

    def __init__(self, interval_ms: int = 1000):
        self.interval_ms: int = interval_ms
        self.interval_sec: float = max(0.1, interval_ms / 1000.0)

        # Thread synchronization & state
        self._lock = threading.Lock()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Static system info
        self._system_info: Dict[str, str] = query_system_info()

        # Initialize sub-collectors
        self.cpu_collector = CPUCollector()
        self.ram_collector = RAMCollector()
        self.gpu_collector = GPUCollector()
        self.process_collector = ProcessCollector()
        self.storage_collector = StorageCollector()
        self.network_collector = NetworkCollector()
        self.thermal_aggregator = ThermalAggregator()

        # Tick-0 instant snapshot generation
        self._latest_snapshot: Dict[str, Any] = self._generate_initial_snapshot()

        # Asynchronous background hardware discovery & cache hydration
        self._discovery_thread = threading.Thread(
            target=self._async_hardware_discovery,
            name="HardwareDiscoveryThread",
            daemon=True,
        )
        self._discovery_thread.start()

    def _async_hardware_discovery(self) -> None:
        """Executes full hardware discovery in the background and saves to cache."""
        try:
            # Re-check system info
            sys_info = query_system_info()

            # Hardware profile payload
            profile = {
                "cpu": {
                    "name": self.cpu_collector.name,
                    "model": self.cpu_collector.model,
                    "cores_physical": self.cpu_collector.cores_physical,
                    "cores_logical": self.cpu_collector.cores_logical,
                    "base_freq_mhz": self.cpu_collector.base_freq_mhz,
                },
                "gpus": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "model": g.model,
                        "vendor": g.vendor,
                        "gpu_type": g.gpu_type,
                        "luid_str": g.luid_str,
                        "dedicated_vram_gb": g.dedicated_vram_gb,
                        "shared_vram_gb": g.shared_vram_gb,
                    }
                    for g in getattr(self.gpu_collector, "adapters", [])
                ],
                "ram": {
                    "total_gb": getattr(self.ram_collector, "total_gb", 64.0),
                    "type_badge": self.ram_collector.type_badge,
                    "memory_type": self.ram_collector.memory_type,
                    "speed_mhz": self.ram_collector.speed_mhz,
                },
                "storage": {
                    "drives": [
                        {
                            "device": k,
                            "letter": k,
                            "type_badge": v.get("type_badge", "Storage Drive"),
                            "mount": v.get("mount", f"{k}\\"),
                        }
                        for k, v in getattr(self.storage_collector, "device_cache", {}).items()
                    ]
                },
                "system_info": sys_info,
            }

            HardwareProfileManager.save_cache(profile)

            with self._lock:
                self._system_info = sys_info
        except Exception as exc:
            logger.debug("Async hardware discovery error: %s", exc)

    def _generate_initial_snapshot(self) -> Dict[str, Any]:
        """Generates a default initial snapshot conforming to the interface contract."""
        cached_profile = HardwareProfileManager.load_cache()

        cpu_data = self.cpu_collector.get_fallback()
        ram_data = self.ram_collector.get_fallback()
        gpu_data = self.gpu_collector.get_fallback()
        process_data = self.process_collector.get_fallback()
        storage_data = self.storage_collector.get_fallback()
        network_data = self.network_collector.get_fallback()
        thermal_data = self.thermal_aggregator.aggregate(cpu_data, gpu_data, storage_data)

        # Hydrate from cache if available for instant warm start
        if isinstance(cached_profile, dict):
            cached_sys_info = cached_profile.get("system_info")
            if isinstance(cached_sys_info, dict):
                for k, v in cached_sys_info.items():
                    if isinstance(k, str) and isinstance(v, str):
                        self._system_info[k] = v

            c = cached_profile.get("cpu")
            if isinstance(c, dict):
                if isinstance(c.get("name"), str):
                    cpu_data["name"] = c["name"]
                if isinstance(c.get("model"), str):
                    cpu_data["model"] = c["model"]
                if isinstance(c.get("cores_physical"), int) and not isinstance(c.get("cores_physical"), bool):
                    cpu_data["cores_physical"] = c["cores_physical"]
                if isinstance(c.get("cores_logical"), int) and not isinstance(c.get("cores_logical"), bool):
                    cpu_data["cores_logical"] = c["cores_logical"]

        return {
            "timestamp": time.time(),
            "cpu": cpu_data,
            "gpus": gpu_data,
            "ram": ram_data,
            "processes": process_data,
            "storage": storage_data,
            "network": network_data,
            "thermals": thermal_data,
            "system_info": self._system_info,
        }

    def poll_once(self) -> Dict[str, Any]:
        """
        Executes a single synchronous telemetry polling cycle across all subsystems.
        Updates internal cached snapshot and returns a deep copy.
        """
        # 1. CPU
        try:
            cpu_data = self.cpu_collector.collect()
        except Exception as exc:
            logger.error("CPU Collector error: %s", exc)
            cpu_data = self.cpu_collector.get_fallback()

        # 2. RAM
        try:
            ram_data = self.ram_collector.collect()
        except Exception as exc:
            logger.error("RAM Collector error: %s", exc)
            ram_data = self.ram_collector.get_fallback()

        # 3. GPUs
        try:
            gpu_data = self.gpu_collector.collect()
        except Exception as exc:
            logger.error("GPU Collector error: %s", exc)
            gpu_data = self.gpu_collector.get_fallback()

        # 4. Processes
        try:
            process_data = self.process_collector.collect()
        except Exception as exc:
            logger.error("Process Collector error: %s", exc)
            process_data = self.process_collector.get_fallback()

        # 5. Storage
        try:
            storage_data = self.storage_collector.collect()
        except Exception as exc:
            logger.error("Storage Collector error: %s", exc)
            storage_data = self.storage_collector.get_fallback()

        # 6. Network
        try:
            network_data = self.network_collector.collect()
        except Exception as exc:
            logger.error("Network Collector error: %s", exc)
            network_data = self.network_collector.get_fallback()

        # 7. Thermals
        try:
            thermal_data = self.thermal_aggregator.aggregate(cpu_data, gpu_data, storage_data)
        except Exception as exc:
            logger.error("Thermal Aggregator error: %s", exc)
            thermal_data = {
                "cpu_c": "N/A",
                "dgpu_c": "N/A",
                "igpu_c": "N/A",
                "gpu_c": "N/A",
                "ssd_c": "N/A",
            }

        snapshot = {
            "timestamp": time.time(),
            "cpu": cpu_data,
            "gpus": gpu_data,
            "ram": ram_data,
            "processes": process_data,
            "storage": storage_data,
            "network": network_data,
            "thermals": thermal_data,
            "system_info": self._system_info,
        }

        with self._lock:
            self._latest_snapshot = snapshot

        return copy.deepcopy(snapshot)

    def _worker_loop(self):
        """Background worker loop executing with monotonic drift compensation."""
        next_tick = time.perf_counter()
        while self._running:
            try:
                snapshot = self.poll_once()

                # Dispatch to subscribers outside of lock
                with self._lock:
                    subscribers = list(self._subscribers)

                for cb in subscribers:
                    try:
                        cb(snapshot)
                    except Exception as exc:
                        logger.error("Subscriber callback exception: %s", exc)

            except Exception as exc:
                logger.error("Unexpected error in telemetry loop: %s", exc)

            # Drift-compensated sleep
            next_tick += self.interval_sec
            sleep_time = next_tick - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # Prevent runaway drift if a lag spike occurred
                next_tick = time.perf_counter()

    def start(self) -> None:
        """Starts the background telemetry daemon thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._worker_loop, name="TelemetryEngineThread", daemon=True
            )
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Gracefully signals the worker thread to stop and joins."""
        with self._lock:
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            self._thread = None

        if hasattr(self, "_discovery_thread") and self._discovery_thread and self._discovery_thread.is_alive():
            self._discovery_thread.join(timeout=timeout)
            self._discovery_thread = None

        # Cleanly release native handles
        try:
            self.process_collector.shutdown()
        except Exception:
            pass

        try:
            self.gpu_collector.shutdown()
        except Exception:
            pass

        try:
            self.cpu_collector.shutdown()
        except Exception:
            pass

    def is_running(self) -> bool:
        """Returns True if the worker thread is running."""
        with self._lock:
            return self._running and (self._thread is not None and self._thread.is_alive())

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Registers a listener callback invoked on every telemetry tick."""
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Removes a registered listener callback."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def get_snapshot(self) -> Dict[str, Any]:
        """Returns a thread-safe deep copy of the latest telemetry snapshot dictionary."""
        with self._lock:
            return copy.deepcopy(self._latest_snapshot)
