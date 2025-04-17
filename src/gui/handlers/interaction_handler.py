# filename: src/gui/handlers/interaction_handler.py
import logging
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtWidgets import QApplication

try:
    from src import config
    # from .settings_state_handler import SettingsStateHandler # For type hint
except ImportError:
    logging.error("InteractionHandler: Failed to import config directly.")
    class ConfigFallback: RESIZE_MARGIN = 10; MIN_WINDOW_WIDTH = 100; MIN_WINDOW_HEIGHT = 100
    config = ConfigFallback()


class InteractionHandler:
    """Handles mouse events for dragging and resizing a frameless window."""

    def __init__(self, window, settings_state_handler): # Added settings_state_handler
        """
        Args:
            window: The main window instance.
            settings_state_handler: The handler managing current settings state.
        """
        self.window = window
        self.settings_state_handler = settings_state_handler # Store handler
        self.ui_manager = getattr(window, 'ui_manager', None)
        if not self.ui_manager: logging.error("InteractionHandler: Could not get ui_manager from window.")

        self.drag_pos = None; self.resizing = False; self.resize_start_pos = None
        self.original_geometry = None; self.resizing_edges = {'left': False, 'top': False, 'right': False, 'bottom': False}

    def is_locked(self):
        """Checks if the window interaction is locked via SettingsStateHandler."""
        if self.settings_state_handler:
            return self.settings_state_handler.get_value('is_locked', False)
        logging.warning("InteractionHandler: SettingsStateHandler not available to check lock state.")
        return False # Default to unlocked if handler missing

    def mousePressEvent(self, event):
        """Handles mouse button presses for dragging and resizing."""
        if self.is_locked(): return

        if event.button() == Qt.LeftButton:
            self.drag_pos = None; self.resizing = False
            pos = event.pos(); self._detect_resize_edges(pos)

            if any(self.resizing_edges.values()):
                self.resizing = True; self.resize_start_pos = event.globalPos()
                self.original_geometry = self.window.geometry(); logging.debug("InteractionHandler: Starting resize.")
            else:
                title_h = 35; is_on_widget = False
                if self.ui_manager:
                    try: # Get button geometries via UIManager
                        close_rect = self.ui_manager.get_button_geometry('close_button')
                        opts_rect = self.ui_manager.get_button_geometry('options_button')
                        grab_rect = self.ui_manager.get_button_geometry('grab_button')
                        # Checkbox geometry might also be needed if it grows
                        live_cb_rect = self.ui_manager.get_widget('live_mode_checkbox').geometry() if self.ui_manager.get_widget('live_mode_checkbox') else QRect()
                        is_on_widget = (close_rect.contains(pos) or opts_rect.contains(pos) or grab_rect.contains(pos) or live_cb_rect.contains(pos))
                    except Exception as e: logging.warning(f"InteractionHandler: Error getting widget geometry: {e}")

                if pos.y() < title_h and not is_on_widget:
                    self.drag_pos = event.globalPos() - self.window.frameGeometry().topLeft()
                    self.window.setCursor(Qt.SizeAllCursor); logging.debug("InteractionHandler: Starting drag.")
                else: self.window.unsetCursor()


    def mouseMoveEvent(self, event):
        # (Identical to previous version)
        if self.is_locked(): return
        is_left_button_down = event.buttons() == Qt.LeftButton
        is_dragging = self.drag_pos is not None and is_left_button_down
        is_resizing = self.resizing and is_left_button_down
        if is_dragging: self.window.move(event.globalPos() - self.drag_pos)
        elif is_resizing: self._handle_resize(event.globalPos())
        else: self._set_resize_cursor(event.pos())

    def mouseReleaseEvent(self, event):
        # (Identical to previous version)
        if event.button() == Qt.LeftButton:
            was_dragging = self.drag_pos is not None or self.resizing
            self.drag_pos = None; self.resizing = False
            self.resizing_edges = {k: False for k in self.resizing_edges}
            self.window.unsetCursor()
            if was_dragging: logging.debug("InteractionHandler: Drag/resize finished.")

    def _detect_resize_edges(self, pos):
        # (Identical to previous version)
        if self.is_locked(): self.resizing_edges = {k: False for k in self.resizing_edges}; return
        x, y = pos.x(), pos.y(); w, h = self.window.width(), self.window.height()
        margin = config.RESIZE_MARGIN
        self.resizing_edges['left'] = (0 <= x < margin); self.resizing_edges['top'] = (0 <= y < margin)
        self.resizing_edges['right'] = (w - margin < x <= w); self.resizing_edges['bottom'] = (h - margin < y <= h)

    def _set_resize_cursor(self, pos):
        # (Identical to previous version)
        if self.is_locked() or self.resizing or (self.drag_pos and QApplication.mouseButtons() == Qt.LeftButton): return
        self._detect_resize_edges(pos); edges = self.resizing_edges
        if (edges['left'] and edges['top']) or (edges['right'] and edges['bottom']): self.window.setCursor(Qt.SizeFDiagCursor)
        elif (edges['right'] and edges['top']) or (edges['left'] and edges['bottom']): self.window.setCursor(Qt.SizeBDiagCursor)
        elif edges['left'] or edges['right']: self.window.setCursor(Qt.SizeHorCursor)
        elif edges['top'] or edges['bottom']: self.window.setCursor(Qt.SizeVerCursor)
        else: self.window.unsetCursor()

    def _handle_resize(self, global_pos):
        # (Identical to previous version)
        if not self.resizing or self.original_geometry is None or self.resize_start_pos is None: return
        delta = global_pos - self.resize_start_pos; new_rect = QRect(self.original_geometry)
        min_w, min_h = config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT
        if self.resizing_edges['right']: new_rect.setWidth(max(min_w, self.original_geometry.width() + delta.x()))
        if self.resizing_edges['bottom']: new_rect.setHeight(max(min_h, self.original_geometry.height() + delta.y()))
        if self.resizing_edges['left']:
             new_left = self.original_geometry.left() + delta.x(); max_left = new_rect.right() - min_w
             new_left = min(new_left, max_left); new_rect.setLeft(new_left)
        if self.resizing_edges['top']:
             new_top = self.original_geometry.top() + delta.y(); max_top = new_rect.bottom() - min_h
             new_top = min(new_top, max_top); new_rect.setTop(new_top)
        if new_rect.width() < min_w: new_rect.setWidth(min_w)
        if new_rect.height() < min_h: new_rect.setHeight(min_h)
        if new_rect != self.window.geometry(): self.window.setGeometry(new_rect)