# Create your views here.

from django.shortcuts import render_to_response,get_object_or_404
from django.contrib.auth import authenticate, login,get_user, logout
from django.http import HttpResponseRedirect,HttpResponse
from django.db.models import Q
from django.db.models import F
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.utils.timezone import utc
import datetime
import hashlib
import logging
import sys
import traceback

import os

import feedparser

from xml.dom import minidom

from models import *

import time
import datetime

from BeautifulSoup import BeautifulSoup
from urlparse import urljoin
import requests


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
        return render_to_response("index.html",{},context_instance=RequestContext(request))


def help(request):
    return render_to_response("help.html",{},context_instance=RequestContext(request))
    


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
    return render_to_response('login.html',vals,context_instance=RequestContext(request))


def logoutpage(request):
    print "logout"
    logout(request)
    return render_to_response('logout.html',{},context_instance=RequestContext(request))
    

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
    
    return render_to_response("feeds.html",vals,context_instance=RequestContext(request))


@login_required
def managefeeds(request):
    vals = {}
    subscriptions = list(Subscription.objects.filter(Q(user = request.user) & Q(parent=None)).order_by("source__name"))
    
    vals["subscriptions"] = subscriptions
    
    return render_to_response("manage.html",vals,context_instance=RequestContext(request))



@login_required
def subscriptionlist(request):
    vals = {}
    subscriptions = list(Subscription.objects.filter(Q(user = request.user) & Q(parent=None)).order_by("source__name"))
    
    vals["subscriptions"] = subscriptions
    
    return render_to_response("sublist.html",vals,context_instance=RequestContext(request))




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
    
    
    return render_to_response("feeds.html",vals,context_instance=RequestContext(request))

@login_required
def feedgarden(request):
    vals = {}
    vals["feeds"] = Source.objects.all().order_by("duePoll")
    return render_to_response('feedgarden.html',vals,context_instance=RequestContext(request))
    


@login_required
def addfeed(request):


    try:
        feed = ""
        if request.method == 'GET':
            if request.GET.__contains__("feed"):
                feed = request.GET["feed"]
            groups = Subscription.objects.filter(Q(user=request.user) & Q(source=None))

            return render_to_response("addfeed.html",{"feed":feed,"groups":groups},context_instance=RequestContext(request))
    
        else:
    
            if request.POST.__contains__("feed"):
                feed = request.POST["feed"]
        
            headers = { "User-Agent": "FeedThing/3.0", "Cache-Control":"no-cache,max-age=0", "Pragma":"no-cache" } #identify ourselves and also stop our requests getting picked up by google's cache

            ret = requests.get(feed, headers=headers)
            #can I be bothered to check return codes here?  I think not on balance
        
            
            ff = feedparser.parse(ret.content) # are we a feed?
            
            isFeed = (len(ff.entries) > 0)            
            

            if not isFeed:
            
                soup = BeautifulSoup(ret.content)
                feedcount = 0
                rethtml = ""
                for l in soup.findAll(name='link'):
                    if l.has_key("rel") and l.has_key("type"):
                        if l['rel'] == "alternate" and (l['type'] == 'application/atom+xml' or l['type'] == 'application/rss+xml'):
                            feedcount += 1
                            try:
                                name = l['title']
                            except Exception as ex:
                                name = "Feed %d" % feedcount
                            rethtml += '<li><form method="post" onsubmit="return false;"> <input type="hidden" name="feed" id="feed-%d" value="%s"><a href="#" onclick="addFeed(%d)" class="button">Subscribe</a> - %s</form></li>' % (feedcount,urljoin(feed,l['href']),feedcount,name)
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
            
            
                    
                ns.name = feed
                try:
                    ns.htmlUrl = ff.feed.link
                    ns.name = ff.feed.title
                except Exception as ex:
                    pass
                ns.feedURL = feed
            
                ns.save()
            
                us = Subscription(source=ns,user=request.user,name=ns.displayName(),parent=parent)
                us.save()


                #you see really, I could parse out the items here and insert them rather than wait for them to come back round in the refresh cycle

                return HttpResponse("<div>Imported feed %s</div>" % ns.name)
    except Exception as xx:
        return HttpResponse("<div>Error %s: %s</div>" % (xx.__class__.__name__,str(xx)))
    
    
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
    return render_to_response('importopml.html',vals,context_instance=RequestContext(request))


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
 
        return render_to_response('subscription.html',vals,context_instance=RequestContext(request))
        
        
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
        
        return render_to_response('feed.html',vals,context_instance=RequestContext(request))
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
def killfeed(request,fid): #kill it stone dead (From feedgarden) - need to make admin only and clean up Subscriptions

    if request.method == "POST":
        
        f = get_object_or_404(Source,id=int(fid))

        Post.objects.filter(source=f).delete()
        
        f.delete()

        return HttpResponse("OK")


