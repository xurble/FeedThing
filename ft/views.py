# Create your views here.

import datetime
import html
import json
import logging
from io import BytesIO
from urllib.parse import urljoin
from xml.dom import minidom

import feedparser
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, InvalidPage, Paginator
from django.db import transaction
from django.db.models import Prefetch, Q, prefetch_related_objects
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from feeds.models import Post, Source, Subscription
from feeds.utils import (
    get_subscription_list_for_user,
    get_unread_subscription_list_for_user,
)

from .feed_http import UnsafeFeedURL, validate_feed_url
from .feed_http import get as get_feed
from .forms import SettingsForm
from .models import SavedPost
from .url_safety import normalize_navigation_url

logger = logging.getLogger(__name__)


def _prepare_posts_for_render(posts, user, include_enclosures=False):
    post_list = list(posts)
    related_lookups = [
        Prefetch(
            "savedpost_set",
            queryset=SavedPost.objects.filter(user=user).only("post_id"),
            to_attr="saved_for_user",
        )
    ]
    if include_enclosures:
        related_lookups.append("enclosures")

    prefetch_related_objects(post_list, *related_lookups)
    return post_list


def _preload_integer(request, parameter, default):
    """Accept bounded decimal integers for browser preload data."""
    raw = request.GET.get(parameter, str(default))
    # Bound conversion work and stay within the project's signed AutoField range.
    if not raw or len(raw) > 10 or not raw.isascii() or not raw.isdecimal():
        return default
    value = int(raw)
    return value if default <= value <= 2147483647 else default


def _get_owned_subscription_or_403(request, subscription_id):
    subscription = get_object_or_404(Subscription, id=int(subscription_id))
    if subscription.user != request.user:
        raise PermissionDenied
    return subscription


def _require_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied


def index(request):
    if request.user.is_authenticated:
        if request.user.default_to_river:
            return HttpResponseRedirect(reverse("userriver"))
        else:
            return HttpResponseRedirect(reverse("feeds"))
    else:
        return render(request, "index.html", {})


def help(request):
    return render(request, "help.html", {})


def well_known_uris(request, uri):
    """
    https://www.iana.org/assignments/well-known-uris/well-known-uris.xhtml
    """

    logging.info("Request for .well-known URI: {}".format(uri))

    if uri == "change-password":
        # https://twitter.com/rmondello/status/1009495517494173697?lang=en
        return HttpResponseRedirect(reverse("account_change_password"))

    raise Http404  # not implemented


@login_required
def user_settings(request):
    if request.method == "POST":
        form = SettingsForm(instance=request.user, data=request.POST)
        if form.is_valid():
            request.user = form.save()
            messages.success(request, "Settings saved.")
    else:
        form = SettingsForm(instance=request.user)

    vals = {"settings_form": form}

    return render(request, "settings.html", vals)


@login_required
def feeds(request):
    vals = {}

    sources = get_unread_subscription_list_for_user(request.user)

    vals["sources"] = sources
    vals["all"] = False

    vals["preload"] = _preload_integer(request, "feed", 0)
    vals["page"] = _preload_integer(request, "page", 1)

    return render(request, "feeds.html", vals)


@login_required
def user_river(request):
    vals = {}
    q = request.GET.get("q", "")

    sub_list = list(
        Subscription.objects.filter(user=request.user).filter(source__isnull=False)
    )

    sources = [sub.source_id for sub in sub_list]

    post_list = Post.objects.filter(source__in=sources)

    if q != "":
        post_list = post_list.filter(Q(title__icontains=q) | Q(body__icontains=q))

    post_list = post_list.order_by("-created")

    try:
        page = int(request.GET.get("page", "1"))
    except Exception:
        page = 1

    paginator = Paginator(post_list, 100)

    try:
        posts = paginator.page(page)
    except (EmptyPage, InvalidPage):
        posts = paginator.page(1)

    subscription_by_source_id = {sub.source_id: sub for sub in sub_list}
    _prepare_posts_for_render(posts, request.user)

    # assign subscriptions
    for p in posts:
        p.subscription = subscription_by_source_id[p.source_id]

    vals["posts"] = posts
    vals["paginator"] = paginator
    vals["q"] = q
    vals["subscription"] = {"id": 0}

    return render(request, "user_river.html", vals)


@login_required
@require_GET
def managefeeds(request):
    vals = {}
    subscriptions = get_subscription_list_for_user(request.user)

    vals["subscriptions"] = subscriptions
    vals["preload"] = _preload_integer(request, "s", 0)

    return render(request, "manage.html", vals)


@login_required
@require_GET
def subscriptionlist(request):
    subscriptions = get_subscription_list_for_user(request.user)
    return render(request, "sublist.html", {"subscriptions": subscriptions})


