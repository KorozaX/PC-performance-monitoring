"""
src/telemetry/thermals.py
Consolidated Thermal Aggregator for CPU, Multi-GPU, and Storage SSDs.
Formats temperature values into standard contract types and provides graceful 'N/A' fallbacks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union


class ThermalAggregator:
    """
    Consolidates temperature readings from CPU, Multi-GPU, and Storage collectors,
    applying strict type formatting, multi-sensor arbitration, and graceful 'N/A' fallbacks.
    """

    @staticmethod
    def aggregate(
        cpu_data: Optional[Dict[str, Any]] = None,
        gpus_data: Optional[List[Dict[str, Any]]] = None,
        storage_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Union[float, str]]:
        # 1. CPU Temperature
        cpu_t = cpu_data.get("temperature_c") if isinstance(cpu_data, dict) else None
        cpu_c: Union[float, str] = (
            round(float(cpu_t), 1) if isinstance(cpu_t, (int, float)) and cpu_t > 0 else "N/A"
        )

        # 2. dGPU & iGPU Temperatures
        dgpu_c: Union[float, str] = "N/A"
        igpu_c: Union[float, str] = "N/A"

        if isinstance(gpus_data, list):
            for g in gpus_data:
                if not isinstance(g, dict):
                    continue
                g_type = g.get("type")
                t_val = g.get("temperature_c")
                if isinstance(t_val, (int, float)) and t_val > 0:
                    if g_type == "dedicated" and dgpu_c == "N/A":
                        dgpu_c = round(float(t_val), 1)
                    elif g_type == "integrated" and igpu_c == "N/A":
                        igpu_c = round(float(t_val), 1)

        # 3. SSD Temperature (Max valid temp among all active drives)
        ssd_c: Union[float, str] = "N/A"
        if isinstance(storage_data, dict) and "drives" in storage_data:
            valid_ssd_temps = [
                d["temperature_c"]
                for d in storage_data["drives"]
                if isinstance(d, dict)
                and isinstance(d.get("temperature_c"), (int, float))
                and d["temperature_c"] > 0
            ]
            if valid_ssd_temps:
                ssd_c = round(float(max(valid_ssd_temps)), 1)

        # Primary GPU alias for legacy UI components and tests
        gpu_c: Union[float, str] = dgpu_c if dgpu_c != "N/A" else igpu_c

        return {
            "cpu_c": cpu_c,
            "dgpu_c": dgpu_c,
            "igpu_c": igpu_c,
            "gpu_c": gpu_c,
            "ssd_c": ssd_c,
        }

    def get_temperatures(
        self,
        cpu_data: Optional[Dict[str, Any]] = None,
        gpus_data: Optional[List[Dict[str, Any]]] = None,
        storage_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Union[float, str]]:
        return self.aggregate(cpu_data, gpus_data, storage_data)
