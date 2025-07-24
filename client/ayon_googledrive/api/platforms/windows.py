import ctypes
import glob
import os
import platform
import re
import subprocess
import threading
import time

from ayon_googledrive.api.lib import clean_relative_path, run_process
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
        self.os_type = "Windows" # Add os_type for base class to use

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
        if platform.system() == "Windows":
            clean_path = clean_path.lstrip("\\/")

        # If a user override for the Shared Drives path exists, check it first
        if any(name in clean_path for name in self.shared_drives_names):
            drive_name_part = clean_path.split('Shared drives\\', 1)[-1].split('Shared Drives\\',1)[-1] # Get the part after "Shared drives\"
            # Further split by any known shared drive name to get the actual drive name
            for sd_name_variant in self.shared_drives_names:
                if sd_name_variant in drive_name_part:
                     #This logic is a bit fragile, assumes drive_name_part starts with sd_name_variant + separator
                    #Adjust if specific drive names can contain parts of sd_name_variant
                    potential_drive_name = drive_name_part.split(sd_name_variant + '\\', 1)[-1]
                    if potential_drive_name != drive_name_part: # ensure split occurred
                        drive_name_part = potential_drive_name
                        break
            
            if self._shared_drives_path_override:
                # The override should point to the folder *containing* specific shared drives
                # e.g., G:\Shared drives or D:\DrivePartages
                path_to_check = os.path.join(self._shared_drives_path_override, drive_name_part)
                if os.path.exists(path_to_check) and os.path.isdir(path_to_check):
                    self.log.info(f"Found source path via user override: {path_to_check}")
                    return path_to_check

        # Check all available drive letters
        drive_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        found_drive_bases = []

        for drive_letter in drive_letters:
            drive_root = f"{drive_letter}:\\"
            if not os.path.exists(drive_root):
                continue

            # Check for any of the internationalized "Shared Drives" names
            for sd_name in self.shared_drives_names:
                potential_shared_drives_folder = os.path.join(drive_root, sd_name)
                if os.path.exists(potential_shared_drives_folder) and os.path.isdir(potential_shared_drives_folder):
                    self.log.debug(f"Found potential Shared Drives folder at {potential_shared_drives_folder}")
                    found_drive_bases.append(potential_shared_drives_folder)
                    # Check if this is the My Drive folder as well
                    my_drive_path = os.path.join(drive_root, "My Drive") # Common name for My Drive
                    if os.path.exists(my_drive_path) and os.path.isdir(my_drive_path):
                         # This drive letter contains both a "Shared drives" variant and "My Drive", good candidate.
                         # Add the root as a base for non-shared drive paths too.
                         if drive_root not in found_drive_bases: # avoid duplicates if sd_name was empty
                            found_drive_bases.append(drive_root)

        if not found_drive_bases and any(name in clean_path for name in self.shared_drives_names):
            # If we expected a shared drive path but found no "Shared Drives" folders
            self.log.warning("Could not find any 'Shared Drives' folder. Prompting user.")
            user_selected_path = self._prompt_user_for_shared_drives_path()
            if user_selected_path:
                self._shared_drives_path_override = user_selected_path
                self.log.info(f"User selected Shared Drives path: {self._shared_drives_path_override}")
                # Retry finding the specific shared drive within this new path
                # This assumes user selects the folder like "G:\Shared drives"
                path_to_check = os.path.join(self._shared_drives_path_override, drive_name_part)
                if os.path.exists(path_to_check) and os.path.isdir(path_to_check):
                    self.log.info(f"Found source path via user prompt: {path_to_check}")
                    return path_to_check
            else:
                self.log.error(f"User did not select a Shared Drives path. Cannot locate: {clean_path}")
                return None # User cancelled or closed dialog
        elif not found_drive_bases:
            self.log.error(f"Could not find any Google Drive mount point. Cannot locate: {clean_path}")
            return None

        # Deduplicate and prioritize user override if it exists and is a shared drive base
        unique_bases = []
        if self._shared_drives_path_override and self._shared_drives_path_override not in found_drive_bases:
            # Check if the override is a parent of any found base, or vice-versa, to avoid redundant checks
            is_related = False
            for base in found_drive_bases:
                if self._shared_drives_path_override.startswith(base) or base.startswith(self._shared_drives_path_override):
                    is_related = True
                    break
            if not is_related:
                 unique_bases.append(self._shared_drives_path_override)
        
        for base in found_drive_bases:
            if base not in unique_bases:
                unique_bases.append(base)

        self.log.debug(f"Searching for '{clean_path}' in bases: {unique_bases}")

        for base_path_to_search in unique_bases:
            # Determine if base_path_to_search is a shared drives folder (e.g., I:\Shared drives) or a root (e.g., I:\)
            is_shared_drives_folder_itself = any(base_path_to_search.rstrip('\\/').endswith(sep + sd_name) for sep in [os.sep, os.altsep] if sep for sd_name in self.shared_drives_names)

            if any(name in clean_path for name in self.shared_drives_names):
                actual_item_name = clean_path
                # Strip all shared drive name variants and separators from the start
                for sd_name_variant in self.shared_drives_names:
                    for sep in ['\\', '/']:
                        prefix_to_check = sd_name_variant + sep
                        if actual_item_name.startswith(prefix_to_check):
                            actual_item_name = actual_item_name[len(prefix_to_check):]
                            break
                    else:
                        if actual_item_name == sd_name_variant:
                            actual_item_name = ""
                            break
                        continue
                    break
                # Remove any remaining shared drive name prefix (defensive)
                for sd_name_variant in self.shared_drives_names:
                    for sep in ['\\', '/']:
                        prefix_to_check = sd_name_variant + sep
                        if actual_item_name.startswith(prefix_to_check):
                            actual_item_name = actual_item_name[len(prefix_to_check):]
                # Only append shared drive name if base is root 
                if is_shared_drives_folder_itself:
                    # base_path_to_search is already a shared drives folder, just append the item name
                    path_variant = os.path.join(base_path_to_search, actual_item_name)
                    self.log.debug(f"Checking path variant (direct shared folder): {path_variant}")
                    if os.path.exists(path_variant):
                        self.log.info(f"Found source path: {path_variant}")
                        return path_variant
                else:
                    # base_path_to_search is a root, append shared drive name and then item name
                    for sd_name in self.shared_drives_names:
                        # Only append if actual_item_name is not empty
                        path_variant = os.path.join(base_path_to_search, sd_name, actual_item_name)
                        self.log.debug(f"Checking path variant (root + lang + item): {path_variant}")
                        if os.path.exists(path_variant):
                            self.log.info(f"Found source path: {path_variant}")
                            return path_variant
            else:
                # Not a shared drive path, treat as My Drive
                if not is_shared_drives_folder_itself:
                    path_variant = os.path.join(base_path_to_search, clean_path.lstrip('\\/'))
                    self.log.debug(f"Checking path variant (My Drive type): {path_variant}")
                    if os.path.exists(path_variant):
                        self.log.info(f"Found source path: {path_variant}")
                        return path_variant

        self.log.error(f"Could not locate path '{clean_path}' in any derived Google Drive locations.")
        return None
    
    def list_shared_drives(self):
        """List available shared drives on Windows"""
        drives = []
        potential_bases = []

        if self._shared_drives_path_override:
            self.log.debug(f"Using user-defined Shared Drives path for listing: {self._shared_drives_path_override}")
            potential_bases.append(self._shared_drives_path_override)

        # Find Google Drive mount points
        for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive_root = f"{drive_letter}:\\"
            if not os.path.exists(drive_root):
                continue
            for sd_name in self.shared_drives_names:
                shared_drive_folder = os.path.join(drive_root, sd_name)
                if os.path.exists(shared_drive_folder) and os.path.isdir(shared_drive_folder):
                    if shared_drive_folder not in potential_bases:
                        potential_bases.append(shared_drive_folder)
        
        if not potential_bases:
            self.log.warning("No potential Shared Drives folders found automatically. Prompting user.")
            user_selected_path = self._prompt_user_for_shared_drives_path()
            if user_selected_path:
                self._shared_drives_path_override = user_selected_path
                self.log.info(f"User selected Shared Drives path: {self._shared_drives_path_override}")
                potential_bases.append(self._shared_drives_path_override)
            else:
                self.log.error("User did not select a Shared Drives path. Cannot list shared drives.")
                return [] # User cancelled or closed dialog

        self.log.debug(f"Listing shared drives from bases: {potential_bases}")
        for sd_path in potential_bases:
            try:
                found = os.listdir(sd_path)
                # Filter out non-directories and hidden items
                current_drives = [d for d in found if os.path.isdir(os.path.join(sd_path, d)) and not d.startswith('.')]
                if current_drives: # If this path yields drives, add them and potentially return
                    drives.extend(d for d in current_drives if d not in drives) # Add new, unique drives
                    # We could return here if we only expect one shared drives location.
                    # If multiple locations are possible (e.g. multiple Google accounts mapped to letters),
                    # we might want to aggregate. For now, let's assume the first one found is canonical or user-picked.
                    # If an override is set, we expect that to be the one, so return its contents.
                    if self._shared_drives_path_override and sd_path == self._shared_drives_path_override:
                        return drives 
            except Exception as e:
                self.log.error(f"Error listing shared drives at {sd_path}: {e}")
        
        if drives:
            self.log.info(f"Found shared drives: {drives}")
        else:
            self.log.warning("No shared drives found in any detected or provided paths.")
        return list(set(drives)) # Return unique list of drives
    
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
        
        # Check if target drive letter already exists
        # Note: os.path.exists() might return False for network drives that aren't accessible
        # So we'll also check via other methods
        drive_exists = os.path.exists(target_path)
        
        # Also check if the drive letter is listed by the system
        if not drive_exists:
            try:
                # Use wmic to check if drive exists regardless of accessibility
                wmic_result = run_process([
                    "wmic", "logicaldisk", "where", f"deviceid='{drive_letter}:'", 
                    "get", "deviceid", "/format:csv"
                ], check=False)
                
                if wmic_result and wmic_result.stdout and f"{drive_letter.upper()}:" in wmic_result.stdout.upper():
                    drive_exists = True
                    self.log.debug(f"Drive {drive_letter}: detected via wmic even though not accessible via os.path.exists")
            except Exception as e:
                self.log.debug(f"Could not check drive existence via wmic: {e}")
        
        if drive_exists:
            try:
                # First check if it's a SUBST mapping
                result = run_process(["subst"], check=False)
                existing_mapping = None
                
                if result and drive_letter + ":" in result.stdout:
                    for line in result.stdout.splitlines():
                        if line.startswith(drive_letter + ":"):
                            existing_mapping = line.split("=>", 1)[1].strip() if "=>" in line else None
                            break
                    
                    if existing_mapping == source_path:
                        self.log.info(f"Drive {drive_letter}: is already mapped to {source_path}")
                        return True
                    else:
                        self.log.warning(f"Drive {drive_letter}: is already mapped via SUBST to {existing_mapping}. Cannot create AYON mapping to {source_path}")
                        self.alert_drive_in_use(drive_letter, f"{existing_mapping} (SUBST)", source_path)
                        return False
                
                # If not a SUBST mapping, check if it's a network drive or other mapping
                if not existing_mapping:
                    # Try to determine what type of drive it is
                    try:
                        # Use wmic to get drive information
                        wmic_result = run_process([
                            "wmic", "logicaldisk", "where", f"deviceid='{drive_letter}:'", 
                            "get", "providername,drivetype", "/format:csv"
                        ], check=False)
                        
                        if wmic_result and wmic_result.stdout:
                            lines = [line.strip() for line in wmic_result.stdout.splitlines() if line.strip()]
                            for line in lines:
                                if f"{drive_letter.upper()}:" in line.upper():
                                    parts = line.split(',')
                                    if len(parts) >= 3:
                                        drive_type = parts[1].strip() if len(parts) > 1 else ""
                                        provider_name = parts[2].strip() if len(parts) > 2 else ""
                                        
                                        if drive_type == "4" and provider_name:  # Network drive
                                            existing_mapping = f"{provider_name} (Network Drive)"
                                        elif drive_type:
                                            type_names = {"2": "Floppy", "3": "Local Disk", "4": "Network Drive", "5": "CD-ROM"}
                                            existing_mapping = f"{type_names.get(drive_type, f'Type {drive_type}')}"
                                        break
                    except Exception as wmic_error:
                        self.log.debug(f"Could not get drive info via wmic: {wmic_error}")
                        existing_mapping = "Unknown drive mapping"
                    
                    if existing_mapping:
                        self.log.warning(f"Drive {drive_letter}: is already in use by {existing_mapping}. Cannot create AYON mapping to {source_path}")
                        self.alert_drive_in_use(drive_letter, existing_mapping, source_path)
                        return False
                
            except Exception as e:
                self.log.error(f"Error checking existing drive mapping: {e}")
                # If we can't determine the existing mapping but drive exists, assume conflict
                self.log.warning(f"Drive {drive_letter}: appears to be in use but could not determine what is using it. Cannot create AYON mapping to {source_path}")
                self.alert_drive_in_use(drive_letter, "Unknown existing mapping", source_path)
                return False
        
        # Create the mapping with simple SUBST command
        try:
            # Use subprocess with hidden window
            result = subprocess.run(
                ["subst", f"{drive_letter}:", source_path], 
                check=False,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                self.log.info(f"Successfully mapped drive {drive_letter}: to {source_path}")
                return True
            else:
                error_msg = result.stderr.strip() if result.stderr else f"Return code: {result.returncode}"
                if result.stdout:
                    error_msg += f" | Output: {result.stdout.strip()}"
                
                # Check if this is a "drive already in use" error
                if (result.returncode == 1 and result.stdout and 
                    ("Invalid parameter" in result.stdout or "already exists" in result.stdout.lower())):
                    
                    # Try to get information about what's using the drive
                    try:
                        wmic_result = run_process([
                            "wmic", "logicaldisk", "where", f"deviceid='{drive_letter}:'", 
                            "get", "providername,drivetype", "/format:csv"
                        ], check=False)
                        
                        existing_mapping = "Unknown"
                        if wmic_result and wmic_result.stdout:
                            lines = [line.strip() for line in wmic_result.stdout.splitlines() if line.strip()]
                            for line in lines:
                                if f"{drive_letter.upper()}:" in line.upper():
                                    parts = line.split(',')
                                    if len(parts) >= 3:
                                        drive_type = parts[1].strip() if len(parts) > 1 else ""
                                        provider_name = parts[2].strip() if len(parts) > 2 else ""
                                        
                                        if drive_type == "4" and provider_name:  # Network drive
                                            existing_mapping = f"{provider_name} (Network Drive)"
                                        elif drive_type:
                                            type_names = {"2": "Floppy", "3": "Local Disk", "4": "Network Drive", "5": "CD-ROM"}
                                            existing_mapping = f"{type_names.get(drive_type, f'Type {drive_type}')}"
                                        break
                        
                        self.log.error(f"Drive {drive_letter}: is already in use by {existing_mapping}. Cannot create AYON mapping to {source_path}")
                        self.alert_drive_in_use(drive_letter, existing_mapping, source_path)
                        return False
                    except Exception as check_error:
                        self.log.debug(f"Could not determine what's using drive {drive_letter}: {check_error}")
                
                self.log.error(f"Failed to create drive mapping. Error: {error_msg}")
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
        if not desired_mount.endswith(':\\'):
            desired_mount += ":\\"
        
        # If drive already at desired letter, all good
        if current_mount == desired_mount:
            self.log.debug(f"Google Drive already mounted at {desired_mount}")
            return True
        
        show_notifications = self.settings.get("show_mount_mismatch_notifications", False)
        if show_notifications:
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
        # Get suggestions for alternative drive letters
        available_drives = self._get_available_drive_letters()
        suggestions = ", ".join(available_drives[:5]) if available_drives else "none available"
        
        message = (
            f"Drive {drive_letter}: is already in use and cannot be mapped!\n\n"
            f"Currently used by: {current_mapping}\n"
            f"AYON needs to map: {desired_mapping}\n\n"
            f"To resolve this conflict:\n"
            f"• Disconnect the existing {drive_letter}: mapping\n"
            f"• Or remap it to an available drive letter\n\n"
            f"Available drive letters: {suggestions}\n\n"
            f"For network drives: Use 'net use {drive_letter}: /delete' to disconnect,\n"
            f"then reconnect to a different letter."
        )
        
        self.log.warning(f"Drive conflict: {message}")
        
        # Try to show a GUI alert
        try:
            ctypes.windll.user32.MessageBoxW(0, message, "AYON Google Drive - Drive Conflict", 0x30)  # Warning icon
        except Exception as e:
            self.log.debug(f"Could not show GUI alert: {e}")
            
    def _get_available_drive_letters(self):
        """Get list of available drive letters"""
        available = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if not os.path.exists(f"{letter}:\\"):
                available.append(f"{letter}:")
        return available

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
                        text=True,
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