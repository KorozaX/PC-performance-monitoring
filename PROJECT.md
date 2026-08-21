# Project: Glassmorphism Laptop Hardware Performance HUD

## Architecture
- **Windowing & GUI Framework**: Python 3.12 + `pywebview` 6.2.1 using Microsoft Edge WebView2 Evergreen runtime.
  - Transparent, borderless window (`frameless=True, transparent=True, easy_drag=True`).
  - Hardware-accelerated CSS `backdrop-filter: blur(20px)` glassmorphism with Electric Cyan (`#00daf3`) and Obsidian Purple (`#d1bcff`) accents.
  - HUD visual elements: SVG circular progress meters ($r=45$, stroke-dasharray 283), HUD corner brackets (`.hud-bracket-tl`, `.hud-bracket-br`), dot-matrix background pattern, Space Grotesk / JetBrains Mono typography.
  - Dual Screen Modes: Standard HUD Overlay Mode (~1200x800) and Ultra-Wide Mode (1920x550) for secondary LCD sensor screens.
- **Hardware Telemetry Engine**: Asynchronous, non-blocking background daemon thread (`TelemetryEngine`) polling at ~1000ms intervals with < 0.25% CPU overhead.
  - Multi-GPU Detection: Pure ctypes NVML for NVIDIA discrete GPUs (load, VRAM, clock, temperature) + Windows PDH / DXGI / WMI for Intel/AMD integrated GPUs.
  - CPU: Model, base/boost frequency, load %, core/thread utilization, package temperature with graceful fallback.
  - RAM: `GlobalMemoryStatusEx` Win32 API for ultra-low latency (<0.03ms) used/free/total GB, utilization %, speed badge.
  - Storage: Delta throughput (Read/Write MB/s), drive utilization %, total capacity.
  - Network: Delta throughput (Download/Upload Mbps and MB/s), active network adapter, connection state.
  - Fault-tolerance: Comprehensive try/catch guards with structured `"N/A"` fallbacks for unexposed or unprivileged sensors.
- **IPC / Bridge**: `pywebview.api` JS-Python bridge + `window.pywebview.api` / evaluated JS event dispatch for instant UI updates.
- **Build & Packaging**: PyInstaller 6.21.0 `--onefile --noconsole` compiling Python scripts and embedded web assets (`ui/`) into a standalone Windows binary `dist/GlassPerformanceHUD.exe`.

## Feature Inventory
Every feature from the survey phase is enumerated below and assigned to a milestone:
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Glassmorphism HUD Window | Borderless, transparent window with 20px backdrop blur, luminous border, HUD corner brackets | M2 | Survey / Spec Miner |
| 2 | Dual Screen Modes | Standard HUD Mode (1200x800) and Ultra-Wide Secondary Screen Mode (1920x550) with layout reflow | M2, M3 | Survey / Spec Miner |
| 3 | Window Controls & Pinning | Draggable header/body (`pywebview-drag-region`), Pin Always-on-Top toggle, Minimize, Close | M3 | Survey / Arch Explorer |
| 4 | CPU Telemetry & Gauges | Model name, GHz clock, CPU load %, core/thread breakdown, temperature (°C / N/A), SVG circular gauge | M1, M2 | Survey / Telemetry Explorer |
| 5 | Multi-GPU Detection & Monitoring | Separate detection & metrics for integrated GPU (Intel/AMD) AND dedicated GPU (NVIDIA RTX/AMD), VRAM, load %, clock, temp | M1, M2 | Survey / Telemetry Explorer |
| 6 | RAM Telemetry & Distribution | Memory utilization %, used GB, free GB, total GB, speed/type badge, 3-segment bar (In-Use/Cached/Free) | M1, M2 | Survey / Telemetry Explorer |
| 7 | Storage / SSD Telemetry | Drive detection, Read/Write throughput (MB/s), active time %, total capacity, drive temp | M1, M2 | Survey / Telemetry Explorer |
| 8 | Network I/O Telemetry | Active adapter name, real-time download & upload bandwidth (Mbps / MB/s), connection state | M1, M2 | Survey / Telemetry Explorer |
| 9 | Thermal Dynamics Panel | Consolidated thermal monitors with dynamic color gradient (<60°C Cyan, 60-79°C Purple, ≥80°C Alert Red) | M1, M2 | Survey / Spec Miner |
| 10 | Low Overhead & Fault Tolerance | <1-2% idle CPU, async non-blocking polling, zero crashing on missing sensors, fallback to "N/A" | M1 | Survey / Telemetry Explorer |
| 11 | Standalone Windows .exe Build | Single-file PyInstaller binary (`GlassPerformanceHUD.exe`) with bundled assets and offline fonts | M4 | Survey / Arch Explorer |
| 12 | Automated Verification & CLI | Headless verification CLI (`--test-telemetry`, `--benchmark`), comprehensive unit & contract tests | E2E-1, M1 | Survey / Arch Explorer |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E-1 | E2E Testing Suite & Infra | Requirements-driven opaque-box test suite (Tiers 1-5, 184 tests, `TEST_READY.md`) | none | DONE |
| M1 | Hardware Telemetry Engine | High-performance, fault-tolerant Python telemetry engine (CPU, Multi-GPU, RAM, SSD, Net) | none | DONE |
| M2 | Glassmorphism HUD Frontend | Modern HUD UI with SVG gauges, HUD brackets, design tokens, dual-screen responsive CSS | none | DONE |
| M3 | HUD Controller & Bridge | PyWebView window manager, JS-Python bridge, drag/pin/mode controllers | M1, M2 | DONE |
| M4 | Standalone .exe Packaging | PyInstaller single-file build (`dist/GlassPerformanceHUD.exe`), resource embedding, verification | M1, M2, M3 | DONE |
| M5 | Final E2E Pass & Adversarial Hardening | 100% E2E test pass (184/184 tests across Tiers 1-5) + Final Forensic Audit CLEAN | E2E-1, M4 | DONE |

