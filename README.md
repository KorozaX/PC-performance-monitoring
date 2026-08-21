# NETA_OS — Aetheric Glassmorphism Performance HUD

A modern, transparent, HUD-style Windows performance monitoring overlay built for gaming and workstation laptops. Floats seamlessly above desktop wallpapers and games with frosted glass acrylic styling, glowing cyan & obsidian purple accents, and ultra-lightweight resource footprint.

---

## Features

### 🖥️ Dual Display Profiles & Glass Overlay
- **Standard HUD Mode (1200x800)**: Floating desktop overlay matching the reference HUD layout.
- **Ultra-Wide Secondary Screen Mode (1920x550)**: Tailored horizontal dashboard optimized for secondary laptop touchscreens (such as Asus ScreenPad / 1920x550 displays) sitting unobtrusively on top of any wallpaper.
- **Glassmorphism Aesthetic**: Real-time frosted glass backdrop (ackdrop-filter: blur(20px)), electric cyan (#00daf3) and obsidian purple (#d1bcff) accents, HUD corner brackets, and crisp Space Grotesk / JetBrains Mono typography.
- **Window Controls**: Borderless design with smooth window dragging, Always-On-Top toggle, and clean minimize/close buttons.

### ⚡ Live Hardware Telemetry (~1s Refresh)
- **CPU**: Model name, real-time clock frequency (GHz), overall CPU utilization %, core/thread topologies, and package/core temperatures.
- **Multi-GPU (Separate iGPU & dGPU)**: Distinct detection and separate monitoring for every GPU in the laptop (e.g. Intel Iris Xe / AMD Radeon iGPU + NVIDIA GeForce RTX dGPU via NVML & DXGI/PDH), displaying utilization %, clock speeds, VRAM allocation (Used / Total), and die temperatures.
- **Volatile Memory (RAM)**: Live RAM usage in GB, total memory, percentage breakdown (In Use, Cached, Free), and memory speed badges.
- **Storage / SSD**: Active storage drive detection, real-time Read and Write throughput (MB/s), drive utilization, and drive temperatures where supported.
- **Network I/O**: Real-time Downlink and Uplink bandwidth (Mbps / MB/s), active network interface name, and connectivity status.
- **Thermal Dynamics**: Real-time thermal sensors for CPU package, GPU die, and SSD drives.

### 🛡️ Fault-Tolerant & Lightweight
- Graceful N/A fallback for unavailable sensors with zero exceptions or crashing.
- Low overhead (< 1.5% CPU during active 1s polling, leak-free memory management).

---

## Quick Start (Run Standalone .EXE)

You can run the pre-compiled standalone executable directly without needing to install Python:

1. Download or locate dist/GlassPerformanceHUD.exe.
2. Double-click **GlassPerformanceHUD.exe** to launch the overlay.
3. Use the header controls:
   - **HUD / 1920x550 Toggle**: Switch between standard HUD mode and ultra-wide secondary display mode.
   - **PIN Button**: Toggle Always-on-Top overlay mode.
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

Run the automated 5-tier test suite (184 test cases covering feature extraction, boundary conditions, cross-module interaction, real-world simulations, and adversarial chaos testing):

`ash
python tests/test_runner.py
`

---

## Project Structure

`
├── dist/
│   └── GlassPerformanceHUD.exe       # Standalone Windows executable
├── src/
│   ├── bridge/
│   │   └── api.py                   # PyWebView JavaScript-Python bridge
│   ├── gui/
│   │   └── window_manager.py        # Frameless transparent window controller
│   ├── telemetry/
│   │   ├── cpu_collector.py         # CPU frequency, load, thermals
│   │   ├── gpu_collector.py         # Multi-GPU NVML + DXGI/PDH collectors
│   │   ├── ram_collector.py         # Win32 GlobalMemoryStatusEx memory
│   │   ├── storage_collector.py     # Disk I/O throughput & capacity
│   │   ├── network_collector.py     # Bandwidth downlink/uplink monitor
│   │   ├── thermals.py              # Thermal dynamics aggregation
│   │   └── engine.py                # Telemetry polling engine coordinator
│   └── main.py                      # Application entry point
├── ui/
│   ├── index.html                   # HUD glassmorphism layout
│   ├── js/
│   │   ├── app.js                   # UI update loop & profile reflow
│   │   └── gauges.js                # SVG circular progress gauge renderer
│   └── styles/
│       ├── glass_hud.css            # Frosted glass, brackets & neon glow
│       └── tailwind.css             # Design tokens & typography
├── tests/                           # 5-Tier automated test suite (184 tests)
├── build_exe.py                     # PyInstaller automated packaging pipeline
└── requirements.txt                 # Python dependencies
`

---

## License & Credits
Design inspired by the Aetheric HUD concept. Built with Python, PyWebView, and Tailwind CSS.
