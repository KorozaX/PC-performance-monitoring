# Original User Request

## Initial Request — 2026-08-21T13:04:42+07:00

Develop a fully functional, lightweight Windows .exe application that displays live laptop hardware performance statistics in a modern, transparent, glassmorphism HUD interface.

Working directory for this project: C:\Users\Koroza\Documents\Antigravity\Performance Stats
Your agent working directory: C:\Users\Koroza\Documents\Antigravity\Performance Stats\.agents\orchestrator_1
User request record: C:\Users\Koroza\Documents\Antigravity\Performance Stats\ORIGINAL_REQUEST.md
Reference design files: C:\Users\Koroza\Documents\Antigravity\Performance Stats\stitch_glass_performance_hud_concept_idea (DESIGN.md, code.html, screen.png)

Key Requirements & Acceptance Criteria:
- R1. Glassmorphism HUD Overlay Window & Screen Modes (borderless, transparent HUD overlay floating above desktop, frosted glass backdrop blur, #00daf3 electric cyan / #d1bcff obsidian purple accents, HUD corner brackets, circular gauges, Space Grotesk / JetBrains Mono typography, draggable, pin always-on-top, minimize/close, Standard HUD mode + Ultra-Wide 1920x550 secondary screen mode).
- R2. Real-Time Hardware Telemetry Monitoring (~1s update):
  * CPU: Model name, clock frequency (GHz), overall CPU load %, core temperature (where available), core/thread details.
  * GPU(s): Distinct detection and separate monitoring sections for every installed GPU (integrated graphics + dedicated GPUs, e.g. Intel UHD/Iris Xe + NVIDIA GeForce/RTX, or AMD Radeon), showing GPU model, load %, clock frequency, VRAM usage/total, GPU temperature.
  * RAM: Memory utilization %, used GB, available/free GB, total physical GB, memory speed/type badge, memory distribution breakdown.
  * Storage/SSD: Detect system storage drives, read/write throughput (MB/s), drive activity %, capacity, temperature where exposed.
  * Network: Real-time download/upload bandwidth throughput (Mbps or MB/s), active interface name, connection state.
- R3. Fault-Tolerance, Missing Sensor Handling & Low Overhead (< 1-2% idle CPU, no crashing on unavailable sensors, display N/A).
- R4. Automated Testing & Verification (automated verification scripts or unit tests to validate telemetry data extraction and verify sensor fallbacks).
- R5. Standalone Windows Executable Build (package and compile into a standalone Windows .exe binary ready to launch directly on Windows).
