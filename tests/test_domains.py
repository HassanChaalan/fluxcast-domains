"""Cross-file rules: nesting, parent ownership, single-character limits."""

from __future__ import annotations

import pytest

from fluxcast_domains.validation import validate_nesting

from conftest import SUBDOMAINS


@pytest.mark.parametrize("subdomain", SUBDOMAINS, ids=SUBDOMAINS or ["<none>"])
def test_nesting_and_ownership(subdomain, ctx):
    if subdomain not in ctx.data_by_subdomain:
        pytest.skip("file failed to parse")
    errors = validate_nesting(subdomain, ctx)
    assert not errors, "\n".join(errors)


def test_one_single_character_subdomain_per_user(ctx):
    """Each non-admin user may hold at most one single-character subdomain."""
    admin_usernames = {
        str(u["username"]).lower() for u in ctx.lists.trusted if u.get("admin")
    }
    owners: dict[str, list[str]] = {}

    for subdomain, data in ctx.data_by_subdomain.items():
        if "." in subdomain or len(subdomain) != 1:
            continue
        owner = str(data.get("owner", {}).get("username", "")).lower()
        if owner in admin_usernames:
            continue
        owners.setdefault(owner, []).append(f"{subdomain}.fluxcast.dev")

    offenders = {
        owner: names for owner, names in owners.items() if len(names) > 1
    }
    assert not offenders, "\n".join(
        f"{owner} owns multiple single-char subdomains: {', '.join(names)}"
        for owner, names in offenders.items()
    )
