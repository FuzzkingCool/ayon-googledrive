import os
import platform
import subprocess
import time
import sys
from pathlib import Path

# If windows import ctypes & winreg
if platform.system() == "Windows":
    import ctypes
    import winreg
 
# Import AYON core libraries
from ayon_core.lib import Logger
from .logger import log
# Add import for the vendor module
from ..vendor import GDriveInstaller

from ayon_googledrive.api.logger import log
from .platforms import get_platform_handler
from .lib import get_settings

class GDriveManager:
    """Handles Google Drive validation and path consistency.
    
    This class delegates platform-specific operations to the appropriate platform handler.
    """
    
    def __init__(self, settings=None):
        self.log = log
        self.os_type = platform.system()
        self.settings = settings
        self.platform_handler = get_platform_handler()
        
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
        """Download and install Google Drive for Desktop silently"""
        self.log.debug("Attempting to install Google Drive for Desktop")
        
        # First check if already installed
        if self.is_googledrive_installed():
            self.log.debug("Google Drive already installed")
            return True
        
        # Initialize installer and download the installation file
        installer = GDriveInstaller()
        installer_path = installer.get_installer_path()
        
        if not installer_path:
            self.log.error("Failed to download Google Drive installer")
            return False
        
        # Install using platform-specific method
        try:
            self.log.debug(f"Running Google Drive installer: {installer_path}")
            result = self.platform_handler.install_googledrive(installer_path)
            installer.cleanup()
            return result
        except Exception as e:
            self.log.error(f"Error installing Google Drive: {e}")
            installer.cleanup()
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
                    from ..ui import notifications
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
                
            self.log.debug(f"Processing mapping '{name}': {source_path} -> {target}")
            
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



