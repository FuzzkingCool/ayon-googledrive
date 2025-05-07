import os
import subprocess
import time
import tempfile

from ayon_googledrive.api.platforms.base import GDrivePlatformBase
from ayon_googledrive.api.lib import clean_relative_path, run_process

class GDriveMacOSPlatform(GDrivePlatformBase):
    """Platform-specific handler for macOS."""

    def __init__(self, settings=None):
        """Initialize the macOS platform handler.
        
        Args:
            settings (dict, optional): Settings dictionary from GDriveManager.
        """
        super(GDriveMacOSPlatform, self).__init__()  # Call base class init
        self.settings = settings  # Add settings attribute
        self._googledrive_path = None
    
    def is_googledrive_installed(self):
        """Check if Google Drive for Desktop is installed on macOS"""
        # Build list of possible paths
        possible_paths = []
        
        # First check the configured path from settings
        if hasattr(self, 'settings') and self.settings and 'googledrive_path' in self.settings:
            macos_path = self.settings['googledrive_path'].get('macos')
            if macos_path:
                possible_paths.append(macos_path)
        
        # Then add common modern paths first
        possible_paths.extend([
            # Modern paths (macOS 15+)
            "/Applications/Google Drive for desktop.app",
            "/Applications/Google Drive for Desktop.app",
        ])
        
        # Then add legacy paths
        possible_paths.extend([
            "/Applications/Google Drive.app",
            "/Applications/Google Drive File Stream.app", 
            "/Applications/GoogleDrive.app",
            "/Applications/Google/Drive.app",
            "/Applications/Google/Google Drive.app",
            "~/Applications/Google Drive.app",
            "~/Applications/GoogleDrive.app"
        ])
        
        self.log.debug(f"Looking for Google Drive in possible paths: {possible_paths}")
        
        # Check if any of the paths exist
        for path in possible_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                self.log.info(f"Found Google Drive installation at: {expanded_path}")
                # Cache the found path for future use
                self._googledrive_path = expanded_path
                return True
                
        self.log.warning("Could not find Google Drive installation in any expected location")
        return False
    
    def is_googledrive_running(self):
        """Check if Google Drive for Desktop is running on macOS"""
        try:
            # Use 'ps' to check for Google Drive processes
            process_names = [
                "Google Drive", 
                "GoogleDrive",
                "Google Drive File Stream",
                "GoogleDriveFS"
            ]
 
            # Setup command
            cmd = ["ps", "-A", "-o", "comm"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            

            for line in result.stdout.splitlines():
                for name in process_names:
                    if name in line:
                        self.log.debug(f"Found running Google Drive process: {line.strip()}")
                        return True
                        
            # If we get here, no matching process was found
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
        """Start Google Drive on macOS."""
        
        # First check if it's installed
        if not self.is_googledrive_installed():
            self.log.info("Attempting to install Google Drive automatically")
            try:
                # Download and install Google Drive first
                from ayon_googledrive.gdrive_installer import GDriveInstaller  
                installer = GDriveInstaller(self.settings)  # Pass settings here
                installer_path = installer.get_installer_path()
                if not installer_path:
                    self.log.error("Failed to download Google Drive installer")
                    return False
                    
                # Call the installer's method - don't use our own implementation
                success = installer._install_on_macos(installer_path)
                if not success:
                    self.log.error("Failed to install Google Drive")
                    return False
                    
                # Clean up temp files
                installer.cleanup()
                
            except Exception as e:
                self.log.error(f"Error starting Google Drive: {e}")
                return False
        
        # If we have Google Drive, try to start it
        try:
            if hasattr(self, '_googledrive_path') and self._googledrive_path:
                # Use the cached path if we have it
                app_path = self._googledrive_path
            else:
                # Otherwise check common locations
                possible_paths = [
                    "/Applications/Google Drive for desktop.app",
                    "/Applications/Google Drive for Desktop.app",
                    "/Applications/Google Drive.app",
                    "/Applications/Google Drive File Stream.app"
                ]
                
                app_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        app_path = path
                        break
                
                if not app_path:
                    self.log.error("Could not find Google Drive application")
                    return False
            
            # Start the application
            self.log.debug(f"Starting Google Drive from: {app_path}")
            subprocess.run(["open", app_path])
            
            # Give it time to start
            time.sleep(2)
            return True
            
        except Exception as e:
            self.log.error(f"Failed to start Google Drive: {e}")
            return False
    
    def install_googledrive(self, installer_path):
        """Install Google Drive on macOS"""
        try:
            self.log.info(f"Installer path: {installer_path}")
            # Mount the DMG
            self.log.debug(f"Mounting Google Drive installer DMG: {installer_path}")
            mount_cmd = ["hdiutil", "attach", installer_path]
            mount_result = subprocess.run(mount_cmd, capture_output=True, text=True)
            
            if mount_result.returncode != 0:
                self.log.error(f"Failed to mount DMG: {mount_result.stderr}")
                from ayon_googledrive.ui.notifications import show_notification
                show_notification(
                    "Google Drive Installation Failed",
                    f"Failed to mount DMG. Please try installing manually.\nInstaller path: {installer_path}",
                    level="error"
                )
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
                from ayon_googledrive.ui.notifications import show_notification
                show_notification(
                    "Google Drive Installation Failed",
                    f"Could not determine DMG mount point. Please try installing manually.\nInstaller path: {installer_path}",
                    level="error"
                )
                return False
            
            self.log.debug(f"DMG mounted at: {mount_point}")
            
            # Look for the app within the mounted DMG
            app_name = None
            for item in os.listdir(mount_point):
                if item.endswith(".app"):
                    app_name = item
                    break
            
            if not app_name:
                self.log.error("Could not find .app in mounted DMG")
                subprocess.run(["hdiutil", "detach", mount_point, "-force"], capture_output=True)
                from ayon_googledrive.ui.notifications import show_notification
                show_notification(
                    "Google Drive Installation Failed",
                    f"Could not find .app in mounted DMG. Please try installing manually.\nInstaller path: {installer_path}",
                    level="error"
                )
                return False
            
            source_app_path = os.path.join(mount_point, app_name)
            target_app_path = os.path.join("/Applications", app_name)
            
            # Check if app already exists and needs to be closed
            if os.path.exists(target_app_path):
                self.log.debug("Closing existing Google Drive application")
                try:
                    subprocess.run(
                        ["osascript", "-e", f'tell application \"{app_name}\" to quit'],
                        capture_output=True, timeout=10
                    )
                    time.sleep(2)
                except Exception:
                    self.log.warning("Could not gracefully close Google Drive")
            
            # Copy app to Applications folder
            self.log.debug(f"Copying {source_app_path} to /Applications/")
            copy_cmd = ["cp", "-r", source_app_path, "/Applications/"]
            copy_result = subprocess.run(copy_cmd, capture_output=True, text=True)
            
            if copy_result.returncode != 0:
                self.log.error(f"Failed to copy app to Applications: {copy_result.stderr}")
                subprocess.run(["hdiutil", "detach", mount_point, "-force"], capture_output=True)
                from ayon_googledrive.ui.notifications import show_notification
                show_notification(
                    "Google Drive Installation Failed",
                    f"Failed to copy app to Applications. Please try installing manually.\nInstaller path: {installer_path}",
                    level="error"
                )
                return False
            
            # Unmount the DMG
            self.log.debug("Unmounting DMG")
            subprocess.run(["hdiutil", "detach", mount_point, "-force"], capture_output=True)
            self.log.debug("Google Drive installation completed")
            return True
        except Exception as e:
            self.log.error(f"Error installing Google Drive: {e}")
            from ayon_googledrive.ui.notifications import show_notification
            show_notification(
                "Google Drive Installation Error",
                f"An error occurred: {str(e)}\nInstaller path: {installer_path}",
                level="error"
            )
            return False
    
    def find_source_path(self, relative_path):
        """Find the full path to a relative path within Google Drive
        
        Args:
            relative_path (str): A path relative to the Google Drive root
            
        Returns:
            str: The full path to the relative path
"""
        self.log.debug(f"Looking for path: {relative_path}")
        
        # Clean up the path (handle Windows-style paths)
        if relative_path.startswith('\\'):
            relative_path = '/' + relative_path.lstrip('\\')
        relative_path = relative_path.replace('\\', '/')
        
        # Get all potential Google Drive paths
        base_paths = self._get_all_gdrive_paths()
        
        # Handle special case for Shared drives
        if "Shared drives" in relative_path or "Shared drives" in relative_path.replace('\\', '/'):
            drive_name = relative_path.split('/')[-1] if '/' in relative_path else relative_path.split('\\')[-1]
            
            for base in base_paths:
                # Try a few variations of shared drives paths
                shared_drive_paths = [
                    os.path.join(base, "Shared drives", drive_name),
                    os.path.join(base, "Shared drives", drive_name),
                ]
                
                for path in shared_drive_paths:
                    if os.path.exists(path) and os.path.isdir(path):
                        self.log.debug(f"Found shared drive at: {path}")
                        return path
            
            # One more check - look for Shared drives in the GoogleDrive mount point
            gdrive_mount = "/Volumes/GoogleDrive"
            if os.path.exists(gdrive_mount):
                shared_path = os.path.join(gdrive_mount, "Shared drives", drive_name)
                if os.path.exists(shared_path):
                    self.log.debug(f"Found shared drive at: {shared_path}")
                    return shared_path
            
            self.log.error(f"Could not locate shared drive '{drive_name}' in any Google Drive mount")
            return None
        
        # Handle regular paths
        for base in base_paths:
            full_path = os.path.join(base, relative_path.lstrip('/'))
            if os.path.exists(full_path):
                self.log.debug(f"Found path at: {full_path}")
                return full_path
        
        self.log.error(f"Could not locate path '{relative_path}' in any Google Drive mount")
        return None
    
    def list_shared_drives(self):
        """List available shared drives on macOS"""
        drives = []
        
        # Get all potential Google Drive paths
        base_paths = self._get_all_gdrive_paths()
        
        # Check each base path for shared drives folder
        for base_path in base_paths:
            shared_drives_path = os.path.join(base_path, "Shared drives")
            if os.path.exists(shared_drives_path) and os.path.isdir(shared_drives_path):
                try:
                    self.log.debug(f"Checking for shared drives in: {shared_drives_path}")
                    found_drives = os.listdir(shared_drives_path)
                    if found_drives:
                        self.log.debug(f"Found shared drives at {shared_drives_path}: {found_drives}")
                        # Filter out hidden folders
                        drives = [d for d in found_drives if not d.startswith('.')]
                        return drives
                except Exception as e:
                    self.log.error(f"Error listing shared drives at {shared_drives_path}: {e}")
                    
        return drives

    def _get_all_gdrive_paths(self):
        """Get all possible Google Drive paths on this system"""
        paths = []
        
        # Check standard paths
        standard_paths = [
            "/Volumes/GoogleDrive",
            "/Volumes/Google Drive", 
            os.path.expanduser("~/Google Drive")
        ]
        
        for path in standard_paths:
            if os.path.exists(path) and os.path.isdir(path):
                paths.append(path)
        
        # Check CloudStorage for GoogleDrive folders
        cloud_storage = os.path.expanduser("~/Library/CloudStorage")
        if os.path.exists(cloud_storage) and os.path.isdir(cloud_storage):
            try:
                for item in os.listdir(cloud_storage):
                    if item.startswith(("GoogleDrive-", "Google Drive-")):
                        gdrive_path = os.path.join(cloud_storage, item)
                        if os.path.isdir(gdrive_path):
                            self.log.debug(f"Found Google Drive in CloudStorage: {gdrive_path}")
                            paths.append(gdrive_path)
            except Exception as e:
                self.log.error(f"Error checking CloudStorage: {e}")
                
        return paths

    def find_googledrive_mount(self):
        """Find the actual Google Drive mount point on macOS"""
        self.log.debug("Finding Google Drive mount point")
        
        # Check the traditional locations first
        traditional_paths = [
            os.path.expanduser("~/Google Drive"),
            "/Volumes/GoogleDrive"
        ]
        
        for path in traditional_paths:
            if os.path.exists(path) and os.path.isdir(path):
                self.log.debug(f"Found traditional Google Drive mount at {path}")
                return path
                
        # Check the modern CloudStorage location
        cloud_storage_base = os.path.expanduser("~/Library/CloudStorage")
        if (os.path.exists(cloud_storage_base)):
            self.log.debug(f"Checking for Google Drive in CloudStorage: {cloud_storage_base}")
            # Look for directories starting with "GoogleDrive-" or "Google Drive-"
            for item in os.listdir(cloud_storage_base):
                if item.startswith(("GoogleDrive-", "Google Drive-")):
                    cloud_drive_path = os.path.join(cloud_storage_base, item)
                    if os.path.isdir(cloud_drive_path):
                        self.log.debug(f"Found modern Google Drive mount at {cloud_drive_path}")
                        return cloud_drive_path
        
        self.log.warning("Could not find Google Drive mount point")
        return None

    def ensure_mount_point(self, desired_mount):
        """Create a symlink from the actual Google Drive location to the desired mount point"""
        self.log.debug(f"Ensuring Google Drive mount point at {desired_mount}")
        
        # Find the actual Google Drive folder
        actual_drive_path = self.find_googledrive_mount()
        
        if not actual_drive_path:
            self.log.warning("Could not find Google Drive folder to symlink")
            return False
        
        # Check if mount point already exists and points to the right place
        if os.path.exists(desired_mount):
            if os.path.islink(desired_mount):
                target = os.readlink(desired_mount)
                if target == actual_drive_path:
                    self.log.debug(f"Mount point already exists at {desired_mount} and points to {actual_drive_path}")
                    return True
                else:
                    self.log.warning(f"Mount point {desired_mount} exists but points to {target} instead of {actual_drive_path}")
                    # Remove the incorrect symlink
                    try:
                        os.remove(desired_mount)
                    except Exception as e:
                        self.log.error(f"Failed to remove incorrect symlink: {e}")
                        return False
            else:
                self.log.warning(f"Mount point {desired_mount} exists but is not a symlink")
                return False
        
        # Create the parent directory if needed
        parent_dir = os.path.dirname(desired_mount)
        if not os.path.exists(parent_dir):
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except Exception as e:
                self.log.error(f"Failed to create parent directory {parent_dir}: {e}")
                return False
        
        # Create the symlink using AppleScript to request admin privileges if needed
        script_content = f'''
        try
            do shell script "ln -sf '{actual_drive_path}' '{desired_mount}'"
            return "Link created successfully"
        on error
            try
                display dialog "AYON needs to create a symbolic link for Google Drive.\\n\\nThis requires administrator privileges." with title "AYON: Configure Google Drive" buttons {{"Cancel", "Create"}} default button "Create"
                
                if button returned of result is "Create" then
                    do shell script "ln -sf '{actual_drive_path}' '{desired_mount}'" with administrator privileges
                    return "Link created successfully with admin privileges"
                else
                    error "Link creation cancelled by user"
                end if
            on error errorMsg
                return "Error: " & errorMsg
            end try
        end try
        '''
        
        # Save the script to a temporary file
        script_path = os.path.join(tempfile.gettempdir(), "ayon_gdrive_link.scpt")
        with open(script_path, "w") as f:
            f.write(script_content)
        
        # Execute the AppleScript
        result = run_process(["osascript", script_path])
        
        # Clean up
        if os.path.exists(script_path):
            os.remove(script_path)
        
        if result and result.returncode == 0:
            self.log.info(f"Successfully created symlink from {actual_drive_path} to {desired_mount}")
            return True
        else:
            error = result.stderr if result else "Unknown error"
            if "cancelled by user" in error:
                self.log.warning("Symlink creation cancelled by user")
            else:
                self.log.error(f"Failed to create symlink: {error}")
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
                    self.log.debug(f"Symlink already exists correctly: {target_path} -> {source_path}")
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
        
        # Try to create the symlink directly first
        try:
            # Create parent directory if needed
            parent_dir = os.path.dirname(target_path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                
            # Create the symlink
            self.log.debug(f"Creating symlink: {target_path} -> {source_path}")
            os.symlink(source_path, target_path)
            self.log.debug(f"Successfully created symlink directly")
            return True
        except PermissionError:
            # Need admin privileges, try with osascript
            self.log.debug("Permission error creating symlink directly, will try with admin privileges")
            
            # Create AppleScript to request admin privileges
            script_content = f"""
            tell application "System Events"
                set sourceQuoted to "{source_path}"
                set targetQuoted to "{target_path}"
                
                try
                    display dialog "AYON needs to create a symbolic link for Google Drive.\\n\\nThis requires administrator privileges." with title "AYON: Configure Google Drive" buttons {{"Cancel", "Create"}} default button "Create"
                    
                    if button returned of result is "Create" then
                        do shell script "mkdir -p \\"" & (do shell script "dirname " & quoted form of targetQuoted) & "\\"" with administrator privileges
                        do shell script "ln -sf \\"" & sourceQuoted & "\\" \\"" & targetQuoted & "\\"" with administrator privileges
                        return "success"
                    else
                        return "cancelled"
                    end if
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
            """
            
            # Save the script to a temporary file
            import tempfile
            script_path = os.path.join(tempfile.gettempdir(), "ayon_gdrive_symlink.scpt")
            with open(script_path, "w") as f:
                f.write(script_content)
            
            # Execute the AppleScript
            result = run_process(["osascript", script_path])
            
            # Clean up
            try:
                os.remove(script_path)
            except Exception:
                pass
            
            # Check result
            if result and result.returncode == 0:
                if "success" in result.stdout:
                    self.log.info(f"Successfully created symlink with admin privileges: {target_path} -> {source_path}")
                    return True
                elif "cancelled" in result.stdout:
                    self.log.warning(f"User cancelled symlink creation")
                    return False
                else:
                    self.log.error(f"AppleScript error: {result.stdout}")
                    
            self.log.error(f"Permission denied creating symlink at {target_path}")
            self.log.debug(f"Admin privileges required: sudo ln -sf '{source_path}' '{target_path}'")
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
        
        self.log.debug(f"Admin privileges required: {command}")
        
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
                from ayon_googledrive.api.lib import get_settings
                settings = get_settings()
                
            mappings = settings.get("mappings", [])
            
            for mapping in mappings:
                target = mapping.get("macos_target", "")
                if target and os.path.exists(target) and os.path.islink(target):
                    self.log.debug(f"Removing symlink: {target}")
                    try:
                        os.unlink(target)
                    except Exception as e:
                        self.log.error(f"Failed to remove symlink {target}: {e}")
                        
            return True
        except Exception as e:
            self.log.error(f"Error removing mappings: {e}")
            return False

    def create_symlink(self, source_path, target_path):
        """Create a symlink with admin privileges if needed"""
        self.log.debug(f"Creating symlink: {target_path} -> {source_path}")
        
        # Check if target already exists and is correct
        if os.path.exists(target_path):
            if os.path.islink(target_path):
                try:
                    existing_target = os.readlink(target_path)
                    if existing_target == source_path:
                        self.log.debug(f"Symlink already exists and is correct at {target_path}")
                        return True
                    self.log.debug(f"Symlink exists but points to wrong target: {existing_target}")
                except Exception as e:
                    self.log.error(f"Error checking existing symlink: {e}")
            else:
                self.log.error(f"Target path exists but is not a symlink: {target_path}")
                return False
        
        # Try creating symlink directly first (will likely fail for /Volumes)
        try:
            if os.path.exists(target_path):
                os.unlink(target_path)
            os.symlink(source_path, target_path)
            self.log.debug(f"Created symlink directly: {target_path} -> {source_path}")
            return True
        except PermissionError:
            self.log.debug("Permission error creating symlink directly, will try with admin privileges")
        except Exception as e:
            self.log.debug(f"Error creating symlink directly: {e}")
        
        # Create a user-friendly notification
        from PyQt5.QtWidgets import QMessageBox
        from ayon_googledrive.api import get_main_window
        
        msg = QMessageBox(get_main_window())
        msg.setWindowTitle("Admin Privileges Required")
        msg.setText("Creating the symlink requires administrator privileges.")
        msg.setInformativeText(f"To map '{os.path.basename(source_path)}' to '{target_path}', please run this command in Terminal:\n\n" +
                               f"sudo ln -sf '{source_path}' '{target_path}'")
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        
        # Return False since we couldn't create the symlink automatically
        return False

    def process_mapping(self, mapping):
        """Process a single mapping configuration with better error handling"""
        name = mapping.get("name", "Unknown")
        source_path = mapping.get("source_path")
        target_path = mapping.get("macos_target")
        
        if not source_path or not target_path:
            self.log.error(f"Invalid mapping configuration for {name}")
            return False
        
        self.log.debug(f"Processing mapping '{name}': {source_path} -> {target_path}")
        
        # Find the full source path in Google Drive
        full_source_path = self.find_source_path(source_path)
        
        if not full_source_path:
            self.log.error(f"Could not find source path for {source_path}")
            return False
            
        self.log.debug(f"Found shared drive at: {full_source_path}")
        
        # Create the symlink
        success = self.create_symlink(full_source_path, target_path)
        if not success:
            # Don't log as error since we've provided instructions to the user
            self.log.debug(f"Could not automatically create symlink for mapping: {name}")
            return False
        
        self.log.info(f"Mapping '{name}' successfully processed: {target_path} -> {full_source_path}")
        return True