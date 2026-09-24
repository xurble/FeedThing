from unittest.mock import patch

import pytest
from feeds.models import Subscription

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("destination", ["existing", "new", "feed"])
@pytest.mark.parametrize("keep_sibling", [False, True])
def test_move_cleans_only_empty_former_folder(
    client, user, make_source, make_subscription, destination, keep_sibling
):
    old = Subscription.objects.create(user=user, name="Old folder")
    moved = make_subscription(parent=old)
    sibling = None
    if keep_sibling:
        sibling = make_subscription(
            source=make_source(feed_url="https://example.com/sibling.xml"), parent=old
        )
    if destination == "existing":
        target = Subscription.objects.create(user=user, name="Destination")
    elif destination == "feed":
        target = make_subscription(
            source=make_source(feed_url="https://example.com/target.xml")
        )
    else:
        target = None

    client.force_login(user)
    response = client.post(
        f"/subscription/{moved.id}/addto/{target.id if target else 0}/"
    )

    assert response.status_code == 200
    moved.refresh_from_db()
    assert moved.parent_id == int(response.content)
    assert moved.parent.source_id is None
    assert moved.parent.user_id == user.id
    assert Subscription.objects.filter(pk=old.pk).exists() is keep_sibling
    if sibling:
        sibling.refresh_from_db()
        assert sibling.parent_id == old.pk
    if destination == "existing":
        assert moved.parent_id == target.pk
    elif destination == "feed":
        target.refresh_from_db()
        assert target.parent_id == moved.parent_id


@pytest.mark.parametrize("shared_parent", [False, True])
@pytest.mark.parametrize("keep_sibling", [False, True])
def test_grouping_two_feeds_cleans_both_former_folders(
    client, user, make_source, make_subscription, shared_parent, keep_sibling
):
    old = Subscription.objects.create(user=user, name="Original")
    target_old = (
        old
        if shared_parent
        else Subscription.objects.create(user=user, name="Target original")
    )
    moved = make_subscription(parent=old)
    target = make_subscription(
        source=make_source(feed_url="https://example.com/target.xml"), parent=target_old
    )
    if keep_sibling:
        sibling = make_subscription(
            source=make_source(feed_url="https://example.com/sibling.xml"),
            parent=target_old,
        )

    client.force_login(user)
    response = client.post(f"/subscription/{moved.id}/addto/{target.id}/")

    assert response.status_code == 200
    moved.refresh_from_db()
    target.refresh_from_db()
    assert moved.parent_id == target.parent_id == int(response.content)
    assert Subscription.objects.filter(pk=target_old.pk).exists() is keep_sibling
    assert Subscription.objects.filter(pk=old.pk).exists() is (
        shared_parent and keep_sibling
    )
    if keep_sibling:
        sibling.refresh_from_db()
        assert sibling.parent_id == target_old.pk


def test_move_within_same_folder_preserves_folder(client, user, make_subscription):
    folder = Subscription.objects.create(user=user, name="Same folder")
    moved = make_subscription(parent=folder)
    client.force_login(user)

    response = client.post(f"/subscription/{moved.id}/addto/{folder.id}/")

    assert response.status_code == 200
    moved.refresh_from_db()
    assert moved.parent_id == folder.pk
    assert Subscription.objects.filter(pk=folder.pk).exists()


@pytest.mark.parametrize("destination", ["existing", "new", "feed"])
def test_cleanup_failure_rolls_back_entire_move(
    client, user, make_source, make_subscription, destination
):
    old = Subscription.objects.create(user=user, name="Original")
    moved = make_subscription(parent=old)
    target = None
    if destination == "existing":
        target = Subscription.objects.create(user=user, name="Destination")
    elif destination == "feed":
        target = make_subscription(
            source=make_source(feed_url="https://example.com/target.xml")
        )
    before = list(Subscription.objects.order_by("pk").values())
    client.force_login(user)

    with patch.object(
        Subscription, "delete", side_effect=RuntimeError("cleanup failed")
    ):
        with pytest.raises(RuntimeError, match="cleanup failed"):
            client.post(f"/subscription/{moved.id}/addto/{target.id if target else 0}/")

    assert list(Subscription.objects.order_by("pk").values()) == before
