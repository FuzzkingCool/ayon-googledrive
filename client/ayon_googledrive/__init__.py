import traceback

try:
    from ayon_googledrive.version import __version__
    from ayon_googledrive.addon import GDriveAddon
    from ayon_googledrive.api.gdrive_manager import GDriveManager

    print(f"Successfully loaded ayon_googledrive {__version__}")

    __all__ = (
        "__version__",
        "GDriveAddon",
        "GDriveManager"
    )
except Exception as e:
    print(f"ERROR loading ayon_googledrive: {e}")
    traceback.print_exc()