"""Public-only feed HTTP transport, including connection-time DNS validation."""

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError

REDIRECT_CODES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 10


class UnsafeFeedURL(ValueError, requests.RequestException):
    pass


def _public_address(address):
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address):
        # Do not permit transition mechanisms to tunnel to an unchecked IPv4 peer.
        if (
            ip.ipv4_mapped
            or ip.sixtofour
            or ip.teredo
            or ip in ipaddress.ip_network("64:ff9b::/96")
        ):
            return False
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


def _resolve_public(host, port):
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not addresses or any(not _public_address(info[4][0]) for info in addresses):
            raise UnsafeFeedURL("Feed address is not public.")
        return addresses
    except (OSError, ValueError) as exc:
        raise UnsafeFeedURL("Feed hostname is invalid or not public.") from exc


def validate_feed_url(url):
    try:
        if not isinstance(url, str) or any(ord(c) < 33 or ord(c) == 127 for c in url):
            raise ValueError("Invalid URL characters")
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Not an HTTP URL")
        if (
            parsed.username is not None
            or parsed.password is not None
            or "%" in parsed.hostname
            or "\\" in url
        ):
            raise ValueError("Credentials or ambiguous hostname")
        if parsed.hostname.lower().rstrip(".") in (
            "localhost",
            "localhost.localdomain",
        ):
            raise UnsafeFeedURL("Localhost feed URLs are not allowed.")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if parsed.port == 0:
            raise ValueError("Invalid port")
        _resolve_public(parsed.hostname, port)
    except ValueError as exc:
        raise UnsafeFeedURL("Feed URL is invalid or not allowed.") from exc
    return url


class _PublicConnection:
    def _new_conn(self):
        # Resolve once and connect to that exact sockaddr; keep self.host unchanged
        # so urllib3 still uses the original hostname for TLS SNI and verification.
        addresses = _resolve_public(self._dns_host, self.port)
        last_error = None
        for family, socktype, proto, _, address in addresses:
            sock = None
            try:
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(self.timeout)
                for option in self.socket_options or ():
                    sock.setsockopt(*option)
                if self.source_address:
                    sock.bind(self.source_address)
                sock.connect(address)
                return sock
            except OSError as exc:
                last_error = exc
                if sock is not None:
                    sock.close()
        raise NewConnectionError(
            self, "Unable to connect to public feed address"
        ) from last_error


class _PublicHTTPConnection(_PublicConnection, HTTPConnection):
    pass


class _PublicHTTPSConnection(_PublicConnection, HTTPSConnection):
    pass


class _PublicHTTPPool(HTTPConnectionPool):
    ConnectionCls = _PublicHTTPConnection


class _PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _PublicHTTPSConnection


class _PublicAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            "http": _PublicHTTPPool,
            "https": _PublicHTTPSPool,
        }


def get(url, *, headers=None, timeout=20, allow_redirects=True, verify=True):
    """A requests.get-compatible subset for the pinned feed reader.

    No ambient proxy, netrc credentials, cookies across hosts, or unverified TLS.
    Even unfollowed redirects are validated before the reader may store them.
    """
    current = url
    request_headers = dict(headers or {})
    with requests.Session() as session:
        session.trust_env = False
        session.mount("http://", _PublicAdapter())
        session.mount("https://", _PublicAdapter())
        for hop in range(MAX_REDIRECTS + 1):
            validate_feed_url(current)
            response = session.get(
                current,
                headers=request_headers,
                timeout=timeout,
                allow_redirects=False,
                verify=True,
            )
            if (
                response.status_code not in REDIRECT_CODES
                or "Location" not in response.headers
            ):
                return response
            target = urljoin(response.url, response.headers["Location"])
            try:
                validate_feed_url(target)
            except UnsafeFeedURL:
                response.close()
                raise
            if not allow_redirects:
                return response
            response.close()
            if hop == MAX_REDIRECTS:
                raise requests.TooManyRedirects("Too many feed redirects")
            if urlsplit(current).netloc != urlsplit(target).netloc:
                request_headers = {
                    k: v
                    for k, v in request_headers.items()
                    if k.lower()
                    not in {
                        "authorization",
                        "cookie",
                        "host",
                        "if-none-match",
                        "if-modified-since",
                    }
                }
            session.cookies.clear()
            current = target
    raise requests.TooManyRedirects("Too many feed redirects")
