"""Translate domain files into Cloudflare records and diff against the zone.

Pure module (no network). Every record we create is tagged with
``MANAGED_COMMENT``; the sync only ever touches records carrying that tag, so
the apex landing page and any hand-made record are never affected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import PROXY_PLACEHOLDER_IP, fqdn

MANAGED_COMMENT = "managed-by:fluxcast-domains"

# For data-based records, only these keys distinguish one record from another;
# Cloudflare echoes extra derived fields we must ignore to avoid false churn.
RELEVANT_DATA_KEYS: dict[str, tuple[str, ...]] = {
    "CAA": ("flags", "tag", "value"),
    "SRV": ("priority", "weight", "port", "target"),
    "DS": ("key_tag", "algorithm", "digest_type", "digest"),
    "TLSA": ("usage", "selector", "matching_type", "certificate"),
}


def make_comparable(
    name: str,
    rtype: str,
    content: str | None,
    priority: int | None,
    proxied: bool,
    data: dict[str, Any] | None,
) -> tuple:
    if rtype in RELEVANT_DATA_KEYS and data is not None:
        keys = RELEVANT_DATA_KEYS[rtype]
        data_key = tuple((k, str(data.get(k))) for k in keys)
        return (name.lower(), rtype, None, None, proxied, data_key)
    norm_content = (content or "").rstrip(".").lower()
    return (name.lower(), rtype, norm_content, priority, proxied, None)


@dataclass(frozen=True)
class DesiredRecord:
    name: str
    type: str
    content: str | None = None
    priority: int | None = None
    proxied: bool = False
    data: dict[str, Any] | None = None

    def comparable(self) -> tuple:
        return make_comparable(
            self.name, self.type, self.content, self.priority, self.proxied, self.data
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "name": self.name,
            "comment": MANAGED_COMMENT,
            "proxied": self.proxied,
            "ttl": 1,  # Cloudflare: 1 = automatic TTL
        }
        if self.data is not None:
            payload["data"] = self.data
        else:
            payload["content"] = self.content
        if self.priority is not None:
            payload["priority"] = self.priority
        return payload


def build_records_for_domain(subdomain: str, data: dict) -> list[DesiredRecord]:
    name = fqdn(subdomain)
    proxied = bool(data.get("proxied"))
    records = data.get("records", {})
    out: list[DesiredRecord] = []

    for rtype, value in records.items():
        if rtype in ("A", "AAAA"):
            for ip in value:
                out.append(DesiredRecord(name, rtype, content=ip, proxied=proxied))
        elif rtype == "CNAME":
            out.append(DesiredRecord(name, "CNAME", content=value, proxied=proxied))
        elif rtype == "MX":
            for rec in value:
                if isinstance(rec, str):
                    out.append(DesiredRecord(name, "MX", content=rec, priority=10))
                else:
                    out.append(
                        DesiredRecord(
                            name, "MX", content=rec["target"], priority=rec["priority"]
                        )
                    )
        elif rtype == "NS":
            for target in value:
                out.append(DesiredRecord(name, "NS", content=target))
        elif rtype == "TXT":
            values = value if isinstance(value, list) else [value]
            for txt in values:
                out.append(DesiredRecord(name, "TXT", content=txt))
        elif rtype == "CAA":
            for rec in value:
                out.append(
                    DesiredRecord(
                        name,
                        "CAA",
                        data={"flags": 0, "tag": rec["tag"], "value": rec["value"]},
                    )
                )
        elif rtype == "SRV":
            for rec in value:
                out.append(
                    DesiredRecord(
                        name,
                        "SRV",
                        data={
                            "priority": rec["priority"],
                            "weight": rec["weight"],
                            "port": rec["port"],
                            "target": rec["target"],
                        },
                    )
                )
        elif rtype == "DS":
            for rec in value:
                out.append(
                    DesiredRecord(
                        name,
                        "DS",
                        data={
                            "key_tag": rec["key_tag"],
                            "algorithm": rec["algorithm"],
                            "digest_type": rec["digest_type"],
                            "digest": rec["digest"],
                        },
                    )
                )
        elif rtype == "TLSA":
            for rec in value:
                out.append(
                    DesiredRecord(
                        name,
                        "TLSA",
                        data={
                            "usage": rec["usage"],
                            "selector": rec["selector"],
                            "matching_type": rec["matching_type"],
                            "certificate": rec["certificate"],
                        },
                    )
                )
        elif rtype == "URL":
            # Cloudflare has no URL type; publish a proxied placeholder A record.
            # The actual HTTP redirect is served by a Cloudflare Redirect Rule.
            out.append(
                DesiredRecord(name, "A", content=PROXY_PLACEHOLDER_IP, proxied=True)
            )

    return out


@dataclass(frozen=True)
class ExistingRecord:
    id: str
    comparable: tuple


@dataclass
class SyncPlan:
    creates: list[DesiredRecord] = field(default_factory=list)
    deletes: list[ExistingRecord] = field(default_factory=list)

    @property
    def is_noop(self) -> bool:
        return not self.creates and not self.deletes


def plan_changes(
    desired: list[DesiredRecord], existing: list[ExistingRecord]
) -> SyncPlan:
    desired_keys = {d.comparable() for d in desired}
    existing_keys = {e.comparable for e in existing}

    seen: set[tuple] = set()
    creates = []
    for d in desired:
        key = d.comparable()
        if key not in existing_keys and key not in seen:
            creates.append(d)
        seen.add(key)

    deletes = [e for e in existing if e.comparable not in desired_keys]
    return SyncPlan(creates=creates, deletes=deletes)
