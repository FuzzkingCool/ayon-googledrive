import ctypes
import os
import re
import subprocess
import threading
import time
import glob

from ayon_googledrive.api.lib import clean_relative_path,  run_process
from ayon_googledrive.api.platforms.base import GDrivePlatformBase
from ayon_googledrive.logger import log


class GDriveWindowsPlatform(GDrivePlatformBase):
    """Windows-specific implementation for Google Drive operations"""
    
    def __init__(self, settings=None):
        """Initialize the Windows platform handler.
        
        Args:
            settings (dict, optional): Settings dictionary from GDriveManager.
        """
        super(GDriveWindowsPlatform, self).__init__()
        self.settings = settings or {}
        self._installing_lock = threading.Lock()
        self._installing = False

    @property
    def installing(self):
        with self._installing_lock:
            return self._installing

    def set_installing(self, value: bool):
        with self._installing_lock:
            self._installing = value

    def is_googledrive_installed(self):
        """Check if Google Drive is installed on Windows by checking for the executable in the latest versioned folder."""
        exe_path = self._get_configured_executable_path()
        if exe_path and os.path.isfile(exe_path):
            self.log.debug(f"Found Google Drive executable at: {exe_path}")
            return True
        self.log.error(f"Google Drive executable not found at any versioned folder. Last checked: {exe_path}")
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
        """Return the Google Drive executable path, or None if not found."""
        exe_path = self._get_configured_executable_path()
        if exe_path and os.path.isfile(exe_path):
            self.log.debug(f"Found Google Drive executable: {exe_path}")
            return exe_path
        self.log.error(f"Google Drive executable not found at any versioned folder. Last checked: {exe_path}")
        return None

    def _get_configured_executable_path(self):
        """Get the Google Drive executable path from settings or use the latest versioned folder."""
        # Prefer settings
        if self.settings and 'googledrive_path' in self.settings:
            path = self.settings['googledrive_path'].get('windows')
            if path:
                # Handle wildcard in path (e.g., C:\\Program Files\\Google\\Drive File Stream\\*\\)
                if '*' in path:
                    # Remove trailing backslash if present
                    base_glob = path.rstrip('\\/')
                    # Find all matching directories
                    matches = glob.glob(base_glob)
                    version_dirs = []
                    for match in matches:
                        if os.path.isdir(match):
                            # Extract version from folder name
                            version = os.path.basename(match)
                            if re.match(r"^\d+\.\d+\.\d+\.\d+$", version):
                                version_dirs.append((version, match))
                    if not version_dirs:
                        log.error(f"No versioned Google Drive folders found matching wildcard: {base_glob}")
                        return None
                    # Sort by version number, descending
                    def version_key(v):
                        return [int(x) for x in v[0].split('.')]
                    version_dirs.sort(key=version_key, reverse=True)
                    latest_version_dir = version_dirs[0][1]
                    exe_path = os.path.join(latest_version_dir, "GoogleDriveFS.exe")
                    log.debug(f"Using Google Drive executable from wildcard: {exe_path}")
                    return exe_path
                if path.lower().endswith('.exe'):
                    log.debug(f"Using configured Google Drive path: {path}")
                    return path
                candidate = os.path.join(path, "GoogleDriveFS.exe")
                log.debug(f"Using configured Google Drive folder: {candidate}")
                return candidate
        # Default: find latest versioned folder
        base_dir = r"C:\\Program Files\\Google\\Drive File Stream"
        if not os.path.isdir(base_dir):
            log.error(f"Google Drive base directory not found: {base_dir}")
            return None
        version_dirs = []
        for name in os.listdir(base_dir):
            full_path = os.path.join(base_dir, name)
            if os.path.isdir(full_path) and re.match(r"^\d+\.\d+\.\d+\.\d+$", name):
                version_dirs.append((name, full_path))
        if not version_dirs:
            log.error(f"No versioned Google Drive folders found in: {base_dir}")
            return None
        # Sort by version number, descending
        def version_key(v):
            return [int(x) for x in v[0].split('.')]
        version_dirs.sort(key=version_key, reverse=True)
        log.debug(f"Found Google Drive versioned folders: {[v[0] for v in version_dirs]}")
        latest_version_dir = version_dirs[0][1]
        exe_path = os.path.join(latest_version_dir, "GoogleDriveFS.exe")
        log.debug(f"Using Google Drive executable from latest versioned folder: {exe_path}")
        return exe_path
    
    def find_source_path(self, relative_path):
        """Find the full path to a Google Drive item on Windows"""
        clean_path = clean_relative_path(relative_path)
        
        # Check all available drive letters (no preference)
        drive_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        # Find Google Drive mount point with "Shared drives" folder
        google_drive_letter = None
        
        self.log.debug("Looking for Google Drive mount with Shared drives folder")
        for drive_letter in drive_letters:
            test_path = f"{drive_letter}:\\"
            shared_drives_path = os.path.join(test_path, "Shared drives")
            
            if os.path.exists(test_path) and os.path.exists(shared_drives_path):
                self.log.info(f"Found Google Drive mount with Shared drives at {test_path}")
                google_drive_letter = drive_letter
                break
        
        if not google_drive_letter:
            self.log.error("Could not find Google Drive mount point on any drive letter")
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
        """Install Google Drive on Windows, with user notification and install-in-progress flag."""
        from ayon_googledrive.ui.notifications import show_notification
        try:
            if not installer_path or not os.path.exists(installer_path):
                self.log.error(f"Installer not found at {installer_path}")
                show_notification(
                    "Google Drive Installer Not Found",
                    f"Installer not found at: {installer_path}",
                    level="error",
                    unique_id="gdrive_installer_not_found"
                )
                return False
            # Notify user that installation is starting
            show_notification(
                "Google Drive Installation",
                "Google Drive installation is starting. Please follow the installer prompts.",
                level="info",
                unique_id="gdrive_install_start"
            )
            self.set_installing(True)
            self.log.info(f"Running Google Drive installer: {installer_path}")
            try:
                process = subprocess.Popen(
                    [installer_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True
                )
                self.log.info("Installer process started, waiting for completion...")
                stdout, stderr = process.communicate(timeout=300)
                return_code = process.returncode
                if stdout:
                    self.log.info(f"Installer stdout: {stdout.decode('utf-8', errors='ignore')}")
                if stderr:
                    self.log.error(f"Installer stderr: {stderr.decode('utf-8', errors='ignore')}")
                self.log.info(f"Installer return code: {return_code}")
                if return_code == 0:
                    self.log.info("Google Drive installer completed successfully")
                    time.sleep(2)
                    if self.is_googledrive_installed():
                        self.log.info("Installation verification passed")
                        self.set_installing(False)
                        return True
                    else:
                        self.log.error("Installation appeared to succeed but Google Drive is not detected")
                        show_notification(
                            "Google Drive Installation Error",
                            f"Installation completed but Google Drive was not detected. Please try installing manually as administrator.\nInstaller path: {installer_path}",
                            level="error",
                            unique_id="gdrive_install_not_detected"
                        )
                        self.set_installing(False)
                        return False
                else:
                    self.log.error(f"Google Drive installer failed with code {return_code}")
                    show_notification(
                        "Google Drive Installation Failed",
                        f"Installer exited with error code {return_code}. Please try installing manually as administrator.\nInstaller path: {installer_path}",
                        level="error",
                        unique_id="gdrive_install_failed"
                    )
                    self.set_installing(False)
                    return False
            except subprocess.TimeoutExpired:
                self.log.warning("Google Drive installer taking too long - continuing anyway")
                process.kill()
                show_notification(
                    "Google Drive Installation Timeout",
                    f"The installer is taking longer than expected. It may still be running in the background. If installation does not complete, please run the installer manually as administrator.\nInstaller path: {installer_path}",
                    level="warning",
                    unique_id="gdrive_install_timeout"
                )
                self.set_installing(False)
                return True
            except Exception as e:
                self.log.error(f"Error during installation process: {e}")
                show_notification(
                    "Google Drive Installation Error",
                    f"An error occurred during installation: {str(e)}\nPlease try running the installer manually as administrator.\nInstaller path: {installer_path}",
                    level="error",
                    unique_id="gdrive_install_exception"
                )
                self.set_installing(False)
                return False
        except Exception as e:
            self.log.error(f"Error installing Google Drive: {e}")
            from ayon_googledrive.ui.notifications import show_notification
            show_notification(
                "Google Drive Installation Error",
                f"An error occurred: {str(e)}\nPlease try running the installer manually as administrator.\nInstaller path: {installer_path}",
                level="error",
                unique_id="gdrive_install_outer_exception"
            )
            self.set_installing(False)
            return False