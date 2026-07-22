"""Semantic validation rules, shared by the pytest suite and the sync.

Each ``validate_*`` function returns a list of error strings; empty means valid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError

from . import ROOT_DOMAIN
from .constants import (
    PROXYABLE_RECORD_TYPES,
    USABLE_RECORD_TYPES,
    VALID_RECORD_TYPES,
    EMAIL_REGEX,
    HOSTNAME_REGEX,
    REDIRECT_PATH_REGEX,
    fqdn,
    is_hexadecimal,
    is_public_ipv4,
    is_public_ipv6,
    is_valid_hostname,
)
from .loader import Lists
from .models import Domain

BLOCKED_FIELDS = (
    "domain",
    "internal",
    "proxy",
    "reserved",
    "services",
    "subdomain",
    "nested",
    "record",
)
GITHUB_NOREPLY_SUFFIX = "@users.noreply.github.com"


@dataclass
class ValidationContext:
    lists: Lists
    filenames: set[str]
    data_by_subdomain: dict[str, dict[str, Any]] = field(default_factory=dict)


def validate_filename(subdomain: str, lists: Lists) -> list[str]:
    f = f"{subdomain}.json"
    errors: list[str] = []

    if subdomain != subdomain.lower():
        errors.append(f"{f}: file name must be all lowercase")
    if ".fluxcast.dev" in subdomain:
        errors.append(f"{f}: file name should not contain .fluxcast.dev")
    if "--" in subdomain:
        errors.append(f"{f}: file name must not contain consecutive hyphens")
    if not HOSTNAME_REGEX.match(fqdn(subdomain)):
        errors.append(
            f"{f}: FQDN must be 1-253 chars: letters, numbers, dots and "
            f"non-consecutive hyphens only"
        )

    if subdomain in lists.reserved or any(
        subdomain.endswith(f".{r}") for r in lists.reserved
    ):
        errors.append(f"{f}: subdomain name is reserved")
    if subdomain in lists.internal or any(
        subdomain.endswith(f".{i}") for i in lists.internal
    ):
        errors.append(f"{f}: subdomain name is registered internally")

    if subdomain.split(".")[-1].startswith("_"):
        errors.append(f"{f}: root subdomains must not start with an underscore")

    return errors


def validate_structure(subdomain: str, data: Any) -> list[str]:
    f = f"{subdomain}.json"
    errors: list[str] = []

    if not isinstance(data, dict):
        return [f"{f}: top-level JSON must be an object"]

    for blocked in BLOCKED_FIELDS:
        if blocked in data:
            errors.append(f"{f}: disallowed field: {blocked}")

    try:
        Domain.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "<root>"
            errors.append(f"{f}: {loc}: {err['msg']}")
        return errors

    email = data.get("owner", {}).get("email")
    if email is not None:
        if not EMAIL_REGEX.match(email):
            errors.append(f"{f}: owner email is not a valid email address")
        if email.endswith(GITHUB_NOREPLY_SUFFIX):
            errors.append(f"{f}: owner email must not be a GitHub no-reply address")

    return errors


def _validate_a(f: str, records: list, proxied: bool) -> list[str]:
    errors = []
    for i, rec in enumerate(records):
        if not isinstance(rec, str) or not is_public_ipv4(rec, proxied):
            errors.append(f"{f}: invalid or non-public IPv4 for A at index {i}")
    return errors


def _validate_aaaa(f: str, records: list) -> list[str]:
    errors = []
    for i, rec in enumerate(records):
        if not isinstance(rec, str) or not is_public_ipv6(rec):
            errors.append(f"{f}: invalid or non-public IPv6 for AAAA at index {i}")
    return errors


def _validate_mx(f: str, records: list) -> list[str]:
    errors = []
    for i, rec in enumerate(records):
        if isinstance(rec, str):
            if not is_valid_hostname(rec):
                errors.append(f"{f}: invalid hostname for MX at index {i}")
        elif isinstance(rec, dict):
            if not is_valid_hostname(rec.get("target", "")):
                errors.append(f"{f}: invalid target for MX at index {i}")
            prio = rec.get("priority")
            if not (isinstance(prio, int) and 0 <= prio <= 65535):
                errors.append(f"{f}: invalid priority for MX at index {i}")
        else:
            errors.append(f"{f}: MX at index {i} must be a string or object")
    return errors


def _valid_int(value: Any, lo: int, hi: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi


def _validate_object_records(f: str, key: str, records: list) -> list[str]:
    errors = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            errors.append(f"{f}: {key} at index {i} must be an object")
            continue
        if key == "CAA":
            if rec.get("tag") not in ("issue", "issuewild", "iodef"):
                errors.append(f"{f}: invalid tag for CAA at index {i}")
            val = rec.get("value")
            if not isinstance(val, str) or not (is_valid_hostname(val) or val == ";"):
                errors.append(f"{f}: CAA value must be a hostname or ';' at index {i}")
        elif key == "DS":
            if not _valid_int(rec.get("key_tag"), 0, 65535):
                errors.append(f"{f}: invalid key_tag for DS at index {i}")
            if not _valid_int(rec.get("algorithm"), 0, 255):
                errors.append(f"{f}: invalid algorithm for DS at index {i}")
            if not _valid_int(rec.get("digest_type"), 0, 255):
                errors.append(f"{f}: invalid digest_type for DS at index {i}")
            if not is_hexadecimal(str(rec.get("digest", ""))):
                errors.append(f"{f}: invalid digest for DS at index {i}")
        elif key == "SRV":
            for fld in ("priority", "weight", "port"):
                if not _valid_int(rec.get(fld), 0, 65535):
                    errors.append(f"{f}: invalid {fld} for SRV at index {i}")
            if not is_valid_hostname(rec.get("target", "")):
                errors.append(f"{f}: invalid target for SRV at index {i}")
        elif key == "TLSA":
            for fld in ("usage", "selector", "matching_type"):
                if not _valid_int(rec.get(fld), 0, 255):
                    errors.append(f"{f}: invalid {fld} for TLSA at index {i}")
            if not is_hexadecimal(str(rec.get("certificate", ""))):
                errors.append(f"{f}: invalid certificate for TLSA at index {i}")
    return errors


def _validate_cname(f: str, subdomain: str, value: Any, lists: Lists) -> list[str]:
    errors = []
    if not isinstance(value, str):
        return [f"{f}: CNAME value must be a string"]
    if not is_valid_hostname(value):
        errors.append(f"{f}: invalid hostname for CNAME")
    if value == fqdn(subdomain):
        errors.append(f"{f}: CNAME cannot point to itself")
    if value == ROOT_DOMAIN:
        errors.append(f"{f}: CNAME cannot point to {ROOT_DOMAIN}")
    for disallowed in lists.disallowed_cnames:
        if disallowed.startswith("."):
            if value.endswith(disallowed):
                errors.append(f"{f}: CNAME cannot end with {disallowed}")
        elif value == disallowed:
            errors.append(f"{f}: CNAME cannot be {disallowed}")
    return errors


def _validate_url(f: str, subdomain: str, value: Any) -> list[str]:
    if not isinstance(value, str):
        return [f"{f}: URL value must be a string"]
    if not (value.startswith("http://") or value.startswith("https://")):
        return [f"{f}: URL must start with http:// or https://"]
    try:
        host = urlparse(value).netloc
    except ValueError:
        return [f"{f}: invalid URL for URL record"]
    if not host:
        return [f"{f}: invalid URL for URL record"]
    if host == fqdn(subdomain):
        return [f"{f}: URL cannot point to itself"]
    return []


def _validate_redirect_config(f: str, subdomain: str, data: dict) -> list[str]:
    errors = []
    cfg = data.get("redirect_config") or {}
    custom_paths = cfg.get("custom_paths") or {}
    url_record = data.get("records", {}).get("URL")

    for i, (path, target) in enumerate(custom_paths.items()):
        msg = f"{f}: custom path in redirect_config"
        if not REDIRECT_PATH_REGEX.match(path):
            errors.append(
                f"{msg} must start with '/', contain only [A-Za-z0-9-_./] and "
                f"not end with '/' at index {i}"
            )
        if not (2 <= len(path) <= 255):
            errors.append(f"{msg} must be 2-255 chars at index {i}")
        if not isinstance(target, str):
            errors.append(f"{msg} target must be a string at index {i}")
            continue
        if target == url_record:
            errors.append(f"{msg} should differ from the URL record at index {i}")
        if not (target.startswith("http://") or target.startswith("https://")):
            errors.append(f"{msg} must start with http:// or https:// at index {i}")
            continue
        if urlparse(target).netloc == fqdn(subdomain):
            errors.append(f"{msg} cannot point to itself at index {i}")
    return errors


def validate_records(subdomain: str, data: dict, lists: Lists) -> list[str]:
    f = f"{subdomain}.json"
    errors: list[str] = []
    records = data.get("records")
    if not isinstance(records, dict):
        return [f"{f}: records must be an object"]

    proxied = bool(data.get("proxied"))
    keys = list(records.keys())

    for key in keys:
        if key not in VALID_RECORD_TYPES:
            errors.append(f"{f}: invalid record type: {key}")

    if "CNAME" in keys:
        if not proxied and len(keys) != 1:
            errors.append(
                f"{f}: CNAME cannot be combined with other records unless proxied"
            )
        if proxied and ("A" in keys or "AAAA" in keys):
            errors.append(f"{f}: CNAME cannot be combined with A or AAAA records")
    if "NS" in keys:
        if not (len(keys) == 1 or (len(keys) == 2 and "DS" in keys)):
            errors.append(f"{f}: NS records may only be combined with DS records")
    if "DS" in keys and "NS" not in keys:
        errors.append(f"{f}: DS records must be combined with NS records")
    if "URL" in keys and ({"A", "AAAA", "CNAME"} & set(keys)):
        errors.append(f"{f}: URL cannot be combined with A, AAAA or CNAME records")

    if data.get("redirect_config"):
        if not ("URL" in keys or proxied):
            errors.append(
                f"{f}: redirect_config requires a URL record or a proxied domain"
            )
        if data["redirect_config"].get("redirect_paths") and "URL" not in keys:
            errors.append(f"{f}: redirect_config.redirect_paths requires a URL record")

    for key, value in records.items():
        if key in ("A", "AAAA", "MX", "NS"):
            if not isinstance(value, list):
                errors.append(f"{f}: {key} value must be an array")
                continue
            if key == "A":
                errors += _validate_a(f, value, proxied)
            elif key == "AAAA":
                errors += _validate_aaaa(f, value)
            elif key == "MX":
                errors += _validate_mx(f, value)
            elif key == "NS":
                for i, rec in enumerate(value):
                    if not (isinstance(rec, str) and is_valid_hostname(rec)):
                        errors.append(f"{f}: invalid hostname for NS at index {i}")
        elif key in ("CAA", "DS", "SRV", "TLSA"):
            if not isinstance(value, list):
                errors.append(f"{f}: {key} value must be an array")
                continue
            errors += _validate_object_records(f, key, value)
        elif key == "CNAME":
            errors += _validate_cname(f, subdomain, value, lists)
        elif key == "URL":
            errors += _validate_url(f, subdomain, value)
        elif key == "TXT":
            values = value if isinstance(value, list) else [value]
            for i, rec in enumerate(values):
                if not isinstance(rec, str):
                    errors.append(f"{f}: TXT value must be a string at index {i}")

    if data.get("redirect_config"):
        errors += _validate_redirect_config(f, subdomain, data)

    return errors


def validate_proxy(subdomain: str, data: dict) -> list[str]:
    if not data.get("proxied"):
        return []
    if not any(k in PROXYABLE_RECORD_TYPES for k in data.get("records", {})):
        return [
            f"{subdomain}.json: proxied is true but no proxy-able record "
            f"({', '.join(sorted(PROXYABLE_RECORD_TYPES))}) is present"
        ]
    return []


def validate_root_usable(subdomain: str, data: dict) -> list[str]:
    if "." in subdomain or subdomain.startswith("_"):
        return []
    if not any(k in USABLE_RECORD_TYPES for k in data.get("records", {})):
        return [
            f"{subdomain}.json: root subdomains must have at least one "
            f"A, AAAA, CNAME, MX, NS or URL record"
        ]
    return []


def validate_nesting(subdomain: str, ctx: ValidationContext) -> list[str]:
    f = f"{subdomain}.json"
    errors: list[str] = []
    parts = subdomain.split(".")

    for i in range(1, len(parts)):
        parent = ".".join(parts[i:])
        if parent.startswith("_"):
            continue
        if f"{parent}.json" not in ctx.filenames:
            errors.append(f'{f}: parent subdomain "{parent}" does not exist')
            continue
        if ctx.data_by_subdomain.get(parent, {}).get("records", {}).get("NS"):
            errors.append(f'{f}: parent subdomain "{parent}" has NS records')

    root_subdomain = parts[-1]
    if root_subdomain != subdomain:
        data = ctx.data_by_subdomain.get(subdomain, {})
        root_data = ctx.data_by_subdomain.get(root_subdomain, {})
        this_owner = str(data.get("owner", {}).get("username", "")).lower()
        root_owner = str(root_data.get("owner", {}).get("username", "")).lower()
        if root_data and this_owner != root_owner:
            errors.append(f"{f}: owner does not match the parent subdomain's owner")

    return errors


def validate_domain(subdomain: str, data: Any, ctx: ValidationContext) -> list[str]:
    errors = validate_filename(subdomain, ctx.lists)
    structural = validate_structure(subdomain, data)
    errors += structural
    # Only run record rules once the structure is sound enough to trust.
    if not structural and isinstance(data, dict):
        errors += validate_records(subdomain, data, ctx.lists)
        errors += validate_proxy(subdomain, data)
        errors += validate_root_usable(subdomain, data)
    return errors
