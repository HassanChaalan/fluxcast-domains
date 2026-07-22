"""Loading domain files and util lists, with duplicate-key detection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import (
    DISALLOWED_CNAMES_FILE,
    DOMAINS_DIR,
    INTERNAL_FILE,
    RESERVED_FILE,
    TRUSTED_FILE,
)


class DuplicateKeyError(ValueError):
    """Raised when a JSON object contains duplicate keys."""


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateKeyError(key)
        seen[key] = value
    return seen


def load_json(path: Path) -> Any:
    # object_pairs_hook rejects duplicate keys, which json.load would silently drop.
    with path.open(encoding="utf-8") as fh:
        return json.load(fh, object_pairs_hook=_no_duplicate_keys)


def iter_domain_files() -> list[Path]:
    if not DOMAINS_DIR.is_dir():
        return []
    return sorted(p for p in DOMAINS_DIR.glob("*.json"))


def domain_filenames() -> set[str]:
    return {p.name for p in iter_domain_files()}


def subdomain_of(path: Path) -> str:
    return path.name[: -len(".json")] if path.name.endswith(".json") else path.name


@dataclass(frozen=True)
class Lists:
    reserved: frozenset[str]
    internal: frozenset[str]
    disallowed_cnames: tuple[str, ...]
    trusted: tuple[dict[str, Any], ...]

    @property
    def trusted_ids(self) -> frozenset[str]:
        return frozenset(str(u["id"]) for u in self.trusted)

    @property
    def admin_ids(self) -> frozenset[str]:
        return frozenset(str(u["id"]) for u in self.trusted if u.get("admin"))


def load_lists() -> Lists:
    return Lists(
        reserved=frozenset(load_json(RESERVED_FILE)),
        internal=frozenset(load_json(INTERNAL_FILE)),
        disallowed_cnames=tuple(load_json(DISALLOWED_CNAMES_FILE)),
        trusted=tuple(load_json(TRUSTED_FILE)),
    )
