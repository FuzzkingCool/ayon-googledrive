import re
from typing import Dict, List, Any, Optional, Union
# from pydantic import Field, validator
from ayon_server.settings import BaseSettingsModel, SettingsField

# AYON Addon settings for Google Drive integration
 
DEFAULT_GDRIVE_SETTINGS = {
    "googledrive_path": {
        "windows": "C:\\Program Files\\Google\\Drive File Stream\\",
        "macos": "/Applications/Google Drive.app",
        "linux": "/home/user/Google Drive"
    },
    "googledrive_mount": {
        "windows": "G:\\",
        "macos": "/Volumes/GoogleDrive",
        "linux": "/mnt/google_drive"
    },
    "mappings": [
        {
            "name": "Projects",
            "source_path": "\\Shared drives\\Projects",
            "windows_target": "Z:\\",
            "macos_target": "/Volumes/Projects",
            "linux_target": "/mnt/projects"
        },
        {
            "name": "Renders",
            "source_path": "\\Shared drives\\Renders",
            "windows_target": "Y:\\",
            "macos_target": "/Volumes/Renders",
            "linux_target": "/mnt/renders"
        }
    ],
    "install_googledrive": True,
    "mount_googledrive": True,
    "download_url": {
        "windows": "https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe",
        "macos": "https://dl.google.com/drive-file-stream/GoogleDrive.dmg",
        "linux": "https://dl.google.com/drive-file-stream/GoogleDrive.deb"
    }
}

# Define nested configuration models for better structure
class GDriveExecutablePaths(BaseSettingsModel):
    """Google Drive paths for different platforms."""
    windows: str = SettingsField(
        default_factory=lambda: "C:\\Program Files\\Google\\Drive File Stream\\",
        title="Windows",
        description="Path to Google Drive installation on Windows"
    )
    
    macos: str = SettingsField(
        default_factory=lambda: "/Applications/Google Drive.app",
        title="macOS",
        description="Path to Google Drive installation on macOS"
    )
    
    linux: str = SettingsField(
        default_factory=lambda: "/home/user/Google Drive",
        title="Linux",
        description="Path to Google Drive installation on Linux"
    )


class GDriveMountPaths(BaseSettingsModel):
    """Mount points for Google Drive on different platforms."""
    windows: str = SettingsField(
        default_factory=lambda: "G:\\",
        title="Windows",
        description="Drive letter for Google Drive on Windows"
    )
    
    macos: str = SettingsField(
        default_factory=lambda: "/Volumes/GoogleDrive",
        title="macOS",
        description="Mount point for Google Drive on macOS"
    )
    
    linux: str = SettingsField(
        default_factory=lambda: "/mnt/google_drive",
        title="Linux",
        description="Mount point for Google Drive on Linux"
    )


class GDriveMapping(BaseSettingsModel):
    """Single drive mapping configuration."""
    name: str = SettingsField(
        "",
        title="Mapping Name",
        description="Descriptive name for this drive mapping (use only letters, numbers, underscores, dots, or hyphens)"
    )
    
    source_path: str = SettingsField(
        "",
        title="Source Path",
        description="Path in Google Drive (e.g. \\Shared drives\\Projects)"
    )
    
    windows_target: str = SettingsField(
        "",
        title="Windows Target",
        description="Windows target drive letter or path (e.g. Z:\\)"
    )
    
    macos_target: str = SettingsField(
        "",
        title="macOS Target",
        description="macOS target mount path (e.g. /Volumes/Projects)"
    )
    
    linux_target: str = SettingsField(
        "",
        title="Linux Target",
        description="Linux target mount path (e.g. /mnt/projects)"
    )
    
 
class GDriveDownloadUrls(BaseSettingsModel):
    """URLs for downloading Google Drive installers."""
    windows: str = SettingsField(
        default_factory=lambda: "https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe",
        title="Windows",
        description="URL to download Google Drive for Windows"
    )
    
    macos: str = SettingsField(
        default_factory=lambda: "https://dl.google.com/drive-file-stream/GoogleDrive.dmg",
        title="macOS",
        description="URL to download Google Drive for macOS"
    )
    
    linux: str = SettingsField(
        default_factory=lambda: "https://dl.google.com/drive-file-stream/GoogleDrive.deb",
        title="Linux",
        description="URL to download Google Drive for Linux"
    )


# Main settings class
class GDriveSettings(BaseSettingsModel):
    """Settings model for Google Drive integration."""

    enabled: bool = SettingsField(
        True,
        title="Enabled",
        description="Enable or disable the Google Drive addon"
    )
    
    install_googledrive: bool = SettingsField(
        True,
        title="Install Google Drive",
        description="Allow AYON to install Google Drive if not present"
    )

    mount_googledrive: bool = SettingsField(
        True,
        title="Mount Google Drive",
        description="Allow AYON to configure Google Drive mount points"
    )
    
    googledrive_path: GDriveExecutablePaths = SettingsField(
        default_factory=GDriveExecutablePaths,
        title="Google Drive Installation Paths",
        description="Paths to Google Drive application on different platforms"
    )

    googledrive_mount: GDriveMountPaths = SettingsField(
        default_factory=GDriveMountPaths,
        title="Google Drive Mount Point",
        description="Default mount points for Google Drive on different platforms"
    )
    
    mappings: List[GDriveMapping] = SettingsField(
        default_factory=list,
        title="Drive Mappings",
        description="Configure mappings between Google Drive paths and local drive letters/paths"
    )
    
    download_url: GDriveDownloadUrls = SettingsField(
        default_factory=GDriveDownloadUrls,
        title="Google Drive Download URLs",
        description="URLs to download Google Drive installers"
    )