@login_required
def allfeeds(request):
    vals = {}

    sources = get_subscription_list_for_user(request.user)

    vals["sources"] = sources
    vals["all"] = True

    vals["preload"] = _preload_integer(request, "feed", 0)
    vals["page"] = _preload_integer(request, "page", 1)

    return render(request, "feeds.html", vals)


@login_required
@require_GET
def feedgarden(request):
    _require_superuser(request)

    vals = {}
    vals["feeds"] = Source.objects.all().order_by("due_poll")
    return render(request, "feedgarden.html", vals)


@login_required
def addfeed(request):
    try:
        if request.method == "GET":
            feed = request.GET.get("feed", "")
            groups = Subscription.objects.filter(Q(user=request.user) & Q(source=None))

            return render(request, "addfeed.html", {"feed": feed, "groups": groups})

        else:
            feed = request.POST.get("feed", "").strip()
            try:
                validate_feed_url(feed)
            except ValueError:
                logger.warning("Rejected invalid add-feed URL", exc_info=True)
                return HttpResponse(
                    "<div>The feed URL is invalid or not allowed.</div>", status=400
                )

            # identify ourselves and also stop our requests getting picked up by google's cache
            headers = {
                "User-Agent": "{agent} (+{server}; Initial Feed Crawler)".format(
                    agent=settings.FEEDS_USER_AGENT, server=settings.FEEDS_SERVER
                ),
                "Cache-Control": "no-cache,max-age=0",
                "Pragma": "no-cache",
            }

            ret = get_feed(feed, headers=headers, timeout=15)
            # can I be bothered to check return codes here?  I think not on balance

            isFeed = False

            content_type = "Not Set"
            if "Content-Type" in ret.headers:
                content_type = ret.headers["Content-Type"]

            feed_title = feed

            body = ret.text.strip()
            if "xml" in content_type or body[0:1] == "<":
                ff = feedparser.parse(
                    BytesIO(ret.content)
                )  # are we a feed?  # imported by django-feed-reader
                isFeed = len(ff.entries) > 0
                if isFeed:
                    feed_title = ff.feed.title
            if "json" in content_type or body[0:1] == "{":
                data = json.loads(body)
                isFeed = "items" in data and len(data["items"]) > 0
                if isFeed:
                    feed_title = data["title"]

            if not isFeed:
                soup = BeautifulSoup(body)
                feedcount = 0
                rethtml = ""
                for lnk in soup.findAll(name="link"):
                    if lnk.has_attr("rel") and lnk.has_attr("type"):
                        if lnk["rel"][0] == "alternate" and (
                            lnk["type"] == "application/atom+xml"
                            or lnk["type"] == "application/rss+xml"
                            or lnk["type"] == "application/json"
                        ):
                            feedcount += 1
                            try:
                                name = lnk["title"]
                            except Exception:
                                name = "Feed %d" % feedcount
                            rethtml += (
                                '<li><form method="post" onsubmit="return false;"> <input type="hidden" name="feed" id="feed-%d" value="%s"><a href="#" onclick="addFeed(%d)" class="btn btn-xs btn-default">Subscribe</a> - %s</form></li>'
                                % (
                                    feedcount,
                                    html.escape(urljoin(feed, lnk["href"]), quote=True),
                                    feedcount,
                                    html.escape(name),
                                )
                            )
                            feed = urljoin(
                                feed, lnk["href"]
                            )  # store this in case there is only one feed and we wind up importing it
                            # TODO: need to accout for relative URLs here
                if feedcount == 0:
                    return HttpResponse("No feeds found")
                else:
                    return HttpResponse(rethtml)

            if isFeed:
                parent = None
                if request.POST["group"] != "0":
                    parent = get_object_or_404(
                        Subscription, id=int(request.POST["group"])
                    )
                    if parent.user != request.user:
                        return HttpResponse(
                            "<div>Internal error.<!--bad group --></div>"
                        )

                s = Source.objects.filter(feed_url=feed)
                if s.count() > 0:
                    # feed already exists
                    s = s[0]
                    us = Subscription.objects.filter(Q(user=request.user) & Q(source=s))
                    if us.count() > 0:
                        return HttpResponse(
                            "<div>Already subscribed to this feed </div>"
                        )
                    else:
                        us = Subscription(
                            source=s,
                            user=request.user,
                            name=s.display_name,
                            parent=parent,
                        )

                        if (
                            s.max_index > 10
                        ):  # don't flood people with all these old things
                            us.last_read = s.max_index - 10

                        us.save()

                        return HttpResponse(
                            "<div>Imported feed %s</div>" % html.escape(us.name)
                        )

                # need to start checking feed parser errors here
                ns = Source()

                ns.name = feed_title
                ns.feed_url = feed
                ns.due_poll = timezone.now()

                ns.save()

                us = Subscription(
                    source=ns, user=request.user, name=ns.display_name, parent=parent
                )
                us.save()

                # you see really, I could parse out the items here and insert them rather than
                # wait for them to come back round in the refresh cycle

                return HttpResponse(
                    "<div>Imported feed %s</div>" % html.escape(ns.name)
                )
    except UnsafeFeedURL:
        return HttpResponse(
            "<div>The feed URL is invalid or not allowed.</div>", status=400
        )
    except Exception:
        logger.exception("Unexpected error while adding feed")
        return HttpResponse(
            "<div>Unable to add feed. Please try again later.</div>", status=500
        )


