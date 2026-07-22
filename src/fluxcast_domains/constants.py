"""Shared constants, paths, and low-level validators."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path

from . import ROOT_DOMAIN

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAINS_DIR = REPO_ROOT / "domains"
UTIL_DIR = REPO_ROOT / "util"

RESERVED_FILE = UTIL_DIR / "reserved.json"
INTERNAL_FILE = UTIL_DIR / "internal.json"
TRUSTED_FILE = UTIL_DIR / "trusted.json"
DISALLOWED_CNAMES_FILE = UTIL_DIR / "disallowed-cnames.json"

VALID_RECORD_TYPES = frozenset(
    {"A", "AAAA", "CAA", "CNAME", "DS", "MX", "NS", "SRV", "TLSA", "TXT", "URL"}
)
PROXYABLE_RECORD_TYPES = frozenset({"A", "AAAA", "CNAME"})
USABLE_RECORD_TYPES = frozenset({"A", "AAAA", "CNAME", "MX", "NS", "URL"})

# Placeholder IP for proxied URL/redirect records (Cloudflare answers for it).
PROXY_PLACEHOLDER_IP = "192.0.2.1"

HOSTNAME_REGEX = re.compile(
    r"^(?=.{1,253}$)(?:(?:[_a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)\.)+[a-zA-Z]{2,63}$"
)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
REDIRECT_PATH_REGEX = re.compile(r"^/[a-zA-Z0-9\-_./]+(?<!/)$")
HEX_REGEX = re.compile(r"^[0-9a-fA-F]+$")


def fqdn(subdomain: str) -> str:
    return f"{subdomain}.{ROOT_DOMAIN}"


def is_valid_hostname(value: str) -> bool:
    return bool(HOSTNAME_REGEX.match(value))


def is_public_ipv4(value: str, proxied: bool = False) -> bool:
    if proxied and value == PROXY_PLACEHOLDER_IP:
        return True
    try:
        addr = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def is_public_ipv6(value: str) -> bool:
    try:
        addr = ipaddress.IPv6Address(value)
    except ipaddress.AddressValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def is_hexadecimal(value: str) -> bool:
    return bool(value) and bool(HEX_REGEX.match(value))
