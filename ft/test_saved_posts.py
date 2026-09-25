import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from django.db import OperationalError, connection, connections, transaction
from django.db.models.query import QuerySet
from django.test import Client, RequestFactory
from django.urls import reverse

from ft.models import SavedPost
from ft.views import forgetpost, savepost

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("endpoint", ["savepost", "forgetpost"])
def test_saved_post_mutations_require_login(client, make_post, endpoint):
    post = make_post()
    response = client.post(reverse(endpoint, args=[post.pk]))
    assert response.status_code == 302
    assert not SavedPost.objects.exists()


@pytest.mark.parametrize("endpoint", ["savepost", "forgetpost"])
def test_saved_post_mutations_reject_missing_posts(client, user, endpoint):
    client.force_login(user)
    response = client.post(reverse(endpoint, args=[999999]))
    assert response.status_code == 404
    assert not SavedPost.objects.exists()


@pytest.mark.parametrize("endpoint", ["savepost", "forgetpost"])
def test_saved_post_mutations_require_csrf(
    user, make_subscription, make_post, endpoint
):
    sub = make_subscription()
    post = make_post(source=sub.source)
    saved = SavedPost.objects.create(user=user, post=post, subscription=sub)
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    response = client.post(reverse(endpoint, args=[post.pk]))
    assert response.status_code == 403
    assert list(SavedPost.objects.values_list("pk", flat=True)) == [saved.pk]


def test_save_rejects_unsubscribed_source(client, user, make_post):
    post = make_post()
    client.force_login(user)
    for _ in range(2):
        response = client.post(reverse("savepost", args=[post.pk]))
        assert response.status_code == 404
    assert not SavedPost.objects.exists()


def test_save_requires_own_subscription(
    client, user, other_user, make_source, make_subscription, make_post
):
    source = make_source()
    post = make_post(source=source)
    sub = make_subscription(source=source, user_override=other_user)
    other_saved = SavedPost.objects.create(user=other_user, post=post, subscription=sub)
    client.force_login(user)

    for _ in range(2):
        response = client.post(reverse("savepost", args=[post.pk]))
        assert response.status_code == 404
    assert list(SavedPost.objects.values_list("pk", flat=True)) == [other_saved.pk]


def test_forget_cannot_remove_another_users_saved_post(
    client, user, other_user, make_subscription, make_post
):
    sub = make_subscription(user_override=other_user)
    post = make_post(source=sub.source)
    other_saved = SavedPost.objects.create(user=other_user, post=post, subscription=sub)
    client.force_login(user)

    for _ in range(2):
        response = client.post(reverse("forgetpost", args=[post.pk]))
        assert response.status_code == 200
        assert response.content == b"OK"
    assert list(SavedPost.objects.values_list("pk", flat=True)) == [other_saved.pk]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("view", [savepost, forgetpost], ids=["save", "forget"])
def test_saved_post_write_contention_is_retryable(
    user, make_subscription, make_post, view
):
    if connection.vendor != "sqlite":
        pytest.skip(
            "Exercises SQLite write-lock contention using independent connections"
        )
    sub = make_subscription()
    post = make_post(source=sub.source)
    if view is forgetpost:
        SavedPost.objects.create(user=user, post=post, subscription=sub)
    locked = Event()
    release = Event()

    def hold_write_lock():
        try:
            with transaction.atomic():
                if view is savepost:
                    SavedPost.objects.create(user=user, post=post, subscription=sub)
                else:
                    SavedPost.objects.filter(user=user, post=post).update(
                        subscription=sub
                    )
                locked.set()
                assert release.wait(timeout=10), (
                    "Request did not finish while lock was held"
                )
        finally:
            connections.close_all()

    request = RequestFactory().post("/")
    request.user = user
    # Keep a real file-backed SQLite database's lock wait below the test deadline.
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA busy_timeout")
        original_timeout = cursor.fetchone()[0]
        cursor.execute("PRAGMA busy_timeout = 100")
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            writer = executor.submit(hold_write_lock)
            try:
                assert locked.wait(timeout=5), "Writer did not acquire its lock"
                response = view(request, post.pk)
            finally:
                release.set()
            writer.result(timeout=5)
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"PRAGMA busy_timeout = {original_timeout}")

    assert response.status_code == 503
    assert response["Retry-After"] == "1"
    assert SavedPost.objects.filter(user=user, post=post).count() == 1
    # Retrying after the competing transaction completes reaches the desired state.
    for _ in range(2):
        response = view(request, post.pk)
        assert response.status_code == 200
        assert response.content == b"OK"
    assert SavedPost.objects.filter(user=user, post=post).count() == (view is savepost)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("view", [savepost, forgetpost], ids=["save", "forget"])
