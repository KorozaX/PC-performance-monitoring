# TEST_INFRA: Glassmorphism Performance HUD Test Infrastructure Specification

## 1. Overview & Test Architecture
The Glassmorphism Performance HUD testing framework provides a 4-tier, requirement-driven, opaque-box test suite designed to validate the functionality, stability, sensor fault-tolerance, and visual/contract integrity of the application.

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
| (12 Features, | | Fallback      |             | Interactions  | | Scenarios     |
| >=5 tests ea) | | (12 Features) |             | (Pairwise)    | | (Simulations) |
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

## 2. 4-Tier Test Methodology

### Tier 1: Feature Functionality Coverage
- **Purpose**: Verify positive (happy path) functional requirements for all 12 inventoried features in `PROJECT.md`.
- **Requirement**: Minimum 5 distinct test cases per feature (>=60 tests total).
- **Target File**: `tests/tier1_feature_tests.py`.

### Tier 2: Boundary Conditions & Sensor Fallback Handling
- **Purpose**: Verify behavior at upper/lower limits, missing sensors, unprivileged environments, and hardware errors.
- **Requirement**: Minimum 5 distinct test cases per feature (>=60 tests total).
- **Target File**: `tests/tier2_boundary_tests.py`.

### Tier 3: Cross-Feature Interactions & Pairwise Dynamics
- **Purpose**: Validate pairwise subsystem dynamics, UI mode switches during active telemetry streaming, and concurrency safety.
- **Requirement**: Minimum 15 pairwise interaction tests.
- **Target File**: `tests/tier3_interaction_tests.py`.

### Tier 4: Real-World Workload Scenarios & End-to-End Sessions
- **Purpose**: Simulate real laptop usage sessions (gaming, thermal throttle, idle battery save, secondary dock).
- **Requirement**: Minimum 10 multi-step workload scenario simulations.
- **Target File**: `tests/tier4_scenario_tests.py`.

---

## 3. Feature Inventory Coverage Mapping

| Feature ID | Feature Name | Description | Tier 1 Suite | Tier 2 Suite | Tier 3 & 4 Coverage |
|---|---|---|---|---|---|
| **F01** | Glassmorphism HUD Window | Borderless, transparent, 20px blur, luminous borders, HUD corner brackets, design tokens | `TestF01_HUDWindowFeature` | `TestF01_HUDWindowBoundary` | Screen modes, transparency & visual contracts |
| **F02** | Dual Screen Modes | Standard HUD (1200x800) vs Ultra-Wide (1920x550) reflow & geometry | `TestF02_DualScreenModesFeature` | `TestF02_DualScreenModesBoundary` | Mode switch during active load, dock scenario |
| **F03** | Window Controls & Pinning | Draggable regions, Pin Always-On-Top, Minimize, Close commands | `TestF03_WindowControlsFeature` | `TestF03_WindowControlsBoundary` | Pin toggle under continuous streaming |
| **F04** | CPU Telemetry & Gauges | Model name, GHz clock, load %, per-core stats, core temp, SVG meter math | `TestF04_CPUTelemetryFeature` | `TestF04_CPUTelemetryBoundary` | CPU+GPU load spike, thermal throttling scenario |
| **F05** | Multi-GPU Detection | Integrated GPU (Intel/AMD) + Dedicated GPU (NVIDIA RTX/AMD), VRAM, clocks | `TestF05_MultiGPUFeature` | `TestF05_MultiGPUBoundary` | Dynamic dGPU engagement in gaming scenario |
| **F06** | RAM Telemetry & Breakdown | Used/Free/Total GB, load %, speed badge, In-Use/Cached/Free 3-segment bar | `TestF06_RAMTelemetryFeature` | `TestF06_RAMTelemetryBoundary` | Memory allocation bursts with disk paging |
| **F07** | Storage / SSD Telemetry | Drive detection, Read/Write MB/s delta throughput, load %, capacity | `TestF07_StorageTelemetryFeature` | `TestF07_StorageTelemetryBoundary` | Simultaneous disk write & network download |
| **F08** | Network I/O Telemetry | Active adapter, Downlink/Uplink Mbps/MB/s delta throughput, connection state | `TestF08_NetworkTelemetryFeature` | `TestF08_NetworkTelemetryBoundary` | Offline adapter switch, high-speed streaming |
| **F09** | Thermal Dynamics Panel | Consolidated CPU/GPU/SSD thermals, dynamic color thresholds (<60 Cyan, 60-79 Purple, >=80 Red) | `TestF09_ThermalsPanelFeature` | `TestF09_ThermalsPanelBoundary` | Dynamic threshold color changes under load |
| **F10** | Low Overhead & Fault Tolerance | Polling loop < 10ms execution, < 1-2% CPU overhead, try/catch shields, `"N/A"` fallbacks | `TestF10_FaultToleranceFeature` | `TestF10_FaultToleranceBoundary` | Long-duration stability, zero memory leaks |
| **F11** | Standalone Packaging Contract | PyInstaller spec verification, embedded `ui/` assets, bundled fonts, single-file `.exe` contract | `TestF11_PackagingContractFeature` | `TestF11_PackagingContractBoundary` | Production build packaging verification |
| **F12** | Automated Verification & CLI | Headless CLI arguments (`--test-telemetry`, `--benchmark`, `--version`), exit codes | `TestF12_CLIVerificationFeature` | `TestF12_CLIVerificationBoundary` | Headless execution in CI/CD pipeline |

