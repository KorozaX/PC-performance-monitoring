# Project: Glassmorphism Performance HUD Refactoring & Enhancement

## Architecture
- **Desktop Runtime**: Python + `pywebview` (Edge Chromium / WebView2 engine) with frameless, transparent glassmorphism UI.
- **Backend Telemetry Engine (`src/telemetry/`)**: High-performance asynchronous telemetry pipeline with low CPU polling overhead (< 1-2% budget, < 5ms sampling).
  - `engine.py`: Telemetry coordinator, asynchronous background hardware discovery, Tick-0 instant snapshot emitter, cached hardware profile loader (`.cache/hw_profile.json`).
  - `cpu_collector.py`: CPU utilization, core clock, topology, multi-layered temperature probe (ACPI / WMI / fallback).
  - `gpu_collector.py`: Simultaneous DXGI multi-GPU adapter discovery, WDDM engine utilization smoothing (PDH parity with Task Manager), NVML/ADL sensor queries.
  - `ram_collector.py`: High-precision memory statistics (`used_mb`, `free_mb`, `total_mb`, `available_mb`, `committed_mb`, `commit_limit_mb`, percentages, DDR speed/type).
  - `process_collector.py`: Ultra-fast native `NtQuerySystemInformation(5)` scanner extracting Top 5 resource consumers (CPU %, Working Set MB/%, Disk I/O MB/s, GPU Engine %).
  - `storage_collector.py`: Drive capacities, read/write I/O throughput, NVMe/SATA IOCTL SMART thermal probes.
  - `thermals.py`: Consolidated thermal dynamics aggregation (CPU, dGPU, iGPU, SSD) with resilient `"N/A"` fallback.
  - `network_collector.py`: Real-time network throughput and active interface stats.
- **Bridge API (`src/bridge/api.py`)**: `HUDBridgeAPI` exposing Python telemetry snapshots, window controls (`minimize_window`, `restore_window`, `close_window`, `toggle_maximize`, `is_maximized`, `set_screen_mode`, `toggle_pin_top`), and view interactions to JavaScript.
- **Frontend UI (`ui/`)**: Aetheric HUD Glassmorphism interface.
  - `index.html`: Frameless window structure, custom titlebar controls, responsive container layouts, view router containers (`#view-monitor`, `#view-telemetry`, `#view-system`).
  - `styles/glass_hud.css` & `styles/tailwind.css`: Aetheric tokens (`#0f1419`, `#00daf3`, `#d1bcff`, 20px blur, glowing borders), fluid responsive breakpoints (Compact <900px, Standard 900-1440px / 1200x800, Ultrawide 1920x550 / >1440px).
  - `js/app.js`: Bridge client, view navigation state manager, dynamic DOM updaters for multi-GPU, Top 5 processes, RAM, Thermals, and System inventory.
  - `js/gauges.js`: SVG circular/linear HUD telemetry gauges with animation easing.
- **Testing & Packaging Track (`tests/`, `build_exe.py`)**: Multi-tiered test suite (Tiers 1-5) and PyInstaller Windows standalone executable generator.

## Code Layout
- `src/main.py`: Application entry point (`--gui`, `--benchmark`, `--test-telemetry`).
- `src/telemetry/`: Telemetry collectors and hardware discovery.
  - `src/telemetry/engine.py`
  - `src/telemetry/cpu_collector.py`
  - `src/telemetry/gpu_collector.py`
  - `src/telemetry/ram_collector.py`
  - `src/telemetry/process_collector.py`
  - `src/telemetry/storage_collector.py`
  - `src/telemetry/thermals.py`
  - `src/telemetry/network_collector.py`
- `src/bridge/api.py`: Python-to-JS bridge API methods.
- `src/gui/window_manager.py`: Window creation, flags, and async initialization.
- `ui/`: HTML/CSS/JS web assets.
  - `ui/index.html`
  - `ui/styles/glass_hud.css`
  - `ui/styles/tailwind.css`
  - `ui/js/app.js`
  - `ui/js/gauges.js`
- `tests/`: Multi-tier test suite.
  - `tests/test_runner.py`
  - `tests/test_tier1_features.py`
  - `tests/test_tier2_boundaries.py`
  - `tests/test_tier3_pairwise.py`
  - `tests/test_tier4_workloads.py`
  - `tests/test_adversarial_faults.py`
  - `tests/test_adversarial_stress.py`
  - `tests/test_challenger_stress.py`
- `build_exe.py`: PyInstaller bundling script for `dist/GlassPerformanceHUD.exe`.

