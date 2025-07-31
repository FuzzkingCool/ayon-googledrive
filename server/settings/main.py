# -*- coding: utf-8 -*-
import re
from typing import Dict, List, Any, Optional, Union
# from pydantic import Field, validator
from ayon_server.settings import BaseSettingsModel, SettingsField

# AYON Addon settings for Google Drive integration
 
DEFAULT_GDRIVE_SETTINGS = {
    "googledrive_path": {
        "windows": "C:\\Program Files\\Google\\Drive File Stream\\*\\",
        "macos": "/Applications/Google Drive for desktop.app",  # Updated path for macOS 15+
        "linux": "/home/user/Google Drive"
    },
    "googledrive_mount": {
        "windows": "G:\\",
        "macos": "/Volumes/GoogleDrive",
        "linux": "/mnt/google_drive"
    },
    "localization": {
        "shared_drive_names": [
            {"name": "English", "locale_code": "en", "shared_drives_names": ["Shared drives", "Shared Drives"]},
            {"name": "French", "locale_code": "fr", "shared_drives_names": ["Drive partagés", "Drive partagé", "Disques partagés"]},
            {"name": "German", "locale_code": "de", "shared_drives_names": ["Geteilte Ablagen"]},
            {"name": "Italian", "locale_code": "it", "shared_drives_names": ["Drive condivisi"]},
            {"name": "Spanish (LatAm/ES)", "locale_code": "es", "shared_drives_names": ["Unidades compartidas"]},
            {"name": "Spanish (Latin America)", "locale_code": "es-419", "shared_drives_names": ["Unidades compartidas"]},
            {"name": "Portuguese (Brazil)", "locale_code": "pt-BR", "shared_drives_names": ["Drives compartilhados"]},
            {"name": "Chinese (Simplified)", "locale_code": "zh-CN", "shared_drives_names": ["共享云端硬盘"]},
            {"name": "Chinese (Traditional)", "locale_code": "zh-TW", "shared_drives_names": ["共用雲端硬碟"]},
            {"name": "Japanese", "locale_code": "ja", "shared_drives_names": ["共有ドライブ"]},
            {"name": "Korean", "locale_code": "ko", "shared_drives_names": ["공유 드라이브"]},
            {"name": "Dutch", "locale_code": "nl", "shared_drives_names": ["Gedeelde drives"]},
            {"name": "Russian", "locale_code": "ru", "shared_drives_names": ["Общие диски"]},
            {"name": "Polish", "locale_code": "pl", "shared_drives_names": ["Dyski udostępnione"]},
            {"name": "Swedish", "locale_code": "sv", "shared_drives_names": ["Delade enheter"]},
            {"name": "Danish", "locale_code": "da", "shared_drives_names": ["Delte drev"]},
            {"name": "Norwegian", "locale_code": "no", "shared_drives_names": ["Delte enheter"]},

        ]
    },
    "mappings": [
        {
            "name": "Projects",
            "source_path": "\\Shared drives\\Projects",
            "windows_target": "P:\\",
            "macos_target": "/Volumes/Projects",
            "linux_target": "/mnt/projects"
        },
        {
            "name": "Renders",
            "source_path": "\\Shared drives\\Renders",
            "windows_target": "R:\\",
            "macos_target": "/Volumes/Renders",
            "linux_target": "/mnt/renders"
        }
    ],
    "install_googledrive": False,
    "download_url": {
        "windows": "https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe",
        "macos": "https://dl.google.com/drive-file-stream/GoogleDrive.dmg",
        "linux": "https://dl.google.com/drive-file-stream/GoogleDrive.deb"
    },
    "show_mount_mismatch_notifications": False   
}

