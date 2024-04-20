# Django settings for feedthing project.

import os
import sys

from feedthing import settings_server

SITE_ROOT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")

# Detect if running locally
RUNNING_LOCAL = 'runserver' in sys.argv

DEBUG = settings_server.DEBUG
LOG_LOCATION = settings_server.LOG_LOCATION
DATABASES = settings_server.DATABASES
if hasattr(settings_server, "EMAIL_BACKEND"):
    EMAIL_BACKEND = settings_server.EMAIL_BACKEND
    EMAIL_HOST = settings_server.EMAIL_HOST
    EMAIL_PORT = settings_server.EMAIL_PORT
    EMAIL_HOST_USER = settings_server.EMAIL_HOST_USER
    EMAIL_HOST_PASSWORD = settings_server.EMAIL_HOST_PASSWORD
    # EMAIL_USE_TLS = settings_server.EMAIL_USE_TLS


DEFAULT_FROM_EMAIL = settings_server.ADMIN_EMAIL_ADDRESS

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS


ALLOWED_HOSTS = settings_server.ALLOWED_HOSTS

INTERNAL_IPS = (
    '127.0.0.1',
)

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'GMT'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

USE_TZ = True

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"

STATIC_ROOT = getattr(settings_server, "STATIC_ROOT", os.path.join(SITE_ROOT, "static"))

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = '/static/admin/'


# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    )

# Make this unique, and don't share it with anybody.
SECRET_KEY = settings_server.SECRET_KEY


MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',

    # Add the account middleware:
    "allauth.account.middleware.AccountMiddleware",
]

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',

    # `allauth` specific authentication methods, such as login by email
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'


ROOT_URLCONF = 'feedthing.urls'

TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [os.path.join(SITE_ROOT, "templates")],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
                'debug': DEBUG,
            },
        },
    ]


INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'ft',
    'web',

    'feeds',

    'django.contrib.auth',
    'django.contrib.admin',

    'allauth',
    'allauth.account',
    # 'allauth.socialaccount',
    # 'allauth.socialaccount.providers.github',

]


SECURE_SSL_REDIRECT = settings_server.SECURE_SSL_REDIRECT

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

VERSION = "3.6"
FEEDS_USER_AGENT = f"FeedThing/{VERSION}"
FEEDS_SERVER = settings_server.FEEDS_SERVER
FEEDS_CLOUDFLARE_WORKER = settings_server.FEEDS_CLOUDFLARE_WORKER

AUTH_USER_MODEL = 'ft.User'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'pwned_passwords_django.validators.PwnedPasswordsValidator',
    },
]

LOGIN_REDIRECT_URL = '/feeds/'

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {
        "level": "INFO",
        "handlers": ["console" if RUNNING_LOCAL else "file"]
    },
    "handlers": {
        "file": {
            "level": "INFO",
            'class': 'logging.handlers.RotatingFileHandler',
            "filename": LOG_LOCATION,
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
            "formatter": "colored" if RUNNING_LOCAL else "app",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "colored",
        },
    },
    "loggers": {
        "django": {
            "handlers": [],
            "level": "INFO",
            "propagate": True
        },
    },
    "formatters": {
        "app": {
            "format": (
                u"%(asctime)s [%(levelname)-8s] "
                "(%(module)s.%(funcName)s) %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "colored": {
            "()": "colorlog.ColoredFormatter",
            "format": "%(log_color)s%(asctime)s [%(levelname)-8s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "log_colors": {
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red",
            },
        },
    },
}
