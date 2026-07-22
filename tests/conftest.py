"""Shared fixtures. Domain files are loaded once and reused across the suite."""

from __future__ import annotations

import pytest

from fluxcast_domains.loader import (
    Lists,
    domain_filenames,
    iter_domain_files,
    load_lists,
    load_json,
    subdomain_of,
)
from fluxcast_domains.loader import DuplicateKeyError
from fluxcast_domains.validation import ValidationContext

# Collected once at import time so tests can be parametrized over them.
DOMAIN_FILES = iter_domain_files()
SUBDOMAINS = [subdomain_of(p) for p in DOMAIN_FILES]


@pytest.fixture(scope="session")
def lists() -> Lists:
    return load_lists()


@pytest.fixture(scope="session")
def ctx(lists: Lists) -> ValidationContext:
    """A validation context with every parseable domain file pre-loaded."""
    data_by_subdomain: dict[str, dict] = {}
    for path in DOMAIN_FILES:
        try:
            data_by_subdomain[subdomain_of(path)] = load_json(path)
        except (ValueError, DuplicateKeyError):
            # Parse/duplicate-key errors are asserted by test_json; skip here so
            # a single malformed file doesn't blow up every other test.
            continue
    return ValidationContext(
        lists=lists,
        filenames=domain_filenames(),
        data_by_subdomain=data_by_subdomain,
    )
