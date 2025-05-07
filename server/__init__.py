try:
    from ayon_server.addons import BaseServerAddon
    from .settings import GDriveSettings, DEFAULT_GDRIVE_SETTINGS  # Use relative import

    class GoogleDrive(BaseServerAddon):
        settings_model = GDriveSettings
    
        async def get_default_settings(self):
            settings_model_cls = self.get_settings_model()
            return settings_model_cls(**DEFAULT_GDRIVE_SETTINGS)
    print("AYON GoogleDrive server addon registered successfully")
except Exception as e:
    import traceback
    try:
        from ayon_googledrive.logger import log
        log.error(f"ERROR registering GoogleDrive server addon: {e}")
        log.error(traceback.format_exc())
    except Exception:
        print(f"ERROR registering GoogleDrive server addon: {e}")
        traceback.print_exc()