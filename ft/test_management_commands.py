import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from feeds.models import Subscription

from ft.models import SavedPost


@pytest.mark.django_db
def test_removed_testme_command_preserves_subscriptions_and_saved_posts(
    user, other_user, make_source, make_subscription, make_post
):
    source = make_source()
    parent_source = make_source(feed_url="https://example.com/parent.xml")
    for owner in (user, other_user):
        parent = make_subscription(
            user_override=owner, source=parent_source, is_river=True
        )
        subscription = make_subscription(
            user_override=owner, source=source, parent=parent
        )
        post = make_post(source=source, index=owner.pk)
        SavedPost.objects.create(user=owner, post=post, subscription=subscription)

    subscriptions_before = list(Subscription.objects.order_by("pk").values())
    saved_posts_before = list(SavedPost.objects.order_by("pk").values())

    with pytest.raises(CommandError, match="Unknown command: 'testme'"):
        call_command("testme")

    assert list(Subscription.objects.order_by("pk").values()) == subscriptions_before
    assert list(SavedPost.objects.order_by("pk").values()) == saved_posts_before
