import importlib

from django.apps import AppConfig

from . import feed_http


class FTConfig(AppConfig):
    name = "ft"

    def ready(self):
        # django-feed-reader 2.0.1b5 has no transport setting. Replace only its
        # module-local requests reference, never the shared requests module.
        # This covers its polling management commands as well as web callers.
        feed_utils = importlib.import_module("feeds.utils")
        feed_utils.requests = feed_http
