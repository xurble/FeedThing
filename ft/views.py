# Create your views here.

from django.shortcuts import render_to_response,get_object_or_404
from django.contrib.auth import authenticate, login,get_user
from django.http import HttpResponseRedirect,HttpResponse
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
import datetime
import hashlib
import logging
import sys

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

@login_required
def feeds(request):
    vals = {}
    vals["sources"] = Source.objects.filter(Q(unreadCount__gt = 0) & Q(inRiver = False)).order_by("name")
    
    return render_to_response("feeds.html",vals,context_instance=RequestContext(request))
        
@login_required
def feedgarden(request):
    vals = {}
    vals["feeds"] = Source.objects.all().order_by("duePoll")
    return render_to_response('feedgarden.html',vals,context_instance=RequestContext(request))
    


@login_required
def addfeed(request):
    feed = ""
    if request.method == 'GET':
        if request.GET.__contains__("feed"):
            feed = request.GET["feed"]
        return render_to_response("addfeed.html",{"feed":feed},context_instance=RequestContext(request))
    
    else:
        import pdb
        pdb.set_trace()
    
        if request.POST.__contains__("feed"):
            feed = request.POST["feed"]
        
        ret = requests.get(feed)
        #can I be bothered to check return codes here?  I think not on balance
        
        soup = BeautifulSoup(ret.content)
        #are we actually RSS
        rss = soup.findAll(name='rss')
        isFeed = False
        if len(rss) == 1:
            #this is an rss file
            isFeed = True
            
        else:
            rss = soup.findAll(name='feed')
            if len(rss) == 1:
                #this is an atom file
                isFeed = True

        if not isFeed:
            feedcount = 0
            rethtml = ""
            for l in soup.findAll(name='link'):
                if l['rel'] == "alternate" and (l['type'] == 'application/atom+xml' or l['type'] == 'application/rss+xml'):
                    feedcount += 1
                    try:
                        name = l['title']
                    except:
                        name = "Feed %d" % feedcount
                    rethtml += '<li><form method="post" onsubmit="addFeed(%d); return false;"><input type="hidden" name="feed" id="feed-%d" value="%s"><input type="submit" value="Subscribe" class="button"> %s</form></li>' % (feedcount,feedcount,urljoin(feed,l['href']),name)
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

            #TODO: need to check for dupe feed urls!
            
            s = Source.objects.filter(feedURL = feed)
            #o(self,"s: %d/%s" % (s.count(),f))
            if s.count() > 0:
                return HttpResponse("<div>Already subscribed to this feed </div>")


            ff = feedparser.parse(ret.content) #need to start checking feed parser errors here
            ns = Source()
            
            
            print request.POST["river"]
            ns.inRiver = (request.POST["river"] == "yes")
                    
            ns.name = feed
            try:
                ns.htmlUrl = ff.feed.link
                ns.name = ff.feed.title
            except:
                pass
            ns.feedURL = feed
            ns.save()
            #you see really, I could parse out the items here and insert them rather than wait for them to come back round in the refresh cycle

            return HttpResponse("<div>Imported feed %s</div>" % ns.name)
    
    
    # TODO: I don't think that this is the most robust import ever :)
@login_required
def importopml(request):

    theFile = request.FILES["opml"].read()

    count = 0
    dom = minidom.parseString(theFile)
    imported  = []
    
    sources = dom.getElementsByTagName("outline")
    for s in sources:

        ns = Source()
        ns.siteURL = s.getAttribute("htmlUrl")
        ns.feedURL = s.getAttribute("xmlUrl") #probably best to see that there isn't a match here :)
        ns.name = s.getAttribute("title")
        ns.save()
        count += 1
        
        imported.append(ns)
    
    vals = {}
    vals["imported"] = imported    
    vals["count"] = count  
    return render_to_response('importopml.html',vals,context_instance=RequestContext(request))

@login_required
def readfeed(request,fid,qty):
        
    vals  = {}
    if qty == "all":
        qty = 100
    else:
        qty = int(qty)
        
    if fid == "river":
        posts = Post.objects.filter(Q(source__inRiver = True)).order_by("-created")[:qty]
        s = None
    else:
        s = get_object_or_404(Source,id=int(fid))
        posts = Post.objects.filter(Q(source = s) & Q(read = False)).order_by("created")[:qty]
    
        if posts.count() == 0:
            posts = list(Post.objects.filter(source = s).order_by("-created")[:10])
            #posts.reverse()
     
        if (s.unreadCount - qty) < 0:
            s.unreadCount = 0
        else:
            s.unreadCount = s.unreadCount - qty
        s.save()

        for p in posts: #could really do with doing this on a deferred call
            p.read = True
            p.save()
    
    vals["source"] = s
    vals["posts"] = posts
    
    
    #if format == "mobile":
    #   #self.vals["depth"] = int(self.request.get("depth")) +1
    #   render (self,"mobile/feed.html")
    #elif format == "touch":
    #   render (self,"touch/feed.html")
    #else:
    #   render(self,"feed.html")
    return render_to_response('feed.html',vals,context_instance=RequestContext(request))


@login_required
def toggleriver(request,fid):

    if request.method == "POST":
        
        f = get_object_or_404(Source,id=int(fid))
        f.inRiver =  not f.inRiver
        f.save()
        return HttpResponse("OK")


@login_required
def revivefeed(request,fid):

    if request.method == "POST":
        
        f = get_object_or_404(Source,id=int(fid))
        f.live = True
        f.duePoll = datetime.datetime.now()
        f.ETag = None
        f.lastModified = None
        f.lastSuccess = None
        f.lastChange = None
        f.save()
        Post.objects.filter(source=f).delete()
        return HttpResponse("OK")

