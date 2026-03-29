import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from feeds.models import Post, Source, Subscription


@pytest.fixture
def user_model():
    return get_user_model()


@pytest.fixture
def user(user_model):
    return user_model.objects.create_user(
        email="user@example.com",
        password="testpass123",
        name="Test User",
    )


@pytest.fixture
def other_user(user_model):
    return user_model.objects.create_user(
        email="other@example.com",
        password="testpass123",
        name="Other User",
    )


@pytest.fixture
def superuser(user_model):
    return user_model.objects.create_superuser(
        email="admin@example.com",
        password="testpass123",
        name="Admin User",
    )


@pytest.fixture
def make_source():
    def _make_source(feed_url="https://example.com/feed.xml", name="Example Feed"):
        return Source.objects.create(
            feed_url=feed_url,
            name=name,
            due_poll=timezone.now(),
        )

    return _make_source


@pytest.fixture
def make_subscription(user, make_source):
    def _make_subscription(
        user_override=None, source=None, name="My Sub", parent=None, is_river=False
    ):
        owner = user_override or user
        src = source or make_source()
        return Subscription.objects.create(
            user=owner,
            source=src,
            name=name,
            parent=parent,
            is_river=is_river,
        )

    return _make_subscription


@pytest.fixture
def make_post(make_source):
    def _make_post(source=None, title="Title", body="Body", index=1):
        src = source or make_source()
        now = timezone.now()
        return Post.objects.create(
            source=src,
            title=title,
            body=body,
            found=now,
            created=now,
            index=index,
        )

    return _make_post
