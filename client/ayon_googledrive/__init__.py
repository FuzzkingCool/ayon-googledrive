import traceback

try:
    from ayon_googledrive.version import __version__
    from ayon_googledrive.addon import GDriveAddon
    from ayon_googledrive.api.gdrive_manager import GDriveManager
    from ayon_googledrive.logger import log

    log.info(f"Successfully loaded ayon_googledrive {__version__}")

    __all__ = (
        "__version__",
        "GDriveAddon",
        "GDriveManager"
    )
except Exception as e:
    import sys
    try:
        from ayon_googledrive.logger import log
        log.error(f"ERROR loading ayon_googledrive: {e}")
        log.error(traceback.format_exc())
    except Exception:
        print(f"ERROR loading ayon_googledrive: {e}")
        traceback.print_exc()