## Interface Contracts

### TelemetryEngine ↔ HUD Bridge Contract (`src/telemetry/` ↔ `src/bridge/`)
The `TelemetryEngine` produces an immutable JSON snapshot dictionary matching the following schema:
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
    "per_core_load": [12.0, 18.5, 9.2, ...]
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
    },
    {
      "id": 1,
      "type": "integrated",
      "vendor": "Intel",
      "model": "Intel(R) UHD Graphics",
      "load_pct": 5.0,
      "freq_mhz": "N/A",
      "vram_used_gb": 0.6,
      "vram_total_gb": "N/A",
      "temperature_c": "N/A"
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

### UI JavaScript Bridge Contract (`ui/app.js` ↔ `src/bridge/api.py`)
- `window.pywebview.api.get_telemetry_snapshot()` -> Returns the latest telemetry JSON snapshot.
- `window.pywebview.api.set_screen_mode(mode_name)` -> `"standard"` (1200x800) or `"ultrawide"` (1920x550).
- `window.pywebview.api.toggle_pin_top()` -> Returns boolean `is_pinned`.
- `window.pywebview.api.minimize_window()` -> Minimizes HUD window.
- `window.pywebview.api.close_window()` -> Closes HUD application.
- `window.onTelemetryUpdate(snapshot)` -> JS callback invoked automatically every tick by the Python daemon.

## Code Layout
```
Performance Stats/
├── src/
│   ├── __init__.py
│   ├── main.py                     # Entry point & CLI handler
│   ├── telemetry/
│   │   ├── __init__.py
│   │   ├── engine.py               # Background daemon coordinator
│   │   ├── cpu_collector.py        # CPU load, clock, temp
│   │   ├── gpu_collector.py        # Multi-GPU (NVML + PDH/DXGI)
│   │   ├── ram_collector.py        # RAM Win32 GlobalMemoryStatusEx
│   │   ├── storage_collector.py    # SSD throughput delta & stats
│   │   └── network_collector.py    # Net bandwidth delta & stats
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── window_manager.py       # PyWebView window creation & styling
│   │   └── dnd_pin.py              # Window dragging & pin always-on-top
│   └── bridge/
│       ├── __init__.py
│       └── api.py                  # PyWebView JS API & event dispatcher
├── ui/
│   ├── index.html                  # Glassmorphism HUD HTML
│   ├── styles/
│   │   ├── tailwind.css            # Tailwind / Design tokens CSS
│   │   └── glass_hud.css           # Glassmorphism, animations & brackets
│   ├── js/
│   │   ├── app.js                  # HUD UI controller & bindings
│   │   └── gauges.js               # SVG circular gauges & bars
│   └── fonts/                      # Local bundled fonts (Space Grotesk, JetBrains Mono)
├── tests/
│   ├── test_runner.py              # Test runner executing all tiers
│   ├── tier1_feature_tests.py      # Tier 1: Feature coverage (>=5 per feature)
│   ├── tier2_boundary_tests.py     # Tier 2: Boundary & sensor fallback tests
│   ├── tier3_interaction_tests.py  # Tier 3: Pairwise cross-feature tests
│   └── tier4_scenario_tests.py     # Tier 4: Real-world laptop workloads
├── build_exe.py                    # PyInstaller packaging script
├── requirements.txt                # Dependencies specification
├── PROJECT.md                      # Global architecture & milestones
├── TEST_INFRA.md                   # Test infrastructure specification
└── ORIGINAL_REQUEST.md             # Verbatim user request record
```
