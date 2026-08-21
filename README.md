# NETA_OS — Aetheric Glassmorphism Performance HUD (v2.0)

A modern, transparent, HUD-style Windows performance monitoring overlay built for gaming and workstation laptops. Floats seamlessly above desktop wallpapers and games with frosted glass acrylic styling, glowing cyan & obsidian purple accents, and ultra-lightweight resource footprint.

---

## What's New in v2.0 (Phase 2 Enhancements)

- 🔲 **Maximize / Restore & Freely Resizable**: Added native maximize button (#btn-max) and responsive layout breakpoints (Compact <900px, Standard 900–1440px, Ultrawide >1440px / 1920x550).
- 🎮 **Simultaneous Multi-GPU Monitoring**: Both integrated (Intel/AMD) and discrete (NVIDIA RTX/AMD Radeon) GPUs render side-by-side with separate circular gauges, VRAM in MB/GB, and WDDM Task Manager parity.
- ⚡ **Top 5 Resource Consumers**: Live ranking table of top 5 active processes dynamically sorted by CPU, Memory (MB / %), and Disk I/O with sub-0.05% polling overhead.
- 📊 **Detailed Numerical RAM**: Displays memory metrics in exact MB and GB (Used MB / Total MB (Pct%), Available MB, Committed memory).
- 🧭 **Multi-View Navigation Router**: Interactive MONITOR (Core HUD), TELEMETRY (Deep per-core matrix & charts), and SYSTEM (Hardware spec sheet) tabs.
- 🌡️ **Enhanced CPU & SSD Thermals**: Multi-layered discovery for CPU ACPI/WMI thermal zones and NVMe/SATA SMART drive temperatures.
- 🚀 **Instant Startup (< 0.15s Boot)**: Asynchronous background hardware discovery and cached profiles for instantaneous window launch.

---

## Features

### 🖥️ Adaptive Layouts & Glass Overlay
- **Standard HUD Mode (1200x800)**: Modular desktop overlay with zero clipping or text overlaps.
- **Ultra-Wide Secondary Screen Mode (1920x550)**: Proportional horizontal dashboard optimized for secondary laptop touchscreens (Asus ScreenPad / ultra-wides) without large empty gaps.
- **Glassmorphism Aesthetic**: Real-time frosted glass backdrop (ackdrop-filter: blur(20px)), electric cyan (#00daf3) and obsidian purple (#d1bcff) accents, HUD corner brackets, and crisp Space Grotesk / JetBrains Mono typography.
- **Window Controls**: Borderless design with smooth window dragging, Always-On-Top pin, Maximize/Restore, and Minimize/Close.

### ⚡ Live Hardware Telemetry Engine (~1s Refresh)
- **CPU**: Model name, clock frequency (GHz), overall utilization %, per-core load matrix, and package/core temperatures.
- **Multi-GPU (Simultaneous)**: Side-by-side telemetry for iGPU + dGPU (NVIDIA NVML + WDDM PDH / DXGI) with Task Manager parity.
- **RAM**: Memory breakdown (In-Use, Cached, Free), exact MB/GB numerical metrics, and memory speed badges.
- **Top 5 Processes**: Dynamic ranking by CPU/RAM consumption via lightweight NtQuerySystemInformation.
- **Storage / SSD**: Read and write throughput (MB/s), drive utilization %, and NVMe/SATA temperatures.
- **Network I/O**: Downlink and Uplink bandwidth (Mbps / MB/s), active network interface, and connectivity status.

### 🛡️ Fault-Tolerant & Lightweight
- Graceful N/A fallback for unavailable sensors with zero exceptions or crashing.
- Low overhead (< 1.5% CPU during active polling, leak-free memory management).

---

## Quick Start (Run Standalone .EXE)

You can run the pre-compiled standalone executable directly without needing to install Python:

1. Download or locate dist/GlassPerformanceHUD.exe.
2. Double-click **GlassPerformanceHUD.exe** to launch the overlay.
3. Use the header controls:
   - **TABS**: Switch between MONITOR, TELEMETRY, and SYSTEM views.
   - **HUD / 1920x550 Toggle**: Switch between standard HUD mode and ultra-wide secondary display mode.
   - **PIN Button**: Toggle Always-on-Top overlay mode.
   - **MAX Button**: Toggle Maximize and Restore window sizes.
   - **Drag**: Click and drag from the top header or empty glass areas to reposition anywhere on screen.

---

## Building from Source

### Prerequisites
- Windows 10 / 11
- Python 3.10+ (tested on Python 3.12)
- Microsoft WebView2 Runtime (pre-installed on Windows 10/11)

### Installation
`ash
# Clone the repository
git clone https://github.com/KorozaX/PC-performance-monitoring.git
cd PC-performance-monitoring

# Install dependencies
pip install -r requirements.txt

# Run directly
python src/main.py
`

### Build Standalone Executable
`ash
# Build the .exe into dist/GlassPerformanceHUD.exe
python build_exe.py
`

---

## Test Suite & Verification

Run the automated 5-tier test suite (337 test cases covering feature extraction, boundary conditions, cross-module interaction, real-world simulations, and adversarial chaos testing):

`ash
python tests/test_runner.py
`

---

## Project Structure

`
├── dist/
│   └── GlassPerformanceHUD.exe       # Standalone Windows executable (~14.5 MB)
├── src/
│   ├── bridge/
│   │   └── api.py                   # PyWebView JavaScript-Python bridge & window controls
│   ├── gui/
│   │   └── window_manager.py        # Frameless transparent window controller & resizer
│   ├── telemetry/
│   │   ├── cpu_collector.py         # CPU frequency, load, thermals
│   │   ├── gpu_collector.py         # Multi-GPU NVML + DXGI/WDDM collectors (Task Manager parity)
│   │   ├── process_collector.py     # Top 5 resource consumers scanner
│   │   ├── ram_collector.py         # Win32 GlobalMemoryStatusEx memory (MB & GB)
│   │   ├── storage_collector.py     # Disk I/O throughput & SMART thermals
│   │   ├── network_collector.py     # Bandwidth downlink/uplink monitor
│   │   ├── thermals.py              # Multi-layer thermal dynamics aggregation
│   │   └── engine.py                # Telemetry polling engine coordinator (async discovery)
│   └── main.py                      # Application entry point
├── ui/
│   ├── index.html                   # Multi-view HUD glassmorphism layout
│   ├── js/
│   │   ├── app.js                   # UI update loop, router, & responsive reflow
│   │   └── gauges.js                # SVG circular progress gauge renderer
│   └── styles/
│       ├── glass_hud.css            # Frosted glass, brackets, responsive container queries
│       └── tailwind.css             # Design tokens & typography
├── tests/                           # 5-Tier automated test suite (337 tests)
├── build_exe.py                     # PyInstaller automated packaging pipeline
└── requirements.txt                 # Python dependencies
`

---

## License & Credits
Design inspired by the Aetheric HUD concept. Built with Python, PyWebView, and Tailwind CSS.
