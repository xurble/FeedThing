# Create your views here.

from django.shortcuts import render,get_object_or_404
from django.template.loader import render_to_string
from django.contrib.auth import authenticate, login,get_user, logout
from django.http import HttpResponseRedirect,HttpResponse
from django.db.models import Q
from django.db.models import F
from django.contrib.auth.decorators import login_required
from django.utils.timezone import utc
import datetime
import hashlib
import logging
import sys
import traceback
import json
import os

import feedparser

from xml.dom import minidom

from models import *

import time
import datetime

from BeautifulSoup import BeautifulSoup
from urlparse import urljoin
import requests

from reader import update_feeds


#class GMT(datetime.tzinfo):
#    def utcoffset(self,dt): 
#        return datetime.timedelta(hours=0,minutes=0) 
#    def tzname(self,dt): 
#        return "GMT" 
#    def dst(self,dt): 
#        return datetime.timedelta(0)     

#_GMT = GMT()

def index(request):

    if request.user.is_authenticated():
        return HttpResponseRedirect("/feeds/")
    else:
        return render(request, "index.html",{})


def help(request):
    return render(request, "help.html",{})
    


def loginpage(request):

    next = "/feeds/"
    vals = {}
    msg = ""
    # If we submitted the form...
    if request.method == 'POST':

        # Check that the test cookie worked (we set it below):
        if request.session.test_cookie_worked():

            # The test cookie worked, so delete it.
            request.session.delete_test_cookie()

            # In practice, we'd need some logic to check username/password
            # here, but since this is an example...

            username = request.POST['username']
            password = request.POST['password']
            vals["username"] = username
            user = authenticate(username=username, password=password)
            if user is not None:
                if user.is_active:
                    login(request,user)
                    return HttpResponseRedirect(next)
                else:
                    msg = "Account is disabled"
            else:
                msg = "Unknown username / password"

        # The test cookie failed, so display an error message. If this
        # was a real site we'd want to display a friendlier message.
        else:
            msg = "Please enable cookies and try again."

    # If we didn't post, send the test cookie along with the login form.
    request.session.set_test_cookie()
    vals["msg"] = msg
    return render(request, 'login.html',vals)


def logoutpage(request):
    print "logout"
    logout(request)
    return render(request, 'logout.html',{})
    

@login_required
def feeds(request):
    vals = {}
    toRead = list(Subscription.objects.filter(Q(user = request.user) & (Q(isRiver = True) | Q(lastRead__lt = F('source__maxIndex')))).order_by("source__name"))
    
    sources = []
    groups = {}
    
    for src in toRead:
        if src.parent:
            if src.parent.isRiver == False:
                #this is a group
                if src.parent.id in groups:
                    grp = groups[src.parent.id]
                    grp._unreadCount += src.unreadCount()
                else:
                    grp = src.parent
                    grp._unreadCount = src.unreadCount()
                    groups[grp.id] = grp
                    sources.append(grp)
        else:
            sources.append(src)
    
    vals["sources"] = sources
    vals["all"] = False
    
    vals["preload"] = request.GET.get("feed","0")
    
    return render(request, "feeds.html",vals)


@login_required
def managefeeds(request):
    vals = {}
    subscriptions = list(Subscription.objects.filter(Q(user = request.user) & Q(parent=None)).order_by("source__name"))
    
    vals["subscriptions"] = subscriptions
    
    return render(request, "manage.html",vals)



@login_required
def subscriptionlist(request):
    vals = {}
    subscriptions = list(Subscription.objects.filter(Q(user = request.user) & Q(parent=None)).order_by("source__name"))
    
    vals["subscriptions"] = subscriptions
    
    return render(request, "sublist.html",vals)




@login_required
def allfeeds(request):
    vals = {}
    toRead = list(Subscription.objects.filter(Q(user = request.user) & Q(parent=None)).order_by("source__name"))
    
    sources = []
    groups = {}
    
    for src in toRead:
        if src.source == None:
            
            src._unreadCount = 0
            
            for c in src.subscription_set.all():
                src._unreadCount += c.unreadCount()
            
        sources.append(src)
    
    vals["sources"] = sources
    vals["all"] = True

    vals["preload"] = request.GET.get("feed","0")

    
    return render(request, "feeds.html",vals)