@login_required
@require_GET
def downloadfeeds(request):
    _require_superuser(request)

    opml = render_to_string("opml.xml", {"feeds": Source.objects.all()})

    ret = HttpResponse(opml, content_type="application/xml+opml")
    ret["Content-Disposition"] = "inline; filename=feedthing-export.xml"
    return ret


# TODO: I don't think that this is the most robust import ever :)
@login_required
def importopml(request):
    theFile = request.FILES["opml"].read()

    count = 0
    dom = minidom.parseString(theFile)
    imported = []

    sources = dom.getElementsByTagName("outline")
    for s in sources:
        url = normalize_navigation_url(s.getAttribute("xmlUrl"))
        if url:
            try:
                validate_feed_url(url)
            except ValueError:
                continue
            ns = Source.objects.filter(feed_url=url)
            if ns.count() > 0:
                # feed already exists - so there may already be a user subscription for it
                ns = ns[0]
                us = Subscription.objects.filter(source=ns).filter(user=request.user)
                if us.count() == 0:
                    us = Subscription(
                        source=ns, user=request.user, name=ns.display_name
                    )

                    if (
                        ns.max_index > 10
                    ):  # don't flood people with all these old things
                        us.last_read = ns.max_index - 10

                    us.save()
                    count += 1

            else:
                # Feed does not already exist it must also be a new sub
                ns = Source()
                ns.due_poll = timezone.now()
                ns.site_url = normalize_navigation_url(s.getAttribute("htmlUrl"))
                ns.feed_url = (
                    url  # probably best to see that there isn't a match here :)
                )
                ns.name = s.getAttribute("title")
                ns.save()

                us = Subscription(source=ns, user=request.user, name=ns.display_name)
                us.save()

                count += 1

            imported.append(ns)

    vals = {}
    vals["imported"] = imported
    vals["count"] = count
    return render(request, "importopml.html", vals)


@login_required
@require_POST
def subscriptionrename(request, sid):
    sub = _get_owned_subscription_or_403(request, sid)
    sub.name = request.POST["name"]
    sub.save()

    return JsonResponse({"ok": True})


@login_required
@require_http_methods(["GET", "POST"])
def subscriptiondetails(request, sid):
    sub = _get_owned_subscription_or_403(request, sid)

    vals = {}
    vals["subscription"] = sub

    if request.method == "POST":
        sub.name = request.POST["subname"]
        sub.is_river = "is_river" in request.POST
        sub.save()

    if sub.source is None:
        vals["sources"] = Subscription.objects.filter(user=request.user, parent=sub)

    else:
        vals["groups"] = Subscription.objects.filter(
            Q(user=request.user) & Q(source=None)
        )

    return render(request, "subscription.html", vals)


@login_required
@require_POST
def promote(request, sid):
    # Take a subscription out of its group

    sub = _get_owned_subscription_or_403(request, sid)
    parent = sub.parent

    sub.parent = None
    sub.save()

    if parent is not None and parent.subscriptions.count() == 0:
        parent.delete()
        return HttpResponse("Kill")

    return HttpResponse("OK")


@login_required
@require_POST
@transaction.atomic
def addto(request, sid, tid):
    toadd = _get_owned_subscription_or_403(request, sid)

    if tid == 0:
        target = Subscription(user=request.user, name="New Folder")
    else:
        target = _get_owned_subscription_or_403(request, tid)

    if toadd.source is None:
        return HttpResponse("Only feeds can be added to groups.", status=400)

    former_parents = {toadd.parent_id}
    if target.source is not None:
        former_parents.add(target.parent_id)
        folder = Subscription.objects.create(user=request.user, name="New Folder")
        target.parent = folder
        target.save()
    else:
        folder = target
        if tid == 0:
            folder.save()

    toadd.parent = folder
    toadd.save()

    for parent in Subscription.objects.filter(
        pk__in=former_parents, user=request.user, source=None
    ):
        if not parent.subscriptions.exists():
            parent.delete()

    return HttpResponse(folder.id)


