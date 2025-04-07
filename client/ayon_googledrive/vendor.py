import os
import sys
import platform
import tempfile
import shutil
import time
import urllib.request
import urllib.error
import ssl
from pathlib import Path

from ayon_core.lib import Logger
from ayon_core.settings import get_project_settings

class GDriveInstaller:
    """Downloads and manages Google Drive installers"""
    
    def __init__(self):
        self.log = Logger.get_logger(self.__class__.__name__)
        self.os_type = platform.system()
        self._temp_dir = None
        self.download_urls = self._get_download_urls()
    
    def _get_download_urls(self):
        """Get download URLs from settings"""
        # Default URLs in case settings aren't available
        default_urls = {
            "Windows": "https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe",
            "Darwin": "https://dl.google.com/drive-file-stream/GoogleDrive.dmg",
            "Linux": "https://dl.google.com/drive-file-stream/GoogleDrive.deb"
        }
        
        try:
            # Get settings
            settings = get_project_settings()
            addon_settings = settings.get("ayon_googledrive", {})
            download_urls = addon_settings.get("download_url", {})
            
            # Map settings keys to platform names
            platform_map = {
                "windows": "Windows",
                "macos": "Darwin",
                "linux": "Linux"
            }
            
            # Build dictionary with platform names as keys
            urls = {}
            for key, platform_name in platform_map.items():
                url = download_urls.get(key, default_urls[platform_name])
                urls[platform_name] = url
                
            return urls
            
        except Exception as e:
            self.log.warning(f"Could not load download URLs from settings: {e}")
            return default_urls
    
    def get_installer_path(self):
        """Download and return path to the Google Drive installer for current platform"""
        # Check if we have a URL for this platform
        if self.os_type not in self.download_urls or not self.download_urls[self.os_type]:
            self.log.error(f"No Google Drive installer URL available for {self.os_type}")
            return None
            
        # Create temp directory if needed
        if not self._temp_dir:
            self._temp_dir = tempfile.mkdtemp(prefix="ayon_googledrive_")
            
        # Download the installer
        download_url = self.download_urls[self.os_type]
        file_name = os.path.basename(download_url)
        installer_path = os.path.join(self._temp_dir, file_name)
        
        self.log.info(f"Downloading Google Drive installer from {download_url}")
        
        try:
            # Some environments have SSL certificate issues
            context = ssl._create_unverified_context()
            
            # Download with progress tracking
            with urllib.request.urlopen(download_url, context=context) as response:
                file_size = int(response.info().get('Content-Length', 0))
                downloaded = 0
                
                with open(installer_path, 'wb') as out_file:
                    block_size = 8192
                    last_time = time.time()
                    
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                            
                        out_file.write(buffer)
                        downloaded += len(buffer)
                        
                        # Show progress every second
                        current_time = time.time()
                        if current_time - last_time > 1:
                            if file_size > 0:
                                percent = downloaded * 100 / file_size
                                self.log.info(f"Downloaded {downloaded / 1024 / 1024:.1f} MB "
                                             f"({percent:.1f}%)")
                            else:
                                self.log.info(f"Downloaded {downloaded / 1024 / 1024:.1f} MB")
                            last_time = current_time
            
            self.log.info(f"Google Drive installer downloaded to {installer_path}")
            return installer_path
            
        except urllib.error.URLError as e:
            self.log.error(f"Failed to download Google Drive installer: {e}")
            return None
        except Exception as e:
            self.log.error(f"Error downloading Google Drive installer: {e}")
            return None
    
    def cleanup(self):
        """Clean up temporary files"""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
                self._temp_dir = None
                self.log.debug("Temporary installation files cleaned up")
            except Exception as e:
                self.log.error(f"Error cleaning up temporary files: {e}")