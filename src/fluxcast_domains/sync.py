"""Reconcile ``domains/*.json`` into a Cloudflare zone.

    fluxcast-sync --dry-run   # show the plan, change nothing
    fluxcast-sync             # apply it

Reads CLOUDFLARE_API_TOKEN (Zone:DNS:Edit, this zone only) and
CLOUDFLARE_ZONE_ID from the environment. Only records tagged
``managed-by:fluxcast-domains`` are ever touched.
"""

from __future__ import annotations

import argparse
import os
import sys

from .loader import (
    domain_filenames,
    iter_domain_files,
    load_json,
    load_lists,
    subdomain_of,
)
from .records import (
    MANAGED_COMMENT,
    DesiredRecord,
    ExistingRecord,
    SyncPlan,
    build_records_for_domain,
    make_comparable,
    plan_changes,
)
from .validation import ValidationContext, validate_domain, validate_nesting


def build_desired() -> tuple[list[DesiredRecord], list[str]]:
    """Load and validate every domain file. Non-empty errors ⇒ do not publish."""
    lists = load_lists()
    data_by_subdomain: dict[str, dict] = {}
    errors: list[str] = []

    for path in iter_domain_files():
        try:
            data_by_subdomain[subdomain_of(path)] = load_json(path)
        except ValueError as exc:
            errors.append(f"{path.name}: {exc}")

    ctx = ValidationContext(
        lists=lists,
        filenames=domain_filenames(),
        data_by_subdomain=data_by_subdomain,
    )

    desired: list[DesiredRecord] = []
    for subdomain, data in data_by_subdomain.items():
        file_errors = validate_domain(subdomain, data, ctx)
        file_errors += validate_nesting(subdomain, ctx)
        if file_errors:
            errors.extend(file_errors)
            continue
        desired.extend(build_records_for_domain(subdomain, data))

    return desired, errors


def _existing_from_cloudflare(client, zone_id: str) -> list[ExistingRecord]:
    existing: list[ExistingRecord] = []
    for rec in client.dns.records.list(zone_id=zone_id, per_page=5000):
        if getattr(rec, "comment", None) != MANAGED_COMMENT:
            continue  # not ours, never touch it
        data = getattr(rec, "data", None)
        if data is not None and not isinstance(data, dict):
            data = dict(data)
        existing.append(
            ExistingRecord(
                id=rec.id,
                comparable=make_comparable(
                    rec.name,
                    rec.type,
                    getattr(rec, "content", None),
                    getattr(rec, "priority", None),
                    bool(getattr(rec, "proxied", False)),
                    data,
                ),
            )
        )
    return existing


def apply_plan(client, zone_id: str, plan: SyncPlan) -> None:
    # Delete before create to avoid transient duplicate conflicts.
    for rec in plan.deletes:
        client.dns.records.delete(dns_record_id=rec.id, zone_id=zone_id)
    for rec in plan.creates:
        client.dns.records.create(zone_id=zone_id, **rec.to_payload())


def _print_plan(plan: SyncPlan) -> None:
    print(f"Plan: +{len(plan.creates)} create, -{len(plan.deletes)} delete")
    for rec in plan.creates:
        detail = rec.content if rec.content is not None else rec.data
        flag = " (proxied)" if rec.proxied else ""
        print(f"  + {rec.type:5} {rec.name} -> {detail}{flag}")
    for rec in plan.deletes:
        print(f"  - {rec.comparable[1]:5} {rec.comparable[0]}  [{rec.id}]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync domains/ to Cloudflare")
    parser.add_argument("--dry-run", action="store_true", help="preview only")
    args = parser.parse_args(argv)

    desired, errors = build_desired()
    if errors:
        print("Refusing to sync, validation errors:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    zone_id = os.environ.get("CLOUDFLARE_ZONE_ID")
    if not token or not zone_id:
        print(
            "CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID must be set.", file=sys.stderr
        )
        return 2

    from cloudflare import Cloudflare

    client = Cloudflare(api_token=token)
    plan = plan_changes(desired, _existing_from_cloudflare(client, zone_id))
    _print_plan(plan)

    if args.dry_run:
        print("Dry run, no changes applied.")
        return 0
    if plan.is_noop:
        print("Zone already up to date.")
        return 0

    apply_plan(client, zone_id, plan)
    print("Sync complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
