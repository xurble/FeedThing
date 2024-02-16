# Create your views here.

from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse, Http404
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.utils.timezone import utc
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.conf import settings

import datetime
import logging
import json
import traceback

from xml.dom import minidom

from .models import SavedPost

from feeds.utils import (
    update_feeds,
    test_feed,
    get_unread_subscription_list_for_user,
    get_subscription_list_for_user
)
from feeds.models import Source, Post, Subscription

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests
from django.urls import reverse
import feedparser


def index(request):

    if request.user.is_authenticated:
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
        return HttpResponseRedirect(reverse("password_change"))

    raise Http404  # not implemented


@login_required
def user_settings(request):
    return render(request, "settings.html", {})


@login_required
def feeds(request):
    vals = {}

    sources = get_unread_subscription_list_for_user(request.user)

    vals["sources"] = sources
    vals["all"] = False

    vals["preload"] = request.GET.get("feed", "0")
    vals["page"] = request.GET.get("page", "1")

    return render(request, "feeds.html", vals)


@login_required
def managefeeds(request):
    vals = {}
    subscriptions = list(Subscription.objects.filter(Q(user=request.user) & Q(parent=None)).order_by("source__name"))

    vals["subscriptions"] = subscriptions
    vals["preload"] = request.GET.get("s", "0")

    return render(request, "manage.html", vals)


@login_required
def subscriptionlist(request):
    vals = {}
    subscriptions = list(Subscription.objects.filter(Q(user=request.user) & Q(parent=None)).order_by("source__name"))

    vals["subscriptions"] = subscriptions

    return render(request, "sublist.html", vals)


@login_required
def allfeeds(request):
    vals = {}

    sources = get_subscription_list_for_user(request.user)

    vals["sources"] = sources
    vals["all"] = True

    vals["preload"] = request.GET.get("feed", "0")
    vals["page"] = request.GET.get("page", "1")

    return render(request, "feeds.html", vals)


@login_required
def feedgarden(request):
    vals = {}
    vals["feeds"] = Source.objects.all().order_by("due_poll")
    return render(request, 'feedgarden.html', vals)


@login_required
def addfeed(request):

    try:
        if request.method == 'GET':
            feed = request.GET.get("feed", "")
            groups = Subscription.objects.filter(Q(user=request.user) & Q(source=None))

            return render(request, "addfeed.html", {"feed": feed, "groups": groups})

        else:

            feed = request.POST.get("feed", "")

            # identify ourselves and also stop our requests getting picked up by google's cache
            headers = {"User-Agent": "{agent} (+{server}; Initial Feed Crawler)".format(agent=settings.FEEDS_USER_AGENT, server=settings.FEEDS_SERVER), "Cache-Control": "no-cache,max-age=0", "Pragma": "no-cache"}

            ret = requests.get(feed, headers=headers, verify=False, timeout=15)
            # can I be bothered to check return codes here?  I think not on balance

            isFeed = False

            content_type = "Not Set"
            if "Content-Type" in ret.headers:
                content_type = ret.headers["Content-Type"]

            feed_title = feed

            body = ret.text.strip()
            if "xml" in content_type or body[0:1] == "<":
                ff = feedparser.parse(body)  # are we a feed?  # imported by django-feed-reader
                isFeed = (len(ff.entries) > 0)
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
                for lnk in soup.findAll(name='link'):
                    if lnk.has_attr("rel") and lnk.has_attr("type"):
                        if lnk['rel'][0] == "alternate" and (lnk['type'] == 'application/atom+xml' or lnk['type'] == 'application/rss+xml' or lnk['type'] == 'application/json'):
                            feedcount += 1
                            try:
                                name = lnk['title']
                            except Exception:
                                name = "Feed %d" % feedcount
                            rethtml += '<li><form method="post" onsubmit="return false;"> <input type="hidden" name="feed" id="feed-%d" value="%s"><a href="#" onclick="addFeed(%d)" class="btn btn-xs btn-default">Subscribe</a> - %s</form></li>' % (feedcount, urljoin(feed, lnk['href']), feedcount, name)
                            feed = urljoin(feed, lnk['href'])  # store this in case there is only one feed and we wind up importing it
                            # TODO: need to accout for relative URLs here
                if feedcount == 0:
                    return HttpResponse("No feeds found")
                else:
                    return HttpResponse(rethtml)

            if isFeed:
                parent = None
                if request.POST["group"] != "0":
                    parent = get_object_or_404(Subscription, id=int(request.POST["group"]))
                    if parent.user != request.user:
                        return HttpResponse("<div>Internal error.<!--bad group --></div>")

                s = Source.objects.filter(feed_url=feed)
                if s.count() > 0:
                    # feed already exists
                    s = s[0]
                    us = Subscription.objects.filter(Q(user=request.user) & Q(source=s))
                    if us.count() > 0:
                        return HttpResponse("<div>Already subscribed to this feed </div>")
                    else:
                        us = Subscription(source=s, user=request.user, name=s.display_name, parent=parent)

                        if s.max_index > 10:  # don't flood people with all these old things
                            us.last_read = s.max_index - 10

                        us.save()

                        s.num_subs = s.subscriptions.count()
                        s.save()

                        return HttpResponse("<div>Imported feed %s</div>" % us.name)

                # need to start checking feed parser errors here
                ns = Source()

                ns.name = feed_title
                ns.feed_url = feed

                ns.save()

                us = Subscription(source=ns, user=request.user, name=ns.display_name, parent=parent)
                us.save()

                # you see really, I could parse out the items here and insert them rather than
                # wait for them to come back round in the refresh cycle

                return HttpResponse("<div>Imported feed %s</div>" % ns.name)
    except Exception as xx:
        traceback_str = ''.join(traceback.format_tb(xx.__traceback__))
        return HttpResponse("<div>Error %s: %s</div><div style='display:none'>%s</div>" % (xx.__class__.__name__, str(xx), traceback_str))


