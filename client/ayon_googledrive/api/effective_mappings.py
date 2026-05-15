# -*- coding: utf-8 -*-
"""Resolve drive mappings per project for the current user (access groups + conflicts)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import ayon_api

_LOG = logging.getLogger(__name__)

_MAPPING_TARGET_FIELDS = ("windows_target", "macos_target", "linux_target")


def _strip(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _project_access_groups(user_data: dict[str, Any], project_name: str) -> list[str]:
    ag = user_data.get("accessGroups") or {}
    if project_name in ag:
        raw = ag[project_name]
        return list(raw) if isinstance(raw, (list, tuple)) else []
    pl = project_name.lower()
    for key, raw in ag.items():
        if isinstance(key, str) and key.lower() == pl:
            return list(raw) if isinstance(raw, (list, tuple)) else []
    return []


def _user_has_implicit_all_groups(user_data: dict[str, Any]) -> bool:
    """True for admin/manager: satisfy non-empty mapping ``access_groups`` without DB lists.

    Admins and managers often have no ``data.accessGroups`` project keys; they still
    need project settings fetched so studio overrides apply. Per-mapping visibility
    still requires non-empty ``access_groups`` on the row; empty list stays hidden.
    """
    return bool(user_data.get("isAdmin") or user_data.get("isManager"))


def _match_projects_for_user(
    projects: list[dict[str, Any]],
    user_data: dict[str, Any],
) -> list[str]:
    """Projects where the user has a non-empty accessGroups entry."""
    names: list[str] = []
    ag = user_data.get("accessGroups") or {}
    if not ag:
        return names

    for proj in projects:
        pname = proj.get("name")
        if not pname:
            continue
        user_ags = _project_access_groups(user_data, pname)
        if user_ags:
            names.append(pname)
    return names


@dataclass
class MappingConflict:
    """Same mount target used with different source paths across projects."""

    platform_field: str
    target: str
    entries: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class EffectiveMappingsResult:
    mappings: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[MappingConflict] = field(default_factory=list)


def resolve_effective_mappings(
    addon_name: str,
    addon_version: str,
    *,
    variant: str | None = None,
    use_site: bool = True,
) -> EffectiveMappingsResult:
    """Filter mappings by access groups and detect cross-project target conflicts."""
    if variant is None:
        try:
            variant = ayon_api.get_default_settings_variant()
        except Exception:
            variant = "production"

    result = EffectiveMappingsResult()

    try:
        user = ayon_api.get_user()
    except Exception:
        return result

    user_data = user.get("data") or {}
    implicit_all_groups = _user_has_implicit_all_groups(user_data)
    skipped_no_access_groups = 0
    skipped_no_role_match = 0

    projects = list(ayon_api.get_projects(active=True))

    if implicit_all_groups:
        project_names = [p.get("name") for p in projects if p.get("name")]
    else:
        project_names = _match_projects_for_user(projects, user_data)
        if not project_names:
            _LOG.info(
                "googledrive effective_mappings: included=%d names=%s "
                "skipped_no_access_groups_configured=%d skipped_no_role_match=%d",
                0,
                [],
                skipped_no_access_groups,
                skipped_no_role_match,
            )
            return result

    candidates: list[dict[str, Any]] = []
    for pname in sorted(project_names):
        try:
            settings = ayon_api.get_addon_project_settings(
                addon_name,
                addon_version,
                pname,
                variant=variant,
                use_site=use_site,
            )
        except Exception:
            continue

        user_ags = set(_project_access_groups(user_data, pname))
        for raw in settings.get("mappings") or []:
            if not isinstance(raw, dict):
                continue
            required = set(raw.get("access_groups") or [])
            if not required:
                skipped_no_access_groups += 1
                continue
            if not implicit_all_groups and not required.intersection(user_ags):
                skipped_no_role_match += 1
                continue
            row = dict(raw)
            row["_project"] = pname
            candidates.append(row)

    if not candidates:
        _LOG.info(
            "googledrive effective_mappings: included=%d names=%s "
            "skipped_no_access_groups_configured=%d skipped_no_role_match=%d",
            0,
            [],
            skipped_no_access_groups,
            skipped_no_role_match,
        )
        return result

    buckets: dict[str, dict[str, list[tuple[str, str, dict[str, Any]]]]] = {
        f: {} for f in _MAPPING_TARGET_FIELDS
    }
    for c in candidates:
        pname = c.get("_project", "")
        src = _strip(c.get("source_path"))
        for platform_key in _MAPPING_TARGET_FIELDS:
            t = _strip(c.get(platform_key))
            if not t:
                continue
            buckets[platform_key].setdefault(t, []).append((pname, src, c))

    conflict_targets: dict[str, set[str]] = {f: set() for f in _MAPPING_TARGET_FIELDS}
    for platform_key in _MAPPING_TARGET_FIELDS:
        for tgt, triples in buckets[platform_key].items():
            sources = {s for _, s, _ in triples}
            if len(sources) > 1:
                conflict_targets[platform_key].add(tgt)
                pairs = sorted({(p, s) for p, s, _ in triples})
                result.conflicts.append(
                    MappingConflict(
                        platform_field=platform_key,
                        target=tgt,
                        entries=pairs,
                    )
                )

    filtered: list[dict[str, Any]] = []
    for c in candidates:
        skip = False
        for platform_key in _MAPPING_TARGET_FIELDS:
            t = _strip(c.get(platform_key))
            if t and t in conflict_targets[platform_key]:
                skip = True
                break
        if not skip:
            filtered.append(c)

    dedup_keys: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for c in sorted(filtered, key=lambda x: str(x.get("_project", ""))):
        key = (
            _strip(c.get("windows_target")),
            _strip(c.get("macos_target")),
            _strip(c.get("linux_target")),
            _strip(c.get("source_path")),
        )
        if key in dedup_keys:
            continue
        dedup_keys.add(key)
        clean = {k: v for k, v in c.items() if k != "_project"}
        out.append(clean)

    result.mappings = out
    included_names = [
        str(m.get("name") or "").strip() or "(unnamed)" for m in out
    ]
    _LOG.info(
        "googledrive effective_mappings: included=%d names=%s "
        "skipped_no_access_groups_configured=%d skipped_no_role_match=%d",
        len(out),
        included_names,
        skipped_no_access_groups,
        skipped_no_role_match,
    )
    return result
