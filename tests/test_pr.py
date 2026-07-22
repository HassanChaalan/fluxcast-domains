"""PR authorship: a contributor may only add/change/delete their own files.

Runs only inside CI, where the workflow exports the PR metadata. Locally (no
env) it is skipped. Trusted users bypass the owner check; deleting/updating a
maintainer-owned file requires an admin.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from fluxcast_domains.constants import DOMAINS_DIR
from fluxcast_domains.loader import load_json, load_lists

REQUIRED_ENV = ("PR_AUTHOR", "PR_AUTHOR_ID", "CHANGED_FILES", "DELETED_FILES")


def _pre_image_from_patch(patch: str) -> dict:
    """Reconstruct the deleted file's JSON from its removal diff hunk."""
    removed = [
        line[1:]
        for line in patch.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    return json.loads("\n".join(removed))


@pytest.mark.skipif(
    not all(os.environ.get(v) for v in REQUIRED_ENV),
    reason="PR metadata not present (local run)",
)
def test_contributor_only_touches_own_files():
    lists = load_lists()
    trusted_ids = lists.trusted_ids
    admin_ids = lists.admin_ids
    admin_usernames = {
        str(u["username"]).lower() for u in lists.trusted if u.get("admin")
    }

    author = os.environ["PR_AUTHOR"].lower()
    author_id = str(os.environ["PR_AUTHOR_ID"])
    labels = os.environ.get("PR_LABELS", "")
    if "ci: bypass-owner-check" in labels:
        pytest.skip("owner check bypassed by label")

    changed = json.loads(os.environ["CHANGED_FILES"])
    deleted = json.loads(os.environ["DELETED_FILES"])

    failures: list[str] = []

    def check(subdomain: str, owner: str, verb: str) -> None:
        owner = owner.lower()
        if owner in admin_usernames:
            if author_id not in admin_ids:
                failures.append(
                    f"{subdomain}: {author} is not authorized to {verb} "
                    f"{subdomain}.fluxcast.dev (maintainer-owned)"
                )
        elif not (owner == author or author_id in trusted_ids):
            failures.append(
                f"{subdomain}: {author} is not authorized to {verb} "
                f"{subdomain}.fluxcast.dev"
            )

    for filename in changed:
        if not filename.startswith("domains/") or not filename.endswith(".json"):
            continue
        subdomain = Path(filename).stem
        data = load_json(DOMAINS_DIR / f"{subdomain}.json")
        check(subdomain, str(data.get("owner", {}).get("username", "")), "update")

    for entry in deleted:
        name = entry.get("name", "")
        if not name.startswith("domains/") or not name.endswith(".json"):
            continue
        subdomain = Path(name).stem
        try:
            data = _pre_image_from_patch(entry.get("data", ""))
        except (ValueError, json.JSONDecodeError):
            failures.append(f"{subdomain}: could not parse deleted file's owner")
            continue
        check(subdomain, str(data.get("owner", {}).get("username", "")), "delete")

    assert not failures, "\n".join(failures)
