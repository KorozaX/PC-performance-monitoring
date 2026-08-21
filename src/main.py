"""
src/main.py
Application Entry Point and Headless Telemetry Test CLI Handler.
Supports headless verification, latency benchmarking, and GUI launch.
"""

import argparse
import json
import logging
import os
import statistics
import sys
import time
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.telemetry.engine import TelemetryEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")


def _attach_console_if_needed():
    """
    Ensures sys.stdout and sys.stderr are functional in a PyInstaller windowed (--noconsole) build.
    1. If standard handles (pipes/redirects) were provided by caller, re-opens them via GetStdHandle.
    2. If launched from a terminal without pipes, attaches to parent console via AttachConsole.
    3. If running headless without terminal or pipes, redirects to os.devnull.
    """
    if sys.platform != "win32":
        return

    import ctypes
    import io
    import msvcrt

    STD_OUTPUT_HANDLE = -11
    STD_ERROR_HANDLE = -12
    INVALID_HANDLE_VALUE = -1

    def _get_stream(std_handle_id: int):
        try:
            handle = ctypes.windll.kernel32.GetStdHandle(std_handle_id)
            if handle and handle != INVALID_HANDLE_VALUE:
                file_type = ctypes.windll.kernel32.GetFileType(handle)
                # 1 = FILE_TYPE_DISK, 2 = FILE_TYPE_CHAR, 3 = FILE_TYPE_PIPE
                if file_type in (1, 2, 3):
                    fd = msvcrt.open_osfhandle(handle, 0)
                    return io.open(fd, mode="w", encoding="utf-8", errors="replace", closefd=False)
        except Exception:
            pass
        return None

    # Recover pipes/redirection if present
    if sys.stdout is None or getattr(sys.stdout, "closed", False):
        recovered_out = _get_stream(STD_OUTPUT_HANDLE)
        if recovered_out is not None:
            sys.stdout = recovered_out

    if sys.stderr is None or getattr(sys.stderr, "closed", False):
        recovered_err = _get_stream(STD_ERROR_HANDLE)
        if recovered_err is not None:
            sys.stderr = recovered_err

    # If still None, attempt AttachConsole to parent terminal
    if sys.stdout is None or sys.stderr is None:
        try:
            if ctypes.windll.kernel32.AttachConsole(0xFFFFFFFF):
                if sys.stdout is None:
                    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                if sys.stderr is None:
                    sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Fallback to devnull to avoid NoneType attribute errors
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def print_snapshot_table(snapshot: Dict[str, Any], sample_num: int, total_samples: int):
    """Prints a rich terminal display of the telemetry snapshot."""
    print(f"\n==================== TELEMETRY SNAPSHOT [{sample_num}/{total_samples}] ====================")
    print(f"Timestamp: {snapshot.get('timestamp')}")

    cpu = snapshot.get("cpu", {})
    cpu_name = cpu.get("name") or cpu.get("model")
    cpu_load = cpu.get("utilization_pct") if "utilization_pct" in cpu else cpu.get("load_pct")
    cpu_freq = cpu.get("frequency_mhz") or (cpu.get("freq_ghz", 0) * 1000)
    print(
        f"CPU:       {cpu_name} | Load: {cpu_load}% | Freq: {cpu_freq} MHz | Temp: {cpu.get('temperature_c')}°C"
    )

    ram = snapshot.get("ram", {})
    dist = ram.get("distribution", {})
    ram_load = ram.get("utilization_pct") if "utilization_pct" in ram else ram.get("load_pct")
    print(
        f"RAM:       {ram.get('used_mb'):,} MB / {ram.get('total_mb'):,} MB ({ram.get('used_gb')}/{ram.get('total_gb')} GB, {ram_load}%) | Badge: {ram.get('type_badge')} | In-Use: {dist.get('in_use_pct')}% Cached: {dist.get('cached_pct')}% Free: {dist.get('free_pct')}%"
    )

    for g in snapshot.get("gpus", []):
        g_name = g.get("name") or g.get("model")
        g_load = g.get("utilization_pct") if "utilization_pct" in g else g.get("load_pct")
        g_clock = g.get("clock_mhz") or g.get("freq_mhz")
        print(
            f"GPU [{g.get('id')}]:   {g_name} ({g.get('type')}) | Load: {g_load}% | Clock: {g_clock} MHz | VRAM: {g.get('vram_used_mb')} / {g.get('vram_total_mb')} MB ({g.get('vram_used_gb')}/{g.get('vram_total_gb')} GB) | Temp: {g.get('temperature_c')}°C"
        )

    for p in snapshot.get("processes", []):
        print(
            f"PROCESS:   PID {p.get('pid'):<6} | {p.get('name'):<22} | CPU: {p.get('cpu_pct'):>5.1f}% | RAM: {p.get('memory_mb'):>7.1f} MB ({p.get('memory_pct'):>4.1f}%) | Disk: {p.get('disk_mbps'):>5.1f} MB/s | GPU: {p.get('gpu_pct'):>5.1f}%"
        )

    for d in snapshot.get("storage", {}).get("drives", []):
        d_letter = d.get("letter") or d.get("device")
        d_type = d.get("type") or d.get("type_badge")
        d_read = d.get("read_mbps") if "read_mbps" in d else d.get("read_mbs")
        d_write = d.get("write_mbps") if "write_mbps" in d else d.get("write_mbs")
        d_load = d.get("utilization_pct") if "utilization_pct" in d else d.get("load_pct")
        print(
            f"STORAGE:   {d_letter} ({d_type}) | Used: {d.get('used_gb')}/{d.get('total_gb')} GB | Read: {d_read} MB/s | Write: {d_write} MB/s | Active: {d_load}% | Temp: {d.get('temperature_c')}°C"
        )

    net = snapshot.get("network", {})
    net_name = net.get("adapter_name") or net.get("interface")
    net_down = net.get("download_mbps") if "download_mbps" in net else net.get("downlink_mbps")
    net_up = net.get("upload_mbps") if "upload_mbps" in net else net.get("uplink_mbps")
    print(
        f"NETWORK:   {net_name} | Connected: {net.get('connected')} | Down: {net_down} Mbps | Up: {net_up} Mbps"
    )

    th = snapshot.get("thermals", {})
    print(
        f"THERMALS:  CPU: {th.get('cpu_c')}°C | dGPU: {th.get('dgpu_c')}°C | iGPU: {th.get('igpu_c')}°C | SSD: {th.get('ssd_c')}°C"
    )

    sys_info = snapshot.get("system_info", {})
    if sys_info:
        print(
            f"SYSTEM:    OS: {sys_info.get('os')} | Arch: {sys_info.get('cpu_arch')} | MB: {sys_info.get('motherboard')} | BIOS: {sys_info.get('bios_version')}"
        )
    print("==========================================================================")