---

## 4. Telemetry Snapshot & Bridge Interface Contracts

### 4.1 Telemetry Snapshot Schema
Every telemetry snapshot produced by `TelemetryEngine` or ingested by `ui/app.js` MUST validate against this JSON structure:
```json
{
  "timestamp": 1724220000.123,
  "cpu": {
    "model": "13th Gen Intel(R) Core(TM) i9-13900HX",
    "load_pct": 14.5,
    "freq_ghz": 3.80,
    "cores_physical": 24,
    "cores_logical": 32,
    "temperature_c": 52.0,
    "per_core_load": [12.0, 18.5, 9.2]
  },
  "gpus": [
    {
      "id": 0,
      "type": "dedicated",
      "vendor": "NVIDIA",
      "model": "NVIDIA GeForce RTX 4080 Laptop GPU",
      "load_pct": 32.0,
      "freq_mhz": 1850,
      "vram_used_gb": 4.2,
      "vram_total_gb": 12.0,
      "temperature_c": 58.0
    }
  ],
  "ram": {
    "load_pct": 38.2,
    "used_gb": 24.5,
    "free_gb": 39.5,
    "total_gb": 64.0,
    "type_badge": "DDR5-6000",
    "distribution": {
      "in_use_pct": 38,
      "cached_pct": 15,
      "free_pct": 47
    }
  },
  "storage": {
    "drives": [
      {
        "device": "C:",
        "type_badge": "NVMe Gen4",
        "used_gb": 480.2,
        "total_gb": 1024.0,
        "load_pct": 12.0,
        "read_mbs": 125.4,
        "write_mbs": 48.2,
        "temperature_c": 41.0
      }
    ]
  },
  "network": {
    "interface": "Wi-Fi 6E (Intel Killer AX1675i)",
    "connected": true,
    "downlink_mbps": 142.5,
    "uplink_mbps": 28.4,
    "downlink_mbs": 17.8,
    "uplink_mbs": 3.55
  },
  "thermals": {
    "cpu_c": 52.0,
    "gpu_c": 58.0,
    "ssd_c": 41.0
  }
}
```

### 4.2 UI Bridge Contract (`window.pywebview.api`)
- `get_telemetry_snapshot()` -> Returns valid Telemetry Snapshot JSON dict.
- `set_screen_mode(mode_name)` -> Sets dimensions: `"standard"` (1200x800) or `"ultrawide"` (1920x550).
- `toggle_pin_top()` -> Toggles always-on-top window flag; returns boolean `is_pinned`.
- `minimize_window()` -> Minimizes window.
- `close_window()` -> Closes window and terminates telemetry daemon.

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
```

### Run Specific Feature Tests
```powershell
python tests/test_runner.py --feature F04
python tests/test_runner.py --feature F05
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

## 6. Pass/Fail Criteria & Exit Codes
- **Exit Code 0**: 100% of executed tests PASSED with zero failures and zero errors.
- **Exit Code 1**: One or more test assertions failed or encountered unexpected exceptions.
- **Telemetry Latency Budget**: Telemetry sampling must complete in $< 10.0\text{ ms}$ per cycle to guarantee $< 1.0\%$ CPU overhead.
