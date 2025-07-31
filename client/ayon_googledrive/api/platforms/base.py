# -*- coding: utf-8 -*-
import os
import logging
import locale
import platform
from typing import List, Optional, Dict, Any

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
    
    def __init__(self, settings=None):
        self.settings = settings
        self.log = logging.getLogger(self.__class__.__name__)
        # Cache for shared drive names to prevent repeated processing
        self._shared_drives_names_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes cache TTL

    def _debug_settings_structure(self):
        """Debug method to inspect settings structure - only called when needed"""
        if not self.log.isEnabledFor(logging.DEBUG):
            return
            
        self.log.debug("=== DEBUG: Complete Settings Structure ===")
        if self.settings:
            self.log.debug(f"Settings type: {type(self.settings)}")
            self.log.debug(f"Settings keys: {list(self.settings.keys())}")
            
            if "localization" in self.settings:
                localization = self.settings["localization"]
                self.log.debug(f"Localization type: {type(localization)}")
                self.log.debug(f"Localization keys: {list(localization.keys())}")
                
                if "shared_drive_names" in localization:
                    shared_drive_names = localization["shared_drive_names"]
                    self.log.debug(f"shared_drive_names type: {type(shared_drive_names)}")
                    self.log.debug(f"shared_drive_names value: {shared_drive_names}")
                    
                    if isinstance(shared_drive_names, list):
                        for i, item in enumerate(shared_drive_names):
                            self.log.debug(f"Item {i}: {item} (type: {type(item)})")
                            if isinstance(item, dict):
                                self.log.debug(f"  Item {i} keys: {list(item.keys())}")
        else:
            self.log.debug("No settings available")
        self.log.debug("=== END DEBUG ===")

    def _get_shared_drives_names(self):
        """Get shared drive names from settings or use defaults with caching"""
        import time
        
        # Check cache first
        current_time = time.time()
        if (self._shared_drives_names_cache is not None and 
            current_time - self._cache_timestamp < self._cache_ttl):
            return self._shared_drives_names_cache
        
        try:
            if self.settings and "localization" in self.settings:
                localization = self.settings["localization"]
                
                if "shared_drive_names" in localization:
                    shared_drive_names = localization["shared_drive_names"]
                    
                    if isinstance(shared_drive_names, list):
                        # Extract just the names from the settings structure
                        names = []
                        
                        for item in shared_drive_names:
                            if isinstance(item, dict):
                                # Handle the new structure where shared_drives_names is a list
                                if "shared_drives_names" in item:
                                    shared_names = item["shared_drives_names"]
                                    
                                    if isinstance(shared_names, list):
                                        names.extend(shared_names)
                                    elif isinstance(shared_names, str):
                                        names.append(shared_names)
                                
                                # Handle legacy structure for backward compatibility
                                elif "shared_drives_name" in item:
                                    names.append(item["shared_drives_name"])
                            
                            elif isinstance(item, str):
                                names.append(item)
                        
                        if names:
                            # Cache the result
                            self._shared_drives_names_cache = names
                            self._cache_timestamp = current_time
                            return names
                        else:
                            self.log.warning("No shared drive names extracted from settings")
                    else:
                        self.log.warning(f"Shared drive names is not a list: {type(shared_drive_names)}")
                else:
                    self.log.warning("No 'shared_drive_names' found in localization settings")
            else:
                self.log.warning("No 'localization' found in settings")
        except Exception as e:
            self.log.warning(f"Error getting shared drive names from settings: {e}")
        
        # Fallback to default names
        self._shared_drives_names_cache = self.default_shared_drives_names
        self._cache_timestamp = current_time
        return self.default_shared_drives_names
    
    def clear_shared_drives_cache(self):
        """Clear the shared drives names cache to force refresh"""
        self._shared_drives_names_cache = None
        self._cache_timestamp = 0
    
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
    
    def get_system_language_info(self):
        """Get system language and locale information"""
        try:
            # Get system locale
            system_locale = locale.getlocale()
            system_language = locale.getdefaultlocale()
            
            # Get platform info
            system_platform = platform.system()
            system_release = platform.release()
            
            # Get additional locale info
            try:
                preferred_encoding = locale.getpreferredencoding()
            except:
                preferred_encoding = "unknown"
            
            # Try to get locale from environment variables as fallback
            env_locale = None
            for env_var in ['LANG', 'LC_ALL', 'LC_MESSAGES']:
                if env_var in os.environ:
                    env_locale = os.environ[env_var]
                    break
            
            # Format locale info more meaningfully
            locale_str = "unknown"
            if system_locale[0]:
                locale_str = system_locale[0]
            elif system_language[0]:
                locale_str = system_language[0]
            elif env_locale:
                # Parse environment locale (e.g., "en_US.UTF-8" -> "en_US")
                locale_str = env_locale.split('.')[0] if '.' in env_locale else env_locale
            
            encoding_str = "unknown"
            if system_locale[1] and system_locale[1] != 'unknown':
                encoding_str = system_locale[1]
            elif preferred_encoding and preferred_encoding != 'unknown':
                encoding_str = preferred_encoding
            elif env_locale and '.' in env_locale:
                encoding_str = env_locale.split('.')[1]
            
            return {
                'system_locale': system_locale,
                'system_language': system_language,
                'system_platform': system_platform,
                'system_release': system_release,
                'preferred_encoding': preferred_encoding,
                'locale_display': locale_str,
                'encoding_display': encoding_str
            }
        except Exception as e:
            self.log.warning(f"Error getting system language info: {e}")
            return {
                'system_locale': ('unknown', 'unknown'),
                'system_language': ('unknown', 'unknown'),
                'system_platform': 'unknown',
                'system_release': 'unknown',
                'preferred_encoding': 'unknown',
                'locale_display': 'unknown',
                'encoding_display': 'unknown'
            }
    
    def debug_path_formation(self):
        """Debug method to show all paths being checked for Google Drive and shared drives"""
        # Get system language info
        lang_info = self.get_system_language_info()
        self.log.info(f"Platform: {lang_info['system_platform']} {lang_info['system_release']}, Locale: {lang_info['locale_display']}, Encoding: {lang_info['encoding_display']}")
        
        # Get shared drive names
        shared_names = self._get_shared_drives_names()
        self.log.info(f"Checking {len(shared_names)} shared drive name variants")
        
        # Platform-specific path checking will be implemented in subclasses