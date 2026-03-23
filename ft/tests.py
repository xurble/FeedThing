from unittest.mock import Mock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from feeds.models import Source, Subscription
from ft.models import SavedPost


pytestmark = pytest.mark.django_db


def test_index_for_anonymous_and_authenticated_redirects(client, user):
    response = client.get(reverse("home"))
    assert response.status_code == 200

    user.default_to_river = False
    user.save()
    client.force_login(user)
    response = client.get(reverse("home"))
    assert response.status_code == 302
    assert response.url == reverse("feeds")

    user.default_to_river = True
    user.save()
    response = client.get(reverse("home"))
    assert response.status_code == 302
    assert response.url == reverse("userriver")


def test_help_and_well_known_uris(client):
    response = client.get(reverse("help"))
    assert response.status_code == 200

    response = client.get("/.well-known/change-password")
    assert response.status_code == 302
    assert reverse("account_change_password") in response["Location"]

    response = client.get("/.well-known/unknown")
    assert response.status_code == 404


def test_login_required_routes_redirect_when_anonymous(client):
    protected_urls = [
        reverse("feeds"),
        reverse("allfeeds"),
        reverse("userriver"),
        reverse("settings"),
        reverse("savedposts"),
        reverse("manage"),
        "/addfeed/",
        "/importopml/",
        "/feedgarden/",
        "/downloadfeeds/",
    ]
    for url in protected_urls:
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response["Location"]


def test_feeds_allfeeds_and_manage_pages(client, user, make_source, make_subscription):
    client.force_login(user)
    source = make_source()
    make_subscription(source=source)

    response = client.get(reverse("feeds"))
    assert response.status_code == 200

    response = client.get(reverse("allfeeds"))
    assert response.status_code == 200

    response = client.get(reverse("manage"))
    assert response.status_code == 200


