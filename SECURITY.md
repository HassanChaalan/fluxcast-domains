# Security Policy

## Reporting a vulnerability

If you find a security issue in the registry tooling or infrastructure, for
example a validation bypass that would let someone register a forbidden record,
hijack another user's subdomain, or reach the Cloudflare credentials, please
report it **privately**.

- Use GitHub's [private vulnerability reporting](../../security/advisories/new), or
- Email the maintainer (see the `owner` contact on the project).

Please **do not** open a public issue for security vulnerabilities.

## Scope

- Validation logic in `src/fluxcast_domains/` and `tests/`.
- The Cloudflare sync (`fluxcast-sync`) and CI/publish workflows.
- Abuse of live `*.fluxcast.dev` subdomains → use the
  [report-abuse](../../issues/new?labels=report-abuse&template=report-abuse.md)
  flow instead.

## What to expect

We aim to acknowledge reports within a few days and to fix confirmed issues as
quickly as is practical for a volunteer-run service.
