# TEST_INFRA: Glassmorphism Performance HUD Test Infrastructure Specification

## 1. Overview & Test Architecture
The Glassmorphism Performance HUD testing framework provides a comprehensive, multi-tiered, requirement-driven, opaque-box E2E test suite designed to validate functionality, edge cases, cross-feature dynamics, real-world application workloads, and sensor fault tolerance across all 24 features defined in `PROJECT.md § Feature Inventory`.

```
                  +----------------------------------------------+
                  |           E2E Test Runner (CLI)              |
                  |          `tests/test_runner.py`              |
                  +----------------------+-----------------------+
                                         |
        +----------------+---------------+---------------+----------------+
        |                |                               |                |
        v                v                               v                v
+---------------+ +---------------+             +---------------+ +---------------+
|    Tier 1     | |    Tier 2     |             |    Tier 3     | |    Tier 4     |
| Feature Tests | | Boundary/     |             | Cross-Feature | | Real-World    |
| (24 Features, | | Fallback      |             | Interactions  | | Scenarios     |
| >=5 tests ea) | | (24 Features) |             | (Pairwise)    | | (Simulations) |
+---------------+ +---------------+             +---------------+ +---------------+
        |                |                               |                |
        +----------------+---------------+---------------+----------------+
                                         |
                                         v
                  +----------------------------------------------+
                  |  Shared Contracts, Mock Engine & Validators  |
                  |          `tests/test_helpers.py`             |
                  +----------------------+-----------------------+
                                         |
        +--------------------------------+--------------------------------+
        |                                                                 |
        v                                                                 v
+-------------------------------+                                 +-------------------------------+
|  Telemetry Engine & Probes   |                                 |  UI Assets & Web Bridge       |
|  (`src/telemetry/`, `src/`)   |                                 |  (`ui/`, `src/bridge/`, etc.) |
+-------------------------------+                                 +-------------------------------+
```

---

## 2. Multi-Tier Test Methodology

### Tier 1: Feature Functionality Coverage
- **Purpose**: Verify positive (happy path) functional requirements and interface contracts for all 24 inventoried features from `PROJECT.md § Feature Inventory`.
- **Requirement**: Minimum 5 distinct test cases per feature (>=120 tests total).
- **Target Files**: `tests/test_tier1_features.py` (aliased as `tests/tier1_feature_tests.py`), `tests/test_gui_bridge.py`.

### Tier 2: Boundary Conditions & Corner Cases
- **Purpose**: Verify behavior at extreme limits (0%/100% loads, 1TB RAM, 14,000 MB/s Gen5 SSD, 10Gbps network), empty process/GPU arrays, unprivileged environments, missing sensors, and `"N/A"` thermal fallbacks across all 24 features.
- **Requirement**: Minimum 5 distinct test cases per feature (>=120 tests total).
- **Target File**: `tests/test_tier2_boundaries.py` (aliased as `tests/tier2_boundary_tests.py`).

### Tier 3: Cross-Feature Pairwise Interactions
- **Purpose**: Validate pairwise subsystem dynamics, simultaneous multi-GPU and top 5 processes live updating, rapid tab navigation with maximize/restore toggling, async startup under concurrent polling, and thermal transitions during GPU ramps.
- **Requirement**: Minimum 20 pairwise interaction tests (25 tests implemented).
- **Target File**: `tests/test_tier3_pairwise.py` (aliased as `tests/tier3_interaction_tests.py`).

### Tier 4: Real-World Application Scenarios & Workload Simulations
- **Purpose**: Simulate multi-step laptop & desktop workloads: AAA gaming session ramp & cooldown, CPU thermal throttling and frequency downscaling, battery saver low-power mode, ultrawide secondary docking, heavy 4K rendering & NVMe scrubbing, cloud backup upload bursts, and 1,000-tick continuous monotonic telemetry stability.
- **Requirement**: Minimum 15 multi-step workload scenarios (16 tests implemented).
- **Target File**: `tests/test_tier4_workloads.py` (aliased as `tests/tier4_scenario_tests.py`).

### Tier 5: Adversarial Fault Injection & Chaos Testing
- **Purpose**: Stress-test hardware collector resilience under extreme fault conditions (missing NVML DLL, Optimus D3 cold sleep, BitLocker locked drives, WMI timeouts, subscriber crashes, total subsystem failures).
- **Target File**: `tests/test_adversarial_faults.py`.

---

## 3. Feature Inventory Coverage Mapping (24 Features)

