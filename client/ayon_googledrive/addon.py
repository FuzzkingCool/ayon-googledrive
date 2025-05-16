import os
import platform
import threading
import time

from ayon_core.addon import AYONAddon, ITrayAddon
from qtpy import QtCore, QtWidgets

from ayon_googledrive.api.gdrive_manager import GDriveManager
from ayon_googledrive.logger import log
from ayon_googledrive.ui.menu_builder import GDriveMenuBuilder
from ayon_googledrive.ui.notifications import show_notification
from ayon_googledrive.version import __version__
from ayon_googledrive.constants import ADDON_ROOT


class GDriveAddon(AYONAddon, ITrayAddon):
    """Google Drive integration addon for AYON.
    
    This addon provides Google Drive monitoring and integration with AYON.
    
    As an ITrayAddon, it shows Google Drive status in the system tray.
    As an ITrayService, it provides Google Drive functionality to other addons.
    
    Service methods:
    - notify(title, message, level="info", **kwargs): Show a notification
    - get_drive_status(): Get current Google Drive status
    - ensure_drive_mappings(): Ensure Google Drive mappings are consistent
    """

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

        # Initialize manager service
        self._gdrive_manager = GDriveManager(self.settings)
        self._menu_builder = GDriveMenuBuilder(self)

        # Initialize other properties
        self._monitor_thread = None
        self._monitoring = False
        self._tray = None
        
        # Auto-start Google Drive if it's installed but not running
        if self.settings.get("auto_restart_googledrive"):
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
            for _ in range(20):
                time.sleep(1)
                if self._gdrive_manager.is_googledrive_running(): 
                    # update ui thread
                    QtCore.QTimer.singleShot(0, self._update_menu)
                    break
  
            # Now check if user is logged in and set up mappings if so
            if self._gdrive_manager.is_user_logged_in():
                log.debug("Google Drive has started - setting up drive mappings")
                self._setup_drive_mappings()
                # No need for a separate thread to verify mappings
            else:
                log.debug("Google Drive has started but no user is logged in - Please log in with your email.")
                
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
            time.sleep(1)
            
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
        from ayon_googledrive.ui.notifications import process_notification_queue
        
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

        # Clean up any mappings
        self._gdrive_manager.platform_handler.remove_all_mappings()
 
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
        """Wait for Google Drive to mount and then set up mappings"""
        from ayon_googledrive.ui import (
            notifications,  # Import at function level to avoid circular imports
        )
        
        # Define a local show_notification function that uses the imported module
        def show_notification(title, message):
            try:
                notifications.show_notification(message, title)
            except Exception as e:
                self.log.warning(f"Could not show notification: {e}")
        
        # Rest of the function remains the same
        start_time = time.time()
        timeout = 60  # Wait up to 60 seconds for mount to appear
        
        while time.time() - start_time < timeout:
            if self._gdrive_manager.is_googledrive_mounted():
                self.log.debug("Google Drive mounted, setting up mappings")
                self._gdrive_manager.ensure_consistent_paths()
                return
            time.sleep(1)
        
        # If we get here, drive didn't mount within timeout
        self.log.error(f"Google Drive mount point didn't appear within {timeout} seconds")
        show_notification("Google Drive Mount Issue", 
                         "Google Drive did not mount within the expected time. " +
                         "Please check your Google Drive installation.")

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
        if self._monitor_thread and self._monitor_thread.is_alive():
            log.debug("Stopping Google Drive monitoring thread")
            # Thread will terminate on its own at next check interval
            # since we set self._monitoring = False
            self._monitor_thread.join(timeout=5)  # Wait for thread to finish

            # Check if the thread is 
            log.debug("Google Drive monitoring thread stopped")
        else:
            log.debug("No monitoring thread to stop")
        # Clean up the thread reference
        self._monitor_thread = None
        self._monitoring = False


    def _monitor_googledrive(self):
        """Monitor Google Drive status in background thread."""
        import os
        import time
        
        check_interval = 30
        menu_update_interval = 10
        log.debug("Google Drive monitoring thread started")

        menu_update_counter = 0
        retry_count = 0
        max_retries = 5
        notified_not_installed = False

        while self._monitoring:
            try:
                is_installed = self._gdrive_manager.is_googledrive_installed()

                if not is_installed:
                    if not notified_not_installed:
                        from ayon_googledrive.ui.notifications import show_notification
                        QtCore.QTimer.singleShot(
                            25000,
                            lambda: show_notification(
                                "Google Drive Not Installed",
                                "Google Drive is not installed. Please install it to use shared drives.",
                                level="warning",
                                unique_id="gdrive_not_installed"
                            )
                        )
                        notified_not_installed = True
                    QtCore.QTimer.singleShot(0, self._update_menu)
                    for _ in range(check_interval):
                        if not self._monitoring:
                            break
                        time.sleep(1)
                    continue

                # Only reach here if installed
                notified_not_installed = False

                process_running = self._gdrive_manager.is_googledrive_running()
                drive_mounted = False
                mounted_letter = None
                if platform.system() == "Windows":
                    for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                        shared_drives_path = f"{drive_letter}:\\Shared drives"
                        if os.path.exists(shared_drives_path):
                            drive_mounted = True
                            mounted_letter = drive_letter
                            break
                    if drive_mounted:
                        log.debug(f"Google Drive mounted at drive letter: {mounted_letter}:")
                else:
                    if platform.system() == "Darwin":
                        if os.path.exists("/Volumes/GoogleDrive"):
                            drive_mounted = True
                    else:
                        if os.path.exists("/mnt/google_drive"):
                            drive_mounted = True

                # log.debug(f"Google Drive status check: process={process_running}, drive_mounted={drive_mounted}")

                # Only attempt restart logic if installed
                if not process_running or not drive_mounted:
                    if retry_count < max_retries:
                        log.warning(f"Google Drive issue detected - process:{process_running}, mounted:{drive_mounted}")
                        from ayon_googledrive.ui.notifications import show_notification
                        show_notification(
                            "Google Drive Restarting",
                            "Google Drive was closed or not responding and will be restarted automatically.",
                            level="warning",
                            unique_id="gdrive_restart"
                        )
                        log.warning("Attempting to restart Google Drive")
                        self._gdrive_manager.start_googledrive()
                        self._wait_for_drive_and_map()
                        retry_count += 1
                    else:
                        log.error(f"Failed to restart Google Drive after {max_retries} attempts")
                        from ayon_googledrive.ui.notifications import show_notification
                        show_notification(
                            "Google Drive Error",
                            f"Failed to restart Google Drive after {max_retries} attempts. Will try again later.",
                            level="error",
                            unique_id="gdrive_restart_failed"
                        )
                        
                        retry_count = 0
                else:
                    retry_count = 0
                    if drive_mounted:
                        self._gdrive_manager.ensure_consistent_paths()

                menu_update_counter += 1
                if menu_update_counter >= menu_update_interval:
                    menu_update_counter = 0
                    QtCore.QTimer.singleShot(0, self._update_menu)

            except Exception as e:
                log.error(f"Error in Google Drive monitoring thread: {e}")

            for _ in range(check_interval):
                if not self._monitoring:
                    log.debug("Monitoring flag turned off, exiting loop")
                    break
                time.sleep(1)

        log.debug("Google Drive monitoring thread exiting")

    def _show_direct_notification(self, title, message, level="info"):
        """Show notification with guaranteed visibility using multiple methods"""
        try:
            # First try standard method
            
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

    def update_menu(self):
        """Update the Google Drive menu"""
        # Force refresh status
        self._gdrive_manager.refresh_status()
        
        # Create menu
        menu = self._tray.create_menu("Google Drive")
        
        # Add status indicator
        if self._gdrive_manager.is_googledrive_installed():
            if self._gdrive_manager.is_googledrive_running():
                menu.add_menu_item("Google Drive: Running", self._on_status_click, enabled=False)
                
                # Check if mounted
                if self._gdrive_manager.is_googledrive_mounted():
                    # Check mappings status
                    all_mappings_ok = True
                    for mapping in self._gdrive_manager.get_mappings():
                        target = mapping.get(f"{self._gdrive_manager.platform}_target")
                        if not os.path.exists(target):
                            all_mappings_ok = False
                            break
                            
                    if all_mappings_ok:
                        menu.add_menu_item("Status: All mappings OK", None, enabled=False)
                    else:
                        menu.add_menu_item("Status: Some mappings missing", self._fix_mappings, checkable=False)
                else:
                    menu.add_menu_item("Status: Not mounted", None, enabled=False)
            else:
                menu.add_menu_item("Google Drive: Not running", self._on_status_click, enabled=False)
                menu.add_menu_item("Start Google Drive", self._start_googledrive)
        else:
            menu.add_menu_item("Google Drive: Not installed", self._on_status_click, enabled=False)
            menu.add_menu_item("Install Google Drive", self._install_googledrive)
        
        # Add separator
        menu.add_separator()
        
        # Add more menu options
        if self._gdrive_manager.is_googledrive_installed():
            if self._gdrive_manager.is_googledrive_running():
                menu.add_menu_item("Open Google Drive", self._open_googledrive)
                menu.add_menu_item("Restart Google Drive", self._restart_googledrive)
                menu.add_separator()
                menu.add_menu_item("Fix Mappings", self._fix_mappings)
            
        # Add settings
        menu.add_separator()
        menu.add_menu_item("Settings...", self._open_settings)

    def _fix_mappings(self):
        """Fix the Google Drive mappings"""
        self._gdrive_manager.ensure_consistent_paths()
        # Force menu update
        self.update_menu()

    def _gdrive_installer_completed(self):
        """Called when Google Drive installer completes"""
        self.log.debug("Google Drive installation completed, updating menu")
        # Force status refresh and menu update after a short delay
        # to allow Google Drive to start up
        from qtpy.QtCore import QTimer
        QTimer.singleShot(3000, self.update_menu)

    def notify(self, title, message, level="info", **kwargs):
        """Show a notification via this service.
        
        Required for ITrayService implementation.
        
        Args:
            title (str): Notification title
            message (str): Notification message
            level (str): Notification level (info, warning, error)
            **kwargs: Additional parameters for the notification
        """
        from ayon_googledrive.ui.notifications import show_notification
        show_notification(title, message, level=level)

    def get_drive_status(self):
        """Get current Google Drive status.
        
        Returns:
            dict: Status information about Google Drive
        """
        try:
            return {
                "installed": self._gdrive_manager.is_googledrive_installed(),
                "running": self._gdrive_manager.is_googledrive_running(),
                "logged_in": self._gdrive_manager.is_user_logged_in()
            }
        except Exception as e:
            log.error(f"Error getting drive status: {e}")
            return {"error": str(e)}

    def ensure_drive_mappings(self):
        """Ensure Google Drive mappings are consistent.
        
        Returns:
            bool: True if mappings are consistent
        """
        try:
            return self._gdrive_manager.ensure_consistent_paths()
        except Exception as e:
            log.error(f"Error ensuring drive mappings: {e}")
            return False
