"""Secure HTTPS document fetcher with SSRF protection, domain allowlist, and size/timeout bounds."""
from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, Optional, Set, Tuple

from ..config import SecurityLimits


class SecurityViolationError(ValueError):
    """Raised when a URL or redirect violates HTTPS, allowlist, or SSRF policies."""


SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    """Sanitize file or directory names to prevent path traversal and invalid chars."""
    cleaned = name.replace("\x00", "").replace("..", "_").strip()
    cleaned = SAFE_FILENAME_RE.sub("_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    if not cleaned or cleaned in (".", ".."):
        return "document"
    return cleaned[:120]


def is_ip_forbidden(ip_str: str) -> bool:
    """Return True if an IP address is loopback, private, link-local, multicast, or reserved."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        )
    except ValueError:
        return False


def validate_url_security(
    url: str,
    allowed_domains: Optional[Iterable[str]] = None,
    require_https: bool = True,
    resolve_dns: bool = False,
) -> str:
    """Validate URL against HTTPS requirement, SSRF local/private ranges, and domain allowlist."""
    if not url or not isinstance(url, str):
        raise SecurityViolationError("Empty or invalid URL")
    parsed = urllib.parse.urlparse(url.strip())
    if require_https and parsed.scheme.lower() != "https":
        raise SecurityViolationError(f"Only HTTPS URLs are permitted: {url}")
    if parsed.scheme.lower() not in ("https", "http"):
        raise SecurityViolationError(f"Unsupported URL scheme: {parsed.scheme}")
    if parsed.username or parsed.password:
        raise SecurityViolationError("Credentials in URLs are forbidden")

    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        raise SecurityViolationError(f"URL missing hostname: {url}")

    forbidden_hosts = {"localhost", "localhost.localdomain", "metadata.google.internal", "ip6-localhost"}
    if host in forbidden_hosts or host.endswith(".local") or host.endswith(".internal"):
        raise SecurityViolationError(f"SSRF protection blocked internal hostname: {host}")

    # Direct IP literal check
    if is_ip_forbidden(host):
        raise SecurityViolationError(f"SSRF protection blocked private/local IP address: {host}")
    try:
        # Also block all raw IP literals even if public when domain allowlist is active
        ipaddress.ip_address(host)
        if allowed_domains is not None:
            raise SecurityViolationError(f"Direct IP literals are not in the allowed domain catalog: {host}")
    except ValueError:
        pass

    if allowed_domains is not None:
        allow_set: Set[str] = {d.lower().strip(".") for d in allowed_domains}
        if not any(host == d or host.endswith("." + d) for d in allow_set):
            raise SecurityViolationError(f"Hostname '{host}' is not in the registered official sources allowlist")

    if resolve_dns:
        try:
            addr_info = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
            for family, _, _, _, sockaddr in addr_info:
                ip_addr = sockaddr[0]
                if is_ip_forbidden(ip_addr):
                    raise SecurityViolationError(f"DNS resolved {host} to forbidden local/private IP: {ip_addr}")
        except socket.gaierror:
            # Let the HTTP fetcher raise network error on connection if offline
            pass

    return url.strip()


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_domains: Optional[Iterable[str]], limits: SecurityLimits):
        super().__init__()
        self.allowed_domains = set(allowed_domains) if allowed_domains else None
        self.limits = limits
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > self.limits.max_redirects:
            raise SecurityViolationError(f"Maximum redirect limit ({self.limits.max_redirects}) exceeded")
        abs_url = urllib.parse.urljoin(req.full_url, newurl)
        validate_url_security(
            abs_url,
            allowed_domains=self.allowed_domains,
            require_https=self.limits.require_https,
            resolve_dns=True,
        )
        return super().redirect_request(req, fp, code, msg, headers, abs_url)


class DocumentFetcher:
    def __init__(
        self,
        allowed_domains: Optional[Iterable[str]] = None,
        limits: Optional[SecurityLimits] = None,
    ):
        self.allowed_domains = set(allowed_domains) if allowed_domains else None
        self.limits = limits or SecurityLimits()

    def fetch_url(self, url: str) -> Tuple[str, str]:
        """Securely fetch content from a verified HTTPS URL with size and timeout limits.

        Returns:
            (decoded_text, final_url)
        """
        clean_url = validate_url_security(
            url,
            allowed_domains=self.allowed_domains,
            require_https=self.limits.require_https,
            resolve_dns=True,
        )
        handler = _SafeRedirectHandler(self.allowed_domains, self.limits)
        opener = urllib.request.build_opener(handler)
        req = urllib.request.Request(
            clean_url,
            headers={
                "User-Agent": "ruby-rails-knowledge/1.0 (Local Technical Documentation Indexer)",
                "Accept": "text/html,text/markdown,text/plain;q=0.9",
            },
            method="GET",
        )
        timeout = min(self.limits.connect_timeout_sec, self.limits.read_timeout_sec)
        with opener.open(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            validate_url_security(
                final_url,
                allowed_domains=self.allowed_domains,
                require_https=self.limits.require_https,
                resolve_dns=False,
            )
            chunks = []
            total = 0
            while True:
                block = resp.read(65536)
                if not block:
                    break
                total += len(block)
                if total > self.limits.max_download_bytes:
                    raise SecurityViolationError(
                        f"Download size exceeded maximum limit of {self.limits.max_download_bytes} bytes"
                    )
                chunks.append(block)
            raw_bytes = b"".join(chunks)
            return (raw_bytes.decode("utf-8", errors="replace"), final_url)