@login_required
def readfeed(request, fid):
    vals = {}

    sub: Subscription = get_object_or_404(Subscription, id=int(fid))

    paginator = None

    try:
        page = int(request.GET.get("page", "1"))
    except Exception:
        page = 1

    if sub.user != request.user:
        raise PermissionDenied

    if sub.is_river:
        posts, paginator = sub.get_paginated_posts(page=page, posts_per_page=40)
    else:
        posts = sub.get_unread_posts(oldest_first=True)
        if len(posts) == 0:
            posts, paginator = sub.get_paginated_posts(page=page, posts_per_page=10)
        else:
            sub.mark_read()

    _prepare_posts_for_render(
        posts,
        request.user,
        include_enclosures=not sub.is_river,
    )

    vals["source"] = sub.source
    vals["subscription"] = sub

    if paginator is not None:
        # Stolen from Stack Overflow: https://stackoverflow.com/questions/30864011/display-only-some-of-the-page-numbers-by-django-pagination

        # Get the index of the current page
        index = page - 1  # edited to something easier without index
        # This value is maximum index of your pages, so the last page - 1
        max_index = len(paginator.page_range)
        # You want a range of 7, so lets calculate where to slice the list
        start_index = index - 2 if index >= 3 else 0
        end_index = index + 3 if index <= max_index - 3 else max_index
        # Get our new page range. In the latest versions of Django page_range returns
        # an iterator. Thus pass it to list, to make our slice possible again.
        vals["page_range"] = list(paginator.page_range)[start_index:end_index]

    vals["posts"] = posts
    vals["paginator"] = paginator

    if sub.is_river:
        return render(request, "river.html", vals)
    else:
        return render(request, "feed.html", vals)


@login_required
@require_POST
def revivefeed(request, fid):
    _require_superuser(request)

    f = get_object_or_404(Source, id=int(fid))
    f.live = True
    f.due_poll = timezone.now() - datetime.timedelta(days=100)
    f.etag = None
    f.last_modified = None
    # f.last_success = None
    # f.last_change = None
    # f.max_index = 0
    f.save()
    # Post.objects.filter(source=f).delete()
    return HttpResponse("OK")


@login_required
@require_GET
def testfeed(request, fid):
    _require_superuser(request)

    f = get_object_or_404(Source, id=int(fid))

    headers = {"User-Agent": settings.FEEDS_USER_AGENT}
    if request.GET.get("cache", "no") == "yes":
        if f.etag:
            headers["If-None-Match"] = str(f.etag)
        if f.last_modified:
            headers["If-Modified-Since"] = str(f.last_modified)
    else:
        headers.update({"Cache-Control": "no-cache,max-age=0", "Pragma": "no-cache"})
    try:
        result = get_feed(f.feed_url, headers=headers, timeout=20)
    except (requests.RequestException, ValueError):
        return HttpResponse(
            "Feed fetch failed or URL is not allowed.",
            status=400,
            content_type="text/plain",
        )
    return HttpResponse(
        f"HTTP status: {result.status_code}\nTest result: {result.ok}",
        content_type="text/plain",
    )


@login_required
@require_POST
def unsubscribefeed(request, sid):
    sub = _get_owned_subscription_or_403(request, sid)

    if not sub.source:
        return HttpResponse("Can't unsubscribe from groups", status=400)

    source = sub.source
    parent = sub.parent
    sub.delete()

    if parent is not None and parent.subscriptions.count() == 0:
        parent.delete()

    if source.subscriber_count == 0:  # this is the last subscription for this source
        source.delete()

    return HttpResponse("OK")


@login_required
@require_POST
def savepost(request, pid):
    post = get_object_or_404(Post, id=int(pid))

    sub = get_object_or_404(Subscription, source=post.source, user=request.user)

    SavedPost.objects.get_or_create(
        post=post,
        user=request.user,
        defaults={"subscription": sub},
    )

    return HttpResponse("OK")


@login_required
@require_POST
def forgetpost(request, pid):
    post = get_object_or_404(Post, id=int(pid))

    SavedPost.objects.filter(post=post, user=request.user).delete()

    return HttpResponse("OK")


@login_required
def savedposts(request):
    vals = {}

    q = request.GET.get("q", "")

    post_list = SavedPost.objects.filter(user=request.user)

    if q != "":
        post_list = post_list.filter(
            Q(post__title__icontains=q) | Q(post__body__icontains=q)
        )

    try:
        page = int(request.GET.get("page", "1"))
    except Exception:
        page = 1

    paginator = Paginator(post_list, 10)

    try:
        posts = paginator.page(page)
    except (EmptyPage, InvalidPage):
        posts = paginator.page(1)

    vals["posts"] = posts
    vals["paginator"] = paginator
    vals["q"] = q

    return render(request, "savedposts.html", vals)
