"""
tests/test_gui_bridge.py
Unit & Integration Tests for Milestone 2 (Frontend HUD) & Milestone 3 (Window Manager & JS Bridge).
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.bridge.api import HUDBridgeAPI
from src.gui.window_manager import create_hud_window, get_ui_entry_url
from src.telemetry.engine import TelemetryEngine


class TestHUDBridgeAPI(unittest.TestCase):
    """Verifies JS-Python bridge contract, window controls, and mode switching."""

    def setUp(self):
        self.mock_engine = MagicMock(spec=TelemetryEngine)
        self.mock_engine.get_snapshot.return_value = {
            "timestamp": 1000.0,
            "cpu": {"model": "Test CPU", "load_pct": 25.0},
        }
        self.bridge = HUDBridgeAPI(engine=self.mock_engine, initial_mode="standard", initial_pinned=True)

    def test_bridge_initial_state(self):
        """Verify bridge initializes with standard 1200x800 dimensions and pinned True."""
        self.assertEqual(self.bridge.current_mode, "standard")
        self.assertEqual(self.bridge.width, 1200)
        self.assertEqual(self.bridge.height, 800)
        self.assertTrue(self.bridge.is_pinned)
        self.assertFalse(self.bridge.is_minimized)
        self.assertFalse(self.bridge.is_closed)

    def test_get_telemetry_snapshot(self):
        """Verify get_telemetry_snapshot delegates to the underlying engine."""
        snap = self.bridge.get_telemetry_snapshot()
        self.mock_engine.get_snapshot.assert_called_once()
        self.assertEqual(snap["cpu"]["load_pct"], 25.0)

    def test_set_screen_mode_ultrawide_and_standard(self):
        """Verify switching between standard and ultrawide resizes window properly."""
        mock_win = MagicMock()
        self.bridge.set_window(mock_win)

        # Switch to ultrawide
        res_uw = self.bridge.set_screen_mode("ultrawide")
        self.assertEqual(res_uw["mode"], "ultrawide")
        self.assertEqual(res_uw["width"], 1920)
        self.assertEqual(res_uw["height"], 550)
        self.assertEqual(self.bridge.width, 1920)
        self.assertEqual(self.bridge.height, 550)
        mock_win.resize.assert_called_with(1920, 550)

        # Switch back to standard
        res_std = self.bridge.set_screen_mode("standard")
        self.assertEqual(res_std["mode"], "standard")
        self.assertEqual(res_std["width"], 1200)
        self.assertEqual(res_std["height"], 800)
        mock_win.resize.assert_called_with(1200, 800)

    def test_set_screen_mode_invalid_raises_value_error(self):
        """Verify invalid screen mode names raise ValueError."""
        with self.assertRaises(ValueError):
            self.bridge.set_screen_mode("vertical_mode")

    def test_toggle_pin_top(self):
        """Verify toggle_pin_top toggles state and updates window on_top property."""
        mock_win = MagicMock()
        self.bridge.set_window(mock_win)

        pinned1 = self.bridge.toggle_pin_top()
        self.assertFalse(pinned1)
        self.assertFalse(self.bridge.is_pinned)

        pinned2 = self.bridge.toggle_pin_top()
        self.assertTrue(pinned2)
        self.assertTrue(self.bridge.is_pinned)

    def test_minimize_and_restore_window(self):
        """Verify minimize and restore window operations."""
        mock_win = MagicMock()
        self.bridge.set_window(mock_win)

        self.assertTrue(self.bridge.minimize_window())
        self.assertTrue(self.bridge.is_minimized)
        mock_win.minimize.assert_called_once()

        self.assertTrue(self.bridge.restore_window())
        self.assertFalse(self.bridge.is_minimized)
        mock_win.restore.assert_called_once()

    def test_close_window(self):
        """Verify close_window destroys native window and unsubscribes from engine."""
        mock_win = MagicMock()
        self.bridge.set_window(mock_win)

        self.assertTrue(self.bridge.close_window())
        self.assertTrue(self.bridge.is_closed)
        mock_win.destroy.assert_called_once()
        self.mock_engine.unsubscribe.assert_called_once()

    def test_on_telemetry_tick_evaluates_js(self):
        """Verify telemetry tick evaluates window.onTelemetryUpdate in webview."""
        mock_win = MagicMock()
        self.bridge.set_window(mock_win)

        snapshot = {"timestamp": 1234.5, "cpu": {"load_pct": 50.0}}
        self.bridge._on_telemetry_tick(snapshot)

        mock_win.evaluate_js.assert_called_once()
        call_arg = mock_win.evaluate_js.call_args[0][0]
        self.assertIn("window.onTelemetryUpdate", call_arg)
        self.assertIn('"load_pct": 50.0', call_arg)

    def test_on_telemetry_tick_silent_when_window_none_or_closed(self):
        """Verify telemetry tick does nothing when window is not set or closed."""
        self.bridge.set_window(None)
        self.bridge._on_telemetry_tick({"timestamp": 1234.5})

        mock_win = MagicMock()
        self.bridge.set_window(mock_win)
        self.bridge.is_closed = True
        self.bridge._on_telemetry_tick({"timestamp": 1234.5})
        mock_win.evaluate_js.assert_not_called()

    def test_get_status(self):
        """Verify get_status returns complete state dictionary."""
        status = self.bridge.get_status()
        self.assertIn("mode", status)
        self.assertIn("width", status)
        self.assertIn("height", status)
        self.assertIn("is_pinned", status)
        self.assertIn("is_minimized", status)
        self.assertIn("is_closed", status)


class TestWindowManager(unittest.TestCase):
    """Verifies PyWebView window creation and configuration."""

    def test_get_ui_entry_url(self):
        """Verify UI entry path resolves to existing ui/index.html."""
        ui_path = get_ui_entry_url()
        self.assertTrue(os.path.exists(ui_path))
        self.assertTrue(ui_path.endswith("index.html"))

    @patch("webview.create_window")
    def test_create_hud_window_parameters(self, mock_create_window):
        """Verify create_hud_window passes required frameless, transparent, easy_drag parameters."""
        mock_win = MagicMock()
        mock_create_window.return_value = mock_win

        engine = TelemetryEngine()
        win, bridge, ret_engine = create_hud_window(engine=engine, screen_mode="standard", pinned=True)

        mock_create_window.assert_called_once()
        kwargs = mock_create_window.call_args[1]

        self.assertTrue(kwargs["frameless"])
        self.assertTrue(kwargs["transparent"])
        self.assertTrue(kwargs["easy_drag"])
        self.assertTrue(kwargs["on_top"])
        self.assertEqual(kwargs["width"], 1200)
        self.assertEqual(kwargs["height"], 800)
        self.assertEqual(kwargs["background_color"], "#000000")
        self.assertEqual(bridge.window, mock_win)
        engine.stop()


class TestUIAssetsIntegrity(unittest.TestCase):
    """Verifies all frontend HTML, CSS, and JS assets exist and contain required contracts."""

    def test_index_html_elements(self):
        """Verify ui/index.html contains all required HUD widget IDs."""
        html_path = os.path.join(PROJECT_ROOT, "ui", "index.html")
        self.assertTrue(os.path.exists(html_path))

        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_ids = [
            "top-nav-bar",
            "sidebar-dock",
            "status-pill",
            "btn-mode",
            "btn-pin",
            "btn-min",
            "btn-close",
            "cpu-progress-circle",
            "cpu-load-text",
            "cpu-freq-text",
            "gpu-progress-circle",
            "gpu-load-text",
            "gpu-freq-text",
            "gpu-tabs-container",
            "temp-cpu-bar",
            "temp-gpu-bar",
            "temp-ssd-bar",
            "net-down-text",
            "net-up-text",
            "ram-bar-in-use",
            "ram-bar-cached",
            "ssd-read-text",
            "ssd-write-text",
        ]
        for elem_id in required_ids:
            self.assertIn(f'id="{elem_id}"', content, f"Missing element id='{elem_id}' in index.html")

    def test_glass_hud_css_classes(self):
        """Verify ui/styles/glass_hud.css defines all required glassmorphism & HUD bracket classes."""
        css_path = os.path.join(PROJECT_ROOT, "ui", "styles", "glass_hud.css")
        self.assertTrue(os.path.exists(css_path))

        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_classes = [
            "hud-glass",
            "hud-glass-elevated",
            "hud-bracket-tl",
            "hud-bracket-br",
            "circular-progress",
            "circular-progress-value",
            "radar-grid",
            "mode-standard",
            "mode-ultrawide",
            "pywebview-drag-region",
        ]
        for cls in required_classes:
            self.assertIn(cls, content, f"Missing class '{cls}' in glass_hud.css")

    def test_gauges_js_file(self):
        """Verify ui/js/gauges.js defines HUDGauges namespace."""
        js_path = os.path.join(PROJECT_ROOT, "ui", "js", "gauges.js")
        self.assertTrue(os.path.exists(js_path))

        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("calculateSvgDashoffset", content)
        self.assertIn("evaluateThermalColor", content)
        self.assertIn("updateCircularGauge", content)
        self.assertIn("updateThermalBar", content)
        self.assertIn("HUDGauges", content)

    def test_app_js_file(self):
        """Verify ui/js/app.js defines window.onTelemetryUpdate."""
        js_path = os.path.join(PROJECT_ROOT, "ui", "js", "app.js")
        self.assertTrue(os.path.exists(js_path))

        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("window.onTelemetryUpdate", content)
        self.assertIn("pywebviewready", content)
        self.assertIn("updateCPU", content)
        self.assertIn("updateGPU", content)
        self.assertIn("updateThermals", content)
        self.assertIn("updateRAM", content)
        self.assertIn("updateStorage", content)
        self.assertIn("updateNetwork", content)


if __name__ == "__main__":
    unittest.main()
