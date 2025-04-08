import logging
from qtpy import QtWidgets

from ..api.logger import log

def show_notification(title, message):
    """Show notification using the best available method."""
    try:
        # Get the application instance
        app = QtWidgets.QApplication.instance()

        # Find the system tray icon
        for widget in app.allWidgets():
            if isinstance(widget, QtWidgets.QSystemTrayIcon):
                widget.showMessage(title, message)
                log.debug(f"Showing notification via system tray: {title}: {message}")
                return

        # If no tray icon found, log instead
        log.info(f"{title}: {message}")
    except Exception as e:
        # If notification fails, just log
        log.debug(f"Failed to show notification: {e}")
        log.info(f"{title}: {message}")