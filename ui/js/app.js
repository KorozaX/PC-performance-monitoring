/**
 * ui/js/app.js
 * Glassmorphism Performance HUD UI Controller & Bridge Event Handler.
 * Integrates real-time hardware telemetry streams with reactive DOM widgets.
 */

(function (window) {
  "use strict";

  // Application State
  const state = {
    currentMode: "standard", // "standard" (1200x800) | "ultrawide" (1920x550)
    isPinned: true,
    selectedGpuIndex: 0,
    latestSnapshot: null,
    isBridgeReady: false,
  };

  /**
   * DOM Element Cache
   */
  const DOM = {
    body: document.body,
    statusPill: document.getElementById("status-pill"),
    statusText: document.getElementById("status-text"),
    statusPing: document.getElementById("status-ping"),
    statusDot: document.getElementById("status-dot"),

    // Window Controls
    pinBtn: document.getElementById("btn-pin"),
    modeBtn: document.getElementById("btn-mode"),
    modeLabel: document.getElementById("mode-label"),
    minBtn: document.getElementById("btn-min"),
    closeBtn: document.getElementById("btn-close"),

    // CPU Elements
    cpuCircle: document.getElementById("cpu-progress-circle"),
    cpuLoadText: document.getElementById("cpu-load-text"),
    cpuFreqText: document.getElementById("cpu-freq-text"),
    cpuModelText: document.getElementById("cpu-model-text"),
    cpuStatusTag: document.getElementById("cpu-status-tag"),

    // GPU Elements
    gpuCircle: document.getElementById("gpu-progress-circle"),
    gpuLoadText: document.getElementById("gpu-load-text"),
    gpuFreqText: document.getElementById("gpu-freq-text"),
    gpuModelText: document.getElementById("gpu-model-text"),
    gpuStatusTag: document.getElementById("gpu-status-tag"),
    gpuVramText: document.getElementById("gpu-vram-text"),
    gpuTabsContainer: document.getElementById("gpu-tabs-container"),

    // Thermals Elements
    tempCpuText: document.getElementById("temp-cpu-text"),
    tempCpuBar: document.getElementById("temp-cpu-bar"),
    tempGpuText: document.getElementById("temp-gpu-text"),
    tempGpuBar: document.getElementById("temp-gpu-bar"),
    tempSsdText: document.getElementById("temp-ssd-text"),
    tempSsdBar: document.getElementById("temp-ssd-bar"),

    // Network Elements
    netDownText: document.getElementById("net-down-text"),
    netDownUnit: document.getElementById("net-down-unit"),
    netUpText: document.getElementById("net-up-text"),
    netUpUnit: document.getElementById("net-up-unit"),
    netAdapterBadge: document.getElementById("net-adapter-badge"),
    netStateDot: document.getElementById("net-state-dot"),

    // RAM Elements
    ramUsedText: document.getElementById("ram-used-text"),
    ramTotalText: document.getElementById("ram-total-text"),
    ramTypeBadge: document.getElementById("ram-type-badge"),
    ramBarInUse: document.getElementById("ram-bar-in-use"),
    ramBarCached: document.getElementById("ram-bar-cached"),
    ramLegendInUse: document.getElementById("ram-legend-in-use"),
    ramLegendCached: document.getElementById("ram-legend-cached"),
    ramLegendFree: document.getElementById("ram-legend-free"),

    // Storage Elements
    ssdReadText: document.getElementById("ssd-read-text"),
    ssdWriteText: document.getElementById("ssd-write-text"),
    ssdTypeBadge: document.getElementById("ssd-type-badge"),
    ssdDriveInfo: document.getElementById("ssd-drive-info"),
  };

  /**
   * Updates CPU Section
   */
  function updateCPU(cpu) {
    if (!cpu) return;

    // Load gauge
    const loadPct = typeof cpu.load_pct === "number" ? cpu.load_pct : 0;
    HUDGauges.updateCircularGauge(DOM.cpuCircle, DOM.cpuLoadText, loadPct);

    // Clock Frequency
    if (cpu.freq_ghz && cpu.freq_ghz !== "N/A") {
      DOM.cpuFreqText.textContent = `${parseFloat(cpu.freq_ghz).toFixed(1)} GHz`;
    } else {
      DOM.cpuFreqText.textContent = "N/A GHz";
    }

    // Model Name
    if (cpu.model && DOM.cpuModelText) {
      DOM.cpuModelText.textContent = cpu.model;
      DOM.cpuModelText.title = cpu.model;
    }

    // Status Tag
    if (DOM.cpuStatusTag) {
      DOM.cpuStatusTag.textContent = loadPct > 80 ? "CPU // PEAK LOAD" : "CPU // ACTIVE";
      DOM.cpuStatusTag.style.color = loadPct > 80 ? "var(--color-error)" : "var(--color-primary)";
    }
  }

  /**
   * Updates GPU Section and Multi-GPU Switcher
   */
  function updateGPU(gpus) {
    if (!gpus || !Array.isArray(gpus) || gpus.length === 0) {
      HUDGauges.updateCircularGauge(DOM.gpuCircle, DOM.gpuLoadText, "N/A");
      if (DOM.gpuFreqText) DOM.gpuFreqText.textContent = "N/A";
      if (DOM.gpuModelText) DOM.gpuModelText.textContent = "GPU Not Detected";
      if (DOM.gpuTabsContainer) DOM.gpuTabsContainer.innerHTML = "";
      return;
    }

    // Build or update Multi-GPU tabs if multiple GPUs detected
    if (DOM.gpuTabsContainer) {
      if (gpus.length > 1) {
        DOM.gpuTabsContainer.style.display = "flex";
        let tabsHtml = "";
        gpus.forEach((gpu, idx) => {
          const isActive = idx === state.selectedGpuIndex;
          const shortName = gpu.vendor ? `${gpu.vendor} ${gpu.type === "dedicated" ? "dGPU" : "iGPU"}` : `GPU ${idx}`;
          const activeClass = isActive
            ? "bg-secondary-container/40 text-secondary-fixed border-secondary-fixed"
            : "bg-surface-container-high/40 text-on-surface-variant/70 border-transparent hover:text-on-surface";
          tabsHtml += `<button class="px-2 py-0.5 text-[10px] font-label-caps rounded border ${activeClass} transition-colors" data-gpu-index="${idx}">${shortName}</button>`;
        });
        DOM.gpuTabsContainer.innerHTML = tabsHtml;

        // Attach tab listeners
        DOM.gpuTabsContainer.querySelectorAll("button").forEach((btn) => {
          btn.addEventListener("click", (e) => {
            e.stopPropagation();
            state.selectedGpuIndex = parseInt(btn.getAttribute("data-gpu-index"), 10);
            if (state.latestSnapshot && state.latestSnapshot.gpus) {
              updateGPU(state.latestSnapshot.gpus);
            }
          });
        });
      } else {
        DOM.gpuTabsContainer.style.display = "none";
      }
    }

    // Get currently selected GPU
    const activeGpu = gpus[state.selectedGpuIndex] || gpus[0];
    const loadPct = typeof activeGpu.load_pct === "number" ? activeGpu.load_pct : 0;

    HUDGauges.updateCircularGauge(DOM.gpuCircle, DOM.gpuLoadText, loadPct);

    // Clock
    if (activeGpu.freq_mhz && activeGpu.freq_mhz !== "N/A") {
      const mhz = parseFloat(activeGpu.freq_mhz);
      DOM.gpuFreqText.textContent = mhz >= 1000 ? `${(mhz / 1000).toFixed(2)} GHz` : `${Math.round(mhz)} MHz`;
    } else {
      DOM.gpuFreqText.textContent = "N/A";
    }

    // Model & Status
    if (DOM.gpuModelText) {
      DOM.gpuModelText.textContent = activeGpu.model || "GPU";
      DOM.gpuModelText.title = activeGpu.model || "GPU";
    }

    if (DOM.gpuStatusTag) {
      DOM.gpuStatusTag.textContent = activeGpu.type === "dedicated" ? "GPU // DEDICATED" : "GPU // INTEGRATED";
    }

    // VRAM Badge / Tooltip
    if (DOM.gpuVramText) {
      if (activeGpu.vram_total_gb && activeGpu.vram_total_gb !== "N/A") {
        const used = typeof activeGpu.vram_used_gb === "number" ? activeGpu.vram_used_gb.toFixed(1) : "0.0";
        const total = typeof activeGpu.vram_total_gb === "number" ? activeGpu.vram_total_gb.toFixed(1) : activeGpu.vram_total_gb;
        DOM.gpuVramText.textContent = `VRAM: ${used} / ${total} GB`;
      } else if (activeGpu.vram_used_gb && activeGpu.vram_used_gb !== "N/A") {
        DOM.gpuVramText.textContent = `VRAM: ${parseFloat(activeGpu.vram_used_gb).toFixed(1)} GB`;
      } else {
        DOM.gpuVramText.textContent = "VRAM: Shared";
      }
    }
  }

  /**
   * Updates Thermals Panel
   */
  function updateThermals(thermals) {
    if (!thermals) return;

    HUDGauges.updateThermalBar(DOM.tempCpuBar, DOM.tempCpuText, thermals.cpu_c);
    HUDGauges.updateThermalBar(DOM.tempGpuBar, DOM.tempGpuText, thermals.gpu_c);
    HUDGauges.updateThermalBar(DOM.tempSsdBar, DOM.tempSsdText, thermals.ssd_c);
  }

  /**
   * Updates Network I/O Panel
   */
  function updateNetwork(network) {
    if (!network) return;

    // Downlink
    const downMbs = typeof network.downlink_mbs === "number" ? network.downlink_mbs : 0;
    const downMbps = typeof network.downlink_mbps === "number" ? network.downlink_mbps : 0;
    DOM.netDownText.textContent = downMbps >= 10.0 ? Math.round(downMbps).toString() : downMbps.toFixed(1);
    DOM.netDownUnit.textContent = "Mbps";

    // Uplink
    const upMbps = typeof network.uplink_mbps === "number" ? network.uplink_mbps : 0;
    DOM.netUpText.textContent = upMbps >= 10.0 ? Math.round(upMbps).toString() : upMbps.toFixed(1);
    DOM.netUpUnit.textContent = "Mbps";

    // Active Adapter Badge & Connection State
    if (DOM.netAdapterBadge) {
      DOM.netAdapterBadge.textContent = network.interface || "No Active Adapter";
      DOM.netAdapterBadge.title = network.interface || "No Active Adapter";
    }

    if (DOM.netStateDot) {
      if (network.connected) {
        DOM.netStateDot.className = "w-2 h-2 rounded-full bg-primary active-pulse-cyan";
      } else {
        DOM.netStateDot.className = "w-2 h-2 rounded-full bg-error";
      }
    }
  }

  /**
   * Updates Volatile Memory (RAM) Panel
   */
  function updateRAM(ram) {
    if (!ram) return;

    const usedGb = typeof ram.used_gb === "number" ? ram.used_gb.toFixed(1) : "0.0";
    const totalGb = typeof ram.total_gb === "number" ? ram.total_gb.toFixed(1) : "0.0";

    DOM.ramUsedText.textContent = usedGb;
    DOM.ramTotalText.textContent = `/ ${totalGb} GB`;

    if (DOM.ramTypeBadge) {
      DOM.ramTypeBadge.textContent = ram.type_badge || "RAM";
    }

    // Segmented Bar
    const dist = ram.distribution || {
      in_use_pct: Math.round(ram.load_pct || 0),
      cached_pct: 10,
      free_pct: Math.max(0, 100 - Math.round(ram.load_pct || 0) - 10),
    };

    const inUsePct = Math.max(0, Math.min(100, dist.in_use_pct || 0));
    const cachedPct = Math.max(0, Math.min(100 - inUsePct, dist.cached_pct || 0));

    DOM.ramBarInUse.style.width = `${inUsePct}%`;
    DOM.ramBarCached.style.width = `${cachedPct}%`;

    DOM.ramLegendInUse.textContent = `IN USE (${inUsePct}%)`;
    DOM.ramLegendCached.textContent = `CACHED (${cachedPct}%)`;
    DOM.ramLegendFree.textContent = `FREE (${Math.max(0, 100 - inUsePct - cachedPct)}%)`;
  }

  /**
   * Updates Non-Volatile Storage (SSD) Panel
   */
  function updateStorage(storage) {
    if (!storage || !storage.drives || storage.drives.length === 0) return;

    const primaryDrive = storage.drives[0];

    const readMbs = typeof primaryDrive.read_mbs === "number" ? primaryDrive.read_mbs : 0;
    const writeMbs = typeof primaryDrive.write_mbs === "number" ? primaryDrive.write_mbs : 0;

    DOM.ssdReadText.textContent = HUDGauges.formatNumber(readMbs, readMbs < 10 ? 1 : 0);
    DOM.ssdWriteText.textContent = HUDGauges.formatNumber(writeMbs, writeMbs < 10 ? 1 : 0);

    if (DOM.ssdTypeBadge) {
      DOM.ssdTypeBadge.textContent = primaryDrive.type_badge || "NVMe";
    }

    if (DOM.ssdDriveInfo) {
      const used = typeof primaryDrive.used_gb === "number" ? Math.round(primaryDrive.used_gb) : 0;
      const total = typeof primaryDrive.total_gb === "number" ? Math.round(primaryDrive.total_gb) : 0;
      const act = typeof primaryDrive.load_pct === "number" ? Math.round(primaryDrive.load_pct) : 0;
      DOM.ssdDriveInfo.textContent = `${primaryDrive.device || "C:"} [${used}/${total} GB] • ${act}% Active`;
    }
  }

  /**
   * Updates Header System Status Badge
   */
  function updateSystemStatus(snapshot) {
    const cpuLoad = (snapshot.cpu && snapshot.cpu.load_pct) || 0;
    const cpuTemp = (snapshot.thermals && snapshot.thermals.cpu_c) || 0;
    const gpuTemp = (snapshot.thermals && snapshot.thermals.gpu_c) || 0;

    const isThermalAlert = (typeof cpuTemp === "number" && cpuTemp >= 85) || (typeof gpuTemp === "number" && gpuTemp >= 85);
    const isHighLoad = cpuLoad >= 90;

    if (isThermalAlert) {
      DOM.statusText.textContent = "THERMAL ALERT";
      DOM.statusText.style.color = "var(--color-error)";
      DOM.statusPing.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-error opacity-75";
      DOM.statusDot.className = "relative inline-flex rounded-full h-3 w-3 bg-error";
    } else if (isHighLoad) {
      DOM.statusText.textContent = "PEAK LOAD";
      DOM.statusText.style.color = "var(--color-secondary)";
      DOM.statusPing.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary opacity-75";
      DOM.statusDot.className = "relative inline-flex rounded-full h-3 w-3 bg-secondary";
    } else {
      DOM.statusText.textContent = "SYSTEM OPTIMAL";
      DOM.statusText.style.color = "var(--color-primary)";
      DOM.statusPing.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75";
      DOM.statusDot.className = "relative inline-flex rounded-full h-3 w-3 bg-primary";
    }
  }

  /**
   * Main Dispatcher for Telemetry Updates
   * @param {Object} snapshot - Telemetry snapshot conforming to PROJECT.md schema.
   */
  window.onTelemetryUpdate = function (snapshot) {
    if (!snapshot) return;
    state.latestSnapshot = snapshot;

    updateCPU(snapshot.cpu);
    updateGPU(snapshot.gpus);
    updateThermals(snapshot.thermals);
    updateNetwork(snapshot.network);
    updateRAM(snapshot.ram);
    updateStorage(snapshot.storage);
    updateSystemStatus(snapshot);
  };

  /**
   * Screen Mode Switcher
   */
  function setScreenMode(mode) {
    state.currentMode = mode;
    DOM.body.className = `bg-background text-on-surface font-body-md min-h-screen mode-${mode}`;

    if (DOM.modeLabel) {
      DOM.modeLabel.textContent = mode === "ultrawide" ? "ULTRAWIDE" : "STANDARD";
    }

    if (window.pywebview && window.pywebview.api && window.pywebview.api.set_screen_mode) {
      window.pywebview.api.set_screen_mode(mode).catch((err) => {
        console.error("Bridge set_screen_mode error:", err);
      });
    }
  }

  /**
   * Setup Event Listeners
   */
  function initEventListeners() {
    // Pin Always-on-Top Toggle
    if (DOM.pinBtn) {
      DOM.pinBtn.addEventListener("click", () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_pin_top) {
          window.pywebview.api.toggle_pin_top().then((isPinned) => {
            state.isPinned = isPinned;
            DOM.pinBtn.classList.toggle("text-primary", isPinned);
            DOM.pinBtn.classList.toggle("text-on-surface-variant", !isPinned);
          });
        } else {
          state.isPinned = !state.isPinned;
          DOM.pinBtn.classList.toggle("text-primary", state.isPinned);
          DOM.pinBtn.classList.toggle("text-on-surface-variant", !state.isPinned);
        }
      });
    }

    // Screen Mode Switcher
    if (DOM.modeBtn) {
      DOM.modeBtn.addEventListener("click", () => {
        const nextMode = state.currentMode === "standard" ? "ultrawide" : "standard";
        setScreenMode(nextMode);
      });
    }

    // Window Minimize
    if (DOM.minBtn) {
      DOM.minBtn.addEventListener("click", () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.minimize_window) {
          window.pywebview.api.minimize_window();
        }
      });
    }

    // Window Close
    if (DOM.closeBtn) {
      DOM.closeBtn.addEventListener("click", () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.close_window) {
          window.pywebview.api.close_window();
        } else {
          window.close();
        }
      });
    }

    // Keyboard Shortcuts
    window.addEventListener("keydown", (e) => {
      if (e.ctrlKey && e.shiftKey) {
        if (e.key === "P" || e.key === "p") {
          if (DOM.pinBtn) DOM.pinBtn.click();
        } else if (e.key === "M" || e.key === "m") {
          if (DOM.modeBtn) DOM.modeBtn.click();
        }
      }
    });
  }

  /**
   * Browser Offline Mock Simulation (Used when testing without native PyWebView container)
   */
  function startBrowserMockTelemetry() {
    console.info("Starting browser mock telemetry ticker (development mode)...");
    let tick = 0;

    setInterval(() => {
      tick++;
      const sinVal = Math.sin(tick * 0.2);
      const mockSnapshot = {
        timestamp: Date.now() / 1000,
        cpu: {
          model: "13th Gen Intel(R) Core(TM) i9-13900HX",
          load_pct: Math.round(20 + 60 * Math.abs(sinVal)),
          freq_ghz: 3.8 + 1.2 * Math.abs(sinVal),
          cores_physical: 24,
          cores_logical: 32,
          temperature_c: Math.round(48 + 35 * Math.abs(sinVal)),
          per_core_load: Array(24).fill(Math.round(20 + 50 * Math.abs(sinVal))),
        },
        gpus: [
          {
            id: 0,
            type: "dedicated",
            vendor: "NVIDIA",
            model: "NVIDIA GeForce RTX 4080 Laptop GPU",
            load_pct: Math.round(30 + 65 * Math.abs(Math.cos(tick * 0.15))),
            freq_mhz: 1850 + Math.round(400 * Math.abs(sinVal)),
            vram_used_gb: 4.2 + 6.0 * Math.abs(sinVal),
            vram_total_gb: 12.0,
            temperature_c: Math.round(52 + 30 * Math.abs(sinVal)),
          },
          {
            id: 1,
            type: "integrated",
            vendor: "Intel",
            model: "Intel(R) UHD Graphics",
            load_pct: 6,
            freq_mhz: "N/A",
            vram_used_gb: 0.6,
            vram_total_gb: "N/A",
            temperature_c: "N/A",
          },
        ],
        ram: {
          load_pct: 42.5,
          used_gb: 27.2,
          free_gb: 36.8,
          total_gb: 64.0,
          type_badge: "DDR5-4800",
          distribution: { in_use_pct: 43, cached_pct: 18, free_pct: 39 },
        },
        storage: {
          drives: [
            {
              device: "C:",
              type_badge: "NVMe Gen4",
              used_gb: 480.2,
              total_gb: 1024.0,
              load_pct: Math.round(15 + 40 * Math.abs(sinVal)),
              read_mbs: Math.round(120 + 3500 * Math.abs(sinVal)),
              write_mbs: Math.round(45 + 1800 * Math.abs(Math.cos(tick * 0.2))),
              temperature_c: 41.0,
            },
          ],
        },
        network: {
          interface: "Wi-Fi 6E (Intel Killer AX1675i)",
          connected: true,
          downlink_mbps: Math.round(140 + 650 * Math.abs(sinVal)),
          uplink_mbps: Math.round(28 + 95 * Math.abs(Math.cos(tick * 0.3))),
          downlink_mbs: (140 + 650 * Math.abs(sinVal)) / 8.0,
          uplink_mbs: (28 + 95 * Math.abs(Math.cos(tick * 0.3))) / 8.0,
        },
        thermals: {
          cpu_c: Math.round(48 + 35 * Math.abs(sinVal)),
          gpu_c: Math.round(52 + 30 * Math.abs(sinVal)),
          ssd_c: 41.0,
        },
      };

      window.onTelemetryUpdate(mockSnapshot);
    }, 1000);
  }

  /**
   * Initialization Routine
   */
  function init() {
    initEventListeners();
    setScreenMode("standard");

    // Handle PyWebView Ready Hook
    window.addEventListener("pywebviewready", () => {
      state.isBridgeReady = true;
      console.info("PyWebView Bridge is ready.");

      if (window.pywebview.api && window.pywebview.api.get_telemetry_snapshot) {
        window.pywebview.api.get_telemetry_snapshot().then((snap) => {
          if (snap && Object.keys(snap).length > 0) {
            window.onTelemetryUpdate(snap);
          }
        });
      }
    });

    // Check if running directly in browser without PyWebView
    setTimeout(() => {
      if (!window.pywebview && !state.latestSnapshot) {
        startBrowserMockTelemetry();
      }
    }, 800);
  }

  // Run on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