@login_required
def downloadfeeds(request):

    if not request.user.is_superuser:
        raise PermissionDenied()

    opml = render_to_string("opml.xml", {"feeds": Source.objects.all()})

    ret = HttpResponse(opml, content_type="application/xml+opml")
    ret['Content-Disposition'] = 'inline; filename=feedthing-export.xml'
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

        url = s.getAttribute("xmlUrl")
        if url.strip() != "":
            ns = Source.objects.filter(feed_url=url)
            if ns.count() > 0:

                # feed already exists - so there may already be a user subscription for it
                ns = ns[0]
                us = Subscription.objects.filter(source=ns).filter(user=request.user)
                if us.count() == 0:
                    us = Subscription(source=ns, user=request.user, name=ns.display_name)

                    if ns.max_index > 10:  # don't flood people with all these old things
                        us.last_read = ns.max_index - 10

                    us.save()
                    count += 1

                ns.num_subs = ns.subscriptions.count()
                ns.save()

            else:
                # Feed does not already exist it must also be a new sub
                ns = Source()
                ns.due_poll = datetime.datetime.utcnow().replace(tzinfo=utc)
                ns.site_url = s.getAttribute("htmlUrl")
                ns.feed_url = url  # probably best to see that there isn't a match here :)
                ns.name = s.getAttribute("title")
                ns.save()

                us = Subscription(source=ns, user=request.user, name=ns.display_name)
                us.save()

                count += 1

            imported.append(ns)

    vals = {}
    vals["imported"] = imported
    vals["count"] = count
    return render(request, 'importopml.html', vals)


@login_required
def subscriptionrename(request, sid):

    sub = get_object_or_404(Subscription, id=int(sid))

    if sub.user == request.user:

        if request.method == "POST":
            sub.name = request.POST["name"]
            sub.save()

        return JsonResponse({"ok": True})


@login_required
def subscriptiondetails(request, sid):

    sub = get_object_or_404(Subscription, id=int(sid))

    if sub.user == request.user:

        vals = {}
        vals["subscription"] = sub

        if request.method == "POST":
            sub.name = request.POST["subname"]
            sub.is_river = "isriver" in request.POST
            sub.save()

        if sub.source is None:
            vals["sources"] = Subscription.objects.filter(parent=sub)

        else:
            vals["groups"] = Subscription.objects.filter(Q(user=request.user) & Q(source=None))

        return render(request, 'subscription.html', vals)

    # else 403 ?


@login_required
def promote(request, sid):
    # Take a subscription out of its group

    sub = get_object_or_404(Subscription, id=int(sid))
    if sub.user == request.user:

        parent = sub.parent

        sub.parent = None
        sub.save()

        if parent.subscriptions.count() == 0:
            parent.delete()
            return HttpResponse("Kill")
        else:
            return HttpResponse("OK")


@login_required
def addto(request, sid, tid):

    toadd = get_object_or_404(Subscription, id=int(sid))

    if tid == "0":
        target = Subscription(user=request.user, name="New Folder")
    else:
        target = get_object_or_404(Subscription, id=int(tid))

    if toadd.user == request.user and target.user == request.user and toadd.source is not None:

        if tid == "0":
            target.save()

        if target.source is None:
            toadd.parent = target
            toadd.save()

            return HttpResponse(target.id)
        else:

            nn = Subscription(user=request.user, name="New Folder")
            nn.save()
            toadd.parent = nn
            toadd.save()
            target.parent = nn
            target.save()

            return HttpResponse(nn.id)