@login_required
def unsubscribefeed(request,fid):

    if request.method == "POST":
        
        f = get_object_or_404(Source,id=int(fid))

        Post.objects.filter(source=f).delete()
        
        f.delete()

        return HttpResponse("OK")


def reader(request):
    response = HttpResponse()

    response["Content-Type"] = "text/plain"

    sources = Source.objects.filter(Q(duePoll__lt = datetime.datetime.now()) & Q(live = True))[:3]
    #sources = Source.gql("WHERE duePoll < :1 and live = :2 ORDER BY duePoll LIMIT 2",datetime.datetime.now(),True)
    response.write("Update Q: %d\n\n" % sources.count())
    for s in sources:
        
        response.write("\n\n------------------------------\n\n")
        
        s.lastPolled = datetime.datetime.now()
        newCount = s.unreadCount
    
        interval = s.interval
    
        headers = { "User-Agent": "FeedThing/3.0", "Cache-Control":"no-cache,max-age=0", "Pragma":"no-cache" } #identify ourselves and also stop our requests getting picked up by google's cache
        if s.ETag:
            headers["If-None-Match"] = s.ETag
        if s.lastModified:
            headers["If-Modified-Since"] = s.lastModified
        response.write(headers)
        ret = None
        response.write("\nFetching %s" % s.feedURL)
        try:
            ret = requests.get(s.feedURL,headers=headers,allow_redirects=False)
            s.status_code = ret.status_code
            s.lastResult = "Unhandled Case"
        except:
            s.lastResult = "Fetch error"
            s.status_code = 0
        
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
            s.lastSuccess = datetime.datetime.now() #in case we start auto unsubscribing long dead feeds
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
            except:
                response.write("error redirecting")
                s.lastResult = "Error redirecting feed"
                interval += 60
                pass
        elif ret.status_code == 302 or ret.status_code == 303 or ret.status_code == 307: #Temporary redirect
            newURL = ""
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
                    td = datetime.datetime.now() - s.last302start
                    if td > datetime.timedelta(days=7):
                        s.feedURL = newURL
                        s.last302url = None

                else:
                    s.last302url = newURL
                    s.last302start = datetime.datetime.now()

                s.lastResult = "Temporary Redirect to " + newURL + " since " + s.last302start.strftime("%d %B")


            except:     
                s.lastResult = "Failed Redirection to " + newURL
                interval += 60
        
        #NOT ELIF, WE HAVE TO START THE IF AGAIN TO COPE WTIH 
        if ret != None and ret.status_code >= 200 and ret.status_code < 300: #now we are not following redirects 302,303 and so forth are going to fail here, but what the hell :)
            #great
            

            
            changed = False 
            
            try:
                s.ETag = ret.headers["ETag"]
            except:
                s.ETag = None                                   
            try:
                s.lastModified = ret.headers["Last-Modified"]
            except:
                s.lastModified = None                                   
            
            
            response.write("\nEtag:%s\nLast Mod:%s\n\n" % (s.ETag,s.lastModified))
            
            #response.write(ret.content)           
            try:
                f = feedparser.parse(ret.content) #need to start checking feed parser errors here
                entries = f['entries']
                s.lastSuccess = datetime.datetime.now() #in case we start auto unsubscribing long dead feeds

            except:
                s.lastResult = "Feed Parse Error"
                entries = []
                interval += 120
                

            try:
                s.siteURL = f.feed.link
                s.name = f.feed.title
            except:
                pass

            #response.write(entries)
            for e in entries:
                try:
                    body = e.content[0].value
                except:
                    try:
                        body = e.description
                    except:
                        body = ""
            
            
                try:
                    guid = e.guid
                except:
                    try:
                        guid = e.link
                    except:
                        m = hashlib.md5()
                        m.update(body.encode("utf-8"))
                        guid = m.hexdigest()
                                
                response.write(guid + "\n")

                try:
                    p  = Post.objects.filter(Q(source=s) & Q(guid=guid))[0]
                    #p  = Post.gql("WHERE source = :1 AND guid = :2",s,guid)[0]
                except: 
                    p = Post()
                    newCount += 1 # some people like to mark changed items as read, but I don't so this is the only current trigger for unreadness.
                    changed = True
                p.source = s
                
                try:
                    title = e.title
                except:
                    title = "No title"
                                    
                #self.response.out.write(e)
                #self.response.out.write(title + "\n")
                #self.response.out.write(e.link + "\n")
                #self.response.out.write(e.date_parsed + "\n")
                #self.response.out.write(guid + "\n")
    
                try:
                    p.link = e.link
                except:
                    p.link = ''
                p.title = title
                #tags = [t["term"] for t in e.tags]
                #link.tags = ",".join(tags)

                try:
                    #dd = datetime.datetime.fromtimestamp(time.mktime(e.date_parsed))
                    #p.created = datetime.datetime(dd.year,dd.month,dd.day,dd.hour,dd.minute,dd.second,tzinfo=_GMT)
                    #response.write(p.created)
                    
                    
                    p.created  = datetime.datetime.fromtimestamp(time.mktime(e.date_parsed))
                except:
                    p.created  = datetime.datetime.now()
                    
                p.guid = guid
                try:
                    p.author = e.author
                except:
                    p.author = ""

                try:
                    p.body = body                       
                    p.save()
                    #response.write(p.body)
                except:
                    print sys.exc_info()[0]
                    response.write("Save error for post")
            if changed:
                interval /= 2
                s.lastResult = "OK (updated)" #and temporary redirects
                s.lastChange = datetime.datetime.now()
            else:
                s.lastResult = "OK"
                interval += 10 # we slow down feeds a little more that don't send headers we can use
                
            s.unreadCount = newCount
        

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
        s.duePoll = datetime.datetime.now() + td
        s.save()
        
        response.write("OK")
    return response
