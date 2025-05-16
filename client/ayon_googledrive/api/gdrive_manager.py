import os
import platform
import time

from ayon_googledrive.api.lib import get_settings
from ayon_googledrive.gdrive_installer import GDriveInstaller
from ayon_googledrive.logger import log


class GDriveManager():
    """Handles Google Drive validation and path consistency.

    This class delegates platform-specific operations to the appropriate platform handler.
    """

    def __init__(self, settings=None):
        """Initialize the GDrive Manager.

        Args:
            settings (dict, optional): Settings dictionary for Google Drive.
        """
        self.settings = settings
        self.log = log

        # Detect the platform and initialize the appropriate handler
        self.os_type = platform.system()
        self.platform_handler = None
        if self.os_type == "Windows":
            from ayon_googledrive.api.platforms.windows import GDriveWindowsPlatform
            self.platform_handler = GDriveWindowsPlatform(settings)
        elif self.os_type == "Darwin":
            from ayon_googledrive.api.platforms.macos import GDriveMacOSPlatform
            self.platform_handler = GDriveMacOSPlatform(settings)
        elif self.os_type == "Linux":
            from ayon_googledrive.api.platforms.linux_generic import GDriveLinuxPlatform
            self.platform_handler = GDriveLinuxPlatform(settings)
        else:
            self.log.error(f"Unsupported platform: {self.os_type}")
            raise NotImplementedError(f"Google Drive integration is not implemented for {self.os_type}")

    def is_googledrive_installed(self):
        """Check if Google Drive for Desktop is installed"""
        return self.platform_handler.is_googledrive_installed()

    def is_googledrive_running(self):
        """Check if Google Drive for Desktop is currently running"""
        return self.platform_handler.is_googledrive_running()

    def is_user_logged_in(self):
        """Check if a user is logged into Google Drive"""
        return self.platform_handler.is_user_logged_in()

    def start_googledrive(self):
        """Start Google Drive application"""
        return self.platform_handler.start_googledrive()

    def install_googledrive(self):
        """Download and install Google Drive for Desktop"""
        self.log.debug("Attempting to install Google Drive for Desktop")
        
        # First check if already installed
        if self.is_googledrive_installed():
            self.log.debug("Google Drive already installed")
            return True
        
        # Check if installation is in progress
        lock_file = os.path.join(os.path.expanduser("~"), ".ayon_gdrive_installing")
        if os.path.exists(lock_file):
            try:
                file_age = time.time() - os.path.getmtime(lock_file)
                if file_age < 600:  # 10 minutes
                    self.log.info("Google Drive installation already in progress")
                    return True
            except Exception as e:
                self.log.error(f"Error checking installation lock file: {e}")

        # Initialize installer and download the installation file
        from ayon_googledrive.ui.notifications import show_notification
        show_notification(
            "Google Drive Required",
            "Google Drive is required and will now be downloaded for installation. Please wait while the installer is being downloaded...",
            level="info",
            unique_id="gdrive_download_start"
        )
        installer = GDriveInstaller(self.settings)
        installer_path = installer.get_installer_path()
        self.log.info(f"Installer path: {installer_path}")

        if not installer_path:
            self.log.error("Failed to download Google Drive installer")
            from ayon_googledrive.ui.notifications import show_notification
            show_notification(
                "Google Drive Installer Download Failed",
                "Failed to download Google Drive installer. Please check your internet connection or try again later.",
                level="error"
            )
            return False
        
        # Call the appropriate installation method for this platform
        success = False
        try:
            # Create lock file to prevent multiple installation attempts
            with open(lock_file, "w") as f:
                f.write(str(time.time()))
            
            if platform.system() == "Windows":
                success = self.platform_handler.install_googledrive(installer_path)
            elif platform.system() == "Darwin":
                success = installer._install_on_macos(installer_path)
            else:
                self.log.error(f"Unsupported platform: {platform.system()}")
                from ayon_googledrive.ui.notifications import show_notification
                show_notification(
                    "Google Drive Installation Unsupported",
                    f"Platform {platform.system()} is not supported for automatic installation.",
                    level="error"
                )
                success = False
            
            # Clean up temp files if installation succeeded
            if success:
                installer.cleanup()
                
            # Reset lock file if installation completed
            if os.path.exists(lock_file):
                os.remove(lock_file)
                
            return success
        except Exception as e:
            self.log.error(f"Error during Google Drive installation: {e}")
            from ayon_googledrive.ui.notifications import show_notification
            show_notification(
                "Google Drive Installation Error",
                f"An error occurred during installation: {str(e)}\nInstaller path: {installer_path}",
                level="error"
            )
            if os.path.exists(lock_file):
                os.remove(lock_file)
            return False

    def get_shared_drives(self):
        """Get a list of available shared drives"""
        return self.platform_handler.list_shared_drives()

    def ensure_consistent_paths(self):
        """Ensure consistent path access across platforms"""
        try:
            # Check if user is logged in first
            if not self.is_user_logged_in():
                self.log.warning("No user is logged into Google Drive")
                return False

            # First ensure Google Drive is mounted at the right location
            result = self.platform_handler.ensure_mount_point(self._get_desired_mount())

            # Handle mount point mismatch notification based on settings
            if isinstance(result, tuple) and not result[0]:  # Mismatch detected, got (False, current_mount)
                self.log.warning("Google Drive mount point might not be at the expected location")

                # Check if we should show notification
                show_notifications = self.settings.get("show_mount_mismatch_notifications", False)

                if show_notifications:
                    from ayon_googledrive.ui import notifications
                    current_mount = result[1]
                    desired_mount = self._get_desired_mount()
                    message = (
                        f"Google Drive is mounted at {current_mount}, not at desired mount point {desired_mount}. "
                        f"This can only be changed in Google Drive settings."
                    )
                    notifications.show_notification(message, "Google Drive Mount Point Mismatch")

                # Continue anyway - maybe individual mappings will work
            elif not result:  # Simple False result - something else went wrong
                self.log.warning("Google Drive mount point might not be at the expected location")
                # Continue anyway - maybe individual mappings will work

            # Get all configured mappings
            mappings = self._get_mappings()

            if not mappings:
                self.log.info("No drive mappings configured - nothing to map")
                return True

            # Process each mapping
            success = True
            for mapping in mappings:
                if not self._process_mapping(mapping):
                    self.log.error(f"Failed to process mapping: {mapping.get('name', 'unnamed')}")
                    success = False

            return success

        except Exception as e:
            self.log.error(f"Error ensuring consistent paths: {e}", exc_info=True)
            return False

    def _get_mappings(self):
        """Get mappings from settings"""
        if self.settings:
            return self.settings.get("mappings", [])

        # If settings aren't already loaded, get them
        settings = get_settings()
        return settings.get("mappings", [])

    def _get_desired_mount(self):
        """Get desired mount point from settings"""
        if self.settings:
            mount = self.settings.get("googledrive_mount", {})
        else:
            # If settings aren't already loaded, get them
            settings = get_settings()
            mount = settings.get("googledrive_mount", {})

        if self.os_type == "Windows":
            return mount.get("windows", "G:")
        elif self.os_type == "Darwin":
            return mount.get("macos", "/Volumes/GoogleDrive")
        elif self.os_type == "Linux":
            return mount.get("linux", "/mnt/google_drive")

        return None

    def _process_mapping(self, mapping):
        """Process a single drive mapping"""
        try:
            name = mapping.get("name", "unnamed")
            source_path = mapping.get("source_path", "")

            # Get target based on platform
            if self.os_type == "Windows":
                target = mapping.get("windows_target", "")
            elif self.os_type == "Darwin":
                target = mapping.get("macos_target", "")
            elif self.os_type == "Linux":
                target = mapping.get("linux_target", "")
            else:
                target = ""

            if not source_path or not target:
                self.log.warning(f"Incomplete mapping definition for '{name}': source={source_path}, target={target}")
                return False

            # self.log.debug(f"Processing mapping '{name}': {source_path} -> {target}")

            # Find the actual source path
            full_source_path = self.platform_handler.find_source_path(source_path)
            if not full_source_path:
                self.log.error(f"Could not find source path for {source_path}")
                return False

            # Create the mapping with name
            return self.platform_handler.create_mapping(full_source_path, target, name)

        except Exception as e:
            self.log.error(f"Error processing mapping: {e}")
            return False

    def is_googledrive_mounted(self):
        """Check if Google Drive is mounted and available (platform-specific)."""
        if self.os_type == "Windows":
            for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                shared_drives_path = f"{drive_letter}:\\Shared drives"
                if os.path.exists(shared_drives_path):
                    return True
            return False
        elif self.os_type == "Darwin":
            # Check /Volumes/GoogleDrive or CloudStorage
            if os.path.exists("/Volumes/GoogleDrive"):
                return True
            cloud_storage = os.path.expanduser("~/Library/CloudStorage")
            if os.path.exists(cloud_storage):
                for item in os.listdir(cloud_storage):
                    if item.startswith(("GoogleDrive-", "Google Drive-")):
                        gdrive_path = os.path.join(cloud_storage, item)
                        if os.path.isdir(gdrive_path):
                            return True
            return False
        elif self.os_type == "Linux":
            # Check common mount points
            possible_mounts = [
                "/mnt/google_drive",
                "/mnt/google-drive",
                os.path.expanduser("~/google-drive"),
                os.path.expanduser("~/GoogleDrive"),
                os.path.expanduser("~/Google Drive")
            ]
            for path in possible_mounts:
                if os.path.exists(path) and os.path.isdir(path):
                    try:
                        if os.listdir(path):
                            return True
                    except Exception:
                        continue
            return False
        return False

    