## Feature Inventory
| # | Feature | Description | Milestone | Status |
|---|---------|-------------|-----------|--------|
| 1 | F1.1 Adaptive Breakpoints | Responsive CSS layouts for Compact, Standard (1200x800), and Ultrawide (1920x550) without text clipping or black voids | M2 | DONE |
| 2 | F1.2 Maximize/Restore Control | Custom window titlebar Maximize/Restore button (`#btn-max`) with icon toggle and `toggle_maximize()` bridge method | M1, M2 | DONE |
| 3 | F1.3 Frameless Window Controls | Polished draggable titlebar, Pin-to-top, Minimize, Maximize, and Close integration | M2 | DONE |
| 4 | F2.1 Simultaneous Multi-GPU Display | Render all detected physical GPUs (iGPU + dGPU) simultaneously side-by-side without tab hiding | M1, M2 | DONE |
| 5 | F2.2 Task Manager GPU Parity | Smooth WDDM/DXGI engine utilization calculation matching Windows Task Manager without erratic spikes | M1 | DONE |
| 6 | F2.3 Per-GPU Telemetry Metrics | VRAM Used/Total in GB and %, GPU clock, thermal readings, and dedicated/integrated badges | M1, M2 | DONE |
| 7 | F3.1 Ultra-Fast Process Scanner | Low-overhead process collector using `NtQuerySystemInformation(5)` (< 5ms polling, < 0.05% CPU overhead) | M1 | DONE |
| 8 | F3.2 Top 5 Processes Ranking | Live ranking by CPU%, Working Set RAM (MB and %), Disk I/O (MB/s), and GPU Engine % | M1 | DONE |
| 9 | F3.3 Top 5 Processes UI Widget | Glassmorphic live-updating table widget embedded in Monitor & Telemetry views | M2 | DONE |
| 10 | F4.1 Async Hardware Discovery | Background threaded initialization of DXGI, NVML, WMI, and SMBIOS for non-blocking startup | M1 | DONE |
| 11 | F4.2 Instant Skeleton & Tick-0 | Sub-0.5s cold launch via immediate window display and instant default fallback snapshot | M1, M2 | DONE |
| 12 | F4.3 Hardware Profile Caching | Local `.cache/hw_profile.json` caching for instant warm-start hardware metadata retrieval | M1 | DONE |
| 13 | F5.1 Enhanced RAM Telemetry | Payload expansion to include exact numerical `used_mb`, `free_mb`, `total_mb`, `available_mb`, `committed_mb` | M1 | DONE |
| 14 | F5.2 Enhanced RAM UI Card | RAM card rendering dual MB and GB values, percentage gauges, and committed/available memory bars | M2 | DONE |
| 15 | F6.1 Interactive Tab Navigation | Navigation pill buttons for `MONITOR`, `TELEMETRY`, `SYSTEM` with view routing and animations | M2 | DONE |
| 16 | F6.2 Monitor View | Core Glassmorphism HUD (CPU, Multi-GPU, RAM, Top 5 Processes, Thermals, Network, Storage) | M2 | DONE |
| 17 | F6.3 Telemetry View | Deep metrics view (per-core CPU bars, live I/O metrics, network interface throughput, GPU engines) | M2 | DONE |
| 18 | F6.4 System View | Complete hardware inventory sheet (CPU microarchitecture, RAM specs, GPU driver, Storage NVMe Gen, OS build) | M2 | DONE |
| 19 | F7.1 Multi-Layer CPU Thermals | CPU temperature detection for AMD Ryzen and Intel Core with multi-layered fallback and graceful `"N/A"` | M1 | DONE |
| 20 | F7.2 SSD SMART Thermal Sensors | Drive temperature detection for NVMe/SATA SSDs via Storage IOCTLs and SMART queries with graceful `"N/A"` | M1 | DONE |
| 21 | F7.3 Consolidated Thermals UI | Thermal dynamics card in UI displaying CPU, dGPU, iGPU, and SSD temperatures simultaneously | M2 | DONE |
| 22 | F8.1 E2E Test Suite Expansion | Full requirement test coverage across Tiers 1-5 verifying 100% test pass rate | E2E, M3 | DONE |
| 23 | F8.2 PyInstaller Executable Build | Standalone executable generation in `dist/GlassPerformanceHUD.exe` with bundled assets and verified launch | M3 | DONE |
| 24 | F8.3 Git Sync | Git commit of all changes with clean commit message and push to remote repository | M3 | DONE |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Independent opaque-box test suite for R1-R8 (Tiers 1-4) publishing `TEST_READY.md` | none | DONE |
| M1 | Backend Core & Telemetry Engine | R2 (Multi-GPU & Task Manager parity), R3 (`NtQuerySystemInformation` process collector), R4 (Async discovery & <0.5s launch), R5 (Enhanced RAM metrics in MB/GB), R7 (CPU & SSD Thermals), and Bridge API window controls | none | DONE |
| M2 | Frontend Glassmorphism UI & Navigation | R1 (Adaptive breakpoints & Maximize button), R2 (Simultaneous Multi-GPU widgets), R3 (Top 5 Processes UI table), R5 (Enhanced RAM MB/GB card), R6 (Monitor, Telemetry, System tab routing), R7 (Thermal dynamics card) | M1 | DONE |
| M3 | Final Verification, Packaging & GitHub Sync | Pass 100% E2E test suite (Tiers 1-4), Tier 5 adversarial hardening, PyInstaller `dist/GlassPerformanceHUD.exe` build verification, and Git sync | M1, M2, E2E | DONE |