# Define nested configuration models for better structure
class SharedDriveName(BaseSettingsModel):
    """Single shared drive name configuration."""
    name: str = SettingsField(
        "",
        title="Name",
        description="Display name for this language entry"
    )
    
    locale_code: str = SettingsField(
        "",
        title="Locale Code",
        description="Language code (e.g. 'en', 'fr', 'es', 'de') that Drive for Desktop reads from the OS"
    )
    
    shared_drives_names: List[str] = SettingsField(
        default_factory=list,
        title="Shared Drives Names",
        description="The actual folder names as they appear in Google Drive (can be multiple variations)"
    )

    def __str__(self):
        """Return the name for display in AYON settings UI."""
        return self.name if self.name else "Unnamed Language"
    
    def __init__(self, **data):
        super().__init__(**data)
        # Set the name field to the language value if not provided
        if not self.name and self.locale_code:
            self.name = self.locale_code


class LocalizationSettings(BaseSettingsModel):
    """Localization settings for Google Drive integration."""
    shared_drive_names: List[SharedDriveName] = SettingsField(
        default_factory=lambda: [
            SharedDriveName(name="English", locale_code="en", shared_drives_names=["Shared drives", "Shared Drives"]),
            SharedDriveName(name="French", locale_code="fr", shared_drives_names=["Drive partagés", "Drive partagé", "Disques partagés"]),
            SharedDriveName(name="German", locale_code="de", shared_drives_names=["Geteilte Ablagen"]),
            SharedDriveName(name="Italian", locale_code="it", shared_drives_names=["Drive condivisi"]),
            SharedDriveName(name="Spanish (LatAm/ES)", locale_code="es", shared_drives_names=["Unidades compartidas"]),
            SharedDriveName(name="Spanish (Latin America)", locale_code="es-419", shared_drives_names=["Unidades compartidas"]),
            SharedDriveName(name="Portuguese (Brazil)", locale_code="pt-BR", shared_drives_names=["Drives compartilhados"]),
            SharedDriveName(name="Chinese (Simplified)", locale_code="zh-CN", shared_drives_names=["共享云端硬盘"]),
            SharedDriveName(name="Chinese (Traditional)", locale_code="zh-TW", shared_drives_names=["共用雲端硬碟"]),
            SharedDriveName(name="Japanese", locale_code="ja", shared_drives_names=["共有ドライブ"]),
            SharedDriveName(name="Korean", locale_code="ko", shared_drives_names=["공유 드라이브"]),
            SharedDriveName(name="Dutch", locale_code="nl", shared_drives_names=["Gedeelde drives"]),
            SharedDriveName(name="Russian", locale_code="ru", shared_drives_names=["Общие диски"]),
            SharedDriveName(name="Polish", locale_code="pl", shared_drives_names=["Dyski udostępnione"]),
            SharedDriveName(name="Swedish", locale_code="sv", shared_drives_names=["Delade enheter"]),
            SharedDriveName(name="Danish", locale_code="da", shared_drives_names=["Delte drev"]),
            SharedDriveName(name="Norwegian", locale_code="no", shared_drives_names=["Delte enheter"])
        ],
        title="Shared Drive Names",
        description="Names of shared drive folders in different languages"
    )


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
    
    auto_install_googledrive: bool = SettingsField(
        False,
        title="Auto-Install Google Drive",
        description="Allow AYON to auto-install Google Drive if not present"
    )
    
    auto_restart_googledrive: bool = SettingsField(
        True,
        title="Auto-Restart Google Drive",
        description="Allow AYON to auto-restart Google Drive if it isn't running"
    )
    
    show_mount_mismatch_notifications: bool = SettingsField(
        False,  # Disabled by default
        title="Show Mount Point Mismatch Notifications",
        description="Show notifications when Google Drive is mounted at a different drive letter than configured"
    )

    keep_symlinks_on_exit: bool = SettingsField(
        True,
        title="Keep Symlinks on Exit (MacOS)",
        description="Keep symlinks on exit (MacOS only)"
    )
    
    localization: LocalizationSettings = SettingsField(
        default_factory=LocalizationSettings,
        title="Localization",
        description="Localization settings for Google Drive integration"
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



