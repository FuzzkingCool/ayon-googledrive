import os
import sys
import platform
import subprocess
import time
import logging
from pathlib import Path

# If windows import ctypes & winreg
if platform.system() == "Windows":
    import ctypes
    import winreg
 
# Import AYON core libraries
from ayon_core.lib import Logger

# Add import for the vendor module
from ..vendor import GDriveInstaller

class GDriveManager:
    """Handles Google Drive validation and path consistency"""
    
    def __init__(self):
        self.log = Logger.get_logger(self.__class__.__name__)
        self.os_type = platform.system()
        
    def is_googledrive_installed(self):
        """Check if Google Drive for Desktop is installed"""
        if self.os_type == "Windows":
            # Check common installation paths
            program_files_paths = [
                os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Drive File Stream"),
                os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Drive File Stream")
            ]
            return any(os.path.exists(path) for path in program_files_paths)
        
        elif self.os_type == "Darwin":  # macOS
            return os.path.exists("/Applications/Google Drive.app")

        elif self.os_type == "Linux":
            # Check if Google Drive is installed via snap or flatpak
            return os.path.exists("/snap/google-drive/current") or os.path.exists("/var/lib/flatpak/app/com.google.drive/current")
        
        return False
    
    def is_googledrive_running(self):
        """Check if Google Drive for Desktop is currently running"""
        if self.os_type == "Windows":
            try:
                output = subprocess.check_output(
                    ["tasklist", "/FI", "IMAGENAME eq GoogleDriveFS.exe"], 
                    shell=True, 
                    universal_newlines=True
                )
                return "GoogleDriveFS.exe" in output
            except subprocess.SubprocessError:
                self.log.error("Failed to check if Google Drive is running")
                return False
        
        elif self.os_type == "Darwin":  # macOS
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "Google Drive"], 
                    capture_output=True, 
                    text=True
                )
                return result.returncode == 0
            except subprocess.SubprocessError:
                self.log.error("Failed to check if Google Drive is running")
                return False
               
        elif self.os_type == "Linux":
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "google-drive"], 
                    capture_output=True, 
                    text=True
                )
                return result.returncode == 0
            except subprocess.SubprocessError:
                self.log.error("Failed to check if Google Drive is running")
                return False
                
        return False

    def is_user_logged_in(self):
        """Check if a user is logged into Google Drive"""
        if self.os_type == "Windows":
            # On Windows, check if there's a user profile directory
            appdata_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), 
                                       "Google", "Drive File Stream", "Accounts")
            if os.path.exists(appdata_path):
                try:
                    # If there are any directories, a user is logged in
                    return len(os.listdir(appdata_path)) > 0
                except Exception as e:
                    self.log.error(f"Error checking Google Drive login status: {e}")
            return False
            
        elif self.os_type == "Darwin":  # macOS
            # Check for user preferences file
            prefs_path = os.path.expanduser(
                "~/Library/Application Support/Google/Drive/user_default")
            return os.path.exists(prefs_path)
            
        return False
    
    def install_googledrive(self):
        """Install Google Drive for Desktop silently"""
        self.log.info("Attempting to install Google Drive for Desktop")
        
        # First check if already installed
        if self.is_googledrive_installed():
            self.log.info("Google Drive already installed")
            return True
        
        installer = GDriveInstaller()
        installer_path = installer.get_installer_path()
        
        if not installer_path:
            self.log.error("Failed to download Google Drive installer")
            return False
        
        try:
            installation_started = False
            
            if self.os_type == "Windows":
                # Silent install flags for Windows
                cmd = [installer_path, "--silent"]
                
                # Run installer
                self.log.info(f"Running Google Drive installer: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    self.log.error(f"Failed to install Google Drive: {result.stderr}")
                    return False
                    
                self.log.info("Google Drive installation started")
                installation_started = True
                
            elif self.os_type == "Darwin":  # macOS
                # Mount the DMG
                mount_cmd = ["hdiutil", "attach", installer_path]
                mount_result = subprocess.run(mount_cmd, capture_output=True, text=True)
                
                if mount_result.returncode != 0:
                    self.log.error(f"Failed to mount Google Drive DMG: {mount_result.stderr}")
                    return False
                
                # Get the mount point
                mount_point = None
                for line in mount_result.stdout.splitlines():
                    if "/Volumes/Google Drive" in line:
                        mount_point = "/Volumes/Google Drive"
                        break
                
                if not mount_point:
                    self.log.error("Failed to find Google Drive mount point")
                    return False
                
                # Copy app to Applications folder
                copy_cmd = ["cp", "-r", f"{mount_point}/Google Drive.app", "/Applications/"]
                copy_result = subprocess.run(copy_cmd, capture_output=True, text=True)
                
                if copy_result.returncode != 0:
                    self.log.error(f"Failed to copy Google Drive app: {copy_result.stderr}")
                    return False
                
                # Unmount the DMG
                subprocess.run(["hdiutil", "detach", mount_point], capture_output=True)
                
                self.log.info("Google Drive installation completed")
                installation_started = True
                
            elif self.os_type == "Linux":
                self.log.error("Automated Google Drive installation not supported on Linux")
                self._show_linux_install_instructions()
                return False
            
            # Clean up the installer
            installer.cleanup()
            
            # Verify installation
            if installation_started:
                return self._verify_installation()
                
            return False
            
        except Exception as e:
            self.log.error(f"Error installing Google Drive: {e}")
            installer.cleanup()
            return False

    def _verify_installation(self):
        """Verify Google Drive was successfully installed"""
        self.log.info("Verifying Google Drive installation...")
        
        # Give the installer some time to finish
        max_attempts = 10
        check_interval = 2  # seconds
        
        for attempt in range(max_attempts):
            if self.is_googledrive_installed():
                self.log.info("Google Drive installation verified successfully")
                return True
                
            self.log.debug(f"Installation verification attempt {attempt+1}/{max_attempts}")
            time.sleep(check_interval)
        
        self.log.error("Failed to verify Google Drive installation")
        return False

    def _show_linux_install_instructions(self):
        """Show instructions for installing Google Drive on Linux"""
        instructions = (
            "To install Google Drive on Linux, please follow these steps:\n"
            "1. Visit https://www.google.com/drive/download/\n"
            "2. Download the appropriate Linux installer\n"
            "3. Follow the installation instructions for your distribution"
        )
        self.log.info(instructions)
        
        # If possible, show a graphical notification
        try:
            import subprocess
            subprocess.Popen(["zenity", "--info", "--text", instructions], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
        except Exception:
            pass
    
    def ensure_consistent_paths(self):
        """Ensure consistent path access across platforms"""
        try:
            # Check if user is logged in first
            if not self.is_user_logged_in():
                self.log.warning("No user is logged into Google Drive")
                return False
                
            # Get shared drive settings
            shared_drives = self.get_shared_drives()
            if not shared_drives:
                self.log.warning("No Google Shared Drives found")
                return False
                
            self.log.info(f"Found shared drives: {', '.join(shared_drives)}")
            
            # Get all configured mappings
            settings = self._get_settings()
            mappings = settings.get("mappings", [])
            
            if not mappings:
                self.log.warning("No drive mappings configured")
                return False
            
            # Process each mapping
            success = True
            for mapping in mappings:
                if not self._process_mapping(mapping):
                    self.log.error(f"Failed to process mapping for {mapping.get('name', 'unnamed')}")
                    success = False
            
            return success
            
        except Exception as e:
            self.log.error(f"Error ensuring consistent paths: {e}")
            return False

    def create_dos_device_mapping(self, drive_letter, target_path):
        """Create a DOS device mapping in the registry (requires admin privileges)."""
        
        try:
            # Check if running as admin
            if not ctypes.windll.shell32.IsUserAnAdmin():
                self.log.warning("Admin privileges required to set drive mapping")
                self._show_admin_instructions_windows(drive_letter, target_path)
                return False
     
            # Format the drive letter and target path
            if drive_letter.endswith(':'):
                reg_name = drive_letter
            else:
                reg_name = f"{drive_letter}:"
                
            if not target_path.startswith("\\??\\"):
                reg_value = f"\\??\\{target_path}"
            else:
                reg_value = target_path
            
            # Open the registry key
            key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\DOS Devices"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, 
                                winreg.KEY_WRITE)
            
            # Set the registry value
            winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, reg_value)
            winreg.CloseKey(key)
            
            self.log.info(f"Successfully mapped {reg_name} to {reg_value}")
            return True
            
        except Exception as e:
            self.log.error(f"Error creating registry mapping: {str(e)}")
            return False

    def _show_admin_instructions_windows(self, drive_letter, target_path):
        """Show instructions for running with admin privileges on Windows"""
        # Create a .reg file content
        if not drive_letter.endswith(':'):
            drive_letter = f"{drive_letter}:"
            
        if not target_path.startswith("\\??\\"):
            target_path = f"\\??\\{target_path}"
            
        reg_content = (
            "Windows Registry Editor Version 5.00\n\n"
            "[HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\DOS Devices]\n"
            f"\"{drive_letter}\"=\"{target_path}\"\n"
        )
        
        # Save to a temporary .reg file
        try:
            temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp"))
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
                
            reg_file = os.path.join(temp_dir, "ayon_googledrive_mapping.reg")
            with open(reg_file, "w") as f:
                f.write(reg_content)
                
            self.log.info(f"Created registry file: {reg_file}")
            
            # Show instructions
            message = (
                f"To map {drive_letter} to Google Drive, you need administrator privileges.\n\n"
                f"Please right-click {reg_file} and select 'Run as administrator'.\n\n"
                "After that, restart your computer for the changes to take effect."
            )
            
            self.log.info(message.replace("\n", " "))
            
            # Try to show a message box if possible
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, message, "AYON Google Drive Setup", 0)
            except Exception:
                # Already logged to console
                pass
                
        except Exception as e:
            self.log.error(f"Failed to create registry file: {e}")

    def _ensure_windows_paths(self):
        """Ensure proper paths on Windows"""
        # Find actual Google Drive path
        googledrive_path = None
        
        for drive_letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            shared_drive_path = f"{drive_letter}:\\Shared drives"
            if os.path.exists(shared_drive_path):
                googledrive_path = f"{drive_letter}:"
                break
        
        if not googledrive_path:
            self.log.error("Google Drive path not found on any drive")
            return False
            
        # Get desired drive letter from settings
        settings = self._get_settings()
        desired_drive = settings["googledrive_mount"]
        if not desired_drive:
            desired_drive = "G:"
        elif not desired_drive.endswith(':'):
            desired_drive += ":"
        
        # If drive already at desired letter, all good
        if googledrive_path == desired_drive:
            self.log.info(f"Google Drive already mounted at {desired_drive}")
            return True
            
        # Try to create a persistent mapping
        try:
            # First try more reliable approaches that require admin privileges
            if ctypes.windll.shell32.IsUserAnAdmin():
                # Use registry for persistent mapping (survives reboots)
                target_path = googledrive_path.replace(":", "")
                return self.create_dos_device_mapping(desired_drive, target_path)
            else:
                # If not admin, try temporary solution with subst
                if self.map_network_drive_persistent(desired_drive, googledrive_path):
                    return True
                    
                # Show admin instructions as a fallback
                self._show_admin_instructions_windows(desired_drive, googledrive_path)
                return False
                    
        except Exception as e:
            self.log.error(f"Failed to map drive: {e}")
            return False

    def map_network_drive_persistent(self, drive_letter, target_path):
        """Map a network drive with a more persistent approach"""
        try:
            if drive_letter.endswith(':'):
                drive_letter = drive_letter[0]  # Just get the letter
                
            # Try to create a permanent drive mapping using net use
            cmd = ["net", "use", f"{drive_letter}:", target_path, "/P:Yes"]
            
            self.log.info(f"Creating persistent drive mapping: {drive_letter}: -> {target_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                # Fall back to subst if net use fails
                self.log.warning(f"Net use failed: {result.stderr}")
                self.log.info("Falling back to temporary subst mapping")
                return self.map_network_drive(drive_letter + ":", target_path)
                
            self.log.info(f"Successfully created persistent mapping {drive_letter}: to {target_path}")
            return True
                
        except Exception as e:
            self.log.error(f"Error creating persistent mapping: {e}")
            return False

    def map_network_drive(self, drive_letter, target_path):
        """Map a network drive using subst (temporary)"""
        try:
            if drive_letter.endswith(':'):
                drive_letter = drive_letter
            else:
                drive_letter = f"{drive_letter}:"
                
            if target_path.endswith('\\'):
                target_path = target_path[:-1]
                
            # Check if drive letter is already in use
            if os.path.exists(drive_letter):
                # Try to remove existing mapping first
                subprocess.run(["subst", drive_letter, "/D"], capture_output=True)
            
            # Create new mapping
            result = subprocess.run(
                ["subst", drive_letter, target_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.log.error(f"Failed to map drive: {result.stderr}")
                return False
                
            self.log.info(f"Successfully mapped {drive_letter} to {target_path} (temporary)")
            self.log.warning("This mapping will not persist after reboot")
            return True
            
        except Exception as e:
            self.log.error(f"Error mapping drive: {e}")
            return False
      
    def _ensure_macos_paths(self):
        """Ensure proper paths on macOS"""
        # Find Google Drive mount point
        googledrive_paths = [
            "/Volumes/GoogleDrive",
            os.path.expanduser("~/Google Drive")
        ]
        
        googledrive_path = None
        for path in googledrive_paths:
            if os.path.exists(path):
                googledrive_path = path
                break
                
        if not googledrive_path:
            self.log.error("Google Drive path not found")
            return False
            
        # Get desired symlink path from settings
        settings = self._get_settings()
        desired_path = settings["googledrive_mount"]
        if not desired_path:
            desired_path = "/AyonStorage"
        
        # Check if symlink exists and points to the right place
        if os.path.islink(desired_path) and os.readlink(desired_path) == googledrive_path:
            self.log.info(f"Symlink already exists: {desired_path} -> {googledrive_path}")
            return True
            
        # Create symlink if it doesn't exist or points elsewhere
        try:
            # Remove existing symlink if it points elsewhere
            if os.path.exists(desired_path):
                if os.path.islink(desired_path):
                    os.unlink(desired_path)
                else:
                    self.log.error(f"{desired_path} exists and is not a symlink")
                    return False
                    
            # Create the symlink
            os.symlink(googledrive_path, desired_path)
            self.log.info(f"Created symlink: {desired_path} -> {googledrive_path}")
            return True
            
        except Exception as e:
            self.log.error(f"Failed to create symlink: {e}")
            return False
    
    def _ensure_linux_paths(self):
        """Ensure proper paths on Linux"""
        # Find Google Drive mount point on Linux
        googledrive_paths = [
            "/mnt/google_drive",
            "/mnt/googledrive",
            os.path.expanduser("~/google-drive"),
            os.path.expanduser("~/.google-drive-desktop")
        ]
        
        googledrive_path = None
        for path in googledrive_paths:
            if os.path.exists(path):
                googledrive_path = path
                break
                
        if not googledrive_path:
            self.log.error("Google Drive path not found on Linux")
            return False
            
        # Get desired symlink path from settings
        settings = self._get_settings()
        desired_path = settings["googledrive_mount"]
        if not desired_path:
            desired_path = "/mnt/ayon_storage"
        
        # Check if symlink exists and points to the right place
        if os.path.islink(desired_path) and os.readlink(desired_path) == googledrive_path:
            self.log.info(f"Symlink already exists: {desired_path} -> {googledrive_path}")
            return True
            
        # Create symlink if it doesn't exist or points elsewhere
        try:
            # Need to check for root permissions on Linux
            if not os.access("/mnt", os.W_OK) and desired_path.startswith("/mnt"):
                self.log.error("Root permissions required to create symlink in /mnt")
                self._show_admin_instructions_linux(googledrive_path, desired_path)
                return False
                
            # Remove existing symlink if it points elsewhere
            if os.path.exists(desired_path):
                if os.path.islink(desired_path):
                    os.unlink(desired_path)
                else:
                    self.log.error(f"{desired_path} exists and is not a symlink")
                    return False
                    
            # Create the symlink
            os.symlink(googledrive_path, desired_path)
            self.log.info(f"Created symlink: {desired_path} -> {googledrive_path}")
            return True
            
        except Exception as e:
            self.log.error(f"Failed to create symlink: {e}")
            return False

    def _show_admin_instructions_linux(self, source_path, target_path):
        """Show instructions for creating symlinks with sudo on Linux"""
        command = f"sudo ln -sf {source_path} {target_path}"
        self.log.info(f"To create the symlink, run this command in terminal: {command}")
        
        # If we have GUI capabilities, show a more user-friendly message
        try:
            import subprocess
            message = (f"Google Drive integration requires creating a symlink at {target_path}.\n\n"
                       f"Please run this command in terminal:\n{command}")
            
            # Try to show a graphical notification
            subprocess.Popen(["zenity", "--info", "--text", message], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
        except Exception:
            # Failed to show GUI notification - already logged to console
            pass

    def get_shared_drives(self):
        """Get a list of available Google Shared Drives"""
        shared_drives = []
        
        if self.os_type == "Windows":
            # Look for mounted shared drives
            for drive_letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
                shared_drive_path = f"{drive_letter}:\\Shared drives"
                if os.path.exists(shared_drive_path):
                    try:
                        shared_drives.append(os.path.basename(shared_drive_path))
                    except Exception as e:
                        self.log.error(f"Error accessing shared drive: {e}")
                        
        elif self.os_type == "Darwin":  # macOS
            # Check common macOS paths for Google Drive
            base_paths = [
                "/Volumes/GoogleDrive/Shared drives",
                os.path.expanduser("~/Google Drive/Shared drives")
            ]
            
            for path in base_paths:
                if os.path.exists(path):
                    try:
                        shared_drives = os.listdir(path)
                        break
                    except Exception as e:
                        self.log.error(f"Error listing shared drives: {e}")
        
        elif self.os_type == "Linux":
            # Check common Linux paths for Google Drive
            base_paths = [
                "/mnt/google_drive/Shared drives",
                os.path.expanduser("~/google-drive/Shared drives")
            ]
            
            for path in base_paths:
                if os.path.exists(path):
                    try:
                        shared_drives = os.listdir(path)
                        break
                    except Exception as e:
                        self.log.error(f"Error listing shared drives: {e}")
                        
        return shared_drives

    def _get_settings(self):
        """Get addon settings with platform-specific values"""
        try:
            self.log.debug("Loading settings for Google Drive addon: _get_settings")
            from ayon_core.settings import get_project_settings
            
            settings = get_project_settings()
            addon_settings = settings.get("googledrive", {})
            
            # Get platform-specific values
            platform_key = {
                "Windows": "windows",
                "Darwin": "macos",
                "Linux": "linux"
            }.get(self.os_type, "windows")
            
            # Extract settings
            result = {
                "googledrive_path": addon_settings.get("googledrive_path", {}).get(platform_key),
                "googledrive_mount": addon_settings.get("googledrive_mount", {}).get(platform_key),
                "mappings": addon_settings.get("mappings", []),
                "install_googledrive": addon_settings.get("install_googledrive", True),
                "mount_googledrive": addon_settings.get("mount_googledrive", True)
            }
            
            return result
        except Exception as e:
            self.log.error(f"Error loading settings: {e}")
            # Return defaults
            return {
                "googledrive_path": None,
                "googledrive_mount": None,
                "mappings": [],
                "install_googledrive": True,
                "mount_googledrive": True
            }

    def _get_platform_target(self, mapping):
        """Get the target path for the current platform from a mapping"""
        if self.os_type == "Windows":
            return mapping.get("windows_target", "")
        elif self.os_type == "Darwin":
            return mapping.get("macos_target", "")
        elif self.os_type == "Linux":
            return mapping.get("linux_target", "")
        return ""

    def _process_mapping(self, mapping):
        """Process a single drive mapping"""
        try:
            name = mapping.get("drive_name", "unnamed")
            source_path = mapping.get("source_path", "")
            target = self._get_platform_target(mapping)
            
            if not source_path or not target:
                self.log.error(f"Invalid mapping configuration for {name}")
                return False
                
            self.log.info(f"Processing mapping '{name}': {source_path} -> {target}")
            
            # Find the full source path
            full_source_path = self._find_source_path(source_path)
            if not full_source_path:
                self.log.error(f"Source path not found: {source_path}")
                return False
                
            # Based on platform, create the appropriate mapping
            if self.os_type == "Windows":
                return self._create_windows_mapping(full_source_path, target)
            elif self.os_type == "Darwin":
                return self._create_macos_mapping(full_source_path, target)
            elif self.os_type == "Linux":
                return self._create_linux_mapping(full_source_path, target)
                
            return False
            
        except Exception as e:
            self.log.error(f"Error processing mapping: {e}")
            return False

    def _find_source_path(self, relative_path):
        """Find the full path to the source based on relative path in Google Drive"""
        # First, find the Google Drive mount point
        if self.os_type == "Windows":
            for drive_letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
                base_path = f"{drive_letter}:\\"
                if os.path.exists(f"{base_path}Shared drives"):
                    # Make sure path uses backslashes on Windows
                    clean_path = relative_path.replace("/", "\\")
                    if not clean_path.startswith("\\"):
                        clean_path = "\\" + clean_path
                    
                    full_path = base_path + clean_path.lstrip("\\")
                    
                    if os.path.exists(full_path):
                        return full_path
                        
                    self.log.warning(f"Path exists but target doesn't: {full_path}")
                    return base_path + clean_path.lstrip("\\")
        
        elif self.os_type == "Darwin":
            base_paths = [
                "/Volumes/GoogleDrive",
                os.path.expanduser("~/Google Drive")
            ]
            
            for base_path in base_paths:
                if os.path.exists(base_path):
                    # Convert Windows path to Unix style
                    clean_path = relative_path.replace("\\", "/")
                    if not clean_path.startswith("/"):
                        clean_path = "/" + clean_path
                    
                    full_path = base_path + clean_path
                    
                    if os.path.exists(full_path):
                        return full_path
                        
                    self.log.warning(f"Base path exists but target doesn't: {full_path}")
                    return base_path + clean_path
                    
        elif self.os_type == "Linux":
            base_paths = [
                "/mnt/google_drive",
                os.path.expanduser("~/google-drive")
            ]
            
            for base_path in base_paths:
                if os.path.exists(base_path):
                    # Convert Windows path to Unix style
                    clean_path = relative_path.replace("\\", "/")
                    if not clean_path.startswith("/"):
                        clean_path = "/" + clean_path
                        
                    full_path = base_path + clean_path
                    
                    if os.path.exists(full_path):
                        return full_path
                        
                    self.log.warning(f"Base path exists but target doesn't: {full_path}")
                    return base_path + clean_path
        
        self.log.error(f"Could not find Google Drive mount point for {relative_path}")
        return None

    def _create_windows_mapping(self, source_path, target):
        """Create Windows mapping for a drive"""
        # Extract drive letter from target
        if not target.endswith(":\\"):
            if target.endswith(":"):
                target = target + "\\"
            elif not target.endswith("\\"):
                target = target + ":\\"
        
        drive_letter = target[0]
        
        self.log.info(f"Creating Windows mapping: {drive_letter}: -> {source_path}")
        
        # Check if target drive letter already exists
        if os.path.exists(target):
            # Check if it's already mapped correctly
            try:
                if os.path.samefile(target, source_path):
                    self.log.info(f"Drive {drive_letter}: is already mapped correctly")
                    return True
                else:
                    # Drive exists but mapped to something different
                    current_mapping = os.path.abspath(target)
                    self.log.warning(f"Drive {drive_letter}: is already in use, mapped to {current_mapping}")
                    self._alert_drive_in_use(drive_letter, current_mapping, source_path)
                    return False
            except Exception as e:
                self.log.error(f"Error comparing drive paths: {e}")
                return False
        
        # If we reach here, the drive doesn't exist yet
        # Try to create mapping based on admin privileges
        if ctypes.windll.shell32.IsUserAnAdmin():
            # Use registry for persistent mapping
            return self.create_dos_device_mapping(drive_letter + ":", source_path)
        else:
            # Try net use first for more persistent mapping
            if self.map_network_drive_persistent(drive_letter, source_path):
                return True
                
            # Fall back to subst
            if self.map_network_drive(drive_letter + ":", source_path):
                return True
                
            # Show admin instructions as last resort
            self._show_admin_instructions_windows(drive_letter + ":", source_path)
            return False

    def _alert_drive_in_use(self, drive_letter, current_mapping, desired_mapping):
        """Alert the user that a drive letter is already in use with a different mapping"""
        message = (
            f"Drive {drive_letter}: is already in use!\n\n"
            f"Current mapping: {current_mapping}\n"
            f"Desired mapping: {desired_mapping}\n\n"
            f"Please modify your AYON settings to use a different drive letter or free up this drive letter."
        )
        
        self.log.warning(f"Drive conflict: {message}")
        
        # Try to show a GUI alert if possible
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "AYON Google Drive - Drive Conflict", 0x10)  # 0x10 = MB_ICONERROR
        except Exception as e:
            self.log.error(f"Failed to show GUI alert: {e}")
            
            # Try to show notification through the addon API
            self._show_notification("Drive Letter Conflict", 
                                  f"Drive {drive_letter}: is already mapped to a different location")

    def _create_macos_mapping(self, source_path, target):
        """Create macOS symlink mapping"""
        if not os.path.exists(source_path):
            self.log.error(f"Source path does not exist: {source_path}")
            return False
            
        # Check if target exists but is not properly linked
        if os.path.exists(target):
            if os.path.islink(target):
                current_target = os.readlink(target)
                if current_target == source_path:
                    self.log.info(f"Symlink already exists correctly: {target} -> {source_path}")
                    return True
                else:
                    # Symlink exists but points elsewhere
                    self.log.warning(f"Path {target} is linked to {current_target} instead of {source_path}")
                    self._alert_path_in_use(target, current_target, source_path)
                    return False
            else:
                # Target exists but is not a symlink
                self.log.warning(f"Path {target} exists but is not a symlink")
                self._alert_path_in_use(target, None, source_path)
                return False
        
        # Create or update symlink
        try:
            # Check parent directory exists
            parent_dir = os.path.dirname(target)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir)
            
            # Create symlink
            os.symlink(source_path, target)
            self.log.info(f"Created symlink: {target} -> {source_path}")
            return True
            
        except PermissionError:
            self.log.error(f"Permission denied creating symlink at {target}")
            return False
        except Exception as e:
            self.log.error(f"Error creating symlink: {e}")
            return False

    def _alert_path_in_use(self, path, current_target, desired_target):
        """Alert the user about path conflicts"""
        if current_target:
            message = (
                f"Path {path} is already linked to a different location:\n"
                f"Current target: {current_target}\n"
                f"Desired target: {desired_target}\n\n"
                f"Please modify your AYON settings or remove the existing link."
            )
        else:
            message = (
                f"Path {path} already exists but is not a symbolic link.\n"
                f"Cannot create link to: {desired_target}\n\n"
                f"Please modify your AYON settings or remove the existing file/directory."
            )
        
        self.log.warning(f"Path conflict: {message}")
        
        # Try to show a platform-appropriate alert
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.run(["osascript", "-e", 
                              f'display dialog "{message}" with title "AYON Google Drive - Path Conflict" '
                              f'buttons {{"OK"}} with icon caution'])
            elif platform.system() == "Linux":
                subprocess.run(["zenity", "--error", "--title", "AYON Google Drive - Path Conflict", 
                              "--text", message])
            else:  # Windows fallback
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, message, "AYON Google Drive - Path Conflict", 0x10)
        except Exception as e:
            self.log.error(f"Failed to show GUI alert: {e}")
            
            # Try to use notification system as fallback
            self._show_notification("Path Conflict", 
                                  f"Path {path} is already in use with a different target")

    def _create_linux_mapping(self, source_path, target):
        """Create Linux symlink mapping"""
        if not os.path.exists(source_path):
            self.log.error(f"Source path does not exist: {source_path}")
            return False
            
        # Check if target exists but is not properly linked
        if os.path.exists(target):
            if os.path.islink(target):
                current_target = os.readlink(target)
                if current_target == source_path:
                    self.log.info(f"Symlink already exists correctly: {target} -> {source_path}")
                    return True
                else:
                    # Symlink exists but points elsewhere
                    self.log.warning(f"Path {target} is linked to {current_target} instead of {source_path}")
                    self._alert_path_in_use(target, current_target, source_path)
                    return False
            else:
                # Target exists but is not a symlink
                self.log.warning(f"Path {target} exists but is not a symlink")
                self._alert_path_in_use(target, None, source_path)
                return False
        
        # Create or update symlink
        try:
            # Check parent directory exists
            parent_dir = os.path.dirname(target)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except PermissionError:
                    self.log.error(f"Permission denied creating directory: {parent_dir}")
                    self._show_admin_instructions_linux(source_path, target)
                    return False
        
            # Create symlink
            try:
                os.symlink(source_path, target)
                self.log.info(f"Created symlink: {target} -> {source_path}")
                return True
            except PermissionError:
                self.log.error(f"Permission denied creating symlink at {target}")
                self._show_admin_instructions_linux(source_path, target)
                return False
            
        except Exception as e:
            self.log.error(f"Error creating symlink: {e}")
            return False

    def _show_notification(self, title, message):
        """Show a notification through available means"""
        self.log.info(f"{title}: {message}")



