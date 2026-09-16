import json

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "route,parameter", [("feeds", "feed"), ("allfeeds", "feed"), ("manage", "s")]
)
@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 0),
        ("0", 0),
        ("42", 42),
        ("2147483647", 2147483647),
        ("", 0),
        ("-1", 0),
        ("2147483648", 0),
        ("9" * 5000, 0),
        ("1.5", 0),
        ("1e2", 0),
        ("0x10", 0),
        ("1_000", 0),
        ("0);alert(document.domain)//", 0),
        ("</script><script>alert(document.domain)</script>", 0),
    ],
)
def test_subscription_preload_is_bounded_inert_json(
    client, user, route, parameter, value, expected
):
    client.force_login(user)
    response = client.get(reverse(route), {} if value is None else {parameter: value})
    assert response.status_code == 200
    assert type(response.context["preload"]) is int
    assert response.context["preload"] == expected
    soup = BeautifulSoup(response.content, "html.parser")
    data = soup.find("script", id="subscription-preload")
    assert data["type"] == "application/json"
    assert json.loads(data.string) == expected
    for script in soup.find_all("script"):
        if script.get("type") != "application/json":
            assert "alert(document.domain)" not in script.get_text()


@pytest.mark.parametrize("route", ["feeds", "allfeeds"])
@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 1),
        ("1", 1),
        ("42", 42),
        ("2147483647", 2147483647),
        ("0", 1),
        ("-1", 1),
        ("2147483648", 1),
        ("9" * 5000, 1),
        ("", 1),
        ("1.5", 1),
        ("1e2", 1),
        ("1_000", 1),
        ("1);alert(document.domain)//", 1),
        ("</script><script>alert(document.domain)</script>", 1),
    ],
)
def test_page_preload_is_bounded_inert_json(client, user, route, value, expected):
    client.force_login(user)
    query = {"feed": "42"}
    if value is not None:
        query["page"] = value
    response = client.get(reverse(route), query)
    assert response.status_code == 200
    assert type(response.context["page"]) is int
    assert response.context["page"] == expected
    soup = BeautifulSoup(response.content, "html.parser")
    data = soup.find("script", id="page-preload")
    assert data["type"] == "application/json"
    assert json.loads(data.string) == expected
    for script in soup.find_all("script"):
        if script.get("type") != "application/json":
            assert "alert(document.domain)" not in script.get_text()