@login_required
def feedgarden(request):
    vals = {}
    vals["feeds"] = Source.objects.all().order_by("duePoll")
    return render(request, 'feedgarden.html',vals)
    


@login_required
def addfeed(request):


    try:
        feed = ""
        if request.method == 'GET':
            if request.GET.__contains__("feed"):
                feed = request.GET["feed"]
            groups = Subscription.objects.filter(Q(user=request.user) & Q(source=None))

            return render(request, "addfeed.html",{"feed":feed,"groups":groups})
    
        else:
    
            if request.POST.__contains__("feed"):
                feed = request.POST["feed"]
                
                
            headers = { "User-Agent": "FeedThing/3.2 (+http://%s; Initial Feed Crawler)" % request.META["HTTP_HOST"], "Cache-Control":"no-cache,max-age=0", "Pragma":"no-cache" } #identify ourselves and also stop our requests getting picked up by google's cache


            ret = requests.get(feed, headers=headers,verify=False)
            #can I be bothered to check return codes here?  I think not on balance
        
            isFeed = False  

            content_type = "Not Set"
            if "Content-Type" in ret.headers:
                content_type = ret.headers["Content-Type"]
                
            feed_title = feed
             
            
            body = ret.content.strip()
            if "xml" in content_type or body[0:1] == "<":
                ff = feedparser.parse(body) # are we a feed?
                isFeed = (len(ff.entries) > 0) 
                if isFeed:
                    feed_title = ff.feed.title
            if "json" in content_type or body[0:1] == "{":
                data = json.loads(body)
                isFeed = "items" in data and len(data["items"]) > 0
                if isFeed:
                    feed_title = data["title"]
            

            if not isFeed:
            
                soup = BeautifulSoup(ret.content)
                feedcount = 0
                rethtml = ""
                for l in soup.findAll(name='link'):
                    if l.has_key("rel") and l.has_key("type"):
                        if l['rel'] == "alternate" and (l['type'] == 'application/atom+xml' or l['type'] == 'application/rss+xml' or l['type'] == 'application/json'):
                            feedcount += 1
                            try:
                                name = l['title']
                            except Exception as ex:
                                name = "Feed %d" % feedcount
                            rethtml += '<li><form method="post" onsubmit="return false;"> <input type="hidden" name="feed" id="feed-%d" value="%s"><a href="#" onclick="addFeed(%d)" class="btn btn-xs btn-default">Subscribe</a> - %s</form></li>' % (feedcount,urljoin(feed,l['href']),feedcount,name)
                            feed = urljoin(feed,l['href']) # store this in case there is only one feed and we wind up importing it
                            #TODO: need to accout for relative URLs here
                #if feedcount == 1:
                    #just 1 feed found, let's import it now
                
                #   ret = fetch(f)
                #   isFeed = True
                if feedcount == 0:
                    return HttpResponse("No feeds found")
                else:
                    return HttpResponse(rethtml)
                
            if isFeed:
                parent = None
                if request.POST["group"] != "0":
                    parent = get_object_or_404(Subscription,id=int(request.POST["group"]))
                    if parent.user != request.user:
                        return HttpResponse("<div>Internal error.<!--bad group --></div>")

            
                s = Source.objects.filter(feedURL = feed)
                if s.count() > 0:
                    #feed already exists
                    s = s[0]
                    us = Subscription.objects.filter(Q(user=request.user) & Q(source=s))
                    if us.count() > 0:
                        return HttpResponse("<div>Already subscribed to this feed </div>")
                    else:
                        us = Subscription(source=s,user=request.user,name=s.displayName(),parent=parent)
                    
                        if s.maxIndex > 10: #don't flood people with all these old things
                            us.lastRead = s.maxIndex - 10
                    
                        us.save()
                    
                        s.num_subs = s.subscription_set.count()
                        s.save()
                    
                        return HttpResponse("<div>Imported feed %s</div>" % us.name)


                # need to start checking feed parser errors here
                ns = Source()
                ns.duePoll = datetime.datetime.utcnow().replace(tzinfo=utc)            
            
                #print request.POST["river"]
                #ns.inRiver = (request.POST["river"] == "yes")
            
            
                    
                ns.name    = feed_title
                ns.feedURL = feed
            
                ns.save()
            
                us = Subscription(source=ns,user=request.user,name=ns.displayName(),parent=parent)
                us.save()


                #you see really, I could parse out the items here and insert them rather than wait for them to come back round in the refresh cycle

                return HttpResponse("<div>Imported feed %s</div>" % ns.name)
    except Exception as xx:
        return HttpResponse("<div>Error %s: %s</div>" % (xx.__class__.__name__,str(xx)))
    
