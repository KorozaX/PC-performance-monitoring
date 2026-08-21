"""
src/bridge/api.py
PyWebView JS-Python Bridge Controller.
Exposes native window controls, screen mode switching, maximize/restore toggles,
view tab routing, and live telemetry streaming to the JavaScript HUD frontend via window.pywebview.api.
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
        self.prev_width: int = self.width
        self.prev_height: int = self.height
        self.is_pinned: bool = initial_pinned
        self.is_minimized: bool = False
        self.is_maximized_state: bool = False
        self.is_closed: bool = False
        self.active_tab: str = "MONITOR"
        self.window: Optional[Any] = None

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
            self.window.evaluate_js(
                f"if (window.onTelemetryUpdate) {{ window.onTelemetryUpdate({serialized}); }}"
            )
        except Exception as exc:
            # Window might be closing or rendering not ready; ignore gracefully
            logger.debug("Telemetry dispatch to webview failed: %s", exc)

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        """
        Returns the latest comprehensive telemetry snapshot JSON.
        Exposed to JS as window.pywebview.api.get_telemetry_snapshot().
        """
        if self.engine is not None and hasattr(self.engine, "get_snapshot"):
            return self.engine.get_snapshot()
        return {}

    def toggle_maximize(self) -> bool:
        """
        Toggles window between maximized state and restored standard/ultrawide dimensions.
        Exposed to JS as window.pywebview.api.toggle_maximize().
        Returns: True if currently maximized, False if restored.
        """
        if not self.is_maximized_state:
            self.prev_width = self.width
            self.prev_height = self.height
            self.is_maximized_state = True
            if self.window is not None:
                try:
                    if hasattr(self.window, "maximize"):
                        self.window.maximize()
                except Exception as exc:
                    logger.warning("Window maximize call failed: %s", exc)
        else:
            self.is_maximized_state = False
            self.width = self.prev_width
            self.height = self.prev_height
            if self.window is not None:
                try:
                    if hasattr(self.window, "restore"):
                        self.window.restore()
                except Exception as exc:
                    logger.warning("Window restore call failed: %s", exc)

        return self.is_maximized_state

    def is_maximized(self) -> bool:
        """
        Checks if the HUD window is currently maximized.
        Exposed to JS as window.pywebview.api.is_maximized().
        """
        return self.is_maximized_state

    def minimize_window(self) -> bool:
        """
        Minimizes the HUD window to the taskbar.
        Exposed to JS as window.pywebview.api.minimize_window().
        """
        self.is_minimized = True
        if self.window is not None:
            try:
                if hasattr(self.window, "minimize"):
                    self.window.minimize()
            except Exception as exc:
                logger.warning("Window minimize failed: %s", exc)
        return True

    def restore_window(self) -> bool:
        """
        Restores the HUD window from minimized or maximized state.
        Exposed to JS as window.pywebview.api.restore_window().
        """
        self.is_minimized = False
        self.is_maximized_state = False
        if self.window is not None:
            try:
                if hasattr(self.window, "restore"):
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
                if hasattr(self.window, "destroy"):
                    self.window.destroy()
            except Exception as exc:
                logger.warning("Window destroy failed: %s", exc)
        return True

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

        self.is_maximized_state = False
        if self.window is not None:
            try:
                if hasattr(self.window, "restore"):
                    self.window.restore()
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

    def switch_tab(self, tab_name: str) -> str:
        """
        Switches active HUD tab (MONITOR, TELEMETRY, SYSTEM).
        Exposed to JS as window.pywebview.api.switch_tab(tab_name).
        """
        valid_tabs = ["MONITOR", "TELEMETRY", "SYSTEM"]
        norm = tab_name.upper() if tab_name else ""
        if norm not in valid_tabs:
            raise ValueError(f"Invalid tab: {tab_name}. Expected one of {valid_tabs}")
        self.active_tab = norm
        return self.active_tab

    def get_status(self) -> Dict[str, Any]:
        """Returns current bridge and window status."""
        return {
            "mode": self.current_mode,
            "width": self.width,
            "height": self.height,
            "is_pinned": self.is_pinned,
            "is_minimized": self.is_minimized,
            "is_maximized": self.is_maximized_state,
            "is_closed": self.is_closed,
            "active_tab": self.active_tab,
        }