def test_user_settings_get_and_post(client, user):
    client.force_login(user)
    response = client.get(reverse("settings"))
    assert response.status_code == 200

    response = client.post(
        reverse("settings"),
        {"name": "Updated Name", "salutation": "Hi", "default_to_river": "on"},
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.name == "Updated Name"
    assert user.salutation == "Hi"
    assert user.default_to_river is True


def test_user_river_page_with_query(client, user, make_source, make_subscription, make_post):
    client.force_login(user)
    source = make_source()
    make_subscription(source=source)
    make_post(source=source, title="Needle title")
    make_post(source=source, title="Other title")

    response = client.get(reverse("userriver"), {"q": "needle"})
    assert response.status_code == 200


def test_feedgarden_and_downloadfeeds_permissions(client, user, superuser, make_source):
    client.force_login(user)
    make_source()
    response = client.get("/feedgarden/")
    assert response.status_code == 200

    response = client.get("/downloadfeeds/")
    assert response.status_code == 403

    client.force_login(superuser)
    response = client.get("/downloadfeeds/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/xml+opml"


@patch("ft.views.requests.get")
@patch("ft.views.feedparser.parse")
def test_addfeed_get_and_post_imports_new_feed(parse_mock, requests_get_mock, client, user):
    client.force_login(user)
    response = client.get("/addfeed/", {"feed": "https://example.com"})
    assert response.status_code == 200

    requests_get_mock.return_value = Mock(
        headers={"Content-Type": "application/rss+xml"},
        text="<rss></rss>",
    )
    parse_mock.return_value = Mock(
        entries=[{"id": "1"}],
        feed=Mock(title="Imported Feed"),
    )

    response = client.post(
        "/addfeed/",
        {"feed": "https://example.com/feed.xml", "group": "0"},
    )
    assert response.status_code == 200
    assert "Imported feed" in response.content.decode()
    assert Source.objects.count() == 1
    assert Subscription.objects.filter(user=user).count() == 1


def test_importopml_creates_subscriptions(client, user):
    client.force_login(user)
    opml = b"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <body>
    <outline text="Example" title="Example" type="rss" xmlUrl="https://example.com/feed.xml" htmlUrl="https://example.com"/>
  </body>
</opml>"""
    upload = SimpleUploadedFile("feeds.opml", opml, content_type="text/xml")
    response = client.post("/importopml/", {"opml": upload})
    assert response.status_code == 200
    assert Source.objects.count() == 1
    assert Subscription.objects.filter(user=user).count() == 1


def test_readfeed_for_owner_and_forbidden_for_other_user(client, user, other_user, make_source, make_subscription, make_post):
    source = make_source()
    sub = make_subscription(user_override=user, source=source)
    make_post(source=source)

    client.force_login(user)
    response = client.get(f"/read/{sub.id}/")
    assert response.status_code == 200

    client.force_login(other_user)
    response = client.get(f"/read/{sub.id}/")
    assert response.status_code == 403


def test_savepost_and_forgetpost(client, user, make_source, make_subscription, make_post):
    source = make_source()
    sub = make_subscription(source=source)
    post = make_post(source=source)

    client.force_login(user)
    response = client.get(reverse("savepost", args=[post.id]))
    assert response.status_code == 200
    assert response.content.decode() == "OK"
    assert SavedPost.objects.filter(user=user, post=post, subscription=sub).exists()

    response = client.get(reverse("forgetpost", args=[post.id]))
    assert response.status_code == 200
    assert response.content.decode() == "OK"
    assert not SavedPost.objects.filter(user=user, post=post).exists()


def test_savedposts_view(client, user, make_source, make_subscription, make_post):
    source = make_source()
    sub = make_subscription(source=source)
    post = make_post(source=source, title="Saved needle")
    SavedPost.objects.create(user=user, post=post, subscription=sub)

    client.force_login(user)
    response = client.get(reverse("savedposts"), {"q": "needle"})
    assert response.status_code == 200


def test_manage_subscription_endpoints(client, user, make_source, make_subscription):
    client.force_login(user)
    source = make_source()
    group = Subscription.objects.create(user=user, source=None, name="Group")
    sub = make_subscription(source=source, parent=group)

    response = client.post(f"/subscription/{sub.id}/rename/", {"name": "Renamed"})
    assert response.status_code == 200
    sub.refresh_from_db()
    assert sub.name == "Renamed"

    response = client.post(
        f"/subscription/{sub.id}/details/",
        {"subname": "Detailed Name", "is_river": "on"},
    )
    assert response.status_code == 200
    sub.refresh_from_db()
    assert sub.name == "Detailed Name"
    assert sub.is_river is True

    response = client.get(f"/subscription/{sub.id}/promote/")
    assert response.status_code == 200
    sub.refresh_from_db()
    assert sub.parent is None


def test_addto_endpoint_existing_and_new_group(client, user, make_source, make_subscription):
    client.force_login(user)
    source_a = make_source(feed_url="https://example.com/a.xml", name="A")
    source_b = make_source(feed_url="https://example.com/b.xml", name="B")
    sub_a = make_subscription(source=source_a, name="Sub A")
    sub_b = make_subscription(source=source_b, name="Sub B")

    response = client.get(f"/subscription/{sub_a.id}/addto/0/")
    assert response.status_code == 200
    sub_a.refresh_from_db()
    assert sub_a.parent is not None

    response = client.get(f"/subscription/{sub_b.id}/addto/{sub_a.id}/")
    assert response.status_code == 200
    sub_a.refresh_from_db()
    sub_b.refresh_from_db()
    assert sub_a.parent is not None
    assert sub_a.parent == sub_b.parent


def test_unsubscribe_subscription(client, user, make_source, make_subscription):
    client.force_login(user)
    source = make_source()
    sub = make_subscription(source=source)

    response = client.post(f"/subscription/{sub.id}/unsubscribe/")
    assert response.status_code == 200
    assert response.content.decode() == "OK"
    assert not Subscription.objects.filter(id=sub.id).exists()


def test_revivefeed_post(client, user, make_source):
    client.force_login(user)
    source = make_source()
    source.live = False
    source.etag = "abc"
    source.last_modified = "yesterday"
    source.save()

    response = client.post(f"/feed/{source.id}/revive/")
    assert response.status_code == 200
    assert response.content.decode() == "OK"

    source.refresh_from_db()
    assert source.live is True
    assert source.etag is None
    assert source.last_modified is None


@patch("ft.views.test_feed")
def test_testfeed_endpoint(test_feed_mock, client, user, make_source):
    client.force_login(user)
    source = make_source()

    response = client.get(f"/feed/{source.id}/test/?cache=yes")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain"
    assert test_feed_mock.called


@patch("ft.views.update_feeds")
def test_refresh_endpoint_calls_update_feeds(update_feeds_mock, client):
    response = client.get(reverse("refresh"))
    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain"
    update_feeds_mock.assert_called_once()
