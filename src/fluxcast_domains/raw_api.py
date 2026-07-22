"""Generate the public ``raw-api/v2.json`` snapshot, served at raw.fluxcast.dev."""

from __future__ import annotations

import json
from typing import Any

from . import ROOT_DOMAIN
from .constants import REPO_ROOT
from .loader import iter_domain_files, load_json, load_lists, subdomain_of

OUTPUT_DIR = REPO_ROOT / "raw-api"
OUTPUT_FILE = OUTPUT_DIR / "v2.json"


def build_v2() -> list[dict[str, Any]]:
    lists = load_lists()
    entries: list[dict[str, Any]] = []

    for subdomain in sorted(lists.internal):
        entries.append(
            {
                "domain": f"{subdomain}.{ROOT_DOMAIN}",
                "subdomain": subdomain,
                "owner": {"username": "fluxcast"},
                "records": {"CNAME": f"internal.{ROOT_DOMAIN}"},
                "internal": True,
            }
        )

    for subdomain in sorted(lists.reserved):
        entries.append(
            {
                "domain": f"{subdomain}.{ROOT_DOMAIN}",
                "subdomain": subdomain,
                "owner": {"username": "fluxcast"},
                "records": {"URL": f"https://{ROOT_DOMAIN}/reserved"},
                "reserved": True,
            }
        )

    for path in iter_domain_files():
        data = load_json(path)
        subdomain = subdomain_of(path)
        owner = dict(data.get("owner", {}))
        owner.pop("email", None)  # strip PII

        entry: dict[str, Any] = {
            "domain": f"{subdomain}.{ROOT_DOMAIN}",
            "subdomain": subdomain,
            "owner": owner,
            "records": data.get("records", {}),
        }
        if data.get("redirect_config"):
            entry["redirect_config"] = data["redirect_config"]
        if data.get("proxied"):
            entry["proxied"] = data["proxied"]
        entries.append(entry)

    entries.sort(key=lambda e: e["domain"])
    return entries


def main(argv: list[str] | None = None) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    v2 = build_v2()
    OUTPUT_FILE.write_text(json.dumps(v2, ensure_ascii=False), encoding="utf-8")
    (OUTPUT_DIR / "CNAME").write_text(f"raw.{ROOT_DOMAIN}\n", encoding="utf-8")
    print(f"Wrote {len(v2)} entries to {OUTPUT_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
