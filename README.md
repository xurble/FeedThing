FeedThing
=========

FeedThing is a django-based feed reader.  I created it when Bloglines was shutting down because I didn't like Google Reader and then of course that shut down anyway.

FeedThing supports all common feed flavours - RSS, Atom and JSON Feed.  It works just as well on mobile as on desktop browsers.

FeedThing treats feeds in the specific manner that I believe to be right.  

- Regular (I want to read everything by this author) feeds are displayed with all the unread posts in *chronological* order.
- High traffic news feeds display all the posts in *reverse chronological* order, paginated 20 posts to a page.
- Regular feeds that have been read up to date display their old posts in *reverse chronological* order, paginated.
 
So you can use FeedThing as both a catch-up, never-miss-a-post service, and a Dave Winer-esque river of news _at the same time_.

Feeds can be placed into folders in which case all the feeds in the folder are treated as if they were a single feed.  There is no further nesting, folders are a single level deep.

A single FeedThing installation can support multiple users, each with their own settings and list of feeds.  Embarrassingly, there is no UI to create those users just now.

I have used this as my daily RSS reader for over a decade.  It is probably missing features that other readers have, but nothing that I have ever missed.

Enjoy.

Installation
============

FeedThing is a pretty simple Python 3 / Django 2.2 application.  There are a few external dependencies that need pip installing (listed in requirements.txt)

The django `settings.py` file  is not quite complete.  It imports some of its settings from `settings_server.py` which is listed in `.gitignore` because it is installation specific.  There is an example.

Host it as you would any other django app.  I had it running for years under fastcgi and it was fine.  I currently run it behind gunicorn & nginx which is better.

### Production HTTPS

Production installations (`DEBUG = False`) mark session and CSRF cookies as
secure, so the site must be served over HTTPS. Keep `SECURE_SSL_REDIRECT = True`
unless the front-end server already redirects every HTTP request before it can
reach Django.

If TLS terminates at a reverse proxy, configure the proxy to remove any
client-supplied `X-Forwarded-Proto` header and replace it with the scheme used by
the original client. Only then enable the following in `settings_server.py`:

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

Do not set `SECURE_PROXY_SSL_HEADER` when Django receives HTTPS directly or the
proxy cannot guarantee that header. A mistaken trust configuration can make an
HTTP request appear secure and can also cause redirect loops.

HSTS is disabled for existing installations until `SECURE_HSTS_SECONDS` is
explicitly configured. Start with a short duration after confirming that the
entire site is HTTPS-only:

```python
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
```

After a successful rollout, increase the duration (commonly to `31536000`). Only
enable subdomains when every subdomain is HTTPS-only, and only enable preload
after meeting browser preload requirements. Run `python manage.py check --deploy`
with the production settings before every deployment; review each warning in the
context of the front-end server and proxy configuration.

Once it is running, keep it reading feeds by scheduling the management command `manage.py refreshfeeds`. The former `/refresh/` HTTP trigger has been removed. Before deploying, migrate any scheduler that still calls it to `manage.py refreshfeeds`; manual operator refreshes use the same command.

I have that set up as a cron job every five minutes.  This was a cheesy way to work around the severe lameness of my last hosting, but its working well enough that I still do it that way.  Celery beat would work too.

Make yourself the first login using `manage.py createsuperuser`

And that's it.
