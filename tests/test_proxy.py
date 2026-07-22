"""Proxy validation: proxied domains must carry a proxy-able record."""

from __future__ import annotations

import pytest

from fluxcast_domains.validation import validate_proxy

from conftest import SUBDOMAINS


@pytest.mark.parametrize("subdomain", SUBDOMAINS, ids=SUBDOMAINS or ["<none>"])
def test_valid_proxy(subdomain, ctx):
    data = ctx.data_by_subdomain.get(subdomain)
    if data is None:
        pytest.skip("file failed to parse")
    errors = validate_proxy(subdomain, data)
    assert not errors, "\n".join(errors)
