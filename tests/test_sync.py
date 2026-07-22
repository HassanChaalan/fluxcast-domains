"""Pure tests for record building and the reconcile diff (no network)."""

from __future__ import annotations

from fluxcast_domains.records import (
    MANAGED_COMMENT,
    ExistingRecord,
    build_records_for_domain,
    make_comparable,
    plan_changes,
)


def _existing_from(desired):
    """Turn desired records into 'already exists in the zone' records."""
    return [
        ExistingRecord(id=f"id{i}", comparable=d.comparable())
        for i, d in enumerate(desired)
    ]


def test_url_becomes_proxied_placeholder_a():
    recs = build_records_for_domain("demo", {"records": {"URL": "https://x.io"}})
    assert len(recs) == 1
    r = recs[0]
    assert r.type == "A" and r.proxied and r.content == "192.0.2.1"
    assert r.to_payload()["comment"] == MANAGED_COMMENT


def test_a_records_expand_per_ip():
    recs = build_records_for_domain(
        "foo", {"records": {"A": ["1.1.1.1", "8.8.8.8"]}}
    )
    assert {r.content for r in recs} == {"1.1.1.1", "8.8.8.8"}
    assert all(r.type == "A" for r in recs)


def test_identical_state_is_noop():
    desired = build_records_for_domain(
        "foo", {"proxied": True, "records": {"CNAME": "foo.github.io"}}
    )
    existing = _existing_from(desired)
    plan = plan_changes(desired, existing)
    assert plan.is_noop


def test_new_domain_is_created():
    desired = build_records_for_domain("foo", {"records": {"A": ["1.1.1.1"]}})
    plan = plan_changes(desired, existing=[])
    assert len(plan.creates) == 1 and not plan.deletes


def test_removed_domain_is_deleted():
    old = build_records_for_domain("foo", {"records": {"A": ["1.1.1.1"]}})
    existing = _existing_from(old)
    plan = plan_changes(desired=[], existing=existing)
    assert not plan.creates and len(plan.deletes) == 1


def test_changed_content_is_delete_plus_create():
    old = build_records_for_domain("foo", {"records": {"A": ["1.1.1.1"]}})
    new = build_records_for_domain("foo", {"records": {"A": ["2.2.2.2"]}})
    plan = plan_changes(new, _existing_from(old))
    assert len(plan.creates) == 1 and len(plan.deletes) == 1


def test_proxied_flip_is_detected():
    off = build_records_for_domain("foo", {"records": {"A": ["1.1.1.1"]}})
    on = build_records_for_domain(
        "foo", {"proxied": True, "records": {"A": ["1.1.1.1"]}}
    )
    plan = plan_changes(on, _existing_from(off))
    assert len(plan.creates) == 1 and len(plan.deletes) == 1


def test_caa_data_record_roundtrips_without_churn():
    domain = {"records": {"CAA": [{"tag": "issue", "value": "letsencrypt.org"}]}}
    desired = build_records_for_domain("foo", domain)
    # Simulate Cloudflare echoing extra derived fields in .data
    echoed = ExistingRecord(
        id="id0",
        comparable=make_comparable(
            "foo.fluxcast.dev",
            "CAA",
            None,
            None,
            False,
            {"flags": 0, "tag": "issue", "value": "letsencrypt.org", "extra": "x"},
        ),
    )
    plan = plan_changes(desired, [echoed])
    assert plan.is_noop