| Feature ID | Feature Name | Tier 1 Tests | Tier 2 Tests | Tier 3 & 4 Coverage |
|---|---|---|---|---|
| **F1.1** | Adaptive Breakpoints | 5 | 5 | Responsive CSS layouts (Compact, Standard 1200x800, Ultrawide 1920x550) |
| **F1.2** | Maximize/Restore Control | 5 | 5 | Window maximize/restore toggle, geometry recovery, `#btn-max` contract |
| **F1.3** | Frameless Window Controls | 5 | 5 | Draggable titlebar, Pin Always-on-Top, Minimize, and Close integration |
| **F2.1** | Simultaneous Multi-GPU Display | 5 | 5 | Render all detected physical GPUs (iGPU + dGPU) side-by-side |
| **F2.2** | Task Manager GPU Parity | 5 | 5 | Smooth WDDM/DXGI engine utilization calculation matching Task Manager |
| **F2.3** | Per-GPU Telemetry Metrics | 5 | 5 | VRAM Used/Total in MB and GB, GPU clock MHz, temperatures, type badges |
| **F3.1** | Ultra-Fast Process Scanner | 5 | 5 | Low-overhead scanner (<5ms polling budget, <0.05% CPU overhead) |
| **F3.2** | Top 5 Processes Ranking | 5 | 5 | Dynamic ranking by CPU%, Working Set RAM (MB/%), Disk MB/s, GPU% |
| **F3.3** | Top 5 Processes UI Widget | 5 | 5 | Glassmorphic live-updating table widget embedded in Monitor & Telemetry |
| **F4.1** | Async Hardware Discovery | 5 | 5 | Background threaded initialization of DXGI, NVML, WMI, and SMBIOS |
| **F4.2** | Instant Skeleton & Tick-0 | 5 | 5 | Sub-0.5s cold launch via immediate window popup and default fallback snapshot |
| **F4.3** | Hardware Profile Caching | 5 | 5 | Local `.cache/hw_profile.json` caching for instant warm-start retrieval |
| **F5.1** | Enhanced RAM Telemetry | 5 | 5 | Exact numerical `used_mb`, `free_mb`, `total_mb`, `available_mb`, `committed_mb` |
| **F5.2** | Enhanced RAM UI Card | 5 | 5 | RAM card rendering dual MB/GB values, percentage gauges, committed bar |
| **F6.1** | Interactive Tab Navigation | 5 | 5 | Navigation pill buttons for `MONITOR`, `TELEMETRY`, `SYSTEM` view routing |
| **F6.2** | Monitor View | 5 | 5 | Core HUD (CPU, Multi-GPU, RAM, Top 5 Processes, Thermals, Network, Storage) |
| **F6.3** | Telemetry View | 5 | 5 | Deep metrics view (per-core CPU bars, live I/O metrics, network streaming) |
| **F6.4** | System View | 5 | 5 | Hardware inventory sheet (CPU microarchitecture, RAM specs, GPU driver) |
| **F7.1** | Multi-Layer CPU Thermals | 5 | 5 | AMD Ryzen and Intel Core thermals with multi-layered fallback and `"N/A"` |
| **F7.2** | SSD SMART Thermal Sensors | 5 | 5 | NVMe/SATA SSD temperatures via Storage IOCTLs with graceful `"N/A"` |
| **F7.3** | Consolidated Thermals UI | 5 | 5 | Thermal dynamics card displaying CPU, dGPU, iGPU, and SSD temperatures |
| **F8.1** | E2E Test Suite Expansion | 5 | 5 | 4-tier test runner verification with CLI filtering and JSON report export |
| **F8.2** | PyInstaller Executable Build | 5 | 5 | Standalone executable in `dist/GlassPerformanceHUD.exe` with bundled assets |
| **F8.3** | Git Sync | 5 | 5 | Clean Git tracking, commit formatting, and remote sync |

---

## 4. Telemetry Snapshot & Bridge Interface Contracts

