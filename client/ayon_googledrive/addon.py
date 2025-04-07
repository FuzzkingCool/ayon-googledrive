import os
import platform
import threading
import time
import traceback


from ayon_core.addon import (
    AYONAddon,
    ITrayAddon,
    ITrayAction
)
from ayon_core.lib import Logger

from .version import __version__
from .api.gdrive_manager import GDriveManager
 


class GDriveAddon(AYONAddon, ITrayAddon):
    """Google Drive integration addon for AYON."""

    name = "googledrive"
    label = "GoogleDrive"
    version = __version__

    _gdrive_manager = None
    _monitor_thread = None
    _monitoring = False
      
    def initialize(self, settings):
        """Initialization of addon."""
        self.log.debug("Initializing Google Drive addon")
        self.log.debug(f"Available settings keys: {list(settings.keys())}")
        
        # Store settings - try both possible keys
        if "enabled" in settings:
            # Direct settings from get_addon_settings
            self.settings = settings
        else:
            # Nested settings from AYON launcher
            self.settings = settings.get("googledrive", {})
           
                
        self.log.debug(f"Loaded settings: {self.settings}")

        # Initialize manager
        self._gdrive_manager = GDriveManager()

        # Initialize other properties
        self._monitor_thread = None
        self._monitoring = False
        self._tray = None
 
    def tray_init(self, tray=None):
        """Initialize addon when tray starts."""
        self.log.debug(f"Initializing Google Drive addon tray with tray: {tray}")
        self._tray = tray
        # Don't call tray_menu or _add_mapping_status_to_menu here
        # AYON will call tray_menu() at the right time

    def tray_start(self):
        """Start addon's logic in tray."""
        self.log.debug("Starting Google Drive addon")

        # Start validation on a separate thread to not block tray startup
        thread = threading.Thread(target=self._validate_googledrive)
        thread.daemon = True
        thread.start()

        # Start monitoring thread if needed
        self._start_monitoring()
  

    def tray_menu(self, tray_menu):
        """Add Google Drive menu to tray."""
        try:
            # Menu for Tray App
            from qtpy import QtWidgets

            self.log.debug("Creating Google Drive tray menu")
            menu = QtWidgets.QMenu(self.label, tray_menu)
            menu.setProperty("submenu", "on")

            # Actions
            status_action = QtWidgets.QAction("Drive Status", menu)
            menu.addAction(status_action)
            status_action.triggered.connect(self._validate_googledrive)
            
            # Only add install action if manager is initialized
            if hasattr(self, "_gdrive_manager") and self._gdrive_manager:
                if not self._gdrive_manager.is_googledrive_installed():
                    install_action = QtWidgets.QAction("Install Google Drive", menu)
                    menu.addAction(install_action)
                    install_action.triggered.connect(self._install_googledrive)
            
            # Add settings action
            settings_action = QtWidgets.QAction("Settings", menu)
            menu.addAction(settings_action)
            settings_action.triggered.connect(self._show_settings)

            # Add the submenu to the tray menu
            self.log.debug("Adding menu to tray")
            tray_menu.addMenu(menu)
            
        except Exception as e:
            import traceback
            self.log.error(f"Error creating tray menu: {e}")
            self.log.error(traceback.format_exc())

    def _add_mapping_status_to_menu(self, menu):
        """Add mapping status to menu with conflict detection"""
        try:
            from qtpy import QtWidgets, QtGui, QtCore
            from ayon_core.settings import get_project_settings
            settings = get_project_settings()
            addon_settings = settings.get("ayon_googledrive", {})
            mappings = addon_settings.get("mappings", [])

            if not mappings:
                # No mappings configured
                no_mappings_action = QtWidgets.QAction("No drive mappings configured", menu)
                no_mappings_action.setEnabled(False)
                menu.addAction(no_mappings_action)
                return

            # Get OS type
            os_type = platform.system()

            # Add status for each mapping
            for mapping in mappings:
                name = mapping.get("drive_name", "Unnamed")

                # Get target path based on platform
                if os_type == "Windows":
                    target = mapping.get("windows_target", "Not set")
                elif os_type == "Darwin":
                    target = mapping.get("macos_target", "Not set")
                elif os_type == "Linux":
                    target = mapping.get("linux_target", "Not set")
                else:
                    target = "Unknown platform"

                # Check if target exists
                target_exists = os.path.exists(target)

                # Determine status icon
                status_action = QtWidgets.QAction(f"{name}", menu)

                if target_exists:
                    source = mapping.get("source_path", "Unknown")
                    source_full_path = self._gdrive_manager._find_source_path(source)

                    # Check if mapping is correct
                    if source_full_path and os.path.exists(target):
                        try:
                            if os.path.samefile(target, source_full_path):
                                # Correctly mapped
                                icon = QtGui.QIcon.fromTheme("dialog-ok")
                                status_action.setIcon(icon)
                                status_text = "OK"
                            else:
                                # Mapped to wrong location
                                icon = QtGui.QIcon.fromTheme("dialog-warning")
                                status_action.setIcon(icon)
                                status_text = "CONFLICT"
                        except:
                            # Can't compare paths
                            icon = QtGui.QIcon.fromTheme("dialog-question")
                            status_action.setIcon(icon)
                            status_text = "UNKNOWN"
                    else:
                        # Source not found
                        icon = QtGui.QIcon.fromTheme("dialog-error")
                        status_action.setIcon(icon)
                        status_text = "ERROR"
                else:
                    # Target doesn't exist
                    icon = QtGui.QIcon.fromTheme("dialog-error")
                    status_action.setIcon(icon)
                    status_text = "MISSING"

                # Add submenu with details
                details = QtWidgets.QMenu(menu)

                source = mapping.get("source_path", "Unknown")
                details.addAction(f"Source: {source}").setEnabled(False)
                details.addAction(f"Target: {target}").setEnabled(False)
                details.addAction(f"Status: {status_text}").setEnabled(False)

                status_action.setMenu(details)
                menu.addAction(status_action)

        except Exception as e:
            self.log.error(f"Error showing mapping status: {e}")
            error_action = QtWidgets.QAction("Error loading mappings", menu)
            error_action.setEnabled(False)
            menu.addAction(error_action)

    def tray_exit(self):
        """Cleanup when tray is closing."""
        self.log.debug("Cleaning up Google Drive addon")
        # Stop monitoring thread if running
        self._stop_monitoring()

    def _validate_googledrive(self):
        """Validate Google Drive mounting and paths."""
        self.log.debug("Google Drive mount validation starting...")

        # Check if Google Drive is installed
        if not self._gdrive_manager.is_googledrive_installed():
            self.log.warning("Google Drive for Desktop is not installed")
            self._show_notification("Google Drive is not installed",
                              "Install Google Drive for Desktop to use shared drives.")
            return False

        # Check if Google Drive is running
        if not self._gdrive_manager.is_googledrive_running():
            self.log.warning("Google Drive for Desktop is not running")
            self._show_notification("Google Drive is not running",
                              "Please start Google Drive for Desktop.")
            return False

        # Check if user is logged in
        if not self._gdrive_manager.is_user_logged_in():
            self.log.warning("No user is logged into Google Drive")
            self._show_notification("Google Drive login required",
                              "Please log in to Google Drive.")
            return False

        # Validate and fix paths if needed
        result = self._gdrive_manager.ensure_consistent_paths()
        if not result:
            self.log.error("Failed to establish consistent Google Drive paths")
            self._show_notification("Google Drive path validation failed",
                              "Could not establish consistent paths for Google Drive.")
            return False

        self.log.info("Google Drive paths validated successfully")
        return True

    def _install_googledrive(self):
        """Install Google Drive if not present."""
        self.log.info("Attempting to install Google Drive")

        # Check if already installed
        if self._gdrive_manager.is_googledrive_installed():
            self._show_notification("Google Drive is already installed",
                              "Google Drive for Desktop is already installed on this machine.")
            return True

        # Install Google Drive
        result = self._gdrive_manager.install_googledrive()

        if result:
            self._show_notification("Google Drive installed",
                              "Google Drive for Desktop was successfully installed.")
        else:
            self._show_notification("Google Drive installation failed",
                              "Failed to install Google Drive for Desktop.")

        return result

    def _show_notification(self, title, message):
        """Show tray notification."""
        # First try using stored tray reference
        if self._tray:
            try:
                self._tray.showMessage(title, message)
                return
            except Exception as e:
                self.log.debug(f"Failed to show notification using tray: {e}")

        # Fall back to other methods
        try:
            # Import Qt modules
            from qtpy import QtWidgets

            # Get the application instance
            app = QtWidgets.QApplication.instance()

            # Find the system tray icon
            for widget in app.allWidgets():
                if isinstance(widget, QtWidgets.QSystemTrayIcon):
                    widget.showMessage(title, message)
                    return

        except Exception as e:
            self.log.debug(f"Failed to show notification: {e}")

        # Log message if notification failed
        self.log.info(f"{title}: {message}")

    def _start_monitoring(self):
        """Start background monitoring of Google Drive status."""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_googledrive)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

    def _stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(1.0)  # Wait for thread to exit

    def _monitor_googledrive(self):
        """Monitor Google Drive status in background thread."""
        check_interval = 300  # Check every 5 minutes

        while self._monitoring:
            time.sleep(check_interval)

            if not self._gdrive_manager.is_googledrive_running():
                self._show_notification("Google Drive not running",
                                  "Google Drive service has stopped.")
                continue

            # Only check paths if Google Drive is running
            if not self._gdrive_manager.ensure_consistent_paths():
                self._show_notification("Google Drive path issue",
                                  "Google Drive paths are not consistent.")

    def _show_settings(self):
        """Show Google Drive settings."""
        try:
            from ayon_core.tools import open_settings_page
            open_settings_page("googledrive")
            self.log.debug("Opened Google Drive settings page")
        except Exception as e:
            self.log.error(f"Failed to open settings: {e}")
            
            # Fallback if open_settings_page fails
            try:
                from urllib.parse import quote
                import webbrowser
                server_url = "http://localhost:5000"  # Default AYON server URL
                settings_url = f"{server_url}/settings/addons/googledrive"
                webbrowser.open(settings_url)
                self.log.debug(f"Opened Google Drive settings in browser: {settings_url}")
            except Exception as e2:
                self.log.error(f"Failed to open settings in browser: {e2}")