@login_required
def readfeed(request, fid):

    river_posts_per_page = 40
    feed_posts_per_page = 10

    posts_per_page = river_posts_per_page

    vals = {}

    sub = get_object_or_404(Subscription, id=int(fid))

    paginator = None

    try:
        page = int(request.GET.get("page", "1"))
    except Exception:
        page = 1

    if sub.user != request.user:
        raise PermissionDenied

    # Since users can rename what a source is called in their subscription
    # we make a map of source ids to subscription names and pass it to the template
    # there is a  template tag that sorts this out later
    sub_map = {}

    if sub.source is None:

        # if source is None then we are are in a folder
        posts = []

        # so we find all the actual subscriptions parented by this folder
        sources = list(Subscription.objects.filter(parent=sub))

        for s in sources:
            sub_map[s.source.id] = s.name

        if not sub.is_river:
            # This folder is not a river, it is an actual set of read everything
            # feeds grouped together by some heathen
            # Gather the posts now and mark them as read
            for src in sources:
                srcposts = list(Post.objects.filter(Q(source=src.source) & Q(index__gt=src.last_read)).order_by("index"))

                src.last_read = src.source.max_index
                src.save()
                posts += srcposts
            posts_per_page = feed_posts_per_page

        if len(posts) == 0:
            # Either didn't find any new posts or are a river
            # In either case get the most recent posts and put them in a paginator
            sources = [src.source for src in sources]
            post_list = Post.objects.filter(source__in=sources).order_by("-created")

            paginator = Paginator(post_list, posts_per_page)

            try:
                posts = paginator.page(page)
            except (EmptyPage, InvalidPage):
                posts = paginator.page(1)

        vals["subscription"] = sub

    else:
        posts = []

        sub_map[sub.source.id] = sub.name

        if not sub.is_river:
            posts = list(Post.objects.filter(Q(source=sub.source) & Q(index__gt=sub.last_read)).order_by("index"))
            posts_per_page = feed_posts_per_page

        if len(posts) == 0:  # No Posts or a river
            post_list = Post.objects.filter(source=sub.source).order_by("-created")
            paginator = Paginator(post_list, posts_per_page)
            try:
                posts = paginator.page(page)
            except (EmptyPage, InvalidPage):
                posts = paginator.page(1)

        # since we always read all new posts, mark it off here.
        sub.last_read = sub.source.max_index
        sub.save()

        vals["source"] = sub.source
        vals["subscription"] = sub

    if paginator is not None:
        # Stolen from Stack Overflow: https://stackoverflow.com/questions/30864011/display-only-some-of-the-page-numbers-by-django-pagination

        # Get the index of the current page
        index = posts.number - 1  # edited to something easier without index
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
    vals["subscription_map"] = sub_map

    if sub.is_river:
        return render(request, 'river.html', vals)
    else:
        return render(request, 'feed.html', vals)


@login_required
def revivefeed(request, fid):

    if request.method == "POST":

        f = get_object_or_404(Source, id=int(fid))
        f.live = True
        f.due_poll = (datetime.datetime.utcnow().replace(tzinfo=utc) - datetime.timedelta(days=100))
        f.etag = None
        f.last_modified = None
        # f.last_success = None
        # f.last_change = None
        # f.max_index = 0
        f.save()
        # Post.objects.filter(source=f).delete()
        return HttpResponse("OK")


@login_required
def testfeed(request, fid):

    f = get_object_or_404(Source, id=int(fid))

    r = HttpResponse()

    test_feed(f, cache=request.GET.get("cache", "no") == "yes", output=r)

    r["Content-type"] = "text/plain"

    return r


@login_required
def unsubscribefeed(request, sid):

    if request.method == "POST":

        sub = get_object_or_404(Subscription, id=int(sid))

        if sub.user == request.user:

            if sub.source:
                source = sub.source
                parent = sub.parent
                sub.delete()

                if parent is not None:
                    if parent.subscriptions.count() == 0:
                        parent.delete()

                source.num_subs = source.subscriptions.count()
                if source.num_subs == 0:  # this is the last subscription for this source
                    Post.objects.filter(source=source).delete()  # cascading delete would do this I think
                    source.delete()
                else:
                    source.save()

                return HttpResponse("OK")
            else:
                return HttpResponse("Can't unsubscribe from groups")
        else:
            return HttpResponse("Nope")


@login_required
def savepost(request, pid):

    post = get_object_or_404(Post, id=int(pid))

    sub = Subscription.objects.filter(source=post.source).filter(user=request.user)[0]

    sp = SavedPost(post=post, user=request.user, subscription=sub)
    sp.save()

    return HttpResponse("OK")


@login_required
def forgetpost(request, pid):

    post = get_object_or_404(Post, id=int(pid))

    sp = SavedPost.objects.filter(post=post).filter(user=request.user)[0]
    sp.delete()

    return HttpResponse("OK")


@login_required
def savedposts(request):

    vals = {}

    q = request.GET.get("q", "")

    post_list = SavedPost.objects.filter(user=request.user)

    if q != "":
        post_list = post_list.filter(Q(post__title__icontains=q) | Q(post__body__icontains=q))

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

    return render(request, 'savedposts.html', vals)


def read_request_listener(request):

    response = HttpResponse()

    update_feeds(3, response)

    response["Content-Type"] = "text/plain"

    return response
