from ayon_server.addons import BaseServerAddon
from .settings import GDriveSettings, DEFAULT_GDRIVE_SETTINGS  # Use relative import

class GoogleDrive(BaseServerAddon):
    settings_model = GDriveSettings
  
    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_GDRIVE_SETTINGS)