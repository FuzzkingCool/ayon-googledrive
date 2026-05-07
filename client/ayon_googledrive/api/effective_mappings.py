# -*- coding: utf-8 -*-
"""Resolve drive mappings per project for the current user (access groups + conflicts)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import ayon_api

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


def _bypass_access_group_mapping_filter(user_data: dict[str, Any]) -> bool:
    """True when server-side access group lists do not apply (same as YNPUT backend).

    Admins and managers often have no ``data.accessGroups`` project keys; drive mappings
    must still resolve so SUBST / path checks can run.
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
    ag_bypass = _bypass_access_group_mapping_filter(user_data)

    projects = list(ayon_api.get_projects(active=True))

    if ag_bypass:
        project_names = [p.get("name") for p in projects if p.get("name")]
    else:
        project_names = _match_projects_for_user(projects, user_data)
        if not project_names:
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
            if not ag_bypass:
                if not required.intersection(user_ags):
                    continue
            row = dict(raw)
            row["_project"] = pname
            candidates.append(row)

    if not candidates:
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
    return result
