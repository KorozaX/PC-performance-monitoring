"""
src/telemetry/engine.py
Hardware Telemetry Coordinator Daemon.
Polls all hardware telemetry subsystems at ~1000ms intervals with drift compensation,
caches the latest immutable snapshot under a thread-safe lock, and broadcasts snapshots to subscribers.
"""

import copy
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from src.telemetry.cpu_collector import CPUCollector
from src.telemetry.gpu_collector import GPUCollector
from src.telemetry.network_collector import NetworkCollector
from src.telemetry.ram_collector import RAMCollector
from src.telemetry.storage_collector import StorageCollector
from src.telemetry.thermals import ThermalAggregator

logger = logging.getLogger(__name__)


class TelemetryEngine:
    """
    Coordinates hardware telemetry gathering across CPU, RAM, Multi-GPU, Storage, and Network.
    Executes in a background daemon thread with drift-compensated interval timing.
    """

    def __init__(self, interval_ms: int = 1000):
        self.interval_ms: int = interval_ms
        self.interval_sec: float = max(0.1, interval_ms / 1000.0)

        # Initialize sub-collectors
        self.cpu_collector = CPUCollector()
        self.ram_collector = RAMCollector()
        self.gpu_collector = GPUCollector()
        self.storage_collector = StorageCollector()
        self.network_collector = NetworkCollector()
        self.thermal_aggregator = ThermalAggregator()

        # Thread synchronization & state
        self._lock = threading.Lock()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._latest_snapshot: Dict[str, Any] = self._generate_initial_snapshot()

    def _generate_initial_snapshot(self) -> Dict[str, Any]:
        """Generates a default initial snapshot conforming to the interface contract."""
        cpu_data = self.cpu_collector.get_fallback()
        ram_data = self.ram_collector.get_fallback()
        gpu_data = self.gpu_collector.get_fallback()
        storage_data = self.storage_collector.get_fallback()
        network_data = self.network_collector.get_fallback()
        thermal_data = self.thermal_aggregator.aggregate(cpu_data, gpu_data, storage_data)

        return {
            "timestamp": time.time(),
            "cpu": cpu_data,
            "gpus": gpu_data,
            "ram": ram_data,
            "storage": storage_data,
            "network": network_data,
            "thermals": thermal_data,
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

        # 4. Storage
        try:
            storage_data = self.storage_collector.collect()
        except Exception as exc:
            logger.error("Storage Collector error: %s", exc)
            storage_data = self.storage_collector.get_fallback()

        # 5. Network
        try:
            network_data = self.network_collector.collect()
        except Exception as exc:
            logger.error("Network Collector error: %s", exc)
            network_data = self.network_collector.get_fallback()

        # 6. Thermals
        try:
            thermal_data = self.thermal_aggregator.aggregate(cpu_data, gpu_data, storage_data)
        except Exception as exc:
            logger.error("Thermal Aggregator error: %s", exc)
            thermal_data = {"cpu_c": "N/A", "gpu_c": "N/A", "ssd_c": "N/A"}

        snapshot = {
            "timestamp": time.time(),
            "cpu": cpu_data,
            "gpus": gpu_data,
            "ram": ram_data,
            "storage": storage_data,
            "network": network_data,
            "thermals": thermal_data,
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
            if not self._running:
                return
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            self._thread = None

        # Cleanly release native handles
        try:
            self.gpu_collector.shutdown()
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
