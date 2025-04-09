import os
import platform
import threading
import time
from qtpy import QtWidgets, QtCore

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
            log.debug("Google Drive is not installed - skipping automatic start and mapping")

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
                log.debug("Google Drive has started - setting up drive mappings")
                self._setup_drive_mappings()
                # No need for a separate thread to verify mappings
            else:
                log.debug("Google Drive has started but no user is logged in - skipping mapping")
                
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
            log.debug("Setting up Google Drive mappings automatically")
            result = self._gdrive_manager.ensure_consistent_paths()
            
            if result:
                log.debug("Successfully set up all Google Drive mappings")
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
        from .ui.notifications import process_notification_queue
        
        # Process any queued notifications now that the tray is ready
        process_notification_queue()
        
        # Update menu contents now that tray is ready
        QtCore.QTimer.singleShot(2000, self._update_menu)
        
        # Start background monitoring of Google Drive
        self._start_monitoring()

    def tray_exit(self):
        """Cleanup when tray is closing."""
        log.debug("Cleaning up Google Drive addon")
        
        # Stop monitoring thread if running
        self._stop_monitoring()
        
        # Clean up any SUBST mappings
        if platform.system() == "Windows" and self._gdrive_manager:
            try:
                log.debug("Removing all Google Drive SUBST mappings")
                self._gdrive_manager.platform_handler.remove_all_mappings()
            except Exception as e:
                log.error(f"Error cleaning up drive mappings: {e}")

    # Definition of Tray menu
    def tray_menu(self, tray_menu):
        """Add Google Drive menu to tray."""
        # Menu for Tray App
        menu = QtWidgets.QMenu(self.label, tray_menu)
        menu.setProperty("submenu", "off")
        
        # Store reference to parent tray menu for notifications
        menu.setProperty("parentTrayMenu", tray_menu)
        
        log.debug("Creating Google Drive tray menu")
        
        # Connect the aboutToShow signal to update the menu contents dynamically
        menu.aboutToShow.connect(lambda: self._menu_builder.update_menu_contents(menu))
        
        # Add our Google Drive menu to the tray menu
        tray_menu.addMenu(menu)
        
        # Store a reference to our menu so notifications can find it
        if not hasattr(QtWidgets.QApplication, "_gdrive_menu"):
            QtWidgets.QApplication._gdrive_menu = menu
            
        # Store a reference to the menu for updates
        self._menu = menu
        
        # Initial update of the menu contents
        QtCore.QTimer.singleShot(1000, lambda: self._menu_builder.update_menu_contents(menu))
        
    def _update_menu(self):
        """Update menu contents if menu exists"""
        if hasattr(self, '_menu') and self._menu:
            self._menu_builder.update_menu_contents(self._menu)

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
        
        # test notification
        show_notification("Google Drive paths validated",
                          "Google Drive paths have been validated successfully.")
        
        log.debug("Google Drive paths validated successfully")
        return True

    def _install_googledrive(self):
        """Install Google Drive if not present."""
        log.debug("Attempting to install Google Drive")

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
        """Start Google Drive application with proper waiting."""
        log.debug("Attempting to start Google Drive")
        
        if self._gdrive_manager.is_googledrive_running():
            show_notification("Google Drive already running",
                            "Google Drive is already running.")
            return True
            
        result = self._gdrive_manager.start_googledrive()
        
        if result:
            show_notification("Google Drive starting",
                            "Google Drive is starting up...")
            
            # Start a background thread to wait for proper initialization and then set up mappings
            thread = threading.Thread(target=self._wait_for_drive_and_map)
            thread.daemon = True
            thread.start()
            
        else:
            show_notification("Failed to start Google Drive",
                            "Could not start Google Drive application.")
            
        return result

    def _wait_for_drive_and_map(self):
        """Wait for Google Drive to initialize fully and then set up mappings."""
        log.debug("Starting Google Drive initialization wait thread")
        
        max_attempts = 30  # Wait up to 30 seconds for Google Drive to start
        poll_interval = 1  # Check every 1 second
        
        # First wait for the process to be running
        for attempt in range(max_attempts):
            if self._gdrive_manager.is_googledrive_running():
                log.debug(f"Google Drive process detected after {attempt+1} seconds")
                break
            time.sleep(poll_interval)
        else:
            log.error("Google Drive process didn't start within expected time")
            return
            
        # Now wait for shared drives to become available (up to 60 seconds)
        max_attempts = 60
        for attempt in range(max_attempts):
            # Look for the Google Drive mount with Shared drives folder on any drive letter
            found = False
            for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                shared_drives_path = f"{drive_letter}:\\Shared drives"
                if os.path.exists(shared_drives_path):
                    log.info(f"Found Google Drive mount with Shared drives at {drive_letter}: after {attempt+1} seconds")
                    found = True
                    break
                    
            if found:
                # Drive is mounted! Now set up our mappings
                log.info("Google Drive mount detected, setting up mappings")
                time.sleep(2)  # Give it a moment more to stabilize
                self._gdrive_manager.ensure_consistent_paths()
                # Update menu after mappings are set up
                QtCore.QTimer.singleShot(0, self._update_menu)
                # Also send a notification
                from .ui.notifications import show_notification
                show_notification("Google Drive Ready", 
                                 "Google Drive has been mounted and mappings set up.",
                                 delay_seconds=1)
                return
                
            time.sleep(poll_interval)
            
        log.error("Google Drive mount point didn't appear within 60 seconds")
        show_notification("Google Drive Mount Issue", 
                        "Google Drive is running but the mount point wasn't detected")

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
        import os
        
        check_interval = 30  # Check every 30 seconds (more responsive)
        menu_update_interval = 10  # Update menu every 10 seconds
        log.debug("Google Drive monitoring thread started")

        menu_update_counter = 0
        while self._monitoring:
            try:
                # First check if process is running
                process_running = self._gdrive_manager.is_googledrive_running()
                
                # Then check if drives are mounted
                drive_mounted = False
                mounted_letter = None
                for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    shared_drives_path = f"{drive_letter}:\\Shared drives"
                    if os.path.exists(shared_drives_path):
                        drive_mounted = True
                        mounted_letter = drive_letter
                        break
                
                # Log the current status
                log.debug(f"Google Drive status check: process={process_running}, drive_mounted={drive_mounted}")
                
                # If either check fails, restart Google Drive
                if not process_running or not drive_mounted:
                    log.warning(f"Google Drive issue detected - process:{process_running}, mounted:{drive_mounted}")
                    
                    # Show notification (before restart to increase chance of it working)
                    self._show_direct_notification(
                        "Google Drive Restarting", 
                        f"Google Drive was closed or not responding and will be restarted automatically.",
                        level="warning"
                    )
                    
                    # Restart Google Drive
                    log.warning("Attempting to restart Google Drive")
                    self._gdrive_manager.start_googledrive()
                    
                    # Wait for it to start up
                    self._wait_for_drive_and_map()
                    continue  # Skip rest of loop and check again
                
                # Verify mappings are still correct if drive is mounted
                if drive_mounted:
                    self._gdrive_manager.ensure_consistent_paths()
                
                # Update menu periodically
                menu_update_counter += 1
                if menu_update_counter >= menu_update_interval:
                    menu_update_counter = 0
                    QtCore.QTimer.singleShot(0, self._update_menu)
                    
            except Exception as e:
                log.error(f"Error in Google Drive monitoring thread: {e}")
                
            # Sleep properly (1 second at a time)
            for _ in range(check_interval):
                if not self._monitoring:
                    break
                time.sleep(1)
                
    def _show_direct_notification(self, title, message, level="info"):
        """Show notification with guaranteed visibility using multiple methods"""
        try:
            # First try standard method
            from .ui.notifications import show_notification
            show_notification(title, message, level=level)
            
            # Also try direct Windows notification as backup
            import platform
            if platform.system() == "Windows":
                try:
                    # Use built-in Windows API directly
                    import ctypes
                    MB_ICONINFORMATION = 0x00000040
                    MB_ICONWARNING = 0x00000030
                    MB_ICONERROR = 0x00000010
                    
                    # Choose icon based on level
                    icon = MB_ICONINFORMATION
                    if level == "warning":
                        icon = MB_ICONWARNING
                    elif level == "error":
                        icon = MB_ICONERROR
                    
                    # Show the notification as a non-blocking message
                    ctypes.windll.user32.MessageBoxTimeoutW(
                        0, message, f"AYON Google Drive - {title}", 
                        icon, 0, 5000  # 5 seconds timeout
                    )
                except Exception as e:
                    log.debug(f"Direct Windows notification failed: {e}")
        except Exception as e:
            log.error(f"Failed to show important notification: {e}")
            # Last resort - print to console
            print(f"\n*** NOTIFICATION: {title} ***\n{message}\n")
