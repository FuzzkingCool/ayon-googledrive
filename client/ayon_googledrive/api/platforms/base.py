from ayon_googledrive.logger import log

class GDrivePlatformBase:
    """Base class for platform-specific Google Drive operations"""
    
    def __init__(self):
        self.log = log
    
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