def test_simultaneous_saved_post_requests(
    user, make_subscription, make_post, monkeypatch, view
):
    sub = make_subscription()
    post = make_post(source=sub.source)
    if view is forgetpost:
        SavedPost.objects.create(user=user, post=post, subscription=sub)
    barrier = Barrier(2, timeout=5)
    method_name = "create" if view is savepost else "delete"
    original = getattr(QuerySet, method_name)

    def overlap(queryset, *args, **kwargs):
        if queryset.model is SavedPost:
            barrier.wait()
        return original(queryset, *args, **kwargs)

    def mutate():
        try:
            request = RequestFactory().post("/")
            request.user = user
            return view(request, post.pk).status_code
        finally:
            connections.close_all()

    with monkeypatch.context() as patch:
        patch.setattr(QuerySet, method_name, overlap)
        with ThreadPoolExecutor(max_workers=2) as executor:
            requests = [executor.submit(mutate) for _ in range(2)]
            statuses = [request.result(timeout=10) for request in requests]
    assert 200 in statuses
    assert set(statuses) <= {200, 503}
    assert SavedPost.objects.filter(user=user, post=post).count() == (view is savepost)
    # A client may safely retry either operation, including one that got a 503.
    assert mutate() == 200
    assert SavedPost.objects.filter(user=user, post=post).count() == (view is savepost)


@pytest.mark.parametrize("view", [savepost, forgetpost], ids=["save", "forget"])
@pytest.mark.parametrize(
    ("vendor", "code"),
    [
        ("sqlite", sqlite3.SQLITE_BUSY),
        ("sqlite", sqlite3.SQLITE_LOCKED_SHAREDCACHE),
        ("mysql", 1205),
        ("mysql", 1213),
    ],
)
def test_recognized_contention_codes_return_retryable_response(
    user, monkeypatch, view, vendor, code
):
    driver_error = sqlite3.OperationalError("driver error")
    if vendor == "sqlite":
        driver_error.sqlite_errorcode = code
    error = OperationalError(code, "driver error")
    error.__cause__ = driver_error

    def fail_lookup(*args, **kwargs):
        raise error

    monkeypatch.setattr("ft.views.get_object_or_404", fail_lookup)
    monkeypatch.setattr(connection, "vendor", vendor)
    request = RequestFactory().post("/")
    request.user = user
    response = view(request, 1)
    assert response.status_code == 503
    assert response["Retry-After"] == "1"
    assert b"driver error" not in response.content


@pytest.mark.parametrize("view", [savepost, forgetpost], ids=["save", "forget"])
@pytest.mark.parametrize("vendor", ["sqlite", "mysql"])
def test_unrelated_database_errors_are_not_hidden(user, monkeypatch, view, vendor):
    error = OperationalError("database unavailable")

    def fail_lookup(*args, **kwargs):
        raise error

    monkeypatch.setattr("ft.views.get_object_or_404", fail_lookup)
    monkeypatch.setattr(connection, "vendor", vendor)
    request = RequestFactory().post("/")
    request.user = user
    with pytest.raises(OperationalError, match="database unavailable"):
        view(request, 1)
