import os
import platform
import threading
import time
from qtpy import QtWidgets

from ayon_core.addon import AYONAddon, ITrayAddon
from ayon_core.lib import Logger

from .version import __version__
from .api.gdrive_manager import GDriveManager
from .api.logger import log
from .ui.menu_builder import GDriveMenuBuilder
from .ui.notifications import show_notification

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
        log.debug("Initializing Google Drive addon")
 
        self.settings = settings.get("googledrive", {})
        log.debug(f"Loaded settings: {self.settings}")

        # Initialize manager
        self._gdrive_manager = GDriveManager(self.settings)
        self._menu_builder = GDriveMenuBuilder(self)

        # Initialize other properties
        self._monitor_thread = None
        self._monitoring = False
        self._tray = None
        
        # Auto-start Google Drive if it's installed but not running
        if self._gdrive_manager.is_googledrive_installed():
            if not self._gdrive_manager.is_googledrive_running():
                self._start_googledrive()
            elif self._gdrive_manager.is_user_logged_in():
                # Setup drive mappings automatically if Google Drive is running and logged in
                self._gdrive_manager.ensure_consistent_paths()
        else:
            log.info("Google Drive is not installed - skipping automatic start and mapping")

    def _delayed_mapping_setup(self):
        """Wait for Google Drive to start and then set up mappings."""
        try:
            # Wait for Google Drive to start (up to 30 seconds)
            for _ in range(30):
                time.sleep(1)
                if self._gdrive_manager.is_googledrive_running():
                    break
                    
            # Wait a bit more for it to fully initialize
            time.sleep(5)
            
            # Now check if user is logged in and set up mappings if so
            if self._gdrive_manager.is_user_logged_in():
                log.info("Google Drive has started - setting up drive mappings")
                self._setup_drive_mappings()
                # No need for a separate thread to verify mappings
            else:
                log.info("Google Drive has started but no user is logged in - skipping mapping")
                
        except Exception as e:
            log.error(f"Error in delayed mapping setup: {e}", exc_info=True)

    def _verify_mappings_exist(self):
        """Simply verify our mappings exist and log the results"""
        try:
            mappings = self._gdrive_manager._get_mappings()
            
            for mapping in mappings:
                name = mapping.get("name", "")
                if self._gdrive_manager.os_type == "Windows":
                    target = mapping.get("windows_target", "")
                    if target and os.path.exists(target):
                        log.debug(f"Verified mapping exists: {name} at {target}")
                    else:
                        log.warning(f"Mapping doesn't exist: {name} at {target}")
        
        except Exception as e:
            log.error(f"Error verifying mappings: {e}", exc_info=True)

    def _setup_drive_mappings(self):
        """Set up drive mappings automatically without user intervention."""
        try:
            # Wait a moment to ensure Google Drive is fully initialized
            time.sleep(2)
            
            # Check if Google Drive is running and user is logged in
            if not self._gdrive_manager.is_googledrive_running():
                log.warning("Google Drive is not running - cannot set up mappings automatically")
                return
                
            if not self._gdrive_manager.is_user_logged_in():
                log.warning("No user logged into Google Drive - cannot set up mappings automatically")
                return
                
            # Set up all mappings
            log.info("Setting up Google Drive mappings automatically")
            result = self._gdrive_manager.ensure_consistent_paths()
            
            if result:
                log.info("Successfully set up all Google Drive mappings")
            else:
                log.warning("Some Google Drive mappings could not be set up automatically")
                
        except Exception as e:
            log.error(f"Error setting up automatic drive mappings: {e}", exc_info=True)

    # ITrayAddon
    def tray_init(self):
        """Tray init."""
        pass

    def tray_start(self):
        """Tray start."""
        pass

    def tray_exit(self):
        """Cleanup when tray is closing."""
        log.debug("Cleaning up Google Drive addon")
        
        # Stop monitoring thread if running
        self._stop_monitoring()
        
        # Clean up any SUBST mappings
        if platform.system() == "Windows" and self._gdrive_manager:
            try:
                log.info("Removing all Google Drive SUBST mappings")
                self._gdrive_manager.platform_handler.remove_all_mappings()
            except Exception as e:
                log.error(f"Error cleaning up drive mappings: {e}")

    # Definition of Tray menu
    def tray_menu(self, tray_menu):
        """Add Google Drive menu to tray."""
        # Menu for Tray App
        menu = QtWidgets.QMenu(self.label, tray_menu)
        menu.setProperty("submenu", "off")

        log.debug("Creating Google Drive tray menu")
        
        # Connect the aboutToShow signal to update the menu contents dynamically
        menu.aboutToShow.connect(lambda: self._menu_builder.update_menu_contents(menu))
        
        # Add our Google Drive menu to the tray menu
        tray_menu.addMenu(menu)

    def _validate_googledrive(self):
        """Validate Google Drive mounting and paths."""
        log.debug("Google Drive mount validation starting...")

        # Check if Google Drive is installed
        if not self._gdrive_manager.is_googledrive_installed():
            log.warning("Google Drive for Desktop is not installed")
            show_notification("Google Drive is not installed",
                          "Install Google Drive for Desktop to use shared drives.")
            return False

        # Check if Google Drive is running
        if not self._gdrive_manager.is_googledrive_running():
            log.warning("Google Drive for Desktop is not running")
            show_notification("Google Drive is not running",
                          "Please start Google Drive for Desktop.")
            return False

        # Check if user is logged in
        if not self._gdrive_manager.is_user_logged_in():
            log.warning("No user is logged into Google Drive")
            show_notification("Google Drive login required",
                          "Please log in to Google Drive.")
            return False

        # Validate and fix paths if needed
        result = self._gdrive_manager.ensure_consistent_paths()
        if not result:
            log.error("Failed to establish consistent Google Drive paths")
            show_notification("Google Drive path validation failed",
                          "Could not establish consistent paths for Google Drive.")
            return False

        log.info("Google Drive paths validated successfully")
        return True

    def _install_googledrive(self):
        """Install Google Drive if not present."""
        log.info("Attempting to install Google Drive")

        # Check if already installed
        if self._gdrive_manager.is_googledrive_installed():
            show_notification("Google Drive is already installed",
                          "Google Drive for Desktop is already installed on this machine.")
            return True

        # Install Google Drive
        result = self._gdrive_manager.install_googledrive()

        if result:
            show_notification("Google Drive installed",
                          "Google Drive for Desktop was successfully installed.")
        else:
            show_notification("Google Drive installation failed",
                          "Failed to install Google Drive for Desktop.")

        return result

    def _start_googledrive(self):
        """Start Google Drive application."""
        log.info("Attempting to start Google Drive")
        
        if self._gdrive_manager.is_googledrive_running():
            show_notification("Google Drive already running",
                            "Google Drive is already running.")
            return True
            
        result = self._gdrive_manager.start_googledrive()
        
        if result:
            show_notification("Google Drive starting",
                            "Google Drive is starting up...")
        else:
            show_notification("Failed to start Google Drive",
                            "Could not start Google Drive application.")
            
        return result

    def _start_monitoring(self):
        """Start background monitoring of Google Drive status."""
        import threading
        
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            log.debug("Monitoring thread already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_googledrive)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        log.debug("Started Google Drive monitoring thread")

    def _stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            log.debug("Stopping Google Drive monitoring thread")
            # Thread will terminate on its own at next check interval
            # since we set self._monitoring = False

    def _monitor_googledrive(self):
        """Monitor Google Drive status in background thread."""
        import time
        
        check_interval = 300  # Check every 5 minutes
        log.debug("Google Drive monitoring thread started")

        while self._monitoring:
            try:
                # Check if Google Drive is still running
                if not self._gdrive_manager.is_googledrive_running():
                    log.warning("Google Drive no longer running - attempting to restart")
                    self._gdrive_manager.start_googledrive()
                    
                # Verify mappings are still correct
                self._gdrive_manager.ensure_consistent_paths()
                    
            except Exception as e:
                log.error(f"Error in Google Drive monitoring thread: {e}")
                
            # Sleep for the check interval
            for _ in range(check_interval):
                if not self._monitoring:
                    break
                time.sleep(1)
                
        log.debug("Google Drive monitoring thread stopped")