def print_benchmark_table(summary: Dict[str, Any], count: int):
    """Prints a formatted benchmark results table."""
    print(f"\n==================== TELEMETRY BENCHMARK RESULTS ({count} iterations) ====================")
    print(
        f"{'Subsystem':<15} | {'Min (ms)':<10} | {'Avg (ms)':<10} | {'Median (ms)':<12} | {'P95 (ms)':<10} | {'Max (ms)':<10}"
    )
    print("-" * 78)
    for sub in ["cpu", "ram", "gpu", "processes", "storage", "network", "thermals", "total"]:
        if sub in summary:
            m = summary[sub]
            print(
                f"{sub.upper():<15} | {m['min_ms']:<10.3f} | {m['avg_ms']:<10.3f} | {m['median_ms']:<12.3f} | {m['p95_ms']:<10.3f} | {m['max_ms']:<10.3f}"
            )
    print("========================================================================================")
    total_avg = summary["total"]["avg_ms"]
    print(f"Total Polling Overhead: {total_avg:.3f} ms / 1000 ms cycle ({(total_avg / 10.0):.3f}% CPU budget)")


def run_test_telemetry(engine: TelemetryEngine, count: int = 1, interval: float = 1.0, fmt: str = "table"):
    """Executes headless telemetry sampling and schema verification."""
    # Warm-up tick to establish baseline delta counters
    engine.poll_once()
    time.sleep(min(0.5, interval))

    for i in range(count):
        snapshot = engine.poll_once()
        if fmt == "json":
            print(json.dumps(snapshot, indent=2))
        else:
            print_snapshot_table(snapshot, sample_num=i + 1, total_samples=count)
        if i < count - 1:
            time.sleep(interval)


