/**
 * ui/js/gauges.js
 * SVG Circular Gauges, Thermal Dynamic Color Thresholds, and Progress Bar Calculators.
 */

(function (window) {
  "use strict";

  const GAUGE_RADIUS = 45.0;
  const CIRCUMFERENCE = 2.0 * Math.PI * GAUGE_RADIUS; // ≈ 282.7433

  /**
   * Calculates the SVG stroke-dashoffset for a circular gauge.
   * @param {number|string} pct - Load percentage (0 - 100).
   * @param {number} [radius=45.0] - Circle radius.
   * @returns {number} Offset value in pixels.
   */
  function calculateSvgDashoffset(pct, radius = GAUGE_RADIUS) {
    const circ = 2.0 * Math.PI * radius;
    if (pct === "N/A" || pct === null || pct === undefined || isNaN(Number(pct))) {
      return circ;
    }
    const clamped = Math.max(0.0, Math.min(100.0, parseFloat(pct)));
    return circ * (1.0 - clamped / 100.0);
  }

  /**
   * Evaluates the hex color token based on hardware temperature.
   * @param {number|string} tempC - Temperature in Celsius.
   * @returns {string} Hex color code.
   */
  function evaluateThermalColor(tempC) {
    if (tempC === "N/A" || tempC === null || tempC === undefined || isNaN(Number(tempC))) {
      return "#849396"; // Neutral gray
    }
    const t = parseFloat(tempC);
    if (t < 60.0) {
      return "#00daf3"; // Electric cyan
    } else if (t < 80.0) {
      return "#d1bcff"; // Obsidian purple / lavender
    } else {
      return "#ffb4ab"; // Alert red
    }
  }

  /**
   * Updates an SVG circular gauge element with animated smooth transitions.
   * @param {SVGElement|string} circleEl - Circle element or selector.
   * @param {HTMLElement|string} textEl - Value text element or selector.
   * @param {number|string} pct - Current percentage.
   */
  function updateCircularGauge(circleEl, textEl, pct) {
    const circle = typeof circleEl === "string" ? document.querySelector(circleEl) : circleEl;
    const text = typeof textEl === "string" ? document.querySelector(textEl) : textEl;

    if (!circle) return;

    const offset = calculateSvgDashoffset(pct);
    circle.style.strokeDashoffset = offset.toFixed(2);

    if (text) {
      if (pct === "N/A" || pct === null || pct === undefined || isNaN(Number(pct))) {
        text.textContent = "N/A";
      } else {
        text.textContent = Math.round(parseFloat(pct)).toString();
      }
    }
  }

  /**
   * Updates a thermal progress bar and text readout with threshold gradient shifting.
   * @param {HTMLElement|string} barEl - Fill bar element.
   * @param {HTMLElement|string} textEl - Temperature text element.
   * @param {number|string} tempC - Temperature in Celsius.
   */
  function updateThermalBar(barEl, textEl, tempC) {
    const bar = typeof barEl === "string" ? document.querySelector(barEl) : barEl;
    const text = typeof textEl === "string" ? document.querySelector(textEl) : textEl;

    if (!bar || !text) return;

    if (tempC === "N/A" || tempC === null || tempC === undefined || isNaN(Number(tempC))) {
      text.textContent = "N/A";
      text.style.color = "#849396";
      bar.style.width = "0%";
      bar.className = "h-full bg-outline-variant/30";
      return;
    }

    const t = parseFloat(tempC);
    text.textContent = `${Math.round(t)}°C`;
    const color = evaluateThermalColor(t);
    text.style.color = color;

    // Scale bar: 30°C to 100°C -> 0% to 100% width
    const clampedPct = Math.max(5, Math.min(100, Math.round(t)));
    bar.style.width = `${clampedPct}%`;

    if (t < 60) {
      bar.className = "h-full bg-gradient-to-r from-primary to-primary-fixed";
      bar.style.background = "linear-gradient(90deg, #00daf3, #9cf0ff)";
    } else if (t < 80) {
      bar.className = "h-full bg-gradient-to-r from-primary-fixed to-secondary-fixed-dim";
      bar.style.background = "linear-gradient(90deg, #9cf0ff, #d1bcff)";
    } else {
      bar.className = "h-full bg-gradient-to-r from-secondary-fixed-dim to-error active-pulse-alert";
      bar.style.background = "linear-gradient(90deg, #d1bcff, #ffb4ab)";
    }
  }

  /**
   * Formats numbers with comma separators for clean data display.
   * @param {number|string} num - Input number.
   * @param {number} [decimals=0] - Decimal places.
   * @returns {string} Formatted string.
   */
  function formatNumber(num, decimals = 0) {
    if (num === "N/A" || num === null || num === undefined || isNaN(Number(num))) {
      return "0";
    }
    const val = parseFloat(num);
    return val.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  // Export to global window object
  window.HUDGauges = {
    calculateSvgDashoffset,
    evaluateThermalColor,
    updateCircularGauge,
    updateThermalBar,
    formatNumber,
  };
})(window);