@login_required
def unsubscribefeed(request,sid):


    if request.method == "POST":
        
        us = get_object_or_404(Subscription,id=int(sid))

        if us.source:
            s = us.source
            us.delete()
            s.num_subs = s.subscription_set.count()
            if s.num_subs == 0: # this is the last subscription for this source
                Post.objects.filter(source=s).delete()
                s.delete()
            else:
                s.save()

            return HttpResponse("OK")
        else:
            return HttpResponse("Can't unsubscribe from groups")


def reader(request):

    
    response = HttpResponse()

    response["Content-Type"] = "text/plain"

    sources = Source.objects.filter(Q(duePoll__lt = datetime.datetime.utcnow().replace(tzinfo=utc)) & Q(live = True))[:3]

    response.write("Update Q: %d\n\n" % sources.count())
    for s in sources:
        
        was302 = False
        
        response.write("\n\n------------------------------\n\n")
        
        s.lastPolled = datetime.datetime.utcnow().replace(tzinfo=utc)
        #newCount = s.unreadCount
    
        interval = s.interval
    
        headers = { "User-Agent": "FeedThing/3.0 at %s (%d subscribers)" % (request.META["HTTP_HOST"],s.num_subs), "Cache-Control":"no-cache,max-age=0", "Pragma":"no-cache" } #identify ourselves and also stop our requests getting picked up by google's cache
        if s.ETag:
            headers["If-None-Match"] = str(s.ETag)
        if s.lastModified:
            headers["If-Modified-Since"] = str(s.lastModified)
        response.write(headers)
        ret = None
        response.write("\nFetching %s" % s.feedURL)
        try:
            ret = requests.get(s.feedURL,headers=headers,allow_redirects=False)
            s.status_code = ret.status_code
            s.lastResult = "Unhandled Case"
        except Exception as ex:
            print ex
            s.lastResult = "Fetch error:" + str(ex)
            s.status_code = 0
            response.write("\nFetch error: " + str(ex))
        
        if ret:
            response.write("\nResult: %d" % ret.status_code)
                    
        if ret == None or s.status_code == 0:
            interval += 120
        elif ret.status_code < 200 or ret.status_code >= 500:
            #errors, impossible return codes
            interval += 120
            s.lastResult = "Server error fetching feed (%d)" % ret.status_code
        elif ret.status_code == 404:
            #not found
            interval += 120
            s.lastResult = "The feed could not be found"
        elif ret.status_code == 403 or ret.status_code == 410: #Forbidden or gone
            s.live = False
            s.lastResult = "Feed is no longer accessible (%d)" % ret.status_code
        elif ret.status_code >= 400 and ret.status_code < 500:
            #treat as bad request
            s.live = False
            s.lastResult = "Bad request (%d)" % ret.status_code
        elif ret.status_code == 304:
            #not modified
            interval += 5
            s.lastResult = "Not modified"
            #s.lastSuccess = datetime.datetime.utcnow().replace(tzinfo=utc) #in case we start auto unsubscribing long dead feeds
            
            if (datetime.datetime.utcnow().replace(tzinfo=utc) - s.lastSuccess).days > 7:
                s.lastResult = "Clearing etag/last modified due to lack of changes"
                s.ETag = None
                s.lastModified = None
        
        elif ret.status_code == 301: #permenant redirect
            try:

                newURL = ret.headers["Location"]
                
                if newURL[0] == "/":
                    #find the domain from the feed
                    start = s.feedURL[:8]
                    end = s.feedURL[8:]
                    if end.find("/") >= 0:
                        end = end[:end.find("/")]
                    
                    newURL = start + end + newURL


                s.feedURL = newURL
                
                s.lastResult = "Moved"
            except exception as Ex:
                response.write("error redirecting")
                s.lastResult = "Error redirecting feed"
                interval += 60
                pass
        elif ret.status_code == 302 or ret.status_code == 303 or ret.status_code == 307: #Temporary redirect
            newURL = ""
            was302 = True
            try:
                newURL = ret.headers["Location"]
                
                if newURL[0] == "/":
                    #find the domain from the feed
                    start = s.feedURL[:8]
                    end = s.feedURL[8:]
                    if end.find("/") >= 0:
                        end = end[:end.find("/")]
                    
                    newURL = start + end + newURL
                    
                
                ret = requests.get(newURL,headers=headers,allow_redirects=True)
                s.status_code = ret.status_code
                s.lastResult = "Temporary Redirect to " + newURL

                
                if s.last302url == newURL:
                    #this is where we 302'd to last time
                    td = datetime.datetime.utcnow().replace(tzinfo=utc) - s.last302start
                    if td > datetime.timedelta(days=60):
                        s.feedURL = newURL
                        s.last302url = " "

                else:
                    s.last302url = newURL
                    s.last302start = datetime.datetime.utcnow().replace(tzinfo=utc)

                s.lastResult = "Temporary Redirect to " + newURL + " since " + s.last302start.strftime("%d %B")


            except Exception as ex:     
                s.lastResult = "Failed Redirection to " + newURL
                interval += 60
        
        #NOT ELIF, WE HAVE TO START THE IF AGAIN TO COPE WTIH 302
        if ret and ret.status_code >= 200 and ret.status_code < 300: #now we are not following redirects 302,303 and so forth are going to fail here, but what the hell :)

            # great!
            
            ok = True
            changed = False 
            
            if was302:
                s.ETag = None
                s.lastModified = None
            else:
                try:
                    s.ETag = ret.headers["ETag"]
                except Exception as ex:
                    s.ETag = None                                   
                try:
                    s.lastModified = ret.headers["Last-Modified"]
                except Exception as ex:
                    s.lastModified = None                                   
            
            response.write("\nEtag:%s\nLast Mod:%s\n\n" % (s.ETag,s.lastModified))
            
            #response.write(ret.content)           
            try:
                f = feedparser.parse(ret.content) #need to start checking feed parser errors here
                entries = f['entries']
                if len(entries):
                    s.lastSuccess = datetime.datetime.utcnow().replace(tzinfo=utc) #in case we start auto unsubscribing long dead feeds
                else:
                    s.lastResult = "Feed is empty"
                    interval += 120
                    ok = False

            except Exception as ex:
                s.lastResult = "Feed Parse Error"
                entries = []
                interval += 120
                ok = False
                
            if ok:

                try:
                    s.siteURL = f.feed.link
                    s.name = f.feed.title
                except Exception as ex:
                    pass
                

                #response.write(entries)
                entries.reverse() # Entries are typically in reverse chronological order - put them in right order
                for e in entries:
                    try:
                        body = e.content[0].value
                    except Exception as ex:
                        try:
                            body = e.description
                        except Exception as ex:
                            body = " "
            
            
                    try:
                        guid = e.guid
                    except Exception as ex:
                        try:
                            guid = e.link
                        except Exception as ex:
                            m = hashlib.md5()
                            m.update(body.encode("utf-8"))
                            guid = m.hexdigest()
                                
                    try:
                        p  = Post.objects.filter(source=s).filter(guid=guid)[0]
                        response.write("EXISTING " + guid + "\n")

                    except Exception as ex:
                        response.write("NEW " + guid + "\n")
                        p = Post(index=0)
                        p.found = datetime.datetime.utcnow().replace(tzinfo=utc)
                        changed = True
                        p.source = s
                
                    try:
                        title = e.title
                    except Exception as ex:
                        title = "No title"
                        
                    import pdb; pdb.set_trace()
                                    
                    try:
                        p.link = e.link
                    except Exception as ex:
                        p.link = ''
                    p.title = title
                    #tags = [t["term"] for t in e.tags]
                    #link.tags = ",".join(tags)

                    try:
                        #dd = datetime.datetime.fromtimestamp(time.mktime(e.date_parsed))
                        #p.created = datetime.datetime(dd.year,dd.month,dd.day,dd.hour,dd.minute,dd.second,tzinfo=_GMT)
                    
                        p.created  = datetime.datetime.fromtimestamp(time.mktime(e.date_parsed)).replace(tzinfo=utc)
                        # p.created  = datetime.datetime.utcnow().replace(tzinfo=utc)
                    except Exception as ex:
                        response.write("CREATED ERROR")     
                        p.created  = datetime.datetime.utcnow().replace(tzinfo=utc)
                    
                    # response.write("CC %s \n" % str(p.created))
                    
                    p.guid = guid
                    try:
                        p.author = e.author
                    except Exception as ex:
                        p.author = ""

                    try:
                        p.body = body                       
                        p.save()
                        # response.write(p.body)
                    except Exception as ex:
                        #response.write(str(sys.exc_info()[0]))
                        response.write("\nSave error for post:" + str(sys.exc_info()[0]))
                        traceback.print_tb(sys.exc_traceback,file=response)
            if ok and changed:
                interval /= 2
                s.lastResult = " OK (updated)" #and temporary redirects
                s.lastChange = datetime.datetime.utcnow().replace(tzinfo=utc)
                
                idx = s.maxIndex
                # give indices to posts based on created date
                posts = Post.objects.filter(Q(source=s) & Q(index=0)).order_by("created")
                for p in posts:
                    idx += 1
                    p.index = idx
                    p.save()
                    
                s.maxIndex = idx

                
                
            elif ok:
                s.lastResult = "OK"
                interval += 10 # we slow down feeds a little more that don't send headers we can use
                
            #s.unreadCount = newCount
        

        #else:
        #   #should not be able to get here
        #   oops = "Gareth can't program! %d" % ret.status_code
        #   logging.error(oops)
        #   s.lastResult = oops
            
        
        if interval < 60:
            interval = 60 #no less than 1 hour
        if interval > (60 * 60 * 24 * 3):
            interval = (60 * 60 * 24 * 3) #no more than 3 days
        
        response.write("\nUpdating interval from %d to %d\n" % (s.interval,interval))
        s.interval = interval
        td = datetime.timedelta(minutes=interval)
        s.duePoll = datetime.datetime.utcnow().replace(tzinfo=utc) + td
        s.save()
        
        response.write("Done")
    return response
    
