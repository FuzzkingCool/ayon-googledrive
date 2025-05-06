import os
import platform
import subprocess
import tempfile
from pathlib import Path

from ayon_api import get_addon_studio_settings

from ..version import __version__ as version
from ayon_googledrive.api.logger import log

def get_settings():
    """Get Google Drive settings from AYON"""
    try:        
        settings = get_addon_studio_settings("ayon_googledrive", version)
        return settings.get("ayon_googledrive", {})
    except Exception as e:
        log.warning(f"Failed to get settings from AYON: {e}")
        return {}

def normalize_path(path):
    """Normalize a path for the current platform"""
    if not path:
        return ""
    
    return os.path.normpath(path)

def clean_relative_path(path):
    """Clean a relative path by removing leading slashes"""
    if not path:
        return ""
        
    if platform.system() == "Windows":
        if path.startswith("\\"):
            return path.lstrip("\\")
    else:
        if path.startswith("/"):
            return path.lstrip("/")
    return path

def create_directory_if_not_exists(path):
    """Create a directory if it doesn't exist"""
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            return True
        except Exception as e:
            log.error(f"Failed to create directory {path}: {e}")
            return False
    return True

def is_symlink_to(link_path, target_path):
    """Check if a symlink points to the expected target"""
    if not os.path.islink(link_path):
        return False
        
    try:
        return os.path.samefile(os.readlink(link_path), target_path)
    except Exception:
        return False

def run_process(args, check=False, **kwargs):
    """Run a subprocess with proper error handling"""
    try:
        if platform.system() == "Windows":
            # Hide command window on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            
            # Add CREATE_NO_WINDOW flag
            creation_flags = subprocess.CREATE_NO_WINDOW
            
            return subprocess.run(
                args,
                check=check,
                text=True,
                capture_output=True,
                startupinfo=startupinfo,
                creationflags=creation_flags,
                **kwargs
            )
        else:
            return subprocess.run(
                args,
                check=check,
                text=True,
                capture_output=True,
                **kwargs
            )
    except subprocess.SubprocessError as e:
        log.error(f"Process execution failed: {e}")
        return None