import threading
import time
from qtpy import QtWidgets, QtCore

from ayon_core.lib import Logger

# Get a logger instance
_logger = Logger.get_logger("googledrive")

# Queue for notifications that need to be shown once the system is ready
_notification_queue = []
_system_ready = False
_tray_icon = None

def show_notification(title, message, level="info", delay_seconds=0):
    """Show notification using best available method.
    
    Args:
        title (str): Notification title
        message (str): Notification message
        level (str): Notification level - "info", "warning" or "error"
        delay_seconds (int): Optional delay before showing notification
    """
    global _notification_queue, _system_ready
    
    # Full message for logging
    full_message = f"{title}: {message}"
    
    # Log the message regardless of notification display
    if level == "error":
        _logger.error(full_message)
    elif level == "warning":
        _logger.warning(full_message)
    else:
        _logger.info(full_message)
        
    # If system isn't ready yet or a delay is requested, queue the notification
    if not _system_ready or delay_seconds > 0:
        _notification_queue.append((title, message, level, delay_seconds))
        return
        
    # Show notification immediately
    _send_notification(title, message, level)
    
def _send_notification(title, message, level):
    """Send notification via the system tray icon"""
    global _tray_icon
    
    try:
        # Try to find system tray using AYON's app property first (most reliable)
        app = QtWidgets.QApplication.instance()
        if app and hasattr(app, "trayIcon"):
            _tray_icon = app.trayIcon
            _logger.debug("Found tray icon via app.trayIcon")
            _tray_icon.showMessage(title, message)
            return
            
        # If we have a cached tray icon, try to use it first
        if _tray_icon is not None:
            try:
                _logger.debug(f"Showing notification using cached tray icon: {title}")
                _tray_icon.showMessage(title, message)
                return
            except Exception as e:
                _logger.debug(f"Cached tray icon failed: {e}")
                # If cached icon fails, reset it and continue with search
                _tray_icon = None
        
        # Find the system tray icon by walking the widget hierarchy
        app = QtWidgets.QApplication.instance()
        if not app:
            _logger.warning("No QApplication instance available")
            
            # Fallback to message box if no app instance
            _show_message_box(title, message)
            return
            
        # Method 1: Get from global variable in AYON core
        if hasattr(app, "tray_icon") and app.tray_icon:
            _tray_icon = app.tray_icon
            _tray_icon.showMessage(title, message)
            _logger.debug(f"Notification sent via app.tray_icon: {title}")
            return
        
        # Method 2: Try through addon registry or QApplication properties
        if hasattr(QtWidgets.QApplication, "_gdrive_menu"):
            menu = QtWidgets.QApplication._gdrive_menu
            if menu and hasattr(menu, "parentTrayMenu") and menu.parentTrayMenu():
                parent_menu = menu.parentTrayMenu()
                parent_widget = parent_menu.parent()
                if parent_widget and hasattr(parent_widget, "systemTrayIcon"):
                    if callable(parent_widget.systemTrayIcon):
                        tray = parent_widget.systemTrayIcon()
                    else:
                        tray = parent_widget.systemTrayIcon
                    
                    if tray:
                        _tray_icon = tray
                        tray.showMessage(title, message)
                        _logger.debug(f"Notification sent via menu parent: {title}")
                        return

        # Method 3: Direct search through top level widgets
        for widget in app.topLevelWidgets():
            # Try to find TrayWidget from AYON
            if hasattr(widget, "systemTrayIcon"):
                if callable(widget.systemTrayIcon):
                    tray = widget.systemTrayIcon()
                else:
                    tray = widget.systemTrayIcon
                    
                if tray and hasattr(tray, "showMessage"):
                    _tray_icon = tray  # Cache for future use
                    tray.showMessage(title, message)
                    _logger.debug(f"Notification sent via found tray icon: {title}")
                    return
        
        # Method 4: Check for QSystemTrayIcon instances
        for widget in app.allWidgets():
            if isinstance(widget, QtWidgets.QSystemTrayIcon):
                _tray_icon = widget  # Cache for future use
                widget.showMessage(title, message)
                _logger.debug(f"Notification sent via QSystemTrayIcon: {title}")
                return
                
        # If all else fails, show a message box
        _logger.warning(f"Could not find system tray icon, using fallback message box: {title}")
        _show_message_box(title, message)
        
    except Exception as e:
        _logger.error(f"Failed to show notification: {e}")
        
        # Fall back to Windows-specific notification as last resort
        import platform
        if platform.system() == "Windows":
            try:
                _logger.debug("Attempting Windows-specific notification fallback")
                import ctypes
                
                # MessageBoxTimeout API - shows non-blocking notification
                prototype = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_wchar_p, 
                                              ctypes.c_wchar_p, ctypes.c_int, ctypes.c_int, ctypes.c_int)
                MessageBoxTimeout = prototype(("MessageBoxTimeoutW", ctypes.windll.user32))
                
                # Show with 5 second timeout (non-blocking)
                MessageBoxTimeout(0, message, f"AYON Google Drive - {title}", 0x00000040, 0, 5000)
                _logger.debug("Windows fallback notification shown")
                return
            except Exception as e:
                _logger.error(f"Windows fallback notification failed: {e}")

def _show_message_box(title, message):
    """Fallback to show message in a dialog box"""
    try:
        # Use QTimer to show message box on main thread
        def show_box():
            msgBox = QtWidgets.QMessageBox()
            msgBox.setWindowTitle("Google Drive Notification")
            msgBox.setText(title)
            msgBox.setInformativeText(message)
            msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msgBox.setIcon(QtWidgets.QMessageBox.Information)
            msgBox.exec_()
        
        # Ensure message box is shown on the main thread
        QtCore.QTimer.singleShot(0, show_box)
    except Exception as e:
        _logger.error(f"Failed to show message box: {e}")

def process_notification_queue():
    """Process any queued notifications - call this from tray_start"""
    global _notification_queue, _system_ready
    
    # Mark system as ready
    _system_ready = True
    
    # Nothing to process
    if not _notification_queue:
        return
        
    # Process notifications with their delays
    def process_queue():
        for title, message, level, delay in _notification_queue:
            if delay > 0:
                time.sleep(delay)
            _send_notification(title, message, level)
        _notification_queue.clear()
        
    # Process in background thread to not block
    thread = threading.Thread(target=process_queue)
    thread.daemon = True
    thread.start()