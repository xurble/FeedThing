import importlib

from django.apps import AppConfig

from . import feed_http


class FTConfig(AppConfig):
    name = "ft"

    def ready(self):
        # django-feed-reader 2.0.1b5 has no transport setting. Replace only its
        # module-local requests references, never the shared requests module.
        # utils_internal also fetches pagination links while parsing feeds.
        for module_name in ("feeds.utils", "feeds.utils_internal"):
            module = importlib.import_module(module_name)
            module.requests = feed_http
