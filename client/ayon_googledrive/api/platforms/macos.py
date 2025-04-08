import os
import subprocess
import time
from pathlib import Path

from .base import GDrivePlatformBase
from ..lib import run_process, normalize_path, clean_relative_path

class GDriveMacOSPlatform(GDrivePlatformBase):
    """macOS-specific implementation for Google Drive operations"""
    
    def is_googledrive_installed(self):
        """Check if Google Drive is installed on macOS"""
        # Check multiple possible app names and locations
        app_paths = [
            "/Applications/Google Drive.app",
            "/Applications/Google Drive File Stream.app"
        ]
        return any(os.path.exists(path) for path in app_paths)
    
    def is_googledrive_running(self):
        """Check if Google Drive is currently running on macOS"""
        try:
            # Check for both common process names
            processes_to_check = ["Google Drive", "GoogleDrive", "Google Drive File Stream"]
            for process in processes_to_check:
                result = run_process(["pgrep", "-f", process], check=False)
                if result and result.returncode == 0:
                    self.log.debug(f"Found running process: {process}")
                    return True
            return False
        except Exception as e:
            self.log.error(f"Error checking if Google Drive is running: {e}")
            return False
    
    def is_user_logged_in(self):
        """Check if a user is logged into Google Drive on macOS"""
        # Check multiple possible preference locations
        login_indicators = [
            # Traditional path
            os.path.expanduser("~/Library/Application Support/Google/Drive/user_default"),
            # For newer versions of Google Drive
            os.path.expanduser("~/Library/Application Support/Google/DriveFS/")
        ]
        
        for path in login_indicators:
            if os.path.exists(path):
                # For directories, check if they contain account data
                if os.path.isdir(path):
                    try:
                        # Look for directories containing numbers (account IDs)
                        items = os.listdir(path)
                        for item in items:
                            item_path = os.path.join(path, item)
                            if os.path.isdir(item_path) and any(c.isdigit() for c in item):
                                self.log.debug(f"Found Google Drive account data at: {item_path}")
                                return True
                    except Exception as e:
                        self.log.debug(f"Error checking directory {path}: {e}")
                else:
                    # For files, existence is enough
                    self.log.debug(f"Found Google Drive user preferences at: {path}")
                    return True
                    
        self.log.debug("No Google Drive login data found")
        return False
    
    def start_googledrive(self):
        """Start Google Drive application on macOS"""
        try:
            # Try multiple possible app paths
            app_paths = [
                "/Applications/Google Drive.app",
                "/Applications/Google Drive File Stream.app"
            ]
            
            for app_path in app_paths:
                if os.path.exists(app_path):
                    self.log.info(f"Starting Google Drive from: {app_path}")
                    subprocess.Popen(["open", app_path])
                    return True
                    
            self.log.error("Could not find Google Drive application")
            return False
        except Exception as e:
            self.log.error(f"Error starting Google Drive: {e}")
            return False
    
    def install_googledrive(self, installer_path):
        """Install Google Drive on macOS"""
        try:
            # Mount the DMG
            self.log.info(f"Mounting Google Drive installer DMG: {installer_path}")
            mount_cmd = ["hdiutil", "attach", installer_path]
            mount_result = subprocess.run(mount_cmd, capture_output=True, text=True)
            
            if mount_result.returncode != 0:
                self.log.error(f"Failed to mount DMG: {mount_result.stderr}")
                return False
            
            # Get the mount point
            mount_point = None
            for line in mount_result.stdout.splitlines():
                if "/Volumes/" in line:
                    parts = line.strip().split("\t")
                    if len(parts) > 2:
                        mount_point = parts[-1]
                        break
            
            if not mount_point:
                self.log.error("Could not determine DMG mount point")
                return False
            
            self.log.info(f"DMG mounted at: {mount_point}")
            
            # Look for the app within the mounted DMG
            app_name = None
            for item in os.listdir(mount_point):
                if item.endswith(".app"):
                    app_name = item
                    break
                    
            if not app_name:
                self.log.error("Could not find .app in mounted DMG")
                # Try to unmount before returning
                subprocess.run(["hdiutil", "detach", mount_point, "-force"], capture_output=True)
                return False
                
            source_app_path = os.path.join(mount_point, app_name)
            target_app_path = os.path.join("/Applications", app_name)
            
            # Check if app already exists and needs to be closed
            if os.path.exists(target_app_path):
                self.log.info(f"Closing existing Google Drive application")
                # Try to gracefully quit the app
                try:
                    subprocess.run(
                        ["osascript", "-e", f'tell application "{app_name}" to quit'],
                        capture_output=True, timeout=10
                    )
                    # Give it a moment to close
                    time.sleep(2)
                except Exception:
                    self.log.warning("Could not gracefully close Google Drive")
            
            # Copy app to Applications folder
            self.log.info(f"Copying {source_app_path} to /Applications/")
            copy_cmd = ["cp", "-r", source_app_path, "/Applications/"]
            copy_result = subprocess.run(copy_cmd, capture_output=True, text=True)
            
            if copy_result.returncode != 0:
                self.log.error(f"Failed to copy app to Applications: {copy_result.stderr}")
                # Try to unmount before returning
                subprocess.run(["hdiutil", "detach", mount_point, "-force"], capture_output=True)
                return False
            
            # Unmount the DMG
            self.log.info("Unmounting DMG")
            subprocess.run(["hdiutil", "detach", mount_point, "-force"], capture_output=True)
            
            self.log.info("Google Drive installation completed")
            return True
            
        except Exception as e:
            self.log.error(f"Error installing Google Drive: {e}")
            return False
    
    def find_source_path(self, relative_path):
        """Find the full path to a Google Drive item on macOS"""
        clean_path = clean_relative_path(relative_path).replace("\\", "/")
        
        # Try common macOS paths for Google Drive
        base_paths = [
            "/Volumes/GoogleDrive",
            "/Volumes/Google Drive",
            os.path.expanduser("~/Google Drive"),
            os.path.expanduser("~/Library/CloudStorage/GoogleDrive-[email protected]") # For newer versions
        ]
        
        self.log.debug(f"Looking for path: {clean_path}")
        self.log.debug(f"Checking base paths: {base_paths}")
        
        for base_path in base_paths:
            if not os.path.exists(base_path):
                self.log.debug(f"Base path does not exist: {base_path}")
                continue
                
            # Try direct path
            full_path = os.path.join(base_path, clean_path)
            if os.path.exists(full_path):
                self.log.info(f"Found source path: {full_path}")
                return full_path
                
            # Try with "Shared drives" prefix if needed
            if "Shared drives" not in clean_path:
                shared_path = os.path.join(base_path, "Shared drives", clean_path)
                if os.path.exists(shared_path):
                    self.log.info(f"Found source path with 'Shared drives' prefix: {shared_path}")
                    return shared_path
                    
            # Try without "Shared drives" prefix if it's already in the path
            if "Shared drives" in clean_path:
                no_shared_prefix = clean_path.replace("Shared drives/", "")
                alt_path = os.path.join(base_path, no_shared_prefix)
                if os.path.exists(alt_path):
                    self.log.info(f"Found source path removing 'Shared drives' prefix: {alt_path}")
                    return alt_path
                
            # Try with "Team Drives" as an alternative name
            team_path = os.path.join(base_path, "Team Drives", 
                                    clean_path.replace("Shared drives/", ""))
            if os.path.exists(team_path):
                self.log.info(f"Found source path using 'Team Drives': {team_path}")
                return team_path
                    
        self.log.error(f"Could not locate path '{clean_path}' in Google Drive on macOS")
        return None
    
    def list_shared_drives(self):
        """List available shared drives on macOS"""
        drives = []
        
        # Check common macOS paths for Google Drive
        base_paths = [
            "/Volumes/GoogleDrive/Shared drives",
            "/Volumes/Google Drive/Shared drives",
            os.path.expanduser("~/Google Drive/Shared drives"),
            os.path.expanduser("~/Library/CloudStorage/GoogleDrive-[email protected]/Shared drives")
        ]
        
        for path in base_paths:
            if os.path.exists(path) and os.path.isdir(path):
                try:
                    self.log.debug(f"Checking for shared drives in: {path}")
                    drives = os.listdir(path)
                    if drives:
                        self.log.info(f"Found shared drives at {path}: {drives}")
                        return drives
                except Exception as e:
                    self.log.error(f"Error listing shared drives at {path}: {e}")
                    
        return drives
    
    def find_googledrive_mount(self):
        """Find the Google Drive mount point on macOS"""
        # Check common macOS paths for Google Drive
        base_paths = [
            "/Volumes/GoogleDrive",
            "/Volumes/Google Drive",
            os.path.expanduser("~/Google Drive"),
            os.path.expanduser("~/Library/CloudStorage/GoogleDrive-[email protected]")
        ]
        
        for path in base_paths:
            if os.path.exists(path):
                self.log.info(f"Found Google Drive mount point: {path}")
                return path
                
        self.log.debug("Could not find Google Drive mount point")
        return None
    
    def ensure_mount_point(self, desired_mount):
        """Ensure Google Drive is mounted at the desired location on macOS"""
        # Find Google Drive mount point
        googledrive_path = self.find_googledrive_mount()
        
        if not googledrive_path:
            self.log.error("Google Drive path not found")
            return False
            
        # If desired mount is the same as the actual mount, no need to do anything
        if os.path.normpath(googledrive_path) == os.path.normpath(desired_mount):
            self.log.info(f"Google Drive already mounted at desired location: {desired_mount}")
            return True
            
        # Check if symlink exists and points to the right place
        if os.path.islink(desired_mount) and os.readlink(desired_mount) == googledrive_path:
            self.log.info(f"Symlink already exists: {desired_mount} -> {googledrive_path}")
            return True
            
        # Create symlink if it doesn't exist or points elsewhere
        try:
            # Remove existing symlink if it points elsewhere
            if os.path.exists(desired_mount):
                if os.path.islink(desired_mount):
                    self.log.info(f"Removing existing symlink: {desired_mount}")
                    os.unlink(desired_mount)
                else:
                    self.log.error(f"Path exists but is not a symlink: {desired_mount}")
                    self.alert_path_in_use(desired_mount, None, googledrive_path)
                    return False
                    
            # Create parent directory if needed
            parent_dir = os.path.dirname(desired_mount)
            if parent_dir and not os.path.exists(parent_dir):
                self.log.info(f"Creating parent directory: {parent_dir}")
                os.makedirs(parent_dir, exist_ok=True)
                    
            # Create the symlink
            self.log.info(f"Creating symlink: {desired_mount} -> {googledrive_path}")
            os.symlink(googledrive_path, desired_mount)
            return True
            
        except PermissionError:
            self.log.error(f"Permission denied creating symlink at {desired_mount}")
            self.show_admin_instructions(googledrive_path, desired_mount)
            return False
        except Exception as e:
            self.log.error(f"Failed to create symlink: {e}")
            return False
    
    def create_mapping(self, source_path, target_path, mapping_name=None):
        """Create a symlink mapping on macOS"""
        if not os.path.exists(source_path):
            self.log.error(f"Source path does not exist: {source_path}")
            return False
            
        # Check if target exists but is not properly linked
        if os.path.exists(target_path):
            if os.path.islink(target_path):
                current_target = os.readlink(target_path)
                if current_target == source_path:
                    self.log.info(f"Symlink already exists correctly: {target_path} -> {source_path}")
                    return True
                else:
                    # Symlink exists but points elsewhere
                    self.log.warning(f"Symlink {target_path} exists but points to {current_target} instead of {source_path}")
                    self.alert_path_in_use(target_path, current_target, source_path)
                    return False
            else:
                # Target exists but is not a symlink
                self.log.warning(f"Path {target_path} exists but is not a symlink")
                self.alert_path_in_use(target_path, None, source_path)
                return False
        
        # Create or update symlink
        try:
            # Check parent directory exists
            parent_dir = os.path.dirname(target_path)
            if parent_dir and not os.path.exists(parent_dir):
                self.log.info(f"Creating parent directory: {parent_dir}")
                os.makedirs(parent_dir, exist_ok=True)
            
            # Create symlink
            self.log.info(f"Creating symlink: {target_path} -> {source_path}")
            os.symlink(source_path, target_path)
            return True
            
        except PermissionError:
            self.log.error(f"Permission denied creating symlink at {target_path}")
            self.show_admin_instructions(source_path, target_path)
            return False
        except Exception as e:
            self.log.error(f"Error creating symlink: {e}")
            return False
    
    def alert_path_in_use(self, path, current_target, desired_target):
        """Alert the user about path conflicts"""
        if current_target:
            message = (
                f"Path {path} is already linked to a different location:\n"
                f"Current target: {current_target}\n"
                f"Desired target: {desired_target}\n\n"
                f"Please modify your settings or remove the existing link."
            )
        else:
            message = (
                f"Path {path} already exists but is not a symbolic link.\n"
                f"Cannot create link to: {desired_target}\n\n"
                f"Please modify your settings or remove the existing file/directory."
            )
        
        self.log.warning(f"Path conflict: {message}")
        
        # Try to show a macOS alert
        try:
            # Sanitize the message for osascript
            safe_message = message.replace('"', '\\"')
            script = f'display dialog "{safe_message}" with title "Google Drive Path Conflict" buttons {{"OK"}} default button "OK" with icon caution'
            subprocess.run(["osascript", "-e", script], capture_output=True)
        except Exception as e:
            self.log.debug(f"Could not show GUI alert: {e}")
    
    def show_admin_instructions(self, source_path, target_path):
        """Show instructions for operations requiring admin privileges"""
        command = f"sudo ln -sf '{source_path}' '{target_path}'"
        message = (
            f"Creating the symlink requires administrator privileges.\n\n"
            f"Please run this command in Terminal:\n{command}"
        )
        
        self.log.info(f"Admin privileges required: {command}")
        
        # Try to show a macOS alert
        try:
            # Sanitize the message for osascript
            safe_message = message.replace('"', '\\"')
            script = f'display dialog "{safe_message}" with title "Google Drive Setup" buttons {{"OK"}} default button "OK"'
            subprocess.run(["osascript", "-e", script], capture_output=True)
        except Exception as e:
            self.log.debug(f"Could not show GUI alert: {e}")
            
    def check_mapping_exists(self, target_path):
        """Check if a mapping exists at the target path"""
        return os.path.exists(target_path)
    
    def check_mapping_valid(self, source_path, target_path):
        """Check if mapping from source to target is valid"""
        if not os.path.exists(target_path):
            return False
            
        if not os.path.islink(target_path):
            return False
            
        try:
            return os.path.samefile(os.readlink(target_path), source_path)
        except Exception:
            return False
            
    def remove_all_mappings(self):
        """Remove all symlink mappings created by AYON"""
        # For macOS, we don't have a clean way to identify which links were created
        # by AYON, so we'll use settings to guide us
        try:
            settings = self.addon.settings if hasattr(self, 'addon') else None
            if not settings:
                from ..lib import get_settings
                settings = get_settings()
                
            mappings = settings.get("mappings", [])
            
            for mapping in mappings:
                target = mapping.get("macos_target", "")
                if target and os.path.exists(target) and os.path.islink(target):
                    self.log.info(f"Removing symlink: {target}")
                    try:
                        os.unlink(target)
                    except Exception as e:
                        self.log.error(f"Failed to remove symlink {target}: {e}")
                        
            return True
        except Exception as e:
            self.log.error(f"Error removing mappings: {e}")
            return False