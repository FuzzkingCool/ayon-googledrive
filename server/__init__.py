try:
    from collections import defaultdict
    from ayon_server.addons import BaseServerAddon
    from ayon_server.events import EventStream
    from ayon_server.helpers.project_list import get_project_list
    from ayon_server.logging import logger
    from ayon_server.settings import BaseSettingsModel

    from .settings import GDriveSettings, DEFAULT_GDRIVE_SETTINGS
    from .settings.main import _MAPPING_TARGET_FIELDS

    class GoogleDrive(BaseServerAddon):
        settings_model = GDriveSettings

        async def get_default_settings(self):
            settings_model_cls = self.get_settings_model()
            return settings_model_cls(**DEFAULT_GDRIVE_SETTINGS)

        async def on_settings_changed(
            self,
            old_settings: BaseSettingsModel,
            new_settings: BaseSettingsModel,
            variant: str = "production",
            project_name: str | None = None,
            site_id: str | None = None,
            user_name: str | None = None,
        ) -> None:
            try:
                await self._audit_cross_project_mapping_conflicts(variant)
            except Exception:
                logger.error(
                    "googledrive mapping conflict audit failed",
                    exc_info=True,
                )

        async def _audit_cross_project_mapping_conflicts(self, variant: str) -> None:
            """Emit events when the same mount target maps to different sources."""
            projects = await get_project_list()
            active_projects = [p for p in projects if p.active]
            buckets: dict[str, dict[str, list[tuple[str, str]]]] = {
                f: defaultdict(list) for f in _MAPPING_TARGET_FIELDS
            }

            for proj in active_projects:
                settings = await self.get_project_settings(proj.name, variant=variant)
                if settings is None:
                    continue
                data = settings.dict()
                for m in data.get("mappings") or []:
                    src = (m.get("source_path") or "").strip()
                    for field in _MAPPING_TARGET_FIELDS:
                        t = (m.get(field) or "").strip()
                        if t:
                            buckets[field][t].append((proj.name, src))

            for field in _MAPPING_TARGET_FIELDS:
                for target, pairs in buckets[field].items():
                    sources = {sp for _, sp in pairs}
                    if len(sources) <= 1:
                        continue
                    description = (
                        f"googledrive: {field} {target!r} points to different "
                        f"source_path values across projects"
                    )
                    logger.error(description)
                    await EventStream.dispatch(
                        "googledrive.mappings.conflict",
                        description=description,
                        summary={
                            "addon": self.name,
                            "addon_version": self.version,
                            "field": field,
                            "target": target,
                            "entries": [
                                {"project": pn, "source_path": sp}
                                for pn, sp in sorted(pairs)
                            ],
                        },
                        payload={"variant": variant},
                    )

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
