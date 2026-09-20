from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from django.core.management import call_command
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("role", ["anonymous", "user", "superuser"])
@pytest.mark.parametrize("method", ["get", "post", "head", "put", "delete", "options"])
def test_removed_refresh_cannot_poll(client, request, role, method):
    if role != "anonymous":
        client.force_login(request.getfixturevalue(role))

    with patch("feeds.utils.update_feeds") as poll:
        # Also intercept the legacy view's imported reference on the old code.
        with patch("ft.views.update_feeds", create=True) as legacy_poll:
            response = getattr(client, method)("/refresh/")

    assert response.status_code == 404
    poll.assert_not_called()
    legacy_poll.assert_not_called()


def test_feed_garden_has_no_http_polling_action(client, superuser):
    client.force_login(superuser)

    response = client.get(reverse("feedgarden"))

    assert response.status_code == 200
    document = BeautifulSoup(response.content, "html.parser")
    assert not document.select('form[action="/refresh/"]')
    assert "Manual Refresh" not in document.get_text()


def test_operator_refreshfeeds_command_still_polls():
    with patch("feeds.management.commands.refreshfeeds.update_feeds") as poll:
        call_command("refreshfeeds")

    poll.assert_called_once_with(30)