@login_required
def downloadfeeds(request):    
    
    
    opml = render_to_string("opml.xml", {"feeds":Source.objects.all()})
    
    
    
    ret =  HttpResponse(opml, content_type="application/xml+opml")
    ret['Content-Disposition'] = 'inline; filename=feedthing-export.xml'
    return ret
    
# TODO: I don't think that this is the most robust import ever :)
@login_required
def importopml(request):

    theFile = request.FILES["opml"].read()

    count = 0
    dom = minidom.parseString(theFile)
    imported  = []
    
    sources = dom.getElementsByTagName("outline")
    for s in sources:

        url  = s.getAttribute("xmlUrl")
        if url.strip() != "":
            ns = Source.objects.filter(feedURL = url)
            if ns.count() > 0:
                
                #feed already exists - so there may already be a user subscription for it
                ns = ns[0]
                us = Subscription.objects.filter(source=ns).filter(user=request.user)
                if us.count() == 0:
                    us = Subscription(source=ns,user=request.user,name=ns.displayName())

                    if ns.maxIndex > 10: #don't flood people with all these old things
                        us.lastRead = ns.maxIndex - 10


                    us.save()
                    count += 1

                ns.num_subs = ns.subscription_set.count()
                ns.save()

                
            else:
                # Feed does not already exist it must also be a new sub
                ns = Source()
                ns.duePoll = datetime.datetime.utcnow().replace(tzinfo=utc)
                ns.siteURL = s.getAttribute("htmlUrl")
                ns.feedURL = url #probably best to see that there isn't a match here :)
                ns.name = s.getAttribute("title")
                ns.save()
    
                us = Subscription(source=ns,user=request.user,name = ns.displayName())
                us.save()
    
                count += 1
            
            imported.append(ns)
    
    vals = {}
    vals["imported"] = imported    
    vals["count"] = count  
    return render(request, 'importopml.html',vals)


@login_required 
def subscriptiondetails(request,sid):

    sub = get_object_or_404(Subscription,id=int(sid))
    
    if sub.user == request.user:
        
        vals = {}
        vals["subscription"] = sub
 
        if request.method == "POST":
            sub.name = request.POST["subname"]
            sub.isRiver = "isriver" in request.POST
            sub.save()

        if sub.source == None:
            vals["sources"] = Subscription.objects.filter(parent=sub)
        
        else:
            vals["groups"] = Subscription.objects.filter(Q(user=request.user) & Q(source=None))
 
        return render(request, 'subscription.html',vals)
        
        
    #else 403 ?      
    
@login_required
def promote(request,sid):
    # Take a subscription out of its group
    
    sub = get_object_or_404(Subscription,id=int(sid))
    if sub.user == request.user:
    
        parent = sub.parent
    
        sub.parent = None
        sub.save()
        
        if parent.subscription_set.count() == 0:
            parent.delete()
            return HttpResponse("Kill")
        else:
            return HttpResponse("OK")
        
        
@login_required
def addto(request,sid,tid):


    toadd  = get_object_or_404(Subscription,id=int(sid))
    
    if tid == "0":
        target = Subscription(user=request.user, name="New Folder")
    else:
        target = get_object_or_404(Subscription,id=int(tid))
    
    if toadd.user == request.user and target.user == request.user and toadd.source is not None:

        if tid == "0":
            target.save()
    
    
        if target.source == None:
            toadd.parent = target
            toadd.save()
            
            return HttpResponse(target.id)
        else:
            
            nn = Subscription(user=request.user,name="New Folder")
            nn.save()
            toadd.parent = nn
            toadd.save()
            target.parent = nn
            target.save()
            
            return HttpResponse(nn.id)
            
    
    
    

