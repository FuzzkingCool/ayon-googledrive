from ayon_googledrive.logger import log
from qtpy import QtWidgets
import os

class GDrivePlatformBase:
    # Default shared drive names (fallback if settings are not available)
    default_shared_drives_names = [
        "Shared drives",  # English
        "Shared Drives",  # English (alternative capitalization)
        "Drive partagés",  # French
        "Disques partagés",  # French (fr-FR)
        "Geteilte Ablagen",  # German
        "Drive condivisi",  # Italian
        "Unidades compartidas",  # Spanish (es and es-419)
        "Drives compartilhados",  # Portuguese (Brazil)
        "共享云端硬盘",  # Chinese (Simplified)
        "共用雲端硬碟",  # Chinese (Traditional)
        "共有ドライブ",  # Japanese
        "공유 드라이브",  # Korean
        "Gedeelde drives",  # Dutch
        "Общие диски",  # Russian
        "Dyski udostępnione",  # Polish
        "Delade enheter",  # Swedish
        "Delte drev",  # Danish
        "Delte enheter",  # Norwegian
    ]

    """Base class for platform-specific Google Drive operations"""
    
    def __init__(self, settings=None):
        self.log = log
        self._shared_drives_path_override = None
        self.settings = settings
    
    def _get_shared_drives_names(self):
        """Get shared drive names from settings or use defaults"""
        try:
            self.log.debug(f"Settings available: {self.settings is not None}")
            if self.settings:
                self.log.debug(f"Settings keys: {list(self.settings.keys())}")
                if "localization" in self.settings:
                    localization = self.settings["localization"]
                    self.log.debug(f"Localization keys: {list(localization.keys())}")
                    if "shared_drive_names" in localization:
                        shared_drive_names = localization["shared_drive_names"]
                        self.log.debug(f"Shared drive names from settings: {shared_drive_names}")
                        if isinstance(shared_drive_names, list):
                            # Extract just the names from the settings structure
                            names = []
                            for item in shared_drive_names:
                                self.log.debug(f"Processing item: {item}")
                                if isinstance(item, dict) and "shared_drives_names" in item:
                                    # Handle the new structure where shared_drives_names is a list
                                    shared_names = item["shared_drives_names"]
                                    if isinstance(shared_names, list):
                                        names.extend(shared_names)
                                    elif isinstance(shared_names, str):
                                        names.append(shared_names)
                                elif isinstance(item, dict) and "shared_drives_name" in item:
                                    # Handle legacy structure for backward compatibility
                                    names.append(item["shared_drives_name"])
                                elif isinstance(item, str):
                                    names.append(item)
                            if names:
                                self.log.debug(f"Using shared drive names from settings: {names}")
                                return names
                            else:
                                self.log.warning("No shared drive names extracted from settings")
                        else:
                            self.log.warning(f"Shared drive names is not a list: {type(shared_drive_names)}")
                    else:
                        self.log.warning("No 'shared_drive_names' found in localization settings")
                else:
                    self.log.warning("No 'localization' found in settings")
            else:
                self.log.warning("No settings available")
        except Exception as e:
            self.log.warning(f"Error getting shared drive names from settings: {e}")
        
        # Fallback to default names
        self.log.debug(f"Using default shared drive names: {self.default_shared_drives_names}")
        return self.default_shared_drives_names
    
    def is_googledrive_installed(self):
        """Check if Google Drive is installed on this platform"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def is_googledrive_running(self):
        """Check if Google Drive is currently running"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def is_user_logged_in(self):
        """Check if a user is logged into Google Drive"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def install_googledrive(self, installer_path):
        """Install Google Drive using the provided installer"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def start_googledrive(self):
        """Start Google Drive application"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def find_googledrive_mount(self):
        """Find the Google Drive mount point"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def find_source_path(self, relative_path):
        """Find the full source path for a relative path in Google Drive"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def list_shared_drives(self):
        """List available shared drives"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def create_mapping(self, source_path, target_path, mapping_name=None):
        """Create a mapping from source_path to target_path
        
        Args:
            source_path (str): Full path to source in Google Drive
            target_path (str): Target path where to map the source
            mapping_name (str, optional): Optional name for the mapping
        
        Returns:
            bool: True if mapping was created successfully
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def ensure_mount_point(self, desired_mount):
        """Ensure Google Drive is mounted at the desired location"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def check_mapping_exists(self, target_path):
        """Check if a mapping exists at the target path"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def check_mapping_valid(self, source_path, target_path):
        """Check if mapping from source to target is valid"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def show_admin_instructions(self, source_path, target_path):
        """Show instructions for operations requiring admin privileges"""
        raise NotImplementedError("Subclasses must implement this method")

    def _prompt_user_for_shared_drives_path(self):
        """Prompt the user to select their 'Shared Drives' folder."""
        app = QtWidgets.QApplication.instance()
        if not app:
            app = QtWidgets.QApplication([])

        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
        dialog.setWindowTitle("Select Your Google Shared Drives Folder")
        dialog.setLabelText(QtWidgets.QFileDialog.Accept, "Select Folder")
        
        start_path = "~"
        if hasattr(self, 'os_type'): # Check if os_type is available for platform-specific paths
            if self.os_type == "Darwin":
                start_path = os.path.expanduser("~/Library/CloudStorage/")
            elif self.os_type == "Windows":
                start_path = os.path.expanduser("~") # Default to home for Windows, can be refined
        
        start_path = os.path.expanduser(start_path)
        if not os.path.exists(start_path):
            start_path = os.path.expanduser("~") # Fallback to home

        dialog.setDirectory(start_path)

        if dialog.exec_():
            selected_path = dialog.selectedFiles()
            if selected_path:
                self.log.info(f"User selected path: {selected_path[0]}")
                return selected_path[0]
        return None