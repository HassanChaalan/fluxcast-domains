# Registering a `*.fluxcast.dev` subdomain

You get a free `yourname.fluxcast.dev` subdomain by opening a pull request that
adds **one JSON file**. That's it.

## Steps

1. **Fork** this repository.
2. Create `domains/<your-subdomain>.json`. The file name (without `.json`) is
   your subdomain: `domains/coolproject.json` → `coolproject.fluxcast.dev`.
3. Fill it in (see below), commit, and open a pull request.
4. Automated checks run on your PR. If they fail, read the error, fix it, and
   push again.
5. A maintainer reviews and merges. Your DNS records go live within a few
   minutes.

## File format

```json
{
    "owner": {
        "username": "your-github-username",
        "email": "you@example.com"
    },
    "records": {
        "CNAME": "your-github-username.github.io"
    }
}
```

- `owner.username` **must** match your GitHub username (this is how ownership is
  enforced: you can only edit your own files).
- `owner.email` is optional but recommended for contact.
- `records` holds your DNS records.

### Supported records

| Type    | Shape                                                              |
| ------- | ----------------------------------------------------------------- |
| `A`     | `["1.2.3.4"]`, array of public IPv4                               |
| `AAAA`  | `["2606:..."]`, array of public IPv6                             |
| `CNAME` | `"target.example.com"`, a single hostname (alone, unless proxied)  |
| `MX`    | `[{"target": "mx.example.com", "priority": 10}]`                  |
| `NS`    | `["ns1.example.com"]`, delegates a subdomain                       |
| `TXT`   | `"value"` or `["v1", "v2"]`                                        |
| `URL`   | `"https://example.com"`, HTTP redirect (proxied)                 |
| `CAA` / `SRV` / `DS` / `TLSA` | advanced records, see examples in `domains/` |

### Options

- `"proxied": true` routes through Cloudflare (free SSL, DDoS protection, hides
  your origin IP). Requires an `A`, `AAAA`, or `CNAME` record.
- `"redirect_config"` sets custom redirect paths (requires a `URL` record or proxy).

### Nested subdomains

`blog.coolproject.fluxcast.dev` → `domains/blog.coolproject.json`. The parent
(`coolproject.json`) must already exist and be owned by you.

## Test locally before opening a PR

```bash
pip install -e ".[dev]"
pytest -q
```

## Rules

- One subdomain per project; don't hoard.
- Only **one** single-character subdomain per user.
- Reserved and internal names (see `util/`) are off-limits.
- No malware, phishing, or illegal content. See the [Terms of Service](TERMS_OF_SERVICE.md).
