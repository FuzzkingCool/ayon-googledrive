import os
import subprocess
import shutil
import time
from pathlib import Path
from ayon_googledrive.api.platforms.base import GDrivePlatformBase
from ayon_googledrive.api.lib import run_process, normalize_path, clean_relative_path

class GDriveLinuxPlatform(GDrivePlatformBase):
    """Linux platform handler for Google Drive operations"""
    
    def __init__(self, settings=None):
        """Initialize the Linux platform handler.
        
        Args:
            settings (dict, optional): Settings dictionary from GDriveManager.
        """
        super(GDriveLinuxPlatform, self).__init__(settings)
        self.settings = settings  # Store the settings passed from GDriveManager
 
        # Detect desktop environment for better UI integration
        self.desktop_env = self._detect_desktop_environment()
        self.log.debug(f"Detected desktop environment: {self.desktop_env}")
    
    def _detect_desktop_environment(self):
        """Detect the current desktop environment"""
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        if desktop:
            if 'gnome' in desktop:
                return 'gnome'
            elif 'kde' in desktop:
                return 'kde'
            elif 'xfce' in desktop:
                return 'xfce'
            else:
                return desktop
        return 'unknown'
    
    def _show_notification(self, title, message):
        """Show a desktop notification using the appropriate method"""
        try:
            if self.desktop_env == 'gnome':
                cmd = ["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                      "--object-path", "/org/freedesktop/Notifications",
                      "--method", "org.freedesktop.Notifications.Notify",
                      "AYON", "0", "", title, message, "[]", "{}", "5000"]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif self.desktop_env == 'kde':
                cmd = ["kdialog", "--title", title, "--passivepopup", message, "5"]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                # Fallback to notify-send which works on most desktop environments
                cmd = ["notify-send", "--expire-time=5000", title, message]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.log.debug(f"Failed to show desktop notification: {e}")
    
    def is_googledrive_installed(self):
        """Check if Google Drive is installed on Linux"""
        # Check for official Google Drive app
        official_paths = [
            "/usr/bin/google-drive-fs",
            "/opt/google/drive/drive",
            "/opt/google/drive-fs/drive-fs"
        ]
        
        # Check for alternative implementations
        alternative_paths = [
            "/usr/bin/google-drive-ocamlfuse",  # FUSE-based client
            "/usr/local/bin/google-drive-ocamlfuse",
            "/usr/bin/rclone",  # rclone can mount Google Drive
            "/usr/local/bin/rclone",
            "/usr/bin/drive",  # drive CLI tool
            "/usr/local/bin/drive"
        ]
        
        # Check application launchers
        desktop_files = [
            "/usr/share/applications/google-drive.desktop",
            "/usr/share/applications/google-drive-fs.desktop",
            os.path.expanduser("~/.local/share/applications/google-drive.desktop")
        ]
        
        # Check any of these paths
        all_paths = official_paths + alternative_paths + desktop_files
        installed_paths = [path for path in all_paths if os.path.exists(path)]
        
        if installed_paths:
            self.log.debug(f"Found Google Drive at: {installed_paths[0]}")
            return True
        
        # If no binary/launcher found, check for scripts or custom installations
        custom_checks = [
            # Check if gdfuse is in PATH
            lambda: shutil.which("google-drive-ocamlfuse") is not None,
            # Check if rclone has a google drive remote configured
            lambda: self._check_rclone_remote_exists()
        ]
        
        for check in custom_checks:
            try:
                if check():
                    self.log.debug("Found custom Google Drive installation")
                    return True
            except Exception:
                pass
                
        return False
    
    def _check_rclone_remote_exists(self):
        """Check if rclone has a Google Drive remote configured"""
        try:
            result = run_process(["rclone", "listremotes"], check=False)
            if result and result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "google" in line.lower() or "drive" in line.lower():
                        return True
            return False
        except Exception:
            return False
    
    def is_googledrive_running(self):
        """Check if Google Drive is currently running on Linux"""
        try:
            # Check for official Google Drive processes
            drive_processes = ["google-drive", "GoogleDriveFS", "drive-fs"]
            
            # Check for alternative clients
            alt_processes = ["google-drive-ocamlfuse", "rclone mount"]
            
            all_processes = drive_processes + alt_processes
            
            # Check each process
            for process in all_processes:
                result = run_process(["pgrep", "-f", process], check=False)
                if result and result.returncode == 0:
                    self.log.debug(f"Found running process: {process}")
                    return True
            
            # Check for mount points as fallback
            mount_points = self._find_gdrive_mount_points()
            if mount_points:
                self.log.debug(f"Found Google Drive mount points: {mount_points}")
                return True
                
            return False
        except Exception as e:
            self.log.error(f"Error checking if Google Drive is running: {e}")
            return False
    
    def _find_gdrive_mount_points(self):
        """Find all potential Google Drive mount points"""
        try:
            result = run_process(["mount"], check=False)
            if not result or result.returncode != 0:
                return []
            
            # Look for Google Drive related mounts
            mount_points = []
            for line in result.stdout.splitlines():
                lower_line = line.lower()
                if any(kw in lower_line for kw in ["google", "drive", "gdrive", "gdfuse"]):
                    parts = line.split()
                    if len(parts) >= 3:
                        mount_point = parts[2]
                        mount_points.append(mount_point)
            
            return mount_points
        except Exception as e:
            self.log.error(f"Error finding mount points: {e}")
            return []
    
    def is_user_logged_in(self):
        """Check if a user is logged into Google Drive on Linux"""
        # Check for official Google Drive login
        config_paths = [
            os.path.expanduser("~/.config/google-drive-fs"),
            os.path.expanduser("~/.gdfuse/default/config"),
            os.path.expanduser("~/.config/rclone/rclone.conf")
        ]
        
        for path in config_paths:
            if os.path.exists(path):
                self.log.debug(f"Found Google Drive config at: {path}")
                return True
        
        # Check active mounts as fallback
        mount_points = self._find_gdrive_mount_points()
        if mount_points:
            for point in mount_points:
                # Try to access the mount point to verify it's functional
                try:
                    os.listdir(point)
                    self.log.debug(f"Found accessible Google Drive mount point: {point}")
                    return True
                except Exception:
                    continue
        
        return False
    
    def start_googledrive(self):
        """Start Google Drive application on Linux"""
        try:
            # Try different methods of starting Google Drive in order of preference
            methods = [
                # 1. Official Google Drive desktop app
                {"cmd": ["google-drive"], "name": "Google Drive Desktop"},
                {"cmd": ["gtk-launch", "google-drive.desktop"], "name": "Google Drive Desktop (launcher)"},
                
                # 2. Google Drive FUSE client - preferred alternative
                {"cmd": ["google-drive-ocamlfuse", os.path.expanduser("~/google-drive")], "name": "Google Drive FUSE"},
                
                # 3. Rclone mount if available
                {"cmd": self._get_rclone_mount_cmd(), "name": "Rclone Google Drive mount"}
            ]
            
            for method in methods:
                cmd = method["cmd"]
                name = method["name"]
                
                if not cmd:  # Skip if command is None (e.g. rclone not configured)
                    continue
                    
                try:
                    if isinstance(cmd, list) and shutil.which(cmd[0]):
                        # Create mount directory if needed for FUSE clients
                        if name in ["Google Drive FUSE", "Rclone Google Drive mount"]:
                            mount_dir = cmd[1] if len(cmd) > 1 else ""
                            if mount_dir and not os.path.exists(mount_dir):
                                os.makedirs(mount_dir, exist_ok=True)
                        
                        # Run the command
                        self.log.debug(f"Starting Google Drive with {name}: {' '.join(cmd)}")
                        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        
                        # Give it a moment to start
                        time.sleep(2)
                        if self.is_googledrive_running():
                            self._show_notification("Google Drive Started", f"{name} has been started and is now running.")
                            return True
                except FileNotFoundError:
                    self.log.debug(f"Command not found: {cmd[0]}")
                except Exception as e:
                    self.log.warning(f"Failed to start {name}: {e}")
                    
            # If we're here, none of the methods worked
            self.log.error("Could not find any method to start Google Drive")
            self._show_notification("Google Drive Error", "Failed to start Google Drive. Please install a compatible client.")
            return False
            
        except Exception as e:
            self.log.error(f"Error starting Google Drive: {e}")
            return False
    
    def _get_rclone_mount_cmd(self):
        """Get rclone mount command if configured"""
        try:
            # Check if rclone is installed
            if not shutil.which("rclone"):
                return None
                
            # Check if there's a Google Drive remote
            result = run_process(["rclone", "listremotes"], check=False)
            if result and result.returncode == 0:
                gdrive_remote = None
                for line in result.stdout.splitlines():
                    if "google" in line.lower() or "drive" in line.lower():
                        gdrive_remote = line.strip()
                        break
                
                if gdrive_remote:
                    mount_dir = os.path.expanduser("~/google-drive")
                    return ["rclone", "mount", gdrive_remote, mount_dir, "--daemon"]
            
            return None
        except Exception:
            return None
    
    def install_googledrive(self, installer_path):
        """Install Google Drive on Linux"""
        try:
            self.log.info(f"Installer path: {installer_path}")
            # Different installation methods depending on the installer type
            if installer_path.endswith(".deb"):
                # Debian/Ubuntu
                if shutil.which("pkexec"):
                    cmd = ["pkexec", "apt-get", "install", "-y", installer_path]
                else:
                    cmd = ["sudo", "apt-get", "install", "-y", installer_path]
            elif installer_path.endswith(".rpm"):
                # Fedora/CentOS/RHEL
                if shutil.which("pkexec"):
                    cmd = ["pkexec", "dnf", "install", "-y", installer_path]
                else:
                    cmd = ["sudo", "dnf", "install", "-y", installer_path]
            elif installer_path.endswith(".AppImage"):
                # Make AppImage executable and move to applications directory
                os.chmod(installer_path, 0o755)
                target_path = os.path.expanduser("~/.local/bin/google-drive")
                shutil.copy2(installer_path, target_path)
                cmd = [target_path, "--appimage-extract-and-run", "--install"]
            else:
                # Assume it's a script or binary installer
                os.chmod(installer_path, 0o755)
                cmd = ["sudo", installer_path]
            
            self.log.debug(f"Running Google Drive installer: {installer_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.log.error(f"Installation failed: {result.stderr}")
                from ayon_googledrive.ui.notifications import show_notification
                show_notification(
                    "Google Drive Installation Failed",
                    f"Google Drive installation failed: {result.stderr[:100]}...\nInstaller path: {installer_path}",
                    level="error"
                )
                return False
            
            self.log.debug("Google Drive installation completed")
            from ayon_googledrive.ui.notifications import show_notification
            show_notification(
                "Google Drive Installation Complete",
                "Google Drive has been installed successfully.",
                level="info"
            )
            # For alternative client installation
            self._configure_alternative_client()
            return self._verify_installation()
        except Exception as e:
            self.log.error(f"Error installing Google Drive: {e}")
            from ayon_googledrive.ui.notifications import show_notification
            show_notification(
                "Google Drive Installation Error",
                f"An error occurred: {str(e)}\nInstaller path: {installer_path}",
                level="error"
            )
            return False
    
    def _configure_alternative_client(self):
        """Configure alternative client if official client not available"""
        try:
            # Check if we need to set up google-drive-ocamlfuse
            if self.is_googledrive_installed() and shutil.which("google-drive-ocamlfuse"):
                # Create mount point
                mount_dir = os.path.expanduser("~/google-drive")
                if not os.path.exists(mount_dir):
                    os.makedirs(mount_dir, exist_ok=True)
                    
                # Create autostart entry
                autostart_dir = os.path.expanduser("~/.config/autostart")
                if not os.path.exists(autostart_dir):
                    os.makedirs(autostart_dir, exist_ok=True)
                    
                desktop_file = os.path.join(autostart_dir, "google-drive-ocamlfuse.desktop")
                with open(desktop_file, "w") as f:
                    f.write(f"""[Desktop Entry]
Type=Application
Exec=google-drive-ocamlfuse {mount_dir}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=Google Drive FUSE
Comment=Mount Google Drive automatically
""")
                os.chmod(desktop_file, 0o755)
        except Exception as e:
            self.log.warning(f"Failed to configure alternative client: {e}")
    
    def _verify_installation(self):
        """Verify Google Drive was successfully installed"""
        # Wait a moment for installation to complete
        time.sleep(2)
        return self.is_googledrive_installed()
    
    def find_googledrive_mount(self):
        """Find the Google Drive mount point on Linux"""
        # Check common mount points
        common_paths = [
            "/mnt/google-drive",
            "/mnt/google_drive", 
            "/media/google-drive",
            os.path.expanduser("~/google-drive"),
            os.path.expanduser("~/GoogleDrive"),
            os.path.expanduser("~/Google Drive")
        ]
        
        # First check configured mount points from settings
        # Then check if any of the common paths exist and are accessible
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.R_OK):
                try:
                    # Make sure it's actually a mount point or has content
                    contents = os.listdir(path)
                    if contents:
                        self.log.debug(f"Found Google Drive mount point at {path} with contents")
                        return path
                except Exception:
                    continue
                    
        # As a fallback, check mount points from system
        mount_points = self._find_gdrive_mount_points()
        for point in mount_points:
            if os.path.exists(point) and os.access(point, os.R_OK):
                return point
                
        self.log.warning("Could not find Google Drive mount point")
        return None
    
    def find_source_path(self, relative_path):
        """Find the full source path for a relative path in Google Drive on Linux"""
        clean_path = clean_relative_path(relative_path).replace("\\", "/")
        
        # Find the base Google Drive mount point
        mount_point = self.find_googledrive_mount()
        if not mount_point:
            self.log.error("Could not find Google Drive mount point")
            return None
        
        self.log.debug(f"Looking for relative path '{clean_path}' in {mount_point}")
        
        # Get shared drive names from settings
        shared_drives_names = self._get_shared_drives_names()
        
        # Try various path patterns
        path_patterns = [
            # Direct path
            os.path.join(mount_point, clean_path),
        ]
        
        # Add patterns for each shared drive name variant
        for sd_name in shared_drives_names:
            # With shared drive name prefix
            path_patterns.append(os.path.join(mount_point, sd_name, clean_path.replace(f"{sd_name}/", "")))
            
            # Handle case where clean_path starts with "Shared drives/" but we need to use the localized name
            if clean_path.startswith("Shared drives/"):
                path_patterns.append(os.path.join(mount_point, sd_name, clean_path.replace("Shared drives/", "")))
        
        # Try stripping My Drive prefix if present
        path_patterns.append(os.path.join(mount_point, clean_path.replace("My Drive/", "")))
        
        for path in path_patterns:
            if os.path.exists(path):
                self.log.debug(f"Found source path: {path}")
                return path
        
        # Additional logging to help diagnose issues
        self.log.warning(f"Could not find '{clean_path}' in Google Drive mount. Contents of mount point:")
        try:
            contents = os.listdir(mount_point)
            for item in contents:
                self.log.debug(f"- {item}")
            
            # Check for Shared drives folder using settings
            for sd_name in shared_drives_names:
                shared_drives_path = os.path.join(mount_point, sd_name)
                if os.path.exists(shared_drives_path):
                    shared_drives = os.listdir(shared_drives_path)
                    self.log.debug(f"Shared drives contents ({sd_name}): {shared_drives}")
        except Exception as e:
            self.log.warning(f"Error listing mount contents: {e}")
        
        self.log.error(f"Could not locate path '{clean_path}' in Google Drive")
        return None
    
    def list_shared_drives(self):
        """List available shared drives on Linux"""
        drives = []
        
        # Find the Google Drive mount point
        mount_point = self.find_googledrive_mount()
        if not mount_point:
            self.log.warning("Could not find Google Drive mount point")
            return drives
        
        # Get shared drive names from settings
        shared_drives_names = self._get_shared_drives_names()
        
        # Check for each shared drive name variant
        for sd_name in shared_drives_names:
            shared_drives_path = os.path.join(mount_point, sd_name)
            if os.path.exists(shared_drives_path) and os.path.isdir(shared_drives_path):
                try:
                    items = os.listdir(shared_drives_path)
                    drives = [d for d in items if os.path.isdir(os.path.join(shared_drives_path, d))]
                    if drives:
                        self.log.debug(f"Found shared drives at {shared_drives_path}: {drives}")
                        return drives
                except Exception as e:
                    self.log.error(f"Error listing shared drives at {shared_drives_path}: {e}")
        
        self.log.warning("No shared drives found")
        return drives
    
    def create_mapping(self, source_path, target_path, mapping_name=None):
        """Create a symlink mapping on Linux"""
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
                    self.log.warning(f"Path {target_path} is linked to {current_target}. Cannot create AYON mapping to {source_path}")
                    self.alert_path_in_use(target_path, f"Existing symlink to {current_target}", source_path, mapping_name)
                    return False
            else:
                # Target exists but is not a symlink
                self.log.warning(f"Path {target_path} exists but is not a symlink. Cannot create AYON mapping to {source_path}")
                self.alert_path_in_use(target_path, "File or directory", source_path, mapping_name)
                return False
        
        # Create or update symlink
        try:
            # Check parent directory exists
            parent_dir = os.path.dirname(target_path)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except PermissionError:
                    self.log.error(f"Permission denied creating directory: {parent_dir}")
                    self.show_admin_instructions(source_path, target_path)
                    return False
        
            # Create symlink
            try:
                os.symlink(source_path, target_path)
                self.log.debug(f"Created symlink: {target_path} -> {source_path}")
                
                # Create desktop shortcut if mapping name provided
                if mapping_name:
                    self._create_desktop_shortcut(target_path, mapping_name)
                
                return True
            except PermissionError:
                self.log.error(f"Permission denied creating symlink at {target_path}")
                self.show_admin_instructions(source_path, target_path)
                return False
            
        except Exception as e:
            self.log.error(f"Error creating symlink: {e}")
            return False
    
    def _create_desktop_shortcut(self, target_path, name):
        """Create a desktop shortcut for the mapping"""
        try:
            desktop_dir = os.path.expanduser("~/Desktop")
            if os.path.exists(desktop_dir):
                shortcut_path = os.path.join(desktop_dir, f"{name}.desktop")
                with open(shortcut_path, "w") as f:
                    f.write(f"""[Desktop Entry]
Type=Link
Name={name}
URL=file://{target_path}
Icon=folder-google-drive
""")
                os.chmod(shortcut_path, 0o755)
                self.log.debug(f"Created desktop shortcut: {shortcut_path}")
        except Exception as e:
            self.log.debug(f"Failed to create desktop shortcut: {e}")
    
    def ensure_mount_point(self, desired_mount):
        """Ensure Google Drive is mounted at the desired location on Linux"""
        # Find actual Google Drive mount point
        googledrive_path = self.find_googledrive_mount()
        
        if not googledrive_path:
            self.log.error("Google Drive not found mounted on this system")
            return False
            
        # Check if the desired mount already exists correctly
        if os.path.normpath(googledrive_path) == os.path.normpath(desired_mount):
            self.log.debug(f"Google Drive already mounted at desired location: {desired_mount}")
            return True
            
        # Check if symlink exists and points to the right place
        if os.path.islink(desired_mount) and os.readlink(desired_mount) == googledrive_path:
            self.log.debug(f"Symlink already exists: {desired_mount} -> {googledrive_path}")
            return True
            
        # Create symlink if it doesn't exist or points elsewhere
        try:
            # Need to check for root permissions for certain paths
            if (desired_mount.startswith("/mnt/") or desired_mount.startswith("/media/")) and \
               not os.access(os.path.dirname(desired_mount), os.W_OK):
                self.log.error(f"Root permissions required to create symlink at {desired_mount}")
                self.show_admin_instructions(googledrive_path, desired_mount)
                return False
                
            # Remove existing symlink if it points elsewhere
            if os.path.exists(desired_mount):
                if os.path.islink(desired_mount):
                    os.unlink(desired_mount)
                else:
                    self.log.error(f"{desired_mount} exists and is not a symlink")
                    return False
            
            # Create parent directory if needed
            parent_dir = os.path.dirname(desired_mount)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except PermissionError:
                    self.log.error(f"Permission denied creating directory: {parent_dir}")
                    self.show_admin_instructions(googledrive_path, desired_mount)
                    return False
                    
            # Create the symlink
            os.symlink(googledrive_path, desired_mount)
            self.log.debug(f"Created symlink: {desired_mount} -> {googledrive_path}")
            return True
            
        except Exception as e:
            self.log.error(f"Failed to create symlink: {e}")
            return False
    
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
    
    def show_admin_instructions(self, source_path, target_path):
        """Show instructions for operations requiring admin privileges"""
        command = f"sudo ln -sf '{source_path}' '{target_path}'"
        self.log.info(f"Admin privileges required. To create the symlink manually: {command}")
        
        message = (
            f"AYON Google Drive requires administrator privileges to create a symlink.\n\n"
            f"Target path: {target_path}\n"
            f"Source path: {source_path}\n\n"
            f"Please run this command in terminal:\n{command}\n\n"
            f"Then restart AYON to complete the setup."
        )
        
        # Try to show a graphical notification based on desktop environment
        try:
            if self.desktop_env == 'gnome' and shutil.which("zenity"):
                subprocess.Popen(["zenity", "--info", "--text", message, "--title", "AYON Google Drive - Admin Required"], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif self.desktop_env == 'kde' and shutil.which("kdialog"):
                subprocess.Popen(["kdialog", "--title", "AYON Google Drive - Admin Required", "--msgbox", message],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                # Try generic tools
                if shutil.which("zenity"):
                    subprocess.Popen(["zenity", "--info", "--text", message, "--title", "AYON Google Drive - Admin Required"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif shutil.which("xmessage"):
                    subprocess.Popen(["xmessage", "-center", message],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.log.debug(f"Could not show GUI notification: {e}")
    
    def alert_path_in_use(self, path, current_usage, desired_target, mapping_name=None):
        """Alert the user about path conflicts"""
        # Get suggestions for alternative paths
        available_paths = self._get_alternative_paths(path)
        suggestions = ", ".join(available_paths[:3]) if available_paths else "none suggested"
        
        title = "AYON Google Drive - Path Conflict"
        if mapping_name:
            title += f" ({mapping_name})"
        
        message = (
            f"Path {path} is already in use and cannot be mapped!\n\n"
            f"Currently used by: {current_usage}\n"
            f"AYON needs to map: {desired_target}\n\n"
            f"To resolve this conflict:\n"
            f"• Remove or relocate the existing {path}\n"
            f"• Or use an alternative path\n\n"
            f"Alternative path suggestions: {suggestions}\n\n"
            f"For symlinks: Use 'rm {path}' to remove the existing symlink,\n"
            f"then restart AYON to create the correct mapping."
        )
        
        self.log.warning(f"Path conflict: {message}")
        self._show_notification(title, message)
        
        # Try to show a more detailed GUI dialog
        self._show_detailed_conflict_dialog(message, title)
        
    def _get_alternative_paths(self, original_path):
        """Get alternative path suggestions"""
        alternatives = []
        base_dir = os.path.dirname(original_path)
        base_name = os.path.basename(original_path)
        
        # Suggest numbered alternatives
        for i in range(2, 6):
            alt_path = os.path.join(base_dir, f"{base_name}_{i}")
            if not os.path.exists(alt_path):
                alternatives.append(alt_path)
        
        # Suggest alternative base directories
        common_alternatives = [
            f"/home/{os.environ.get('USER', 'user')}/ayon_mounts",
            "/tmp/ayon_mounts",
            f"/home/{os.environ.get('USER', 'user')}/Desktop"
        ]
        
        for alt in common_alternatives:
            alt_path = os.path.join(alt, base_name)
            if not os.path.exists(alt_path):
                alternatives.append(alt_path)
                
        return alternatives
        
    def _show_detailed_conflict_dialog(self, message, title):
        """Show a detailed conflict dialog using available GUI tools"""
        try:
            if self.desktop_env == 'gnome' and shutil.which("zenity"):
                subprocess.Popen([
                    "zenity", "--warning", "--text", message, "--title", title, "--width", "400"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif self.desktop_env == 'kde' and shutil.which("kdialog"):
                subprocess.Popen([
                    "kdialog", "--title", title, "--sorry", message
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif shutil.which("zenity"):
                subprocess.Popen([
                    "zenity", "--warning", "--text", message, "--title", title, "--width", "400"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.log.debug(f"Could not show detailed conflict dialog: {e}")
    
    def remove_all_mappings(self):
        """Remove all symlink mappings created by AYON"""
        try:
            # Get mappings from settings
            settings = self.addon.settings if hasattr(self, 'addon') else None
            
            if not settings:
                from ayon_googledrive.api.lib import get_settings
                settings = get_settings()
                
            mappings = settings.get("mappings", [])
            
            for mapping in mappings:
                target = mapping.get("linux_target", "")
                if target and os.path.exists(target) and os.path.islink(target):
                    self.log.debug(f"Removing symlink: {target}")
                    try:
                        os.unlink(target)
                        
                        # Also remove desktop shortcut if it exists
                        name = mapping.get("name", "")
                        if name:
                            shortcut_path = os.path.expanduser(f"~/Desktop/{name}.desktop")
                            if os.path.exists(shortcut_path):
                                os.unlink(shortcut_path)
                                
                    except Exception as e:
                        self.log.error(f"Failed to remove symlink {target}: {e}")
                        
            return True
        except Exception as e:
            self.log.error(f"Error removing mappings: {e}")
            return False
