import pytest
from django.contrib.auth import authenticate
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client, superuser, settings):
    settings.AUTH_PASSWORD_VALIDATORS = [
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}
    ]
    client.force_login(superuser)
    return client


@pytest.fixture
def account_data():
    return {
        "email": "new@example.com",
        "name": "New Reader",
        "password1": "A-long-test-password-100",
        "password2": "A-long-test-password-100",
        "_save": "Save",
    }


def test_admin_creates_user_with_hashed_authenticating_password(
    admin_client, user_model, account_data
):
    response = admin_client.post(reverse("admin:ft_user_add"), account_data)
    assert response.status_code == 302
    user = user_model.objects.get(email=account_data["email"])
    assert user.name == account_data["name"]
    assert user.password != account_data["password1"]
    assert user.check_password(account_data["password1"])
    assert authenticate(email=user.email, password=account_data["password1"]) == user
    assert not user.is_staff
    assert not user.is_superuser


@pytest.mark.parametrize("password2", ["different-password", ""])
def test_admin_creation_rejects_missing_or_mismatched_confirmation(
    admin_client, user_model, account_data, password2
):
    account_data["password2"] = password2
    response = admin_client.post(reverse("admin:ft_user_add"), account_data)
    assert response.status_code == 200
    assert "password2" in response.context["adminform"].form.errors
    assert not user_model.objects.filter(email=account_data["email"]).exists()


def test_admin_creation_runs_password_validation(
    admin_client, user_model, account_data
):
    account_data.update(password1="short", password2="short")
    response = admin_client.post(reverse("admin:ft_user_add"), account_data)
    assert response.status_code == 200
    assert "password2" in response.context["adminform"].form.errors
    assert not user_model.objects.filter(email=account_data["email"]).exists()


def test_admin_profile_edit_cannot_replace_or_expose_password(admin_client, user):
    original_hash = user.password
    url = reverse("admin:ft_user_change", args=[user.pk])
    response = admin_client.get(url)
    assert response.status_code == 200
    assert original_hash not in response.content.decode()
    assert b'name="password"' not in response.content
    response = admin_client.post(
        url,
        {
            "email": user.email,
            "name": "Edited Reader",
            "salutation": "Reader",
            "default_to_river": "on",
            "is_active": "on",
            "password": "injected-plain-text",
            "_save": "Save",
        },
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.name == "Edited Reader"
    assert user.salutation == "Reader"
    assert user.default_to_river
    assert user.password == original_hash


def test_admin_changes_password_through_dedicated_workflow(admin_client, user):
    url = reverse("admin:auth_user_password_change", args=[user.pk])
    assert admin_client.get(url).status_code == 200
    password = "Replacement-test-password-100"
    response = admin_client.post(url, {"password1": password, "password2": password})
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.password != password
    assert user.check_password(password)
    assert not user.check_password("testpass123")
    assert authenticate(email=user.email, password=password) == user


@pytest.mark.parametrize(
    ("password1", "password2"),
    [("Replacement-test-password-100", "different-password"), ("short", "short")],
)
def test_admin_password_change_rejects_invalid_passwords(
    admin_client, user, password1, password2
):
    original_hash = user.password
    response = admin_client.post(
        reverse("admin:auth_user_password_change", args=[user.pk]),
        {"password1": password1, "password2": password2},
    )
    assert response.status_code == 200
    assert response.context["adminForm"].form.errors
    user.refresh_from_db()
    assert user.password == original_hash


def test_non_admin_cannot_create_users_or_change_passwords(client, user, user_model):
    client.force_login(user)
    original_hash = user.password
    response = client.post(
        reverse("admin:ft_user_add"),
        {"email": "blocked@example.com", "name": "Blocked", "password1": "password"},
    )
    assert response.status_code == 302
    assert not user_model.objects.filter(email="blocked@example.com").exists()
    response = client.post(
        reverse("admin:auth_user_password_change", args=[user.pk]),
        {
            "password1": "Replacement-test-password-100",
            "password2": "Replacement-test-password-100",
        },
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.password == original_hash
