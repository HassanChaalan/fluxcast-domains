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


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>fluxcast.dev registry API</title>
<style>
    body {
        margin: 0; min-height: 100vh; display: grid; place-items: center;
        background: #0B0C10; color: #F8FAFC;
        font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
        text-align: center; padding: 2rem;
    }
    main { max-width: 560px; }
    h1 { font-size: 1.6rem; margin: 0 0 0.75rem; }
    p { color: #94A3B8; line-height: 1.6; }
    code { font-family: ui-monospace, "Fira Code", monospace; color: #4ADE80; }
    a { color: #4ADE80; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .endpoint {
        display: inline-block; margin: 1.5rem 0; padding: 0.9rem 1.4rem;
        background: #1A1C23; border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px; font-size: 1.05rem;
    }
    .foot { font-size: 0.85rem; margin-top: 2rem; }
</style>
</head>
<body>
<main>
    <h1>fluxcast.dev registry API</h1>
    <p>Public, read-only snapshot of every <code>.fluxcast.dev</code> subdomain.</p>
    <a class="endpoint" href="/v2.json">→ /v2.json</a>
    <p class="foot">
        Registry: <a href="https://github.com/IlyaP358/fluxcast-domains">github.com/IlyaP358/fluxcast-domains</a>
        &nbsp;·&nbsp; <a href="https://fluxcast.dev">fluxcast.dev</a>
    </p>
</main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    v2 = build_v2()
    OUTPUT_FILE.write_text(json.dumps(v2, ensure_ascii=False), encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (OUTPUT_DIR / "CNAME").write_text(f"raw.{ROOT_DOMAIN}\n", encoding="utf-8")
    print(f"Wrote {len(v2)} entries to {OUTPUT_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
