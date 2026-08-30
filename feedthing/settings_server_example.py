import os

SITE_ROOT = os.path.dirname(os.path.realpath(__file__))


ALLOWED_HOSTS = ["localhost"]  # change this to your servers domain

FEEDS_SERVER = "https://example.com/"  # change this to where you are running  -  it's in the user agent string used when polling sites
FEEDS_CLOUDFLARE_WORKER = None  # You will need a cloudflare account with the django-feed-reader cloudflare worker installed to use this setting

ADMIN_EMAIL_ADDRESS = "bob@example.com"

DEBUG = False  # or true if you are running locally

SECURE_SSL_REDIRECT = not DEBUG

# Enable HSTS gradually after confirming that the entire site is HTTPS-only.
# Start with one hour, then increase to 31536000 after a successful rollout.
SECURE_HSTS_SECONDS = 3600 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Leave this unset when Gunicorn receives HTTPS directly. When TLS terminates at
# a reverse proxy, enable it only if the proxy strips any incoming
# X-Forwarded-Proto header and sets its own trusted value.
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# this is where collectstatic will gather its files
STATIC_ROOT = os.path.join(SITE_ROOT, "..", "static")


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",  # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        "NAME": "feedthing",  # Or path to database file if using sqlite3.
        "USER": "auser",  # Not used with sqlite3.
        "PASSWORD": "apassword",  # Not used with sqlite3.
        "HOST": "",  # Set to empty string for localhost. Not used with sqlite3.
        "PORT": "",  # Set to empty string for default. Not used with sqlite3.
        "OPTIONS": {
            "init_command": "SET default_storage_engine=INNODB",
        },
    }
}

# Make this unique, and don't share it with anybody.
SECRET_KEY = "BigLongStringOfCharactersHere"
