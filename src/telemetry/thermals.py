"""
src/telemetry/thermals.py
Consolidated Thermal Aggregator for CPU, GPU(s), and SSDs.
Formats temperature values into standard contract types and provides graceful 'N/A' fallbacks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union


class ThermalAggregator:
    """
    Consolidates temperature readings from CPU, GPU, and Storage collectors,
    applying strict type formatting and graceful 'N/A' fallbacks.
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
            round(float(cpu_t), 1) if isinstance(cpu_t, (int, float)) else "N/A"
        )

        # 2. GPU Temperature (Priority: dedicated GPU > max valid temp > "N/A")
        gpu_c: Union[float, str] = "N/A"
        if isinstance(gpus_data, list) and gpus_data:
            dgpu_temps = [
                g["temperature_c"]
                for g in gpus_data
                if isinstance(g, dict)
                and g.get("type") == "dedicated"
                and isinstance(g.get("temperature_c"), (int, float))
            ]
            if dgpu_temps:
                gpu_c = round(float(max(dgpu_temps)), 1)
            else:
                all_gpu_temps = [
                    g["temperature_c"]
                    for g in gpus_data
                    if isinstance(g, dict) and isinstance(g.get("temperature_c"), (int, float))
                ]
                if all_gpu_temps:
                    gpu_c = round(float(max(all_gpu_temps)), 1)

        # 3. SSD Temperature
        ssd_c: Union[float, str] = "N/A"
        if isinstance(storage_data, dict) and "drives" in storage_data:
            valid_ssd_temps = [
                d["temperature_c"]
                for d in storage_data["drives"]
                if isinstance(d, dict) and isinstance(d.get("temperature_c"), (int, float))
            ]
            if valid_ssd_temps:
                ssd_c = round(float(max(valid_ssd_temps)), 1)

        return {
            "cpu_c": cpu_c,
            "gpu_c": gpu_c,
            "ssd_c": ssd_c,
        }
