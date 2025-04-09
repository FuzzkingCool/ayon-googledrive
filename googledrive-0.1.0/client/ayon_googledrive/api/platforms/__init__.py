import platform

def get_platform_handler():
    """Get the appropriate platform handler for the current OS"""
    system = platform.system()
    
    if system == "Windows":
        from .windows import GDriveWindowsPlatform
        return GDriveWindowsPlatform()
    elif system == "Darwin":
        from .macos import GDriveMacOSPlatform
        return GDriveMacOSPlatform()
    elif system == "Linux":
        from .linux_generic import GDriveLinuxPlatform
        return GDriveLinuxPlatform()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")