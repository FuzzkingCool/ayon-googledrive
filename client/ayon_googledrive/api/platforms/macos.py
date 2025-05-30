import errno
import json
import os
import subprocess
import tempfile
import time
import traceback

from ayon_googledrive.api.lib import run_process
from ayon_googledrive.api.platforms.base import GDrivePlatformBase


class GDriveMacOSPlatform(GDrivePlatformBase):
    """Platform-specific handler for macOS."""

    def __init__(self, settings=None):
        """Initialize the macOS platform handler.
        
        Args:
            settings (dict, optional): Settings dictionary from GDriveManager.
        """
        super(GDriveMacOSPlatform, self).__init__()
        self.settings = settings
        self._googledrive_path = None
        self.os_type = "Darwin" # Add os_type for base class to use
        self._shared_drives_path_override = None
    
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
        
        #self.log.debug(f"Looking for Google Drive in possible paths: {possible_paths}")
        
        # Check if any of the paths exist
        for path in possible_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                # self.log.info(f"Found Google Drive installation at: {expanded_path}")
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
                        # self.log.debug(f"Found running Google Drive process: {line.strip()}")
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
                                # self.log.debug(f"Found Google Drive account data at: {item_path}")
                                return True
                    except Exception as e:
                        self.log.debug(f"Error checking directory {path}: {e}")
                        self.log.debug(traceback.format_exc())
                else:
                    # For files, existence is enough
                    self.log.debug(f"Found Google Drive user preferences at: {path}")
                    return True
                    
        #self.log.debug("No Google Drive login data found")
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
            #self.log.debug(f"Starting Google Drive from: {app_path}")
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
            #self.log.debug(f"Mounting Google Drive installer DMG: {installer_path}")
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
            
            #self.log.debug(f"DMG mounted at: {mount_point}")
            
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
                #self.log.debug("Closing existing Google Drive application")
                try:
                    subprocess.run(
                        ["osascript", "-e", f'tell application \"{app_name}\" to quit'],
                        capture_output=True, timeout=10
                    )
                    time.sleep(2)
                except Exception:
                    self.log.warning("Could not gracefully close Google Drive")
            
            # Copy app to Applications folder
            #self.log.debug(f"Copying {source_app_path} to /Applications/")
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
            #self.log.debug("Unmounting DMG")
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
        #self.log.debug(f"Looking for path: {relative_path}")
        
        # Clean up the path (handle Windows-style paths)
        if relative_path.startswith('\\'):
            relative_path = '/' + relative_path.lstrip('\\')
        relative_path = relative_path.replace('\\', '/')
        
        # Get all potential Google Drive paths
        base_paths = self._get_all_gdrive_paths()
        
        # Handle special case for Shared drives
        # Define a list of known "Shared Drives" folder names in different languages
        shared_drives_names = [
            "Shared drives",  # English
            "Shared Drives",  # English (alternative capitalization)
            "Drive partages",  # French
            "Compartidos conmigo",  # Spanish
            "Geteilte Ablagen",  # German
            "Condivisi con me",  # Italian
            "Gedeelde drives",  # Dutch
            # Add more translations as needed
        ]

        if any(name in relative_path for name in shared_drives_names):
            drive_name = relative_path.split('/')[-1] if '/' in relative_path else relative_path.split('\\')[-1]
            
            if self._shared_drives_path_override and os.path.exists(os.path.join(self._shared_drives_path_override, drive_name)):
                self.log.debug(f"Using user-defined Shared Drives path: {self._shared_drives_path_override}")
                return os.path.join(self._shared_drives_path_override, drive_name)

            for base in base_paths:
                for name in shared_drives_names:
                    shared_drive_folder_path = os.path.join(base, name)
                    if os.path.exists(shared_drive_folder_path) and os.path.isdir(shared_drive_folder_path):
                        path_to_check = os.path.join(shared_drive_folder_path, drive_name)
                        if os.path.exists(path_to_check) and os.path.isdir(path_to_check):
                            #self.log.debug(f"Found shared drive at: {path_to_check}")
                            return path_to_check
            
            # One more check - look for Shared drives in the GoogleDrive mount point
            gdrive_mount = "/Volumes/GoogleDrive"
            if os.path.exists(gdrive_mount):
                for name in shared_drives_names:
                    shared_drive_folder_path = os.path.join(gdrive_mount, name)
                    if os.path.exists(shared_drive_folder_path) and os.path.isdir(shared_drive_folder_path):
                        path_to_check = os.path.join(shared_drive_folder_path, drive_name)
                        if os.path.exists(path_to_check) and os.path.isdir(path_to_check):
                            #self.log.debug(f"Found shared drive at: {path_to_check}")
                            return path_to_check
            
            # If still not found, prompt the user
            self.log.warning(f"Could not locate shared drive folder for '{drive_name}'. Prompting user.")
            user_selected_path = self._prompt_user_for_shared_drives_path()
            if user_selected_path and os.path.exists(os.path.join(user_selected_path, drive_name)):
                self._shared_drives_path_override = user_selected_path
                self.log.info(f"User selected Shared Drives path: {self._shared_drives_path_override}")
                return os.path.join(self._shared_drives_path_override, drive_name)

            self.log.error(f"Could not locate shared drive '{drive_name}' in any Google Drive mount or via user prompt")
            return None
        
        # Handle regular paths
        for base in base_paths:
            full_path = os.path.join(base, relative_path.lstrip('/'))
            if os.path.exists(full_path):
                #self.log.debug(f"Found path at: {full_path}")
                return full_path
        
        self.log.error(f"Could not locate path '{relative_path}' in any Google Drive mount")
        return None
    
    def list_shared_drives(self):
        """List available shared drives on macOS"""
        drives = []
        
        # Get all potential Google Drive paths
        base_paths = self._get_all_gdrive_paths()

        if self._shared_drives_path_override:
            # Prioritize user-defined path. Ensure it is treated as the direct "Shared Drives" folder.
            # The structure of base_paths expects paths *containing* a "Shared Drives" folder, 
            # so we don't add the override directly to base_paths here if it's already the SD folder.
            # Instead, we check it separately first.
            try:
                #self.log.debug(f"Checking user-defined shared drives path: {self._shared_drives_path_override}")
                found_drives = os.listdir(self._shared_drives_path_override)
                if found_drives:
                    drives = [d for d in found_drives if not d.startswith('.') and os.path.isdir(os.path.join(self._shared_drives_path_override, d))]
                    if drives: 
                        return drives
            except Exception as e:
                self.log.error(f"Error listing shared drives from override path {self._shared_drives_path_override}: {e}")

        # Check each base path for shared drives folder
        for base_path in base_paths:
            for name in self.shared_drives_names:
                shared_drives_folder_path = os.path.join(base_path, name)
                if os.path.exists(shared_drives_folder_path) and os.path.isdir(shared_drives_folder_path):
                    try:
                        #self.log.debug(f"Checking for shared drives in: {shared_drives_folder_path}")
                        found_drives = os.listdir(shared_drives_folder_path)
                        if found_drives:
                            #self.log.debug(f"Found shared drives at {shared_drives_folder_path}: {found_drives}")
                            # Filter out hidden folders
                            drives = [d for d in found_drives if not d.startswith('.') and os.path.isdir(os.path.join(shared_drives_folder_path, d))]
                            if drives: # ensure we found actual drives
                                return drives
                    except Exception as e:
                        self.log.error(f"Error listing shared drives at {shared_drives_folder_path}: {e}")
        
        # If still not found by direct listing, and no override has been successfully used, prompt the user
        # (The override might exist but be empty or invalid, so we re-check 'drives' list)
        if not drives:
            # Avoid prompting if an override was set but simply yielded no drives.
            # Only prompt if no override path is set at all.
            if not self._shared_drives_path_override:
                self.log.warning("Could not locate Shared Drives folder automatically. Prompting user.")
                user_selected_path = self._prompt_user_for_shared_drives_path() # Uses method from base class
                if user_selected_path:
                    self._shared_drives_path_override = user_selected_path
                    self.log.info(f"User selected Shared Drives path: {self._shared_drives_path_override}")
                    # Retry listing from the user-provided path
                    try:
                        found_drives = os.listdir(self._shared_drives_path_override)
                        if found_drives:
                            drives = [d for d in found_drives if not d.startswith('.') and os.path.isdir(os.path.join(self._shared_drives_path_override, d))]
                            return drives # Return immediately after successful prompt and list
                    except Exception as e:
                        self.log.error(f"Error listing shared drives from user path {self._shared_drives_path_override}: {e}")

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
                            #self.log.debug(f"Found Google Drive in CloudStorage: {gdrive_path}")
                            paths.append(gdrive_path)
            except Exception as e:
                self.log.error(f"Error checking CloudStorage: {e}")
                
        return paths

    def find_googledrive_mount(self):
        """Find the actual Google Drive mount point on macOS"""
        #self.log.debug("Finding Google Drive mount point")
        
        # Check the traditional locations first
        traditional_paths = [
            os.path.expanduser("~/Google Drive"),
            "/Volumes/GoogleDrive"
        ]
        
        for path in traditional_paths:
            if os.path.exists(path) and os.path.isdir(path):
                #self.log.debug(f"Found traditional Google Drive mount at {path}")
                return path
                
        # Check the modern CloudStorage location
        cloud_storage_base = os.path.expanduser("~/Library/CloudStorage")
        if (os.path.exists(cloud_storage_base)):
            #self.log.debug(f"Checking for Google Drive in CloudStorage: {cloud_storage_base}")
            # Look for directories starting with "GoogleDrive-" or "Google Drive-"
            for item in os.listdir(cloud_storage_base):
                if item.startswith(("GoogleDrive-", "Google Drive-")):
                    cloud_drive_path = os.path.join(cloud_storage_base, item)
                    if os.path.isdir(cloud_drive_path):
                        #self.log.debug(f"Found modern Google Drive mount at {cloud_drive_path}")
                        return cloud_drive_path
        
        self.log.warning("Could not find Google Drive mount point")
        return None

    def ensure_mount_point(self, desired_mount):
        """Create a symlink from the actual Google Drive location to the desired mount point"""
        self.log.debug(f"Ensuring Google Drive mount point at {desired_mount}")
        
        actual_drive_path = self.find_googledrive_mount()
        
        if not actual_drive_path:
            self.log.warning("Could not find Google Drive folder to symlink for main mount point.")
            return False # (False, "Google Drive folder not found") # Or more detailed status

        # Normalize paths to be absolute and clean
        actual_drive_path = os.path.normpath(os.path.abspath(actual_drive_path)).replace('"', '\\"')
        desired_mount = os.path.normpath(os.path.abspath(desired_mount)).replace('"', '\\"')

        # Check if mount point already exists and points to the right place
        if os.path.lexists(desired_mount): # Use lexists for symlinks
            if os.path.islink(desired_mount):
                try:
                    current_target = os.readlink(desired_mount)
                    if os.path.normpath(os.path.abspath(current_target)) == actual_drive_path:
                        self.log.debug(f"Mount point {desired_mount} already correctly links to {actual_drive_path}")
                        return True # (True, "Already correctly linked")
                except OSError as e:
                    self.log.warning(f"Error reading existing symlink {desired_mount}: {e}. Will attempt to recreate.")
            else:
                # Path exists but is not a symlink. This is a conflict.
                self.log.error(f"Path {desired_mount} exists but is not a symlink. Cannot create mount point.")
                # self.alert_path_in_use(desired_mount, "existing file/directory", actual_drive_path)
                return False # (False, f"Path {desired_mount} is not a symlink")
        
        # Prepare AppleScript
        # Using -sfn: -s for symbolic, -f to force (remove existing destination files), 
        # -n to treat link like a normal file if it's a symlink to a directory (safer for /Volumes)
        script_content = f'''
        set p_actual_drive_path to "{actual_drive_path}"
        set p_desired_mount to "{desired_mount}"
        set p_parent_of_desired to do shell script "dirname " & quoted form of p_desired_mount

        -- Try direct first (no admin privileges for creating the symlink itself)
        -- Parent directory creation might still need admin if it's in a restricted area
        try
            do shell script "mkdir -p " & quoted form of p_parent_of_desired
            do shell script "ln -sfn " & quoted form of p_actual_drive_path & " " & quoted form of p_desired_mount
            return "success_direct"
        on error errmsg_direct number errnum_direct
            -- If direct attempt fails (likely permission error for /Volumes or parent dir), try with admin prompt
            try
                display dialog "AYON needs to create a symbolic link for the main Google Drive mount point:" & return & return & "From: " & p_actual_drive_path & return & "To: " & p_desired_mount & return & return & "This requires administrator privileges." with title "AYON: Configure Google Drive Mount" buttons {{"Cancel", "Create"}} default button "Create" with icon note
                
                if button returned of result is "Create" then
                    do shell script "mkdir -p " & quoted form of p_parent_of_desired & " && ln -sfn " & quoted form of p_actual_drive_path & " " & quoted form of p_desired_mount with administrator privileges
                    return "success_admin"
                else
                    -- User cancelled
                    return "cancelled"
                end if
            on error errmsg_admin number errnum_admin
                -- Error during admin attempt or dialog
                return "error_admin: (" & errnum_admin & ") " & errmsg_admin
            end try
        end try
        ''' 
        
        script_path = os.path.join(tempfile.gettempdir(), "ayon_gdrive_ensure_mount.scpt")
        try:
            with open(script_path, "w") as f:
                f.write(script_content)
            
            self.log.debug(f"Executing AppleScript for ensure_mount_point: {script_path}")
            result = run_process(["osascript", script_path])
            
            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""

            self.log.debug(f"ensure_mount_point osascript stdout: {stdout}")
            if stderr:
                self.log.debug(f"ensure_mount_point osascript stderr: {stderr}")

            if "success_direct" in stdout or "success_admin" in stdout:
                self.log.info(f"Successfully configured mount point {desired_mount} -> {actual_drive_path} (Method: {stdout})")
                # Verify after creation
                if os.path.islink(desired_mount) and os.path.normpath(os.path.abspath(os.readlink(desired_mount))) == actual_drive_path:
                    return True #(True, stdout)
                else:
                    self.log.error(f"Symlink at {desired_mount} post-creation check failed or points incorrectly.")
                    return False #(False, "Post-creation check failed")
            elif "cancelled" in stdout:
                self.log.warning(f"User cancelled creation of mount point {desired_mount}")
                return False #(False, "User cancelled")
            else:
                # Includes "error_admin" or other script issues
                self.log.error(f"Failed to configure mount point {desired_mount}. Script output: {stdout}. Error: {stderr}")
                return False #(False, f"AppleScript execution failed: {stdout} {stderr}")

        except Exception as e:
            self.log.error(f"Exception while executing AppleScript for ensure_mount_point: {e}", exc_info=True)
            return False #(False, f"Python exception: {e}")
        finally:
            if os.path.exists(script_path):
                try:
                    os.remove(script_path)
                except Exception as e_rm:
                    self.log.warning(f"Failed to remove temp AppleScript file {script_path}: {e_rm}")

    def create_mapping(self, source_path, target_path, mapping_name=None):
        """Create a symlink on macOS, prompting for admin if needed, and record it."""
        if not mapping_name:
            mapping_name = os.path.basename(target_path) 
        # Normalize paths to be absolute and clean for reliable comparison and creation
        source_path = os.path.normpath(os.path.abspath(source_path)).replace('"', '\\"')
        target_path = os.path.normpath(os.path.abspath(target_path)).replace('"', '\\"')

        # Normalize paths to be absolute and clean for reliable comparison and creation
        # The source_path from find_source_path should already be absolute
        # However, target_path from settings might be relative or messy
        target_path = os.path.normpath(os.path.abspath(target_path))
        # source_path is expected to be already an absolute, existing path from find_source_path
        if not os.path.isabs(source_path):
            self.log.warning(f"Source path '{source_path}' for mapping '{mapping_name}' is not absolute. This is unexpected.")
            # Attempt to make it absolute assuming it's relative to some default, or just fail.
            # For now, we proceed, but this indicates a potential issue upstream.

        self.log.info(f"Attempting to create mapping '{mapping_name}': {source_path} -> {target_path}")

        parent_dir = os.path.dirname(target_path)

        # Check if target_path already exists
        if os.path.lexists(target_path):
            if os.path.islink(target_path):
                try:
                    current_link_target = os.readlink(target_path)
                    # Normalize current_link_target as well, in case it's relative
                    if not os.path.isabs(current_link_target):
                         # This is tricky: relative symlinks are relative to their parent dir
                        current_link_target = os.path.normpath(os.path.join(os.path.dirname(target_path), current_link_target))
                    else:
                        current_link_target = os.path.normpath(current_link_target)
                    
                    normalized_source_path = os.path.normpath(source_path)

                    if current_link_target == normalized_source_path:
                        self.log.info(f"Symlink for '{mapping_name}' at {target_path} already exists and points correctly.")
                        self._record_mapping(mapping_name, source_path, target_path)
                        return True
                    else:
                        self.log.warning(f"Symlink {target_path} for '{mapping_name}' exists but points to {current_link_target} (expected {normalized_source_path}). It will be replaced.")
                        # os.unlink might need admin, handled by the ln -sfn in script later
                except OSError as e:
                    self.log.warning(f"Error checking existing symlink {target_path} for '{mapping_name}': {e}. Will attempt to (re)create.")
            else:
                self.log.error(f"Path {target_path} for '{mapping_name}' already exists and is not a symlink. Cannot create mapping.")
                return False

        # Attempt to create the symlink directly first
        try:
            if not os.path.exists(parent_dir):
                # Try to create parent dir without admin first. If it's in /Volumes, this will fail and be handled by AppleScript.
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                    self.log.debug(f"Created parent directory (direct): {parent_dir} for mapping '{mapping_name}'")
                except OSError as e_mkdir:
                    if e_mkdir.errno != errno.EEXIST: # Don't log if it just already existed
                        self.log.debug(f"Direct mkdir failed for {parent_dir} (mapping '{mapping_name}'): {e_mkdir}. Will be retried by AppleScript if needed.")
            
            # If symlink exists and was wrong, unlink it first (best effort, might need admin)
            if os.path.lexists(target_path) and os.path.islink(target_path):
                 try:
                    os.unlink(target_path)
                 except OSError as e_unlink_direct:
                    self.log.debug(f"Direct unlink of existing symlink {target_path} failed: {e_unlink_direct}. Will rely on ln -sfn.")

            os.symlink(source_path, target_path)
            self.log.info(f"Successfully created symlink (direct) for '{mapping_name}': {target_path} -> {source_path}")
            self._record_mapping(mapping_name, source_path, target_path)
            return True
        except OSError as e:
            if e.errno in [errno.EACCES, errno.EPERM, errno.ENOENT]: # ENOENT if parent dir couldn't be made in restricted area
                self.log.warning(f"Direct symlink creation for '{mapping_name}' failed: {e}. Attempting with administrator privileges.")
                
                # Using -sfn: -s for symbolic, -f to force (remove existing destination files),
                # -n to treat link like a normal file if it's a symlink to a directory (safer for /Volumes)
                script_content = f'''
                set p_source_path to "{source_path}"
                set p_target_path to "{target_path}"
                set p_parent_of_target to do shell script "dirname " & quoted form of p_target_path

                try
                    display dialog "AYON needs to create a symbolic link for the mapping '{mapping_name}':" & return & return & "From: " & p_source_path & return & "To: " & p_target_path & return & return & "This requires administrator privileges." with title "AYON: Configure Drive Mapping" buttons {{"Cancel", "Create"}} default button "Create" with icon note
                    
                    if button returned of result is "Create" then
                        do shell script "mkdir -p " & quoted form of p_parent_of_target & " && ln -sfn " & quoted form of p_source_path & " " & quoted form of p_target_path with administrator privileges
                        return "success_admin"
                    else
                        return "cancelled"
                    end if
                on error errmsg number errnum
                    return "error_admin: (" & errnum & ") " & errmsg
                end try
                '''
                script_path = os.path.join(tempfile.gettempdir(), f"ayon_gdrive_create_mapping_{mapping_name.replace(' ', '_')}.scpt")
                try:
                    with open(script_path, "w") as f:
                        f.write(script_content)
                    
                    self.log.debug(f"Executing AppleScript for create_mapping '{mapping_name}': {script_path}")
                    result = run_process(["osascript", script_path])
                    stdout = result.stdout.strip() if result.stdout else ""
                    stderr = result.stderr.strip() if result.stderr else ""
                    self.log.debug(f"create_mapping '{mapping_name}' osascript stdout: {stdout}")
                    if stderr: self.log.debug(f"create_mapping '{mapping_name}' osascript stderr: {stderr}")

                    if "success_admin" in stdout:
                        self.log.info(f"Successfully created symlink via AppleScript for '{mapping_name}': {target_path} -> {source_path}")
                        self._record_mapping(mapping_name, source_path, target_path)
                        return True
                    elif "cancelled" in stdout:
                        self.log.warning(f"User cancelled symlink creation for '{mapping_name}'.")
                        return False
                    else:
                        self.log.error(f"AppleScript execution failed for '{mapping_name}'. Script output: {stdout}. Error: {stderr}")
                        return False
                except Exception as e_script:
                    self.log.error(f"Exception during AppleScript execution for '{mapping_name}': {e_script}", exc_info=True)
                    return False
                finally:
                    if os.path.exists(script_path):
                        try: os.remove(script_path)
                        except Exception as e_rm: self.log.warning(f"Failed to remove temp AppleScript file {script_path}: {e_rm}")
            else:
                self.log.error(f"Failed to create symlink for '{mapping_name}' due to an unexpected OS error: {e}", exc_info=True)
                return False
        except Exception as e_general:
            self.log.error(f"An unexpected error occurred during symlink creation for '{mapping_name}': {e_general}", exc_info=True)
            return False

    def _get_mappings_file_path(self):
        """Returns the path to the file storing active mappings."""
        # tempfile.gettempdir() ensures this is a writable location
        return os.path.join(tempfile.gettempdir(), "ayon_gdrive_macos_mappings.json")

    def _record_mapping(self, name, source, target):
        """Records an active symlink mapping to a file."""
        mappings_file = self._get_mappings_file_path()
        mappings = {}
        if os.path.exists(mappings_file):
            try:
                with open(mappings_file, "r") as f:
                    mappings = json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                self.log.warning(f"Could not read existing mappings file {mappings_file}: {e}. It will be overwritten.")
        
        mappings[name] = {"source_path": source, "target_path": target, "timestamp": time.time()}
        
        try:
            with open(mappings_file, "w") as f:
                json.dump(mappings, f, indent=4)
            self.log.debug(f"Recorded mapping '{name}' to {mappings_file}")
        except IOError as e:
            self.log.error(f"Failed to write to mappings file {mappings_file}: {e}")

    def _get_active_mappings_from_file(self):
        """Reads active symlink mappings from the file."""
        mappings_file = self._get_mappings_file_path()
        if not os.path.exists(mappings_file):
            return {}
        try:
            with open(mappings_file, "r") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            self.log.error(f"Failed to read or parse mappings file {mappings_file}: {e}")
            return {}

    def _clear_active_mappings_file(self):
        """Clears the active mappings file."""
        mappings_file = self._get_mappings_file_path()
        if os.path.exists(mappings_file):
            try:
                os.remove(mappings_file)
                self.log.info(f"Cleared active mappings file: {mappings_file}")
            except OSError as e:
                self.log.error(f"Failed to remove mappings file {mappings_file}: {e}")

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
        """Remove all created symlinks and unmount any drives if applicable."""
        self.log.info("Attempting to remove all Google Drive mappings on macOS")

        if self.settings and self.settings.get("keep_symlinks_on_exit", False):
            self.log.info("Skipping symlink removal as 'keep_symlinks_on_exit' is enabled.")
            return True

        mappings = self._get_active_mappings_from_file()
        if not mappings:
            self.log.info("No active mappings found to remove.")
            return True

        success_all = True
        for mapping_name, details in list(mappings.items()): # Iterate over a copy for safe deletion
            target_path = details.get("target_path")
            if target_path and os.path.islink(target_path):
                try:
                    # Verify it's a link we likely created by checking if source matches, if available
                    # This is an extra precaution, actual check is based on the record file
                    # recorded_source = details.get("source_path")
                    # current_source = os.readlink(target_path)
                    # if recorded_source and os.path.normpath(current_source) != os.path.normpath(recorded_source):
                    #    self.log.warning(f"Symlink {target_path} points to {current_source}, expected {recorded_source}. Will not remove.")
                    #    continue # Skip removal if it doesn't point to what we recorded

                    os.unlink(target_path)
                    self.log.info(f"Successfully removed symlink: {target_path} for mapping '{mapping_name}'")
                except OSError as e:
                    self.log.error(f"Failed to remove symlink {target_path} for mapping '{mapping_name}': {e}")
                    success_all = False
                except Exception as e:
                    self.log.error(f"Unexpected error removing symlink {target_path} for '{mapping_name}': {e}")
                    success_all = False
            elif target_path and os.path.exists(target_path):
                # This case should ideally not happen if we only record symlinks we create
                self.log.warning(f"Path {target_path} for mapping '{mapping_name}' exists but is not a symlink. Manual removal might be needed.")
            else:
                self.log.debug(f"Symlink {target_path} for mapping '{mapping_name}' not found or already removed.")

        if success_all:
            self.log.info("Successfully removed all symlinks based on active mappings record.")
            self._clear_active_mappings_file() # Clear the record of active mappings
        else:
            self.log.warning("Some symlinks could not be removed. The record file will not be cleared.")
            # Potentially, you might want to update the record file to remove only successfully deleted links
            # For now, we leave it as is, so on next run it might try again or show which ones failed.

        return success_all