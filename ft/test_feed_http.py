import socket
from io import StringIO
from unittest.mock import patch

import pytest
import requests
from django.core.files.uploadedfile import SimpleUploadedFile
from feeds import utils as feed_utils
from feeds.models import Source, Subscription

from ft import feed_http

PUBLIC = "93.184.216.34"


def address(ip=PUBLIC, port=443):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]


@pytest.fixture
def public_dns():
    with patch("ft.feed_http.socket.getaddrinfo", return_value=address()) as resolver:
        yield resolver


def response(url, status=200, location=None, body=b"secret upstream body"):
    result = requests.Response()
    result.url = url
    result.status_code = status
    result._content = body
    result._content_consumed = True
    if location is not None:
        result.headers["Location"] = location
    return result


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "0.0.0.0",
        "224.0.0.1",
        "240.0.0.1",
        "100.64.0.1",
        "192.0.2.1",
        "::1",
        "::",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "::ffff:127.0.0.1",
        "64:ff9b::7f00:1",
        "2002:7f00:1::",
    ],
)
def test_special_addresses_rejected_before_socket(ip):
    with (
        patch("ft.feed_http.socket.getaddrinfo", return_value=address(ip)),
        patch("ft.feed_http.socket.socket") as create,
    ):
        with pytest.raises(feed_http.UnsafeFeedURL):
            feed_http._PublicHTTPConnection("example.com", timeout=5)._new_conn()
        create.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com",
        "http://user:password@example.com",
        "http://localhost/x",
        "http://example.com:0/x",
        "http://example.com:99999/x",
        "http://example.com\\@127.0.0.1",
        "http://exa\nmple.com",
        "http://[fe80::1%eth0]",
    ],
)
def test_invalid_urls_rejected(url):
    with pytest.raises(feed_http.UnsafeFeedURL):
        feed_http.validate_feed_url(url)


def test_mixed_public_private_dns_rejected():
    with patch(
        "ft.feed_http.socket.getaddrinfo", return_value=address() + address("10.0.0.1")
    ):
        with pytest.raises(feed_http.UnsafeFeedURL):
            feed_http.validate_feed_url("https://example.com")


def test_connection_revalidates_after_admission_dns_changes():
    with (
        patch(
            "ft.feed_http.socket.getaddrinfo",
            side_effect=[address(), address("127.0.0.1")],
        ),
        patch("ft.feed_http.socket.socket") as create,
    ):
        feed_http.validate_feed_url("https://example.com")
        with pytest.raises(feed_http.UnsafeFeedURL):
            feed_http._PublicHTTPSConnection("example.com", timeout=5)._new_conn()
        create.assert_not_called()


def test_socket_connects_to_exact_validated_address(public_dns):
    with patch("ft.feed_http.socket.socket") as create:
        connection = feed_http._PublicHTTPSConnection("example.com", timeout=5)
        assert connection._new_conn() is create.return_value
        create.return_value.connect.assert_called_once_with((PUBLIC, 443))
        public_dns.assert_called_once_with("example.com", 443, type=socket.SOCK_STREAM)
        assert connection.host == "example.com"


@pytest.mark.parametrize("follow", [True, False])
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_private_redirect_not_fetched_or_returned(follow, status):
    def resolve(host, port, **kwargs):
        return address("127.0.0.1" if host == "internal.example" else PUBLIC, port)

    first = response(
        "https://example.com/feed", status, "http://internal.example/admin"
    )
    with (
        patch("ft.feed_http.socket.getaddrinfo", side_effect=resolve),
        patch("requests.Session.get", return_value=first) as fetch,
    ):
        with pytest.raises(feed_http.UnsafeFeedURL):
            feed_http.get(first.url, allow_redirects=follow)
        assert fetch.call_count == 1
        assert fetch.call_args.kwargs["allow_redirects"] is False


