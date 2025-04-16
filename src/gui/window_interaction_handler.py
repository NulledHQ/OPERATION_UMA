# src/gui/window_interaction_handler.py

import logging
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtWidgets import QApplication

# Use absolute import from src package root
from src import config

class WindowInteractionHandler:
    """Handles mouse events for dragging and resizing a frameless window."""

    def __init__(self, window):
        """
        Args:
            window: The QWidget instance to handle interactions for.
        """
        self.window = window
        self.drag_pos = None
        self.resizing = False
        self.resize_start_pos = None
        self.original_geometry = None
        self.resizing_edges = {'left': False, 'top': False, 'right': False, 'bottom': False}
        # Note: self.window.is_locked should be checked directly where needed

    def mousePressEvent(self, event):
        """Handles mouse button presses for dragging and resizing."""
        # Ignore if locked (check window's property)
        if getattr(self.window, 'is_locked', False): return

        if event.button() == Qt.LeftButton:
            self.drag_pos = None # Reset drag position
            self.resizing = False # Reset resizing flag
            pos = event.pos()
            self._detect_resize_edges(pos) # Check if cursor is near edge

            if any(self.resizing_edges.values()):
                self.resizing = True
                self.resize_start_pos = event.globalPos() # Store global start pos for resize calc
                self.original_geometry = self.window.geometry() # Store original geometry
                logging.debug("InteractionHandler: Starting resize.")
            else:
                # Check if click is in the 'title bar' area (excluding buttons/text area)
                # Requires knowledge of the window layout (passed or accessed)
                title_h = 35 # Approximate title bar height
                # Access widgets directly from the window instance
                close_rect = getattr(self.window, 'close_button', None).geometry() if hasattr(self.window, 'close_button') else QRect()
                opts_rect = getattr(self.window, 'options_button', None).geometry() if hasattr(self.window, 'options_button') else QRect()
                grab_rect_btn = getattr(self.window, 'grab_button', None).geometry() if hasattr(self.window, 'grab_button') else QRect()
                text_rect = getattr(self.window, 'text_display', None).geometry() if hasattr(self.window, 'text_display') else QRect()

                # Check if click is within title height but NOT on buttons or text area
                is_on_widget = (close_rect.contains(pos) or
                                opts_rect.contains(pos) or
                                grab_rect_btn.contains(pos) or
                                text_rect.contains(pos))

                if pos.y() < title_h and not is_on_widget:
                    # Start dragging
                    self.drag_pos = event.globalPos() - self.window.frameGeometry().topLeft()
                    self.window.setCursor(Qt.SizeAllCursor) # Provide visual feedback
                    logging.debug("InteractionHandler: Starting drag.")
                else:
                    # Click was on a widget or outside title bar, unset cursor
                    self.window.unsetCursor()

    def mouseMoveEvent(self, event):
        """Handles mouse movement for dragging and resizing."""
        # Ignore if locked
        if getattr(self.window, 'is_locked', False): return

        # Determine current state
        is_left_button_down = event.buttons() == Qt.LeftButton
        is_dragging = self.drag_pos is not None and is_left_button_down
        is_resizing = self.resizing and is_left_button_down

        if is_dragging:
            # Move window based on drag position
            self.window.move(event.globalPos() - self.drag_pos)
        elif is_resizing:
            # Handle resize logic
            self._handle_resize(event.globalPos())
        else:
            # Update resize cursor if mouse is just moving over edges (no button down)
            self._set_resize_cursor(event.pos())

    def mouseReleaseEvent(self, event):
        """Handles mouse button releases to stop dragging/resizing."""
        if event.button() == Qt.LeftButton:
            was_resizing = self.resizing # Check if we were resizing before resetting flags
            self.drag_pos = None
            self.resizing = False
            self.resizing_edges = {k: False for k in self.resizing_edges} # Reset edge flags
            self.window.unsetCursor() # Restore default cursor

            # If we just finished resizing, trigger a settings save
            # Note: This creates a dependency back to the main window's save logic.
            # Consider using signals for better decoupling later.
            # if was_resizing and hasattr(self.window, 'save_settings'):
            #     self.window.save_settings() # Save geometry changes implicitly

            logging.debug("InteractionHandler: Mouse released, drag/resize finished.")

    def _detect_resize_edges(self, pos):
        """Detects if the mouse position is within the resize margin of window edges."""
        if getattr(self.window, 'is_locked', False):
            self.resizing_edges = {k: False for k in self.resizing_edges}
            return

        x, y = pos.x(), pos.y()
        w, h = self.window.width(), self.window.height()
        margin = config.RESIZE_MARGIN

        self.resizing_edges['left'] = (0 <= x < margin)
        self.resizing_edges['top'] = (0 <= y < margin)
        # Adjust right/bottom check to include the margin fully
        self.resizing_edges['right'] = (w - margin < x <= w)
        self.resizing_edges['bottom'] = (h - margin < y <= h)

    def _set_resize_cursor(self, pos):
        """Sets the appropriate resize cursor based on mouse position near edges."""
        # Don't change cursor if locked, currently resizing, or dragging
        if getattr(self.window, 'is_locked', False) or self.resizing or (self.drag_pos and QApplication.mouseButtons() == Qt.LeftButton):
            return

        self._detect_resize_edges(pos)
        edges = self.resizing_edges # Use dictionary keys

        if (edges['left'] and edges['top']) or (edges['right'] and edges['bottom']):
            self.window.setCursor(Qt.SizeFDiagCursor) # Diagonal NW-SE / SW-NE
        elif (edges['right'] and edges['top']) or (edges['left'] and edges['bottom']):
            self.window.setCursor(Qt.SizeBDiagCursor) # Diagonal NE-SW / NW-SE
        elif edges['left'] or edges['right']:
            self.window.setCursor(Qt.SizeHorCursor) # Horizontal
        elif edges['top'] or edges['bottom']:
            self.window.setCursor(Qt.SizeVerCursor) # Vertical
        else:
            self.window.unsetCursor() # Default arrow cursor

    def _handle_resize(self, global_pos):
        """Calculates and applies the new window geometry during resizing."""
        if not self.resizing or self.original_geometry is None or self.resize_start_pos is None:
             return # Should not happen if resizing is true, but safeguard

        delta = global_pos - self.resize_start_pos
        new_rect = QRect(self.original_geometry) # Start with original geometry

        min_w, min_h = config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT

        # Adjust right edge
        if self.resizing_edges['right']:
             new_rect.setWidth(max(min_w, self.original_geometry.width() + delta.x()))

        # Adjust bottom edge
        if self.resizing_edges['bottom']:
             new_rect.setHeight(max(min_h, self.original_geometry.height() + delta.y()))

        # Adjust left edge (moves top-left corner and potentially width)
        if self.resizing_edges['left']:
             new_left = self.original_geometry.left() + delta.x()
             # Prevent shrinking beyond minimum width by adjusting left edge relative to right edge
             max_left = new_rect.right() - min_w + 1 # Calculate max allowed left pos
             new_left = min(new_left, max_left) # Ensure left doesn't go too far right
             new_rect.setLeft(new_left)

        # Adjust top edge (moves top-left corner and potentially height)
        if self.resizing_edges['top']:
             new_top = self.original_geometry.top() + delta.y()
             # Prevent shrinking beyond minimum height
             max_top = new_rect.bottom() - min_h + 1 # Calculate max allowed top pos
             new_top = min(new_top, max_top) # Ensure top doesn't go too far down
             new_rect.setTop(new_top)

        # Final geometry check (should be redundant if logic above is correct, but safe)
        if new_rect.width() < min_w: new_rect.setWidth(min_w)
        if new_rect.height() < min_h: new_rect.setHeight(min_h)

        self.window.setGeometry(new_rect)