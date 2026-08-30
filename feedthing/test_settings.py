import runpy
import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType

from django.test import Client, override_settings

FEEDTHING_PACKAGE = import_module("feedthing")
SETTINGS_PATH = Path(__file__).with_name("settings.py")


def load_settings(monkeypatch, **overrides):
    server_settings = ModuleType("feedthing.settings_server")
    values = {
        "ADMIN_EMAIL_ADDRESS": "admin@example.com",
        "ALLOWED_HOSTS": ["testserver"],
        "DATABASES": {},
        "DEBUG": False,
        "FEEDS_CLOUDFLARE_WORKER": None,
        "FEEDS_SERVER": "https://example.com/",
        "LOG_LOCATION": "/tmp/feedthing-test.log",
        "SECRET_KEY": "test-only-secret-key",
        "SECURE_SSL_REDIRECT": True,
    }
    values.update(overrides)
    for name, value in values.items():
        setattr(server_settings, name, value)

    monkeypatch.setitem(sys.modules, "feedthing.settings_server", server_settings)
    monkeypatch.setattr(
        FEEDTHING_PACKAGE, "settings_server", server_settings, raising=False
    )
    return runpy.run_path(str(SETTINGS_PATH))


def test_security_middleware_runs_first(monkeypatch):
    project_settings = load_settings(monkeypatch)

    assert project_settings["MIDDLEWARE"][0] == (
        "django.middleware.security.SecurityMiddleware"
    )


@override_settings(SECURE_SSL_REDIRECT=True)
def test_security_middleware_redirects_http_requests_to_https():
    response = Client().get("/")

    assert response.status_code == 301
    assert response["Location"] == "https://testserver/"


def test_production_uses_secure_cookies(monkeypatch):
    project_settings = load_settings(monkeypatch, DEBUG=False)

    assert project_settings["SESSION_COOKIE_SECURE"] is True
    assert project_settings["CSRF_COOKIE_SECURE"] is True


def test_local_development_allows_http_cookies(monkeypatch):
    project_settings = load_settings(monkeypatch, DEBUG=True)

    assert project_settings["SESSION_COOKIE_SECURE"] is False
    assert project_settings["CSRF_COOKIE_SECURE"] is False


def test_hsts_and_proxy_trust_default_to_disabled(monkeypatch):
    project_settings = load_settings(monkeypatch)

    assert project_settings["SECURE_HSTS_SECONDS"] == 0
    assert project_settings["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is False
    assert project_settings["SECURE_HSTS_PRELOAD"] is False
    assert project_settings["SECURE_PROXY_SSL_HEADER"] is None


def test_production_can_explicitly_enable_hsts_and_proxy_trust(monkeypatch):
    project_settings = load_settings(
        monkeypatch,
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    )

    assert project_settings["SECURE_HSTS_SECONDS"] == 31536000
    assert project_settings["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is True
    assert project_settings["SECURE_HSTS_PRELOAD"] is True
    assert project_settings["SECURE_PROXY_SSL_HEADER"] == (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )


def test_debug_mode_disables_hsts_even_if_configured(monkeypatch):
    project_settings = load_settings(
        monkeypatch,
        DEBUG=True,
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
    )

    assert project_settings["SECURE_HSTS_SECONDS"] == 0
    assert project_settings["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is False
    assert project_settings["SECURE_HSTS_PRELOAD"] is False
