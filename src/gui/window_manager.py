"""
src/gui/window_manager.py
PyWebView Frameless Window Controller for Glassmorphism Performance HUD.
Creates and configures the transparent desktop overlay window using Microsoft Edge WebView2.
"""

import logging
import os
import sys
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Base project directory resolution (supports PyInstaller bundle extraction)
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BUNDLE_DIR = sys._MEIPASS  # type: ignore
else:
    BUNDLE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

UI_HTML_PATH = os.path.join(BUNDLE_DIR, "ui", "index.html")


def get_ui_entry_url() -> str:
    """Returns the absolute file:// URL or local path to ui/index.html."""
    if not os.path.exists(UI_HTML_PATH):
        logger.warning("UI entry HTML not found at expected path: %s", UI_HTML_PATH)
    return UI_HTML_PATH


def create_hud_window(
    engine: Optional[Any] = None,
    screen_mode: str = "standard",
    pinned: bool = True,
    interval_ms: int = 1000,
) -> Tuple[Any, Any, Any]:
    """
    Creates and configures the PyWebView frameless, transparent HUD overlay window.
    Returns (window, bridge_api, engine).
    """
    try:
        import webview
    except ImportError as exc:
        logger.error("pywebview is required to create HUD window: %s", exc)
        raise

    from src.bridge.api import HUDBridgeAPI
    from src.telemetry.engine import TelemetryEngine

    if engine is None:
        engine = TelemetryEngine(interval_ms=interval_ms)

    width = 1200 if screen_mode == "standard" else 1920
    height = 800 if screen_mode == "standard" else 550

    bridge_api = HUDBridgeAPI(
        engine=engine, initial_mode=screen_mode, initial_pinned=pinned
    )

    ui_url = get_ui_entry_url()

    window = webview.create_window(
        title="NETA_OS - Performance Monitoring HUD",
        url=ui_url,
        js_api=bridge_api,
        width=width,
        height=height,
        frameless=True,
        transparent=True,
        easy_drag=True,
        on_top=pinned,
        min_size=(600, 400),
        background_color="#00000000",
    )

    bridge_api.set_window(window)

    def on_closed():
        logger.info("HUD window closed. Stopping telemetry engine...")
        engine.stop()

    window.events.closed += on_closed

    return window, bridge_api, engine


def launch_gui(
    screen_mode: str = "standard",
    pinned: bool = True,
    interval_ms: int = 1000,
    debug: bool = False,
) -> None:
    """
    Main GUI entry point. Starts telemetry polling engine and launches the PyWebView GUI event loop.
    """
    try:
        import webview
    except ImportError:
        print("ERROR: pywebview is not installed. Please run: pip install pywebview")
        return

    from src.telemetry.engine import TelemetryEngine

    engine = TelemetryEngine(interval_ms=interval_ms)
    engine.start()

    window, bridge_api, _ = create_hud_window(
        engine=engine, screen_mode=screen_mode, pinned=pinned, interval_ms=interval_ms
    )

    logger.info("Launching Glassmorphism Performance HUD (mode=%s)...", screen_mode)

    try:
        # Start PyWebView with Microsoft Edge WebView2 Evergreen runtime
        webview.start(debug=debug, gui="edgechromium")
    except Exception as exc:
        logger.error("Failed to start PyWebView with EdgeChromium: %s", exc)
        # Try fallback without specific GUI backend flag
        try:
            webview.start(debug=debug)
        except Exception as fallback_exc:
            logger.critical("Critical error starting GUI: %s", fallback_exc)
    finally:
        engine.stop()
