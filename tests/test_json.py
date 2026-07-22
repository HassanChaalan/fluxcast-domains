"""File-shape validation: parseable JSON, no duplicate keys, valid names/fields."""

from __future__ import annotations

import pytest

from fluxcast_domains.constants import DOMAINS_DIR, REPO_ROOT
from fluxcast_domains.loader import DuplicateKeyError, load_json, subdomain_of
from fluxcast_domains.validation import validate_filename, validate_structure

from conftest import DOMAIN_FILES, SUBDOMAINS

ALLOWED_ROOT_JSON = {"package.json", "package-lock.json"}


def test_no_json_files_in_repo_root():
    stray = [
        p.name
        for p in REPO_ROOT.glob("*.json")
        if p.name not in ALLOWED_ROOT_JSON
    ]
    assert not stray, f"JSON files must live in domains/, not the repo root: {stray}"


@pytest.mark.parametrize("path", DOMAIN_FILES, ids=SUBDOMAINS or ["<none>"])
def test_valid_json_no_duplicate_keys(path):
    try:
        load_json(path)
    except DuplicateKeyError as exc:
        pytest.fail(f"{path.name}: duplicate key found: {exc}")
    except ValueError as exc:
        pytest.fail(f"{path.name}: invalid JSON: {exc}")


@pytest.mark.parametrize("subdomain", SUBDOMAINS, ids=SUBDOMAINS or ["<none>"])
def test_valid_file_name(subdomain, lists):
    errors = validate_filename(subdomain, lists)
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("subdomain", SUBDOMAINS, ids=SUBDOMAINS or ["<none>"])
def test_valid_fields(subdomain, ctx):
    data = ctx.data_by_subdomain.get(subdomain)
    if data is None:
        pytest.skip("file failed to parse (covered by test_valid_json_no_duplicate_keys)")
    errors = validate_structure(subdomain, data)
    assert not errors, "\n".join(errors)


def test_domains_dir_exists():
    assert DOMAINS_DIR.is_dir(), "domains/ directory is missing"