### 4.1 Telemetry Snapshot Schema
Every telemetry snapshot produced by `TelemetryEngine` or ingested by `ui/js/app.js` conforms to this JSON structure:
```json
{
  "timestamp": 1724231800.123,
  "cpu": {
    "name": "AMD Ryzen 9 6900HX",
    "cores_physical": 8,
    "cores_logical": 16,
    "utilization_pct": 14.5,
    "frequency_mhz": 3294.0,
    "temperature_c": 55.0,
    "per_core_utilization": [12.0, 15.0, 10.0, 18.0, 12.0, 30.0, 14.0, 25.0]
  },
  "gpus": [
    {
      "id": 0,
      "name": "NVIDIA GeForce RTX 3060 Laptop GPU",
      "type": "dedicated",
      "utilization_pct": 28.0,
      "vram_used_gb": 2.4,
      "vram_total_gb": 6.0,
      "vram_used_mb": 2457.6,
      "vram_total_mb": 6144.0,
      "clock_mhz": 1425,
      "temperature_c": 52.0
    },
    {
      "id": 1,
      "name": "AMD Radeon(TM) Graphics",
      "type": "integrated",
      "utilization_pct": 4.0,
      "vram_used_gb": 0.3,
      "vram_total_gb": 0.5,
      "vram_used_mb": 307.2,
      "vram_total_mb": 512.0,
      "clock_mhz": 2200,
      "temperature_c": "N/A"
    }
  ],
  "ram": {
    "used_gb": 22.6,
    "total_gb": 63.3,
    "free_gb": 40.7,
    "used_mb": 23142.4,
    "total_mb": 64780.0,
    "free_mb": 41637.6,
    "available_mb": 42090.0,
    "committed_mb": 26223.0,
    "commit_limit_mb": 68876.0,
    "utilization_pct": 35.7,
    "memory_type": "DDR5",
    "speed_mhz": 4800
  },
  "processes": [
    {
      "pid": 1234,
      "name": "chrome.exe",
      "cpu_pct": 8.4,
      "memory_mb": 842.5,
      "memory_pct": 1.3,
      "disk_mbps": 1.2,
      "gpu_pct": 4.5
    }
  ],
  "storage": {
    "drives": [
      {
        "letter": "C:",
        "type": "NVMe Gen4",
        "used_gb": 613.8,
        "total_gb": 928.5,
        "free_gb": 314.7,
        "utilization_pct": 66.1,
        "read_mbps": 12.4,
        "write_mbps": 5.8,
        "temperature_c": 42.0
      }
    ]
  },
  "thermals": {
    "cpu_c": 55.0,
    "dgpu_c": 52.0,
    "igpu_c": "N/A",
    "ssd_c": 42.0
  },
  "network": {
    "adapter_name": "Wi-Fi 2",
    "download_mbps": 15.2,
    "upload_mbps": 2.4
  },
  "system_info": {
    "os": "Windows 11 Home 23H2 (Build 22631)",
    "cpu_arch": "x86_64",
    "motherboard": "Standard OEM",
    "bios_version": "1.04"
  }
}
```

### 4.2 UI Bridge Contract (`window.pywebview.api`)
- `get_telemetry_snapshot() -> dict`: Returns valid Telemetry Snapshot JSON dict.
- `set_screen_mode(mode_name: str) -> dict`: Sets dimensions (`"standard"` 1200x800 or `"ultrawide"` 1920x550).
- `toggle_maximize() -> bool`: Toggles window maximize/restore state; returns `True` if maximized, `False` if restored.
- `is_maximized() -> bool`: Returns current maximize state.
- `toggle_pin_top() -> bool`: Toggles Always-On-Top window flag; returns `is_pinned`.
- `minimize_window() -> bool`: Minimizes window to taskbar.
- `restore_window() -> bool`: Restores window from minimized state.
- `close_window() -> bool`: Closes and destroys HUD window.

---

## 5. Execution Commands & Test CLI

### Run Complete Test Suite
```powershell
python tests/test_runner.py
```

### Run Specific Test Tier
```powershell
python tests/test_runner.py --tier 1
python tests/test_runner.py --tier 2
python tests/test_runner.py --tier 3
python tests/test_runner.py --tier 4
python tests/test_runner.py --tier 5
```

### Run Specific Feature Tests
```powershell
python tests/test_runner.py --feature F1_1
python tests/test_runner.py --feature CPU
python tests/test_runner.py --feature GPU
```

### Generate Machine-Readable JSON Report
```powershell
python tests/test_runner.py --json-report test_report.json
```

### Verbose Mode
```powershell
python tests/test_runner.py -v
```

---

## 6. Pass/Fail Criteria & Performance Standards
- **Exit Code 0**: 100% of executed tests PASSED with zero failures and zero errors.
- **Exit Code 1**: One or more test assertions failed or encountered unexpected exceptions.
- **Telemetry Latency Budget**: Telemetry sampling and validation must complete in $< 5.0\text{ ms}$ per cycle to guarantee $< 1.0\%$ CPU overhead.
- **Instant Cold Start**: Application window creation and initial snapshot display must execute in $< 0.5\text{ s}$.