@login_required
def readfeed(request,fid,qty):
        
    vals  = {}
    if qty == "all":
        qty = 100
    else:
        qty = int(qty)
        

    sub = get_object_or_404(Subscription,id=int(fid))
    if sub.user == request.user:
        if sub.source == None:  
        
            posts = []
            
            sources = list(Subscription.objects.filter(parent=sub))
            
            
            if not sub.isRiver:
                for src in sources:
                    srcposts = list(Post.objects.filter(Q(source = src.source) & Q(index__gt = src.lastRead)).order_by("index")[:qty])
        
                    src.lastRead = src.source.maxIndex
                    src.save()
                    posts += srcposts
                

            if len(posts) == 0: # Either didn't find any new posts or are a river
                sources = [sub.source for sub in sources]
                posts = list(Post.objects.filter(source__in = sources).order_by("-created")[:20])
                    
            
        else:
            posts = [] 
            if not sub.isRiver:
                posts = list(Post.objects.filter(Q(source = sub.source) & Q(index__gt = sub.lastRead)).order_by("index")[:qty])
        
            if len(posts) == 0: # No Posts or a river
                posts = list(Post.objects.filter(source = sub.source).order_by("-created")[:10])
         
            #this assumes that we always read all posts which kind of defeats 
            #the quantity argument above.  Quantity is vestigial
            
            sub.lastRead = sub.source.maxIndex
            sub.save()
        
            vals["source"] = sub.source
            vals["subscription"] = sub
        
        vals["posts"] = posts
        
        return render(request, 'feed.html',vals)
    #else 403

@login_required
def revivefeed(request,fid):

    if request.method == "POST":
        
        f = get_object_or_404(Source,id=int(fid))
        f.live = True
        f.duePoll = datetime.datetime.utcnow().replace(tzinfo=utc)
        f.ETag = None
        f.lastModified = None
        # f.lastSuccess = None
        # f.lastChange = None
        # f.maxIndex = 0
        f.save()
        # Post.objects.filter(source=f).delete()
        return HttpResponse("OK")


@login_required
def revivefeed(request,fid):

    if request.method == "POST":
        
        f = get_object_or_404(Source,id=int(fid))
        f.live = True
        f.duePoll = datetime.datetime.utcnow().replace(tzinfo=utc)
        f.ETag = None
        f.lastModified = None
        # f.lastSuccess = None
        # f.lastChange = None
        # f.maxIndex = 0
        f.save()
        # Post.objects.filter(source=f).delete()
        return HttpResponse("OK")


@login_required
def testfeed(request,fid): #kill it stone dead (From feedgarden) - need to make admin only and clean up Subscriptions

        f = get_object_or_404(Source,id=int(fid))


        headers = { "User-Agent": "FeedThing/3.2 (+http://%s; Updater; %d subscribers)" % (request.META["HTTP_HOST"],f.num_subs), "Cache-Control":"no-cache,max-age=0", "Pragma":"no-cache" } #identify ourselves and also stop our requests getting picked up by google's cache

        ret = requests.get(f.feedURL,headers=headers,allow_redirects=False,verify=False)
        
        
        r = HttpResponse("%s\n------------------------------\n\nResponse: %d\n-------------------------\n%s\n--------------------\n%s" % (headers,ret.status_code,ret.headers,ret.content))
        r["Content-type"] = "text/plain"
        
        return r


@login_required
def unsubscribefeed(request,sid):


    if request.method == "POST":
        
        sub = get_object_or_404(Subscription,id=int(sid))
        
        if sub.user == request.user:

            if sub.source:
                source = sub.source
                parent = sub.parent
                sub.delete()
    
                if parent is not None:
                    if parent.subscription_set.count() == 0:
                        parent.delete()
    
                source.num_subs = source.subscription_set.count()
                if source.num_subs == 0: # this is the last subscription for this source
                    Post.objects.filter(source=source).delete() # cascading delete would do this I think
                    source.delete()
                else:
                    source.save()
    
                return HttpResponse("OK")
            else:
                return HttpResponse("Can't unsubscribe from groups")
        else:
            return HttpResoponse("Nope")


def read_request_listener(request):

    ret = update_feeds(request.META["HTTP_HOST"])
    
    response = HttpResponse(ret)

    response["Content-Type"] = "text/plain"

    return response
    
