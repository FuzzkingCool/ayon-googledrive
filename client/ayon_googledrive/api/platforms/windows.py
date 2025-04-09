import os
import re
import ctypes
import winreg
import subprocess
import time
from pathlib import Path

from .base import GDrivePlatformBase
from ..lib import run_process, normalize_path, clean_relative_path

from ...ui import notifications 


class GDriveWindowsPlatform(GDrivePlatformBase):
    """Windows-specific implementation for Google Drive operations"""
    
    def is_googledrive_installed(self):
        """Check if Google Drive is installed on Windows"""
        try:
            # Check program files directories
            program_files_paths = [
                os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Drive File Stream"),
                os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Drive File Stream")
            ]
            
            for base_path in program_files_paths:
                if os.path.exists(base_path):
                    self.log.debug(f"Found Google Drive installation at {base_path}")
                    return True
                    
            # Check registry as fallback
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                   r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Google Drive") as key:
                    self.log.debug("Found Google Drive in registry")
                    return True
            except FileNotFoundError:
                self.log.debug("Google Drive not found in registry")
                
            return False
                
        except Exception as e:
            self.log.error(f"Error checking if Google Drive is installed: {e}")
            return False
    
    def is_googledrive_running(self):
        """Check if Google Drive is currently running on Windows"""
        try:
            result = run_process(["tasklist", "/FI", "IMAGENAME eq GoogleDriveFS.exe"], check=False)
            if result and "GoogleDriveFS.exe" in result.stdout:
                self.log.debug("Google Drive process is running")
                return True
            return False
        except Exception as e:
            self.log.error(f"Error checking if Google Drive is running: {e}")
            return False
    
    def is_user_logged_in(self):
        """Check if a user is logged into Google Drive on Windows"""
        # Check if there are any numeric directories in the DriveFS folder (account IDs)
        driveFS_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "DriveFS")
        
        if not os.path.exists(driveFS_path):
            return False
        
        try:
            dirs = [d for d in os.listdir(driveFS_path) 
                   if os.path.isdir(os.path.join(driveFS_path, d)) and 
                   any(c.isdigit() for c in d)]
            return len(dirs) > 0
        except Exception as e:
            self.log.error(f"Error checking Google Drive login: {e}")
            return False
    
    def start_googledrive(self):
        """Start Google Drive application on Windows"""
        try:
            drive_exe_path = self._find_googledrive_executable()
            
            if drive_exe_path and os.path.exists(drive_exe_path):
                self.log.info(f"Starting Google Drive from: {drive_exe_path}")
                
                # Create startupinfo to hide window
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                
                subprocess.Popen(
                    [drive_exe_path],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                return True
                
            self.log.error("Could not find Google Drive executable")
            return False
            
        except Exception as e:
            self.log.error(f"Error starting Google Drive: {e}")
            return False
    
    def _find_googledrive_executable(self):
        """Find the Google Drive executable by locating the latest version folder"""
        try:
            base_dirs = [
                os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Drive File Stream"),
                os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Drive File Stream")
            ]
            
            for base_dir in base_dirs:
                if not os.path.exists(base_dir):
                    continue
            
                # Look for version folders (e.g., "106.0.4.0")
                version_pattern = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
                version_dirs = []
                
                # Collect all version directories
                for item in os.listdir(base_dir):
                    full_path = os.path.join(base_dir, item)
                    if os.path.isdir(full_path) and version_pattern.match(item):
                        version_dirs.append((item, full_path))
                
                if not version_dirs:
                    continue
                
                # Sort versions and get the latest
                version_dirs.sort(key=lambda x: [int(n) for n in x[0].split('.') if n.isdigit()], reverse=True)
                latest_version, latest_dir = version_dirs[0]
                
                # Construct path to executable
                exe_path = os.path.join(latest_dir, "GoogleDriveFS.exe")
                
                if os.path.exists(exe_path):
                    self.log.debug(f"Found Google Drive executable: {exe_path}")
                    return exe_path
            
            self.log.error("Google Drive executable not found")
            return None
        
        except Exception as e:
            self.log.error(f"Error finding Google Drive executable: {e}")
            return None
    
    def find_source_path(self, relative_path):
        """Find the full path to a Google Drive item on Windows"""
        clean_path = clean_relative_path(relative_path)
        
        # Check all available drive letters (no preference)
        drive_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        # Find Google Drive mount point with "Shared drives" folder
        google_drive_letter = None
        
        self.log.debug(f"Looking for Google Drive mount with Shared drives folder")
        for drive_letter in drive_letters:
            test_path = f"{drive_letter}:\\"
            shared_drives_path = os.path.join(test_path, "Shared drives")
            
            if os.path.exists(test_path) and os.path.exists(shared_drives_path):
                self.log.info(f"Found Google Drive mount with Shared drives at {test_path}")
                google_drive_letter = drive_letter
                break
        
        if not google_drive_letter:
            self.log.error(f"Could not find Google Drive mount point on any drive letter")
            return None
        
        # Now try to find the exact shared drive
        base_path = f"{google_drive_letter}:\\"
        shared_drives_path = os.path.join(base_path, "Shared drives")
        
        # Log all available shared drives to help with debugging
        if os.path.exists(shared_drives_path):
            try:
                drives = os.listdir(shared_drives_path)
                drives = [drive for drive in drives if os.path.isdir(os.path.join(shared_drives_path, drive))]
                self.log.info(f"Available shared drives: {', '.join(drives)}")
            except Exception as e:
                self.log.error(f"Error listing shared drives: {e}")
        
        # Try different path variants
        path_variants = [
            # Original path
            os.path.join(base_path, clean_path),
            # Path with backslashes normalized
            os.path.join(base_path, clean_path.replace('\\', os.path.sep)),
            # In Shared drives directly
            os.path.join(base_path, "Shared drives", clean_path.replace('\\Shared drives\\', '').lstrip('\\')),
            # Try different capitalization
            os.path.join(base_path, "Shared Drives", clean_path.replace('\\Shared drives\\', '').lstrip('\\'))
        ]
        
        for path in path_variants:
            self.log.debug(f"Checking path variant: {path}")
            if os.path.exists(path):
                self.log.info(f"Found source path: {path}")
                return path
        
        self.log.error(f"Could not locate path '{clean_path}' in Google Drive on {google_drive_letter}:")
        return None
    
    def list_shared_drives(self):
        """List available shared drives on Windows"""
        drives = []
        
        # Find Google Drive mount point
        for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            shared_drive_path = f"{drive_letter}:\\Shared drives"
            if os.path.exists(shared_drive_path):
                try:
                    drives = os.listdir(shared_drive_path)
                    self.log.info(f"Found shared drives on {drive_letter}: {drives}")
                    return drives
                except Exception as e:
                    self.log.error(f"Error listing shared drives: {e}")
                
        return drives
    
    def create_mapping(self, source_path, target_path, mapping_name=None):
        """Create a Windows mapping from source to target using SUBST"""
        # Extract and format drive letter from target
        if not target_path.endswith(":\\"):
            if target_path.endswith(":"):
                target_path = target_path + "\\"
            elif not target_path.endswith("\\"):
                target_path = target_path + "\\"
        
        drive_letter = target_path[0]
        
        self.log.info(f"Creating mapping: {drive_letter}: -> {source_path}")
        
        # Check if target drive letter already exists with correct mapping
        if os.path.exists(target_path):
            try:
                # Check if existing mapping is what we want
                result = run_process(["subst"], check=False)
                if result and drive_letter + ":" in result.stdout:
                    existing_mapping = None
                    for line in result.stdout.splitlines():
                        if line.startswith(drive_letter + ":"):
                            existing_mapping = line.split("=>", 1)[1].strip() if "=>" in line else None
                    
                    if existing_mapping == source_path:
                        self.log.info(f"Drive {drive_letter}: is already mapped to {source_path}")
                        return True
                    else:
                        self.log.warning(f"Drive {drive_letter}: is already mapped to {existing_mapping}, not {source_path}")
                        self.alert_drive_in_use(drive_letter, existing_mapping, source_path)
                        return False
            except Exception as e:
                self.log.error(f"Error checking existing drive mapping: {e}")
        
        # Create the mapping with simple SUBST command
        try:
            # Use subprocess with hidden window
            result = subprocess.run(
                ["subst", f"{drive_letter}:", source_path], 
                check=False,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                self.log.info(f"Successfully mapped drive {drive_letter}: to {source_path}")
                return True
            else:
                self.log.error(f"Failed to create drive mapping. Error: {result.stderr}")
                return False
        except Exception as e:
            self.log.error(f"Error creating drive mapping: {e}")
            return False

    def ensure_mount_point(self, desired_mount):
        """Ensure Google Drive is mounted at the desired drive letter"""
        # Find actual Google Drive path
        current_mount = None
        for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            shared_drive_path = f"{drive_letter}:\\Shared drives"
            if os.path.exists(shared_drive_path):
                current_mount = f"{drive_letter}:"
                break
        
        if not current_mount:
            self.log.error("Google Drive path not found on any drive")
            return False
            
        # Clean up desired mount format
        if not desired_mount.endswith(':'):
            desired_mount += ":"
        
        # If drive already at desired letter, all good
        if current_mount == desired_mount:
            self.log.debug(f"Google Drive already mounted at {desired_mount}")
            return True
            
        # We can't actually change the Google Drive mount point from code
        notification = (
            f"Google Drive is mounted at {current_mount}, not at desired mount point {desired_mount}. "
            f"It ought to be set to {desired_mount}. This can only be changed in Google Drive settings."
        )
        self.log.warning(f"Google Drive mount point mismatch: {notification}")
        
        # Return the mismatch information so the manager can decide what to do
        return False, current_mount

    def alert_drive_in_use(self, drive_letter, current_mapping, desired_mapping):
        """Alert the user that a drive letter is already in use"""
        message = (
            f"Drive {drive_letter}: is already in use!\n\n"
            f"Current mapping: {current_mapping}\n"
            f"Desired mapping: {desired_mapping}\n\n"
            f"Please modify your settings to use a different drive letter."
        )
        
        self.log.warning(f"Drive conflict: {message}")
        
        # Try to show a GUI alert
        try:
            ctypes.windll.user32.MessageBoxW(0, message, "Google Drive - Drive Conflict", 0x10)
        except Exception as e:
            self.log.debug(f"Could not show GUI alert: {e}")

    def remove_all_mappings(self):
        """Remove all SUBST mappings created by AYON"""
        try:
            # Get list of all existing SUBST mappings
            result = run_process(["subst"], check=False)
            if not result or result.returncode != 0:
                self.log.error("Failed to list SUBST mappings")
                return False
                
            # Process each line and remove mappings
            for line in result.stdout.splitlines():
                if '=>' in line:
                    drive_letter = line.split(':')[0].strip()
                    self.log.info(f"Removing SUBST mapping for {drive_letter}:")
                    
                    # Run SUBST /D to delete the mapping
                    subprocess.run(
                        ["subst", f"{drive_letter}:", "/D"], 
                        check=False,
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
            
            return True
        except Exception as e:
            self.log.error(f"Error removing drive mappings: {e}")
            return False

    def check_mapping_exists(self, target_path):
        """Check if a mapping exists at the target path"""
        if target_path.endswith(":\\"):
            drive_letter = target_path[0]
        elif target_path.endswith(":"):
            drive_letter = target_path[0]
        else:
            drive_letter = target_path[0]
            
        # Check if the drive exists
        return os.path.exists(f"{drive_letter}:\\")
    
    def check_mapping_valid(self, source_path, target_path):
        """Check if mapping from source to target is valid"""
        try:
            if not self.check_mapping_exists(target_path):
                return False
                
            # Clean up target path format
            if target_path.endswith(":\\"):
                drive_letter = target_path[0]
            elif target_path.endswith(":"):
                drive_letter = target_path[0]
            else:
                drive_letter = target_path[0]
                
            # Run SUBST to see what the drive is mapped to
            result = run_process(["subst"], check=False)
            if not result or result.returncode != 0:
                return False
                
            for line in result.stdout.splitlines():
                if line.startswith(f"{drive_letter}:"):
                    current_target = line.split("=>", 1)[1].strip() if "=>" in line else None
                    return current_target == source_path
                    
            return False
        except Exception as e:
            self.log.error(f"Error checking mapping validity: {e}")
            return False
    
    def show_admin_instructions(self, source_path, target_path):
        """Show instructions for operations requiring admin privileges"""
        drive_letter = target_path[0]
        message = (
            f"To create a permanent drive mapping for {drive_letter}: to {source_path},\n"
            f"you need administrator privileges. You can run this command in an\n"
            f"elevated Command Prompt:\n\n"
            f"subst {drive_letter}: \"{source_path}\""
        )
        
        self.log.info(f"Admin instructions: {message}")
        
        # Try to show a GUI message
        try:
            ctypes.windll.user32.MessageBoxW(0, message, "Google Drive - Administrator Required", 0x40)
        except Exception as e:
            self.log.debug(f"Could not show GUI message: {e}")
            
    def install_googledrive(self, installer_path):
        """Install Google Drive on Windows"""
        try:
            # Check if installer exists
            if not os.path.exists(installer_path):
                self.log.error(f"Installer not found at {installer_path}")
                return False
                
            self.log.info(f"Running Google Drive installer: {installer_path}")
            
            # Run the installer with hidden window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            
            # Run installer silently
            process = subprocess.Popen(
                [installer_path, "--silent"],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Wait for installer to finish with timeout
            try:
                return_code = process.wait(timeout=300)  # 5 minute timeout
                if return_code == 0:
                    self.log.info("Google Drive installer completed successfully")
                    return True
                else:
                    self.log.error(f"Google Drive installer failed with code {return_code}")
                    return False
            except subprocess.TimeoutExpired:
                self.log.warning("Google Drive installer taking too long - continuing anyway")
                return True
                
        except Exception as e:
            self.log.error(f"Error installing Google Drive: {e}")
            return False