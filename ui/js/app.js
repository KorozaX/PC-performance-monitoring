/**
 * ui/js/app.js
 * Glassmorphism Performance HUD UI Controller & PyWebView JS-Python Bridge Handler.
 * Integrates real-time hardware telemetry streams with reactive DOM widgets,
 * simultaneous multi-GPU views, top process ranking, and tab navigation routing.
 */

(function (window) {
  "use strict";

  // Application State
  const state = {
    currentMode: "standard", // "standard" (1200x800) | "ultrawide" (1920x550)
    isPinned: true,
    isMaximized: false,
    activeTab: "monitor", // "monitor" | "telemetry" | "system"
    selectedGpuIndex: 0,
    latestSnapshot: null,
    isBridgeReady: false,
    pollingTimer: null,
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
    maxBtn: document.getElementById("btn-max"),
    iconMax: document.getElementById("icon-max"),
    closeBtn: document.getElementById("btn-close"),

    // Navigation Tabs
    tabMonitor: document.getElementById("tab-monitor"),
    tabTelemetry: document.getElementById("tab-telemetry"),
    tabSystem: document.getElementById("tab-system"),
    sideTabMonitor: document.getElementById("side-tab-monitor"),
    sideTabTelemetry: document.getElementById("side-tab-telemetry"),
    sideTabSystem: document.getElementById("side-tab-system"),

    // View Panels
    viewMonitor: document.getElementById("view-monitor"),
    viewTelemetry: document.getElementById("view-telemetry"),
    viewSystem: document.getElementById("view-system"),

    // CPU Elements
    cpuCircle: document.getElementById("cpu-progress-circle"),
    cpuLoadText: document.getElementById("cpu-load-text"),
    cpuFreqText: document.getElementById("cpu-freq-text"),
    cpuModelText: document.getElementById("cpu-model-text"),
    cpuStatusTag: document.getElementById("cpu-status-tag"),

    // GPU Primary (GPU 0) Elements
    gpuCircle: document.getElementById("gpu-progress-circle"),
    gpuLoadText: document.getElementById("gpu-load-text"),
    gpuFreqText: document.getElementById("gpu-freq-text"),
    gpuModelText: document.getElementById("gpu-model-text"),
    gpuStatusTag: document.getElementById("gpu-status-tag"),
    gpuVramText: document.getElementById("gpu-vram-text"),
    gpuTabsContainer: document.getElementById("gpu-tabs-container"),
    gpuCountBadge: document.getElementById("gpu-count-badge"),

    // GPU Secondary (GPU 1) Elements
    gpuSecondaryWrapper: document.getElementById("gpu-secondary-wrapper"),
    gpuSecondaryCircle: document.getElementById("gpu-secondary-circle"),
    gpuSecondaryLoadText: document.getElementById("gpu-secondary-load-text"),
    gpuSecondaryFreqText: document.getElementById("gpu-secondary-freq-text"),
    gpuSecondaryModelText: document.getElementById("gpu-secondary-model-text"),
    gpuSecondaryStatusTag: document.getElementById("gpu-secondary-status-tag"),
    gpuSecondaryVramText: document.getElementById("gpu-secondary-vram-text"),

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
    ramUsedMb: document.getElementById("ram-used-mb"),
    ramTotalMb: document.getElementById("ram-total-mb"),
    ramLoadText: document.getElementById("ram-load-text"),
    ramFreeText: document.getElementById("ram-free-text"),
    ramCommittedText: document.getElementById("ram-committed-text"),
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

    // Processes Elements
    processesTableBody: document.getElementById("processes-table-body"),
    extendedProcessesTableBody: document.getElementById("extended-processes-table-body"),

    // Telemetry View Elements
    coreCountBadge: document.getElementById("core-count-badge"),
    perCoreGrid: document.getElementById("per-core-grid"),

    // System View Elements
    sysCpuModel: document.getElementById("sys-cpu-model"),
    sysCpuArch: document.getElementById("sys-cpu-arch"),
    sysCpuCores: document.getElementById("sys-cpu-cores"),
    sysCpuBase: document.getElementById("sys-cpu-base"),
    sysCpuCache: document.getElementById("sys-cpu-cache"),
    sysGpusContainer: document.getElementById("sys-gpus-container"),
    sysRamTotal: document.getElementById("sys-ram-total"),
    sysRamType: document.getElementById("sys-ram-type"),
    sysRamSpeed: document.getElementById("sys-ram-speed"),
    sysRamCommitted: document.getElementById("sys-ram-committed"),
    sysOsName: document.getElementById("sys-os-name"),
    sysMotherboard: document.getElementById("sys-motherboard"),
    sysBios: document.getElementById("sys-bios"),
  };

  /**
   * Switches Active View Tab (MONITOR | TELEMETRY | SYSTEM)
   * @param {string} tabName - 'monitor' | 'telemetry' | 'system'
   */
  function switchViewTab(tabName) {
    if (!tabName) return;
    const normTab = tabName.toLowerCase();
    state.activeTab = normTab;

    // View Panels Toggle
    if (DOM.viewMonitor) DOM.viewMonitor.classList.toggle("hidden", normTab !== "monitor");
    if (DOM.viewTelemetry) DOM.viewTelemetry.classList.toggle("hidden", normTab !== "telemetry");
    if (DOM.viewSystem) DOM.viewSystem.classList.toggle("hidden", normTab !== "system");

    // Header Nav Tabs Highlight
    const headerTabs = [DOM.tabMonitor, DOM.tabTelemetry, DOM.tabSystem];
    headerTabs.forEach((tab) => {
      if (!tab) return;
      const isTarget = tab.getAttribute("data-tab") === normTab;
      tab.classList.toggle("active", isTarget);
      tab.classList.toggle("text-primary", isTarget);
      tab.classList.toggle("font-bold", isTarget);
      tab.classList.toggle("text-on-surface-variant/70", !isTarget);
      tab.classList.toggle("font-medium", !isTarget);
    });

    // Sidebar Nav Buttons Highlight
    const sidebarTabs = [
      { el: DOM.sideTabMonitor, name: "monitor" },
      { el: DOM.sideTabTelemetry, name: "telemetry" },
      { el: DOM.sideTabSystem, name: "system" },
    ];
    sidebarTabs.forEach(({ el, name }) => {
      if (!el) return;
      const isTarget = name === normTab;
      el.classList.toggle("sidebar-tab-active", isTarget);
      el.classList.toggle("bg-primary/10", isTarget);
      el.classList.toggle("text-primary", isTarget);
      el.classList.toggle("border-primary", isTarget);
      el.classList.toggle("text-on-surface-variant/70", !isTarget);
      el.classList.toggle("border-transparent", !isTarget);
    });

    // Notify Bridge if supported
    if (window.pywebview && window.pywebview.api && window.pywebview.api.switch_tab) {
      window.pywebview.api.switch_tab(normTab.toUpperCase()).catch(() => {});
    }

    // Refresh view specific components immediately
    if (state.latestSnapshot) {
      if (normTab === "telemetry") {
        updateTelemetryView(state.latestSnapshot);
      } else if (normTab === "system") {
        updateSystemView(state.latestSnapshot);
      }
    }
  }

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
   * Updates GPU Section with Simultaneous Multi-GPU Display (R2)
   */
  function updateGPU(gpus) {
    if (!gpus || !Array.isArray(gpus) || gpus.length === 0) {
      HUDGauges.updateCircularGauge(DOM.gpuCircle, DOM.gpuLoadText, "N/A");
      if (DOM.gpuFreqText) DOM.gpuFreqText.textContent = "N/A";
      if (DOM.gpuModelText) DOM.gpuModelText.textContent = "GPU Not Detected";
      if (DOM.gpuTabsContainer) DOM.gpuTabsContainer.innerHTML = "";
      if (DOM.gpuSecondaryWrapper) DOM.gpuSecondaryWrapper.classList.add("hidden");
      return;
    }

    // Update GPU Count Badge
    if (DOM.gpuCountBadge) {
      DOM.gpuCountBadge.textContent = gpus.length > 1 ? `${gpus.length} GPUS ACTIVE` : "1 GPU ACTIVE";
    }

    // Primary GPU (GPU 0 / Discrete or first adapter)
    const primaryGpu = gpus[0];
    const primaryLoad = typeof primaryGpu.load_pct === "number" ? primaryGpu.load_pct : 0;
    HUDGauges.updateCircularGauge(DOM.gpuCircle, DOM.gpuLoadText, primaryLoad);

    if (DOM.gpuFreqText) {
      if (primaryGpu.freq_mhz && primaryGpu.freq_mhz !== "N/A") {
        const mhz = parseFloat(primaryGpu.freq_mhz);
        DOM.gpuFreqText.textContent = mhz >= 1000 ? `${(mhz / 1000).toFixed(2)} GHz` : `${Math.round(mhz)} MHz`;
      } else {
        DOM.gpuFreqText.textContent = "N/A";
      }
    }

    if (DOM.gpuModelText) {
      DOM.gpuModelText.textContent = primaryGpu.model || primaryGpu.name || "GPU";
      DOM.gpuModelText.title = primaryGpu.model || primaryGpu.name || "GPU";
    }

    if (DOM.gpuStatusTag) {
      const typeLabel = primaryGpu.type === "dedicated" ? "DEDICATED" : "INTEGRATED";
      DOM.gpuStatusTag.textContent = `GPU 0 // ${typeLabel}`;
    }

    if (DOM.gpuVramText) {
      if (primaryGpu.vram_total_gb && primaryGpu.vram_total_gb !== "N/A") {
        const used = typeof primaryGpu.vram_used_gb === "number" ? primaryGpu.vram_used_gb.toFixed(1) : "0.0";
        const total = typeof primaryGpu.vram_total_gb === "number" ? primaryGpu.vram_total_gb.toFixed(1) : primaryGpu.vram_total_gb;
        DOM.gpuVramText.textContent = `VRAM: ${used} / ${total} GB`;
      } else if (primaryGpu.vram_used_gb && primaryGpu.vram_used_gb !== "N/A") {
        DOM.gpuVramText.textContent = `VRAM: ${parseFloat(primaryGpu.vram_used_gb).toFixed(1)} GB`;
      } else {
        DOM.gpuVramText.textContent = "VRAM: Shared";
      }
    }

    // Secondary GPU (GPU 1 / Integrated or secondary discrete adapter)
    if (gpus.length > 1 && DOM.gpuSecondaryWrapper) {
      DOM.gpuSecondaryWrapper.classList.remove("hidden");
      DOM.gpuSecondaryWrapper.classList.add("flex");

      const secGpu = gpus[1];
      const secLoad = typeof secGpu.load_pct === "number" ? secGpu.load_pct : 0;
      HUDGauges.updateCircularGauge(DOM.gpuSecondaryCircle, DOM.gpuSecondaryLoadText, secLoad);

      if (DOM.gpuSecondaryFreqText) {
        if (secGpu.freq_mhz && secGpu.freq_mhz !== "N/A") {
          const mhz = parseFloat(secGpu.freq_mhz);
          DOM.gpuSecondaryFreqText.textContent = mhz >= 1000 ? `${(mhz / 1000).toFixed(2)} GHz` : `${Math.round(mhz)} MHz`;
        } else {
          DOM.gpuSecondaryFreqText.textContent = "N/A";
        }
      }

      if (DOM.gpuSecondaryModelText) {
        DOM.gpuSecondaryModelText.textContent = secGpu.model || secGpu.name || "Secondary GPU";
        DOM.gpuSecondaryModelText.title = secGpu.model || secGpu.name || "Secondary GPU";
      }

      if (DOM.gpuSecondaryStatusTag) {
        const typeLabel = secGpu.type === "dedicated" ? "DEDICATED" : "INTEGRATED";
        DOM.gpuSecondaryStatusTag.textContent = `GPU 1 // ${typeLabel}`;
      }

      if (DOM.gpuSecondaryVramText) {
        if (secGpu.vram_total_gb && secGpu.vram_total_gb !== "N/A") {
          const used = typeof secGpu.vram_used_gb === "number" ? secGpu.vram_used_gb.toFixed(1) : "0.0";
          const total = typeof secGpu.vram_total_gb === "number" ? secGpu.vram_total_gb.toFixed(1) : secGpu.vram_total_gb;
          DOM.gpuSecondaryVramText.textContent = `VRAM: ${used} / ${total} GB`;
        } else if (secGpu.vram_used_gb && secGpu.vram_used_gb !== "N/A") {
          DOM.gpuSecondaryVramText.textContent = `VRAM: ${parseFloat(secGpu.vram_used_gb).toFixed(1)} GB`;
        } else {
          DOM.gpuSecondaryVramText.textContent = "VRAM: Shared";
        }
      }
    } else if (DOM.gpuSecondaryWrapper) {
      DOM.gpuSecondaryWrapper.classList.add("hidden");
      DOM.gpuSecondaryWrapper.classList.remove("flex");
    }

    // Populate #gpu-tabs-container for test parity
    if (DOM.gpuTabsContainer) {
      if (gpus.length > 1) {
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
      } else {
        DOM.gpuTabsContainer.innerHTML = "";
      }
    }
  }

  /**
   * Updates Thermals Panel (R7)
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
   * Updates Volatile Memory (RAM) Panel (R5: Dual MB/GB)
   */
  function updateRAM(ram) {
    if (!ram) return;

    const usedGb = typeof ram.used_gb === "number" ? ram.used_gb.toFixed(1) : "0.0";
    const totalGb = typeof ram.total_gb === "number" ? ram.total_gb.toFixed(1) : "0.0";
    const freeGb = typeof ram.free_gb === "number" ? ram.free_gb.toFixed(1) : "0.0";

    const usedMb = typeof ram.used_mb === "number" ? Math.round(ram.used_mb) : Math.round(parseFloat(usedGb) * 1024);
    const totalMb = typeof ram.total_mb === "number" ? Math.round(ram.total_mb) : Math.round(parseFloat(totalGb) * 1024);
    const freeMb = typeof ram.free_mb === "number" ? Math.round(ram.free_mb) : Math.round(parseFloat(freeGb) * 1024);

    DOM.ramUsedText.textContent = usedGb;
    DOM.ramTotalText.textContent = `/ ${totalGb} GB`;

    if (DOM.ramUsedMb) DOM.ramUsedMb.textContent = `${HUDGauges.formatNumber(usedMb)} MB`;
    if (DOM.ramTotalMb) DOM.ramTotalMb.textContent = `/ ${HUDGauges.formatNumber(totalMb)} MB`;

    const loadPct = typeof ram.load_pct === "number" ? ram.load_pct : 0;
    if (DOM.ramLoadText) DOM.ramLoadText.textContent = `${loadPct.toFixed(1)}%`;

    if (DOM.ramFreeText) {
      DOM.ramFreeText.textContent = `Free: ${HUDGauges.formatNumber(freeMb)} MB`;
    }

    if (DOM.ramCommittedText) {
      if (ram.committed_mb && ram.commit_limit_mb) {
        DOM.ramCommittedText.textContent = `Committed: ${HUDGauges.formatNumber(Math.round(ram.committed_mb))} / ${HUDGauges.formatNumber(Math.round(ram.commit_limit_mb))} MB`;
      } else {
        DOM.ramCommittedText.textContent = `Committed: ${usedGb} / ${totalGb} GB`;
      }
    }

    if (DOM.ramTypeBadge) {
      DOM.ramTypeBadge.textContent = ram.type_badge || "DDR5";
    }

    // 3-Segment RAM Distribution Bar
    const dist = ram.distribution || {
      in_use_pct: Math.round(loadPct),
      cached_pct: 10,
      free_pct: Math.max(0, 100 - Math.round(loadPct) - 10),
    };

    const inUsePct = Math.max(0, Math.min(100, dist.in_use_pct || 0));
    const cachedPct = Math.max(0, Math.min(100 - inUsePct, dist.cached_pct || 0));
    const freePct = Math.max(0, 100 - inUsePct - cachedPct);

    DOM.ramBarInUse.style.width = `${inUsePct}%`;
    DOM.ramBarCached.style.width = `${cachedPct}%`;

    DOM.ramLegendInUse.textContent = `IN USE (${inUsePct}%)`;
    DOM.ramLegendCached.textContent = `CACHED (${cachedPct}%)`;
    DOM.ramLegendFree.textContent = `FREE (${freePct}%)`;
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
   * Updates Top 5 Resource-Consuming Processes Table (R3)
   */
  function updateProcesses(processes) {
    if (!DOM.processesTableBody) return;

    if (!processes || !Array.isArray(processes) || processes.length === 0) {
      DOM.processesTableBody.innerHTML = `
        <tr class="text-on-surface-variant/60">
          <td colspan="4" class="py-3 text-center">No active consumer processes detected</td>
        </tr>`;
      if (DOM.extendedProcessesTableBody) {
        DOM.extendedProcessesTableBody.innerHTML = `
          <tr class="text-on-surface-variant/60">
            <td colspan="5" class="py-4 text-center">No process telemetry available</td>
          </tr>`;
      }
      return;
    }

    // Render Top 5 Table in Monitor View
    const top5 = processes.slice(0, 5);
    let rowsHtml = "";
    top5.forEach((proc, idx) => {
      const cpuPct = typeof proc.cpu_pct === "number" ? proc.cpu_pct.toFixed(1) : "0.0";
      const memMb = typeof proc.memory_mb === "number" ? Math.round(proc.memory_mb) : 0;
      const name = proc.name || `PID_${proc.pid}`;
      const pid = proc.pid || "-";

      const cpuBarWidth = Math.min(100, Math.max(2, Math.round(parseFloat(cpuPct) * 2)));
      const memBarWidth = Math.min(100, Math.max(2, Math.round((memMb / 4096) * 100)));

      rowsHtml += `
        <tr class="process-row py-1">
          <td class="py-1 font-medium truncate max-w-[110px]" title="${name}">
            <span class="text-primary font-bold mr-1">#${idx + 1}</span>
            <span>${name}</span>
          </td>
          <td class="py-1 text-right text-on-surface-variant/70">${pid}</td>
          <td class="py-1 text-right">
            <div class="flex items-center justify-end gap-1">
              <div class="w-8 h-1 bg-surface-container-high rounded-full overflow-hidden hidden sm:block">
                <div class="h-full bg-primary" style="width: ${cpuBarWidth}%;"></div>
              </div>
              <span class="text-primary font-bold">${cpuPct}%</span>
            </div>
          </td>
          <td class="py-1 text-right">
            <div class="flex items-center justify-end gap-1">
              <div class="w-8 h-1 bg-surface-container-high rounded-full overflow-hidden hidden sm:block">
                <div class="h-full bg-secondary" style="width: ${memBarWidth}%;"></div>
              </div>
              <span class="text-on-surface">${HUDGauges.formatNumber(memMb)} <span class="text-[9px] text-on-surface-variant">MB</span></span>
            </div>
          </td>
        </tr>
      `;
    });
    DOM.processesTableBody.innerHTML = rowsHtml;

    // Render Extended Table in Telemetry View
    if (DOM.extendedProcessesTableBody) {
      const top10 = processes.slice(0, 10);
      let extRowsHtml = "";
      top10.forEach((proc, idx) => {
        const cpuPct = typeof proc.cpu_pct === "number" ? proc.cpu_pct.toFixed(1) : "0.0";
        const memMb = typeof proc.memory_mb === "number" ? Math.round(proc.memory_mb) : 0;
        const diskMb = typeof proc.disk_mbps === "number" ? proc.disk_mbps.toFixed(1) : "0.0";
        const name = proc.name || `PID_${proc.pid}`;
        const pid = proc.pid || "-";

        extRowsHtml += `
          <tr class="process-row py-1.5">
            <td class="py-1.5 font-medium truncate max-w-[140px]" title="${name}">
              <span class="text-secondary font-bold mr-1.5">#${idx + 1}</span>
              <span>${name}</span>
            </td>
            <td class="py-1.5 text-right text-on-surface-variant/70">${pid}</td>
            <td class="py-1.5 text-right text-primary font-bold">${cpuPct}%</td>
            <td class="py-1.5 text-right text-secondary">${HUDGauges.formatNumber(memMb)} MB</td>
            <td class="py-1.5 text-right text-on-surface-variant/90">${diskMb} MB/s</td>
          </tr>
        `;
      });
      DOM.extendedProcessesTableBody.innerHTML = extRowsHtml;
    }
  }

  /**
   * Updates Telemetry View Components (Per-Core Matrix, etc.)
   */
  function updateTelemetryView(snapshot) {
    if (!snapshot) return;

    // Per-Core CPU Load Matrix
    if (DOM.perCoreGrid && snapshot.cpu) {
      const perCore = snapshot.cpu.per_core_load || [];
      const totalCores = perCore.length || snapshot.cpu.cores_logical || 16;

      if (DOM.coreCountBadge) {
        DOM.coreCountBadge.textContent = `${totalCores} THREADS`;
      }

      let gridHtml = "";
      for (let i = 0; i < totalCores; i++) {
        const val = perCore[i] !== undefined ? Math.round(perCore[i]) : Math.round(snapshot.cpu.load_pct || 0);
        let colorClass = "bg-primary";
        if (val >= 80) colorClass = "bg-error active-pulse-alert";
        else if (val >= 60) colorClass = "bg-secondary";

        gridHtml += `
          <div class="hud-glass-card p-2 rounded flex flex-col justify-between">
            <div class="flex justify-between items-center text-[10px] font-data-mono mb-1">
              <span class="text-on-surface-variant/70">T${i}</span>
              <span class="font-bold ${val >= 80 ? 'text-error' : val >= 60 ? 'text-secondary' : 'text-primary'}">${val}%</span>
            </div>
            <div class="h-2 w-full bg-surface-container-lowest rounded-sm overflow-hidden">
              <div class="core-meter-bar h-full ${colorClass}" style="width: ${val}%;"></div>
            </div>
          </div>
        `;
      }
      DOM.perCoreGrid.innerHTML = gridHtml;
    }
  }

  /**
   * Updates System View Components (Hardware Inventory Sheet)
   */
  function updateSystemView(snapshot) {
    if (!snapshot) return;

    // CPU Specs
    if (snapshot.cpu) {
      if (DOM.sysCpuModel) DOM.sysCpuModel.textContent = snapshot.cpu.model || snapshot.cpu.name || "N/A";
      if (DOM.sysCpuArch) DOM.sysCpuArch.textContent = (snapshot.system_info && snapshot.system_info.cpu_arch) || "x86_64";
      if (DOM.sysCpuCores) {
        const phys = snapshot.cpu.cores_physical || "-";
        const log = snapshot.cpu.cores_logical || "-";
        DOM.sysCpuCores.textContent = `Physical: ${phys} • Logical: ${log}`;
      }
      if (DOM.sysCpuBase) {
        DOM.sysCpuBase.textContent = snapshot.cpu.base_freq_mhz ? `${snapshot.cpu.base_freq_mhz} MHz` : "N/A";
      }
    }

    // GPUs Specs
    if (DOM.sysGpusContainer && snapshot.gpus && Array.isArray(snapshot.gpus)) {
      let gpusHtml = "";
      snapshot.gpus.forEach((gpu, idx) => {
        const vram = gpu.vram_total_gb ? `${gpu.vram_total_gb} GB` : "Shared System Memory";
        const typeBadge = gpu.type === "dedicated" ? "Discrete (dGPU)" : "Integrated (iGPU)";
        gpusHtml += `
          <div class="hud-glass-card p-3 rounded space-y-1">
            <div class="flex justify-between items-center text-secondary font-bold">
              <span>Adapter ${idx}: ${gpu.model || gpu.name || 'GPU'}</span>
              <span class="text-[10px] px-1.5 py-0.5 bg-surface-container-high rounded">${typeBadge}</span>
            </div>
            <div class="flex justify-between text-[11px] text-on-surface-variant">
              <span>Vendor: ${gpu.vendor || 'N/A'}</span>
              <span>VRAM: ${vram}</span>
            </div>
          </div>
        `;
      });
      DOM.sysGpusContainer.innerHTML = gpusHtml;
    }

    // RAM Specs
    if (snapshot.ram) {
      const totalGb = snapshot.ram.total_gb || 0;
      const totalMb = snapshot.ram.total_mb || Math.round(totalGb * 1024);
      if (DOM.sysRamTotal) DOM.sysRamTotal.textContent = `${totalGb} GB (${HUDGauges.formatNumber(totalMb)} MB)`;
      if (DOM.sysRamType) DOM.sysRamType.textContent = snapshot.ram.memory_type || snapshot.ram.type_badge || "DDR5";
      if (DOM.sysRamSpeed) DOM.sysRamSpeed.textContent = snapshot.ram.speed_mhz ? `${snapshot.ram.speed_mhz} MHz` : "Configured Speed";
      if (DOM.sysRamCommitted) {
        DOM.sysRamCommitted.textContent = snapshot.ram.commit_limit_mb ? `${HUDGauges.formatNumber(Math.round(snapshot.ram.commit_limit_mb))} MB` : "System Managed";
      }
    }

    // Platform / OS Specs
    if (snapshot.system_info) {
      if (DOM.sysOsName) DOM.sysOsName.textContent = snapshot.system_info.os || "Windows";
      if (DOM.sysMotherboard) DOM.sysMotherboard.textContent = snapshot.system_info.motherboard || "Standard OEM";
      if (DOM.sysBios) DOM.sysBios.textContent = snapshot.system_info.bios_version || "N/A";
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
      DOM.statusDot.className = "relative inline-flex rounded-full h-2.5 w-2.5 bg-error";
    } else if (isHighLoad) {
      DOM.statusText.textContent = "PEAK LOAD";
      DOM.statusText.style.color = "var(--color-secondary)";
      DOM.statusPing.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary opacity-75";
      DOM.statusDot.className = "relative inline-flex rounded-full h-2.5 w-2.5 bg-secondary";
    } else {
      DOM.statusText.textContent = "SYSTEM OPTIMAL";
      DOM.statusText.style.color = "var(--color-primary)";
      DOM.statusPing.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75";
      DOM.statusDot.className = "relative inline-flex rounded-full h-2.5 w-2.5 bg-primary";
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
    updateProcesses(snapshot.processes);
    updateSystemStatus(snapshot);

    if (state.activeTab === "telemetry") {
      updateTelemetryView(snapshot);
    } else if (state.activeTab === "system") {
      updateSystemView(snapshot);
    }
  };

  /**
   * Screen Mode Switcher (Standard 1200x800 vs Ultrawide 1920x550)
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
    // Navigation Tab Switching (Header)
    [DOM.tabMonitor, DOM.tabTelemetry, DOM.tabSystem].forEach((btn) => {
      if (!btn) return;
      btn.addEventListener("click", () => {
        const tab = btn.getAttribute("data-tab");
        switchViewTab(tab);
      });
    });

    // Navigation Tab Switching (Sidebar Dock)
    [DOM.sideTabMonitor, DOM.sideTabTelemetry, DOM.sideTabSystem].forEach((btn) => {
      if (!btn) return;
      btn.addEventListener("click", () => {
        const tab = btn.getAttribute("data-tab");
        switchViewTab(tab);
      });
    });

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

    // Window Maximize / Restore Toggle (R1)
    if (DOM.maxBtn) {
      DOM.maxBtn.addEventListener("click", () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_maximize) {
          window.pywebview.api.toggle_maximize().then((isMaximized) => {
            state.isMaximized = isMaximized;
            if (DOM.iconMax) {
              DOM.iconMax.textContent = isMaximized ? "filter_none" : "crop_square";
            }
            DOM.maxBtn.title = isMaximized ? "Restore Window" : "Maximize Window";
          }).catch(() => {});
        } else {
          state.isMaximized = !state.isMaximized;
          if (DOM.iconMax) {
            DOM.iconMax.textContent = state.isMaximized ? "filter_none" : "crop_square";
          }
          DOM.maxBtn.title = state.isMaximized ? "Restore Window" : "Maximize Window";
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
        } else if (e.key === "X" || e.key === "x") {
          if (DOM.maxBtn) DOM.maxBtn.click();
        } else if (e.key === "1") {
          switchViewTab("monitor");
        } else if (e.key === "2") {
          switchViewTab("telemetry");
        } else if (e.key === "3") {
          switchViewTab("system");
        }
      }
    });
  }

  /**
   * Browser Offline Mock Simulation
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
          name: "Intel Core i9-13900HX",
          load_pct: Math.round(20 + 60 * Math.abs(sinVal)),
          freq_ghz: 3.8 + 1.2 * Math.abs(sinVal),
          cores_physical: 24,
          cores_logical: 32,
          base_freq_mhz: 2200,
          temperature_c: Math.round(48 + 35 * Math.abs(sinVal)),
          per_core_load: Array.from({ length: 32 }, (_, i) => Math.round(15 + 75 * Math.abs(Math.sin(tick * 0.15 + i * 0.3)))),
        },
        gpus: [
          {
            id: 0,
            type: "dedicated",
            vendor: "NVIDIA",
            model: "NVIDIA GeForce RTX 4080 Laptop GPU",
            name: "RTX 4080 Laptop GPU",
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
            name: "Intel UHD Graphics",
            load_pct: Math.round(6 + 14 * Math.abs(sinVal)),
            freq_mhz: "N/A",
            vram_used_gb: 0.8,
            vram_total_gb: "N/A",
            temperature_c: "N/A",
          },
        ],
        ram: {
          load_pct: 42.5,
          used_gb: 27.2,
          free_gb: 36.8,
          total_gb: 64.0,
          used_mb: 27852.8,
          free_mb: 37683.2,
          total_mb: 65536.0,
          available_mb: 37683.2,
          committed_mb: 32150.0,
          commit_limit_mb: 73728.0,
          type_badge: "DDR5-4800",
          memory_type: "DDR5",
          speed_mhz: 4800,
          distribution: { in_use_pct: 43, cached_pct: 18, free_pct: 39 },
        },
        processes: [
          { pid: 14280, name: "chrome.exe", cpu_pct: 14.8, memory_mb: 1842.5, memory_pct: 2.8, disk_mbps: 3.2, gpu_pct: 4.5 },
          { pid: 8924, name: "Code.exe", cpu_pct: 8.4, memory_mb: 950.0, memory_pct: 1.5, disk_mbps: 0.8, gpu_pct: 1.2 },
          { pid: 3412, name: "python.exe", cpu_pct: 4.6, memory_mb: 620.0, memory_pct: 0.9, disk_mbps: 1.5, gpu_pct: 0.0 },
          { pid: 1204, name: "Discord.exe", cpu_pct: 2.1, memory_mb: 480.0, memory_pct: 0.7, disk_mbps: 0.1, gpu_pct: 0.5 },
          { pid: 560, name: "System", cpu_pct: 1.5, memory_mb: 120.0, memory_pct: 0.2, disk_mbps: 12.4, gpu_pct: 0.0 },
        ],
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
        system_info: {
          os: "Windows 11 Pro 24H2 (Build 26100)",
          cpu_arch: "x86_64",
          motherboard: "Alienware m18 R1",
          bios_version: "1.14.0",
        },
      };

      window.onTelemetryUpdate(mockSnapshot);
    }, 1000);
  }

  /**
   * Continuous Telemetry Polling Routine
   */
  function startPollingTelemetry() {
    if (state.pollingTimer) {
      clearInterval(state.pollingTimer);
    }

    const fetchTelemetry = async () => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.get_telemetry_snapshot) {
        try {
          const snap = await window.pywebview.api.get_telemetry_snapshot();
          if (snap && typeof snap === "object" && Object.keys(snap).length > 0) {
            window.onTelemetryUpdate(snap);
          }
        } catch (err) {
          console.error("Telemetry fetch error:", err);
        }
      }
    };

    fetchTelemetry();
    state.pollingTimer = setInterval(fetchTelemetry, 1000);
  }

  /**
   * Initialization Routine
   */
  function init() {
    initEventListeners();

    state.currentMode = "standard";
    DOM.body.className = "bg-background text-on-surface font-body-md min-h-screen mode-standard";
    if (DOM.modeLabel) DOM.modeLabel.textContent = "STANDARD";

    // Set initial view tab
    switchViewTab("monitor");

    // Handle PyWebView Ready Hook
    window.addEventListener("pywebviewready", () => {
      state.isBridgeReady = true;
      console.info("PyWebView Bridge is ready.");
      startPollingTelemetry();
    });

    // Fallback interval check for pywebview bridge injection
    const bridgeCheck = setInterval(() => {
      if (window.pywebview && window.pywebview.api) {
        clearInterval(bridgeCheck);
        if (!state.isBridgeReady) {
          state.isBridgeReady = true;
          startPollingTelemetry();
        }
      }
    }, 200);

    // Browser testing fallback
    setTimeout(() => {
      if (!window.pywebview && !state.latestSnapshot) {
        clearInterval(bridgeCheck);
        startBrowserMockTelemetry();
      }
    }, 1200);
  }

  // Run on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