def run_benchmark(engine: TelemetryEngine, count: int = 50, fmt: str = "table"):
    """Runs high-iteration latency benchmark across all telemetry subsystems."""
    engine.poll_once()  # Warm-up

    timings = {
        "cpu": [],
        "ram": [],
        "gpu": [],
        "processes": [],
        "storage": [],
        "network": [],
        "thermals": [],
        "total": [],
    }

    for _ in range(count):
        t_total_start = time.perf_counter()

        t0 = time.perf_counter()
        cpu_data = engine.cpu_collector.collect()
        timings["cpu"].append((time.perf_counter() - t0) * 1000.0)

        t0 = time.perf_counter()
        ram_data = engine.ram_collector.collect()
        timings["ram"].append((time.perf_counter() - t0) * 1000.0)

        t0 = time.perf_counter()
        gpu_data = engine.gpu_collector.collect()
        timings["gpu"].append((time.perf_counter() - t0) * 1000.0)

        t0 = time.perf_counter()
        engine.process_collector.collect()
        timings["processes"].append((time.perf_counter() - t0) * 1000.0)

        t0 = time.perf_counter()
        storage_data = engine.storage_collector.collect()
        timings["storage"].append((time.perf_counter() - t0) * 1000.0)

        t0 = time.perf_counter()
        net_data = engine.network_collector.collect()
        timings["network"].append((time.perf_counter() - t0) * 1000.0)

        t0 = time.perf_counter()
        engine.thermal_aggregator.aggregate(cpu_data, gpu_data, storage_data)
        timings["thermals"].append((time.perf_counter() - t0) * 1000.0)

        timings["total"].append((time.perf_counter() - t_total_start) * 1000.0)

    summary = {}
    for sub, vals in timings.items():
        sorted_vals = sorted(vals)
        p95_idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * 0.95))
        summary[sub] = {
            "min_ms": round(min(vals), 3),
            "avg_ms": round(statistics.mean(vals), 3),
            "median_ms": round(statistics.median(vals), 3),
            "p95_ms": round(sorted_vals[p95_idx], 3),
            "max_ms": round(max(vals), 3),
        }

    if fmt == "json":
        print(json.dumps({"benchmark_iterations": count, "latency_metrics": summary}, indent=2))
    else:
        print_benchmark_table(summary, count)


VERSION = "1.0.0"


def main():
    _attach_console_if_needed()
    parser = argparse.ArgumentParser(description="Glassmorphism Hardware Performance HUD")
    parser.add_argument(
        "--test-telemetry", action="store_true", help="Run headless telemetry verification"
    )
    parser.add_argument(
        "--benchmark", action="store_true", help="Run telemetry latency benchmark"
    )
    parser.add_argument(
        "--format", choices=["table", "json"], default="table", help="Output format"
    )
    parser.add_argument("--count", type=int, default=None, help="Iteration count")
    parser.add_argument(
        "--interval", type=float, default=1.0, help="Interval between samples in seconds"
    )
    parser.add_argument(
        "--gui", action="store_true", help="Launch interactive Glassmorphism HUD GUI"
    )
    parser.add_argument(
        "--mode",
        choices=["standard", "ultrawide"],
        default="standard",
        help="Initial screen mode ('standard' 1200x800 or 'ultrawide' 1920x550)",
    )
    parser.add_argument(
        "--pin",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pin window Always-on-Top (default: true)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable PyWebView developer tools"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {VERSION}"
    )
    args = parser.parse_args()

    if args.test_telemetry:
        engine = TelemetryEngine()
        count = args.count if args.count is not None else 1
        run_test_telemetry(engine, count=count, interval=args.interval, fmt=args.format)
        engine.stop()
        sys.exit(0)
    elif args.benchmark:
        engine = TelemetryEngine()
        count = args.count if args.count is not None else 50
        run_benchmark(engine, count=count, fmt=args.format)
        engine.stop()
        sys.exit(0)
    else:
        try:
            from src.gui.window_manager import launch_gui

            interval_ms = int(args.interval * 1000)
            launch_gui(
                screen_mode=args.mode,
                pinned=args.pin,
                interval_ms=interval_ms,
                debug=args.debug,
            )
        except ImportError as exc:
            logger.warning("Could not launch GUI (%s). Running single telemetry test instead.", exc)
            engine = TelemetryEngine()
            run_test_telemetry(engine, count=1, fmt="table")
            engine.stop()


if __name__ == "__main__":
    main()
