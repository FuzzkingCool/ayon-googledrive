from pathlib import Path
import platform
import os
import tempfile
import urllib.request
import subprocess
import time
import shutil


from ayon_googledrive.api.logger import log
from ayon_googledrive.api.lib import get_settings, run_process

class GDriveInstaller:
    """Downloads and manages Google Drive installers"""
    
    def __init__(self, settings=None):
        """Initialize the installer with settings
        
        Args:
            settings (dict): Settings containing Google Drive download URLs
        """
        self.log = log
        self.os_type = platform.system()
        self._temp_dir = None
        self.settings = settings or get_settings()
        
        # Initialize download_urls from settings
        self.download_urls = self._get_download_urls()

    def _get_download_urls(self):
        """Get download URLs from settings"""
        urls = {}
        
        try:
            if self.settings:
                
                download_cfg = self.settings["download_url"]
                
                # Map platform keys to OS types
                platform_map = {
                    "windows": "Windows",
                    "macos": "Darwin",
                    "linux": "Linux"
                }
                
                # Create a lookup by OS type
                for platform_key, os_type in platform_map.items():
                    if platform_key in download_cfg:
                        urls[os_type] = download_cfg[platform_key]
                
                return urls
            else:
                log.warning("No download_url in settings, using defaults")
        except Exception as e:
            log.error(f"Error getting download URLs from settings: {e}")
        
        # Return default URLs if settings don't have them
        return {
            "Windows": "https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe",
            "Darwin": "https://dl.google.com/drive-file-stream/GoogleDrive.dmg",
            "Linux": "https://dl.google.com/drive-file-stream/GoogleDrive.deb"
        }

    def get_installer_path(self):
        """Get the path to the installer file (downloaded if needed)"""
        if self.os_type not in self.download_urls or not self.download_urls[self.os_type]:
            log.error(f"No Google Drive installer URL available for {self.os_type}")
            return None
            
        url = self.download_urls[self.os_type]
        
        # Create a temporary directory if needed
        if not self._temp_dir:
            self._temp_dir = tempfile.mkdtemp()
        
        # Determine file name from URL
        file_name = url.split("/")[-1]
        installer_path = os.path.join(self._temp_dir, file_name)
        
        # Download the file if it doesn't exist
        if not os.path.exists(installer_path):
            log.debug(f"Downloading Google Drive installer from {url}")
            try:
                urllib.request.urlretrieve(url, installer_path)
                log.debug(f"Downloaded installer to {installer_path}")
                return installer_path
            except Exception as e:
                log.error(f"Failed to download Google Drive installer: {e}")
                return None
        else:
            log.debug(f"Using existing installer at {installer_path}")
            return installer_path

    def cleanup(self):
        """Clean up temporary files"""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
                self._temp_dir = None
                self.log.debug("Temporary installation files cleaned up")
            except Exception as e:
                self.log.error(f"Error cleaning up temporary files: {e}")

    def _install_on_macos(self, installer_path):
        """Install Google Drive on macOS using system GUI prompts"""
        self.log.debug(f"Installing Google Drive on macOS from {installer_path}")
        
        lock_file = os.path.join(os.path.expanduser("~"), ".ayon_gdrive_installing")
        try:
            with open(lock_file, "w") as f:
                f.write(str(time.time()))
        except Exception:
            pass
        
        mount_point = None
        try:
            # Mount DMG
            self.log.debug(f"Mounting DMG: {installer_path}")
            mount_process = run_process(["hdiutil", "attach", installer_path])
            if not mount_process or mount_process.returncode != 0:
                self.log.error("Failed to mount Google Drive disk image")
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                return False
                
            # Find the mount point
            for i in range(10):
                potential_name = f"/Volumes/Install Google Drive{' ' + str(i) if i > 0 else ''}"
                if os.path.exists(potential_name):
                    mount_point = potential_name
                    break
                    
            if not mount_point:
                for name in ["GoogleDrive", "Google Drive"]:
                    if os.path.exists(f"/Volumes/{name}"):
                        mount_point = f"/Volumes/{name}"
                        break
                        
            if not mount_point:
                self.log.error("Could not find Google Drive mount point")
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                return False
                
            self.log.debug(f"DMG mounted at: {mount_point}")
                
            # Find the .pkg file
            pkg_file = None
            for item in os.listdir(mount_point):
                if item.endswith(".pkg"):
                    pkg_file = os.path.join(mount_point, item)
                    break
                    
            if not pkg_file:
                self.log.error("Could not find installer package in mounted DMG")
                run_process(["hdiutil", "detach", mount_point, "-force"])
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                return False
                
            self.log.debug(f"Found installer package at: {pkg_file}")
            
            # Use AppleScript for system authentication dialog
            applescript = f'''
            tell application "System Events"
                display dialog "AYON needs to install Google Drive for Desktop.\\n\\nThis will require administrator privileges." buttons {{"Cancel", "Install"}} default button "Install" with title "AYON: Install Google Drive" with icon caution
                if button returned of result is "Install" then
                    try
                        do shell script "installer -pkg \\"{pkg_file}\\" -target /" with administrator privileges
                        return "Installation completed successfully"
                    on error errMsg
                        display dialog "Failed to install Google Drive: " & errMsg buttons {{"OK"}} default button "OK" with title "Installation Failed" with icon stop
                        return "Installation failed: " & errMsg
                    end try
                else
                    return "Installation cancelled by user"
                end if
            end tell
            '''
            
            # Write the AppleScript to a file
            script_path = os.path.join(tempfile.gettempdir(), "gdrive_install.scpt")
            with open(script_path, "w") as f:
                f.write(applescript)
                
            # Run the AppleScript
            self.log.debug("Running installer with system authentication dialog")
            install_result = run_process(["osascript", script_path])
            
            if install_result and install_result.returncode == 0:
                self.log.info(f"Installation result: {install_result.stdout}")
                success = "failed" not in install_result.stdout.lower() and "cancelled" not in install_result.stdout.lower()
            else:
                self.log.error(f"Installation script error: {install_result.stderr if install_result else 'Unknown error'}")
                success = False
                
            # Create a delayed cleanup script
            cleanup_script = f'''#!/bin/bash
# Wait 2 minutes for installation to complete
sleep 120

# Detach DMG if still mounted
hdiutil detach "{mount_point}" -force &>/dev/null || true

# Remove lock file
rm -f "{lock_file}"

# Remove script
rm -f "{script_path}"
'''
            
            cleanup_path = os.path.join(tempfile.gettempdir(), "gdrive_cleanup.sh")
            with open(cleanup_path, "w") as f:
                f.write(cleanup_script)
                
            os.chmod(cleanup_path, 0o755)
            
            # Run cleanup in background
            subprocess.Popen(
                ["/bin/bash", cleanup_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            return success
                
        except Exception as e:
            self.log.error(f"Error installing Google Drive: {e}")
            if os.path.exists(lock_file):
                os.remove(lock_file)
            return False