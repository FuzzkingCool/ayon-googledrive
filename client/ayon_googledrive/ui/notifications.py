import threading
import time
import os
import re

from qtpy import QtWidgets


from ayon_googledrive.logger import log
from ayon_googledrive.constants import ADDON_ROOT

# Queue for notifications that need to be shown once the system is ready
_notification_queue = []
_system_ready = False
_tray_icon = None

# Track which notifications have been sent this session to avoid duplicates
_sent_notifications = set()

# Try to import ayon_toastnotify
try:
    from ayon_toastnotify import send_notification as toast_send_notification

    _toastnotify_available = True
except ImportError:
    _toastnotify_available = False


def show_notification(
    title, message, level="info", delay_seconds=0, unique_id=None, icon_path=None
):
    """Show notification using best available method.

    Args:
        title (str): Notification title
        message (str): Notification message
        level (str): Notification level - "info", "warning" or "error"
        delay_seconds (int): Optional delay before showing notification
        unique_id (str): Optional unique identifier for deduplication
        icon (str): Optional icon path
    """
    global _notification_queue, _system_ready, _sent_notifications

    # Use a unique_id to deduplicate notifications, or fallback to title+message+level
    if unique_id is None:
        unique_id = f"{title}|{message}|{level}"
    if unique_id in _sent_notifications:
        return
    _sent_notifications.add(unique_id)

    # Full message for logging
    full_message = f"{title}: {message}"

    # Log the message regardless of notification display
    if level == "error":
        log.error(full_message)
    elif level == "warning":
        log.warning(full_message)
    else:
        log.info(full_message)

    # Set default icon if not provided
    if icon_path is None:
        icon_path = os.path.normpath(f"{ADDON_ROOT}/resources/AYON_icon.png").replace("\\" , "/")

    log.debug(f"Showing notification: {title} {message} {level} {delay_seconds} {unique_id} {icon_path}")

    # If toastnotify is available, use it and do nothing else
    if _toastnotify_available:
        try:
            toast_send_notification(title, message, icon=icon_path, crop=False)
            return
        except Exception as e:
            log.warning(f"Toastnotify notification failed: {e}")
            # If toastnotify fails, fall back to tray notification below

    # If system isn't ready yet or a delay is requested, queue the notification
    if not _system_ready or delay_seconds > 0:
        _notification_queue.append(
            (title, message, level, delay_seconds, unique_id, icon_path)
        )
        return

    # Show notification immediately
    _send_notification(title, message, level, icon_path)


def _send_notification(title, message, level, icon=None):
    """Send notification via the system tray icon"""
    global _tray_icon

    try:
        app = QtWidgets.QApplication.instance()
        if app and hasattr(app, "trayIcon"):
            _tray_icon = app.trayIcon
            log.debug("Found tray icon via app.trayIcon")
            _tray_icon.showMessage(title, message, icon=icon)
            return
        if _tray_icon is not None:
            try:
                log.debug(f"Showing notification using cached tray icon: {title}")
                _tray_icon.showMessage(title, message, icon=icon)
                return
            except Exception as e:
                log.debug(f"Cached tray icon failed: {e}")
                _tray_icon = None
        app = QtWidgets.QApplication.instance()
        if not app:
            log.warning("No QApplication instance available; cannot show notification.")
            return
        if hasattr(app, "tray_icon") and app.tray_icon:
            _tray_icon = app.tray_icon
            _tray_icon.showMessage(title, message, icon=icon)
            log.debug(f"Notification sent via app.tray_icon: {title}")
            return
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
                        tray.showMessage(title, message, icon=icon)
                        log.debug(f"Notification sent via menu parent: {title}")
                        return
        for widget in app.topLevelWidgets():
            if hasattr(widget, "systemTrayIcon"):
                if callable(widget.systemTrayIcon):
                    tray = widget.systemTrayIcon()
                else:
                    tray = widget.systemTrayIcon
                if tray and hasattr(tray, "showMessage"):
                    _tray_icon = tray
                    tray.showMessage(title, message, icon=icon)
                    log.debug(f"Notification sent via found tray icon: {title}")
                    return
        for widget in app.allWidgets():
            if isinstance(widget, QtWidgets.QSystemTrayIcon):
                _tray_icon = widget
                widget.showMessage(title, message, icon=icon)
                log.debug(f"Notification sent via QSystemTrayIcon: {title}")
                return
        log.warning(f"Could not find system tray icon, notification not shown: {title}")
    except Exception as e:
        log.error(f"Failed to show notification: {e}")
        # Do not show any dialog or message box here


def process_notification_queue():
    """Process any queued notifications - call this from tray_start"""
    global _notification_queue, _system_ready, _sent_notifications

    # Mark system as ready
    _system_ready = True

    # Nothing to process
    if not _notification_queue:
        return

    # Process notifications with their delays
    def process_queue():
        for title, message, level, delay, unique_id, icon in list(_notification_queue):
            if unique_id in _sent_notifications:
                continue
            if delay > 0:
                time.sleep(delay)
            show_notification(
                title, message, level, delay_seconds=0, unique_id=unique_id, icon_path=icon
            )
        _notification_queue.clear()

    # Process in background thread to not block
    thread = threading.Thread(target=process_queue)
    thread.daemon = True
    thread.start()
