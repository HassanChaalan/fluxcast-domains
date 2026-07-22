"""DNS record validation: types, value formats, and combination rules."""

from __future__ import annotations

import pytest

from fluxcast_domains.validation import validate_records, validate_root_usable

from conftest import SUBDOMAINS


@pytest.mark.parametrize("subdomain", SUBDOMAINS, ids=SUBDOMAINS or ["<none>"])
def test_valid_records(subdomain, ctx):
    data = ctx.data_by_subdomain.get(subdomain)
    if data is None:
        pytest.skip("file failed to parse")
    errors = validate_records(subdomain, data, ctx.lists)
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("subdomain", SUBDOMAINS, ids=SUBDOMAINS or ["<none>"])
def test_root_subdomain_has_usable_record(subdomain, ctx):
    data = ctx.data_by_subdomain.get(subdomain)
    if data is None:
        pytest.skip("file failed to parse")
    errors = validate_root_usable(subdomain, data)
    assert not errors, "\n".join(errors)
