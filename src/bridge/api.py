"""
src/bridge/api.py
PyWebView JS-Python Bridge Controller.
Exposes native window controls, screen mode switching, and live telemetry streaming
to the JavaScript HUD frontend via window.pywebview.api and evaluated events.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class HUDBridgeAPI:
    """
    JS-Python Bridge API exposed to the PyWebView container as window.pywebview.api.
    Implements bidirectional communication between the Glassmorphism HUD UI and
    the Python telemetry daemon / native OS window.
    """

    def __init__(
        self,
        engine: Optional[Any] = None,
        initial_mode: str = "standard",
        initial_pinned: bool = True,
    ):
        self.engine = engine
        self.current_mode: str = initial_mode
        self.width: int = 1200 if initial_mode == "standard" else 1920
        self.height: int = 800 if initial_mode == "standard" else 550
        self.is_pinned: bool = initial_pinned
        self.is_minimized: bool = False
        self.is_closed: bool = False
        self.window: Optional[Any] = None

        # Engine reference is stored for get_telemetry_snapshot polling
        # Background thread evaluate_js is not auto-subscribed to avoid WinForms COM deadlocks

    def set_window(self, window: Any) -> None:
        """Attaches the active pywebview.Window instance."""
        self.window = window

    def _on_telemetry_tick(self, snapshot: Dict[str, Any]) -> None:
        """Callback invoked on every background telemetry tick. Dispatches to JS."""
        if self.window is None or self.is_closed:
            return
        try:
            # Safely serialize snapshot to JSON string and execute onTelemetryUpdate in JS
            serialized = json.dumps(snapshot)
            self.window.evaluate_js(f"if (window.onTelemetryUpdate) {{ window.onTelemetryUpdate({serialized}); }}")
        except Exception as exc:
            # Window might be closing or rendering not ready; ignore gracefully
            logger.debug("Telemetry dispatch to webview failed: %s", exc)

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        """
        Returns the latest telemetry JSON snapshot.
        Exposed to JS as window.pywebview.api.get_telemetry_snapshot().
        """
        if self.engine is not None and hasattr(self.engine, "get_snapshot"):
            return self.engine.get_snapshot()
        return {}

    def set_screen_mode(self, mode_name: str) -> Dict[str, Any]:
        """
        Switches between Standard HUD mode (1200x800) and Ultra-Wide secondary screen mode (1920x550).
        Resizes the native window and returns new geometry.
        Exposed to JS as window.pywebview.api.set_screen_mode(mode_name).
        """
        if mode_name == "ultrawide":
            self.current_mode = "ultrawide"
            self.width = 1920
            self.height = 550
        elif mode_name == "standard":
            self.current_mode = "standard"
            self.width = 1200
            self.height = 800
        else:
            raise ValueError(f"Unknown screen mode: {mode_name}")

        if self.window is not None:
            try:
                self.window.resize(self.width, self.height)
            except Exception as exc:
                logger.warning("Window resize to %dx%d failed: %s", self.width, self.height, exc)

        return {
            "mode": self.current_mode,
            "width": self.width,
            "height": self.height,
        }

    def toggle_pin_top(self) -> bool:
        """
        Toggles Always-On-Top window pinning.
        Exposed to JS as window.pywebview.api.toggle_pin_top().
        """
        self.is_pinned = not self.is_pinned
        if self.window is not None:
            try:
                if hasattr(self.window, "on_top"):
                    self.window.on_top = self.is_pinned
                elif hasattr(self.window, "set_on_top"):
                    self.window.set_on_top(self.is_pinned)
            except Exception as exc:
                logger.warning("Toggle on_top failed: %s", exc)
        return self.is_pinned

    def minimize_window(self) -> bool:
        """
        Minimizes the HUD window to the taskbar.
        Exposed to JS as window.pywebview.api.minimize_window().
        """
        self.is_minimized = True
        if self.window is not None:
            try:
                self.window.minimize()
            except Exception as exc:
                logger.warning("Window minimize failed: %s", exc)
        return True

    def restore_window(self) -> bool:
        """
        Restores the HUD window from minimized state.
        Exposed to JS as window.pywebview.api.restore_window().
        """
        self.is_minimized = False
        if self.window is not None:
            try:
                self.window.restore()
            except Exception as exc:
                logger.warning("Window restore failed: %s", exc)
        return True

    def close_window(self) -> bool:
        """
        Closes and destroys the HUD window.
        Exposed to JS as window.pywebview.api.close_window().
        """
        self.is_closed = True
        if self.engine is not None and hasattr(self.engine, "unsubscribe"):
            try:
                self.engine.unsubscribe(self._on_telemetry_tick)
            except Exception:
                pass
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception as exc:
                logger.warning("Window destroy failed: %s", exc)
        return True

    def get_status(self) -> Dict[str, Any]:
        """Returns current bridge and window status."""
        return {
            "mode": self.current_mode,
            "width": self.width,
            "height": self.height,
            "is_pinned": self.is_pinned,
            "is_minimized": self.is_minimized,
            "is_closed": self.is_closed,
        }
