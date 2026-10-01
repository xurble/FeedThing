import pytest
from django.db.models.signals import post_init
from feeds.models import Subscription

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("missing", [False, True])
@pytest.mark.parametrize(
    "endpoint",
    [
        "details-get",
        "details-post",
        "rename",
        "promote",
        "addto",
        "target",
        "unsubscribe",
    ],
)
def test_rejected_subscription_access_does_not_load_or_mutate_foreign_objects(
    client, user, other_user, make_subscription, endpoint, missing
):
    own = make_subscription()
    foreign = make_subscription(user_override=other_user, source=own.source)
    identifier = foreign.pk + 10000 if missing else foreign.pk
    before = list(Subscription.objects.order_by("pk").values())
    loaded = []

    def record_loaded_subscription(sender, instance, **kwargs):
        loaded.append(instance.pk)

    client.force_login(user)
    post_init.connect(record_loaded_subscription, sender=Subscription)
    try:
        if endpoint == "details-get":
            response = client.get(f"/subscription/{identifier}/details/")
        elif endpoint == "details-post":
            response = client.post(
                f"/subscription/{identifier}/details/", {"subname": "Changed"}
            )
        elif endpoint == "target":
            response = client.post(f"/subscription/{own.pk}/addto/{identifier}/")
        else:
            suffix = "addto/0" if endpoint == "addto" else endpoint
            response = client.post(
                f"/subscription/{identifier}/{suffix}/", {"name": "Changed"}
            )
    finally:
        post_init.disconnect(record_loaded_subscription, sender=Subscription)

    assert response.status_code == (404 if missing else 403)
    assert foreign.pk not in loaded
    assert list(Subscription.objects.order_by("pk").values()) == before


@pytest.mark.parametrize("method", ["put", "patch", "delete", "head", "options"])
@pytest.mark.parametrize(
    "endpoint", ["details", "rename", "promote", "addto/0", "revive"]
)
def test_subscription_methods_reject_without_mutation(
    client, superuser, make_subscription, method, endpoint
):
    sub = make_subscription(user_override=superuser)
    source = sub.source
    before = list(Subscription.objects.order_by("pk").values())
    source_before = (source.live, source.due_poll, source.etag, source.last_modified)
    client.force_login(superuser)
    url = (
        f"/feed/{source.pk}/revive/"
        if endpoint == "revive"
        else f"/subscription/{sub.pk}/{endpoint}/"
    )
    response = getattr(client, method)(url)
    assert response.status_code == 405
    assert response.headers["Allow"] == (
        "GET, POST" if endpoint == "details" else "POST"
    )
    assert list(Subscription.objects.order_by("pk").values()) == before
    source.refresh_from_db()
    assert (
        source.live,
        source.due_poll,
        source.etag,
        source.last_modified,
    ) == source_before


def test_owner_can_update_subscription_details(client, user, make_subscription):
    sub = make_subscription()
    client.force_login(user)
    response = client.post(
        f"/subscription/{sub.pk}/details/", {"subname": "Updated", "is_river": "on"}
    )
    assert response.status_code == 200
    sub.refresh_from_db()
    assert sub.name == "Updated"
    assert sub.is_river is True
