# -*- coding: utf-8 -*-
import os
import platform
import time

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
            with open(lock_file, "w", encoding="utf-8") as f:
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
        """Get list of available shared drives"""
        try:
            drives = self.platform_handler.list_shared_drives()
            if drives:
                return drives
            else:
                self.log.warning("GDriveManager: No shared drives found")
                return []
        except Exception as e:
            self.log.error(f"GDriveManager: Error getting shared drives: {e}")
            return []

    def ensure_consistent_paths(self):
        """Ensure Google Drive paths are consistent with configured mappings"""
        if not self.is_user_logged_in():
            self.log.warning("No user is logged into Google Drive")
            return False

        # Check if Google Drive is mounted
        if not self.is_googledrive_mounted():
            self.log.warning("Google Drive mount point might not be at the expected location")
            return False

        # Get configured mappings
        mappings = self._get_mappings()
        # self.log.debug(f"Found {len(mappings) if mappings else 0} configured mappings")
        if mappings:
            for i, mapping in enumerate(mappings):
                # self.log.debug(f"  Mapping {i+1}: {mapping.get('name', 'unnamed')} -> {mapping.get('source_path', 'no source')} -> {mapping.get('windows_target', 'no target')}")
                pass
        
        if not mappings:
            self.log.info("No drive mappings configured - nothing to map")
            return True

        # Process each mapping
        success = True
        for mapping in mappings:
            try:
                if not self._process_mapping(mapping):
                    success = False
            except Exception:
                self.log.error(f"Failed to process mapping: {mapping.get('name', 'unnamed')}")
                success = False

        return success

    def _get_mappings(self):
        """Get configured drive mappings from settings"""
        mappings = self.settings.get("mappings", [])
        # self.log.debug(f"Retrieved mappings from settings: {len(mappings) if mappings else 0} mappings found")
        return mappings

    def _get_desired_mount(self):
        """Get the desired mount point for this platform"""
        googledrive_mount = self.settings.get("googledrive_mount", {})
        if self.os_type == "Windows":
            return googledrive_mount.get("windows", "G:\\")
        elif self.os_type == "Darwin":
            return googledrive_mount.get("macos", "/Volumes/GoogleDrive")
        elif self.os_type == "Linux":
            return googledrive_mount.get("linux", "/mnt/google_drive")
        else:
            self.log.warning("Google Drive mount point might not be at the expected location")
            return None

    def _process_mapping(self, mapping):
        """Process a single drive mapping"""
        name = mapping.get("name")
        source_path = mapping.get("source_path")
        
        # Get target path for current platform
        if self.os_type == "Windows":
            target = mapping.get("windows_target")
        elif self.os_type == "Darwin":
            target = mapping.get("macos_target")
        elif self.os_type == "Linux":
            target = mapping.get("linux_target")
        else:
            target = None

        if not source_path or not target:
            self.log.warning(f"Incomplete mapping definition for '{name}': source={source_path}, target={target}")
            return False

        # Find the actual source path within Google Drive
        actual_source = self.platform_handler.find_source_path(source_path)
        if not actual_source:
            self.log.error(f"Could not find source path for {source_path}")
            return False

        try:
            # Create the mapping
            return self.platform_handler.create_mapping(actual_source, target, name)
        except Exception as e:
            self.log.error(f"Error processing mapping: {e}")
            return False

    def is_googledrive_mounted(self):
        """Check if Google Drive is mounted at the expected location"""
        # Use the platform handler to find the actual mount point
        actual_mount = self.platform_handler.find_googledrive_mount()
        if actual_mount:
            # self.log.debug(f"Found Google Drive mount point: {actual_mount}")
            return True
            
        # Fallback to checking the configured mount point
        desired_mount = self._get_desired_mount()
        if not desired_mount:
            self.log.debug("No desired mount point configured")
            return False

        if self.os_type == "Windows":
            exists = os.path.exists(desired_mount)
            self.log.debug(f"Windows mount point {desired_mount} exists: {exists}")
            return exists
        elif self.os_type == "Darwin":
            exists = os.path.exists(desired_mount)
            self.log.debug(f"macOS mount point {desired_mount} exists: {exists}")
            return exists
        elif self.os_type == "Linux":
            exists = os.path.exists(desired_mount)
            self.log.debug(f"Linux mount point {desired_mount} exists: {exists}")
            return exists
        else:
            self.log.debug(f"Unknown platform: {self.os_type}")
            return False

    def debug_localization_info(self):
        """Debug method to print localization information - always runs for troubleshooting"""
            
        # self.log.info(f"Platform: {self.os_type}")
        
        if self.settings:
            localization = self.settings.get("localization", {})
            if localization:
                shared_drive_names = localization.get("shared_drive_names", [])
                if isinstance(shared_drive_names, list):
                    # self.log.info(f"Loaded {len(shared_drive_names)} localization configurations")
                    pass
                else:
                    self.log.warning("Shared drive names not configured properly")
            else:
                self.log.warning("No localization settings found")
        else:
            self.log.warning("No settings available")
        
        # Get shared drive names from platform handler
        try:
            shared_names = self.platform_handler._get_shared_drives_names()
            # self.log.info(f"Using {len(shared_names)} shared drive name variants")
            pass
        except Exception as e:
            self.log.error(f"Error getting shared drive names: {e}")
        
        # Get system locale
        try:
            import locale
            current_locale = locale.getlocale()
            # self.log.info(f"System locale: {current_locale}")
            pass
        except Exception as e:
            self.log.debug(f"Could not get system locale: {e}")
        
        # Call platform-specific path debugging
        try:
            self.platform_handler.debug_path_formation()
        except Exception as e:
            self.log.error(f"Error in path formation debugging: {e}")

    