def test_relative_redirect_and_proxy_isolation(public_dns, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8080")
    seen = []
    replies = [
        response("https://example.com/a", 302, "/b"),
        response("https://example.com/b"),
    ]

    def fetch(session, url, **kwargs):
        seen.append(url)
        assert session.trust_env is False
        assert (
            session.get_adapter(url).poolmanager.pool_classes_by_scheme["https"]
            is feed_http._PublicHTTPSPool
        )
        assert kwargs["allow_redirects"] is False
        assert kwargs["verify"] is True
        return replies.pop(0)

    with patch("requests.Session.get", autospec=True, side_effect=fetch):
        result = feed_http.get("https://example.com/a", verify=False)
    assert result.status_code == 200
    assert seen == ["https://example.com/a", "https://example.com/b"]


def test_redirect_loop_bounded(public_dns):
    with patch(
        "requests.Session.get",
        return_value=response("https://example.com/a", 302, "/a"),
    ) as fetch:
        with pytest.raises(requests.TooManyRedirects):
            feed_http.get("https://example.com/a")
        assert fetch.call_count == feed_http.MAX_REDIRECTS + 1


@pytest.mark.django_db
def test_opml_rejects_private_new_and_existing_sources(client, user, make_source):
    source = make_source(feed_url="http://127.0.0.1/feed")
    client.force_login(user)
    opml = b'<opml><body><outline xmlUrl="http://127.0.0.1/feed"/><outline xmlUrl="http://169.254.169.254/latest"/></body></opml>'
    with patch("ft.feed_http.socket.getaddrinfo", return_value=address("127.0.0.1")):
        result = client.post(
            "/importopml/", {"opml": SimpleUploadedFile("feeds.opml", opml)}
        )
    assert result.status_code == 200
    assert Source.objects.count() == 1
    assert not Subscription.objects.filter(source=source).exists()


@pytest.mark.django_db
def test_diagnostic_returns_status_without_upstream_body(
    client, superuser, make_source, public_dns
):
    source = make_source()
    client.force_login(superuser)
    with patch("requests.Session.get", return_value=response(source.feed_url)):
        result = client.get(f"/feed/{source.id}/test/")
    assert result.status_code == 200
    assert result.content == b"HTTP status: 200\nTest result: True"


@pytest.mark.django_db
def test_diagnostic_rejects_private_stored_source(client, superuser, make_source):
    source = make_source(feed_url="http://127.0.0.1/feed")
    client.force_login(superuser)
    with (
        patch("ft.feed_http.socket.getaddrinfo", return_value=address("127.0.0.1")),
        patch("requests.Session.get") as fetch,
    ):
        result = client.get(f"/feed/{source.id}/test/")
    assert result.status_code == 400
    fetch.assert_not_called()


@pytest.mark.django_db
def test_background_poll_uses_safe_transport_for_stored_sources(make_source):
    source = make_source(feed_url="http://127.0.0.1/feed")
    assert feed_utils.requests is feed_http
    assert requests.get is not feed_http.get
    with (
        patch("ft.feed_http.socket.getaddrinfo", return_value=address("127.0.0.1")),
        patch("requests.Session.get") as fetch,
    ):
        feed_utils.read_feed(source, output=StringIO())
    fetch.assert_not_called()
    source.refresh_from_db()
    assert source.status_code == 0


@pytest.mark.django_db
def test_addfeed_private_redirect_rejected(client, user, public_dns):
    client.force_login(user)
    first = response("https://example.com/feed", 302, "http://localhost/secret")
    with patch("requests.Session.get", return_value=first) as fetch:
        result = client.post("/addfeed/", {"feed": first.url, "group": "0"})
    assert result.status_code == 400
    assert Source.objects.count() == 0
    assert fetch.call_count == 1


def paginated_feed(next_url):
    return f'''<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
    <channel><title>Feed</title><link>https://example.com/</link>
    <atom:link rel="next" href="{next_url}"/>
    <item><title>Entry</title><guid>https://example.com/entry</guid>
    <link>https://example.com/entry</link><description>Body</description>
    <pubDate>Sat, 12 Sep 2026 09:00:00 GMT</pubDate></item>
    </channel></rss>'''.encode()


@pytest.mark.django_db
@pytest.mark.parametrize("via_redirect", [False, True])
def test_background_pagination_uses_safe_transport(make_source, via_redirect):
    source = make_source()
    private_url = "http://127.0.0.1/private"
    next_url = "https://example.com/page2" if via_redirect else private_url
    seen = []

    def resolve(host, port, **kwargs):
        return address("127.0.0.1" if host == "127.0.0.1" else PUBLIC, port)

    def fetch(session, method, url, **kwargs):
        seen.append(url)
        if url == source.feed_url:
            return response(url, body=paginated_feed(next_url))
        if via_redirect and url == next_url:
            return response(url, 302, private_url)
        pytest.fail("Pagination attempted a private request")

    with (
        patch("ft.feed_http.socket.getaddrinfo", side_effect=resolve),
        patch("requests.Session.request", autospec=True, side_effect=fetch),
    ):
        with pytest.raises(feed_http.UnsafeFeedURL):
            feed_utils.read_feed(source, output=StringIO())
    assert source.posts.count() == 1
    assert seen == [source.feed_url] + ([next_url] if via_redirect else [])
