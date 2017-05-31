import feedparser
from django.db.models import Q

from models import *

import time
import datetime

from BeautifulSoup import BeautifulSoup
from urlparse import urljoin
import requests
import StringIO
import pyrfc3339
import json
import traceback

def update_feeds(host_name, max_feeds=3):


    import pdb; pdb.set_trace()
    sources = Source.objects.filter(Q(duePoll__lt = datetime.datetime.utcnow().replace(tzinfo=utc)) & Q(live = True)).order_by('duePoll')[:max_feeds]


    ret = "Update Q: %d\n\n" % sources.count()
    for s in sources:
        
        ret = ret + read_feed(s,host_name)
        
        
    ret += ("\n\nDone")
    
    
    return ret
    
    
def read_feed(source_feed, host_name):

    response = StringIO.StringIO()

    was302 = False
    
    response.write("\n\n------------------------------\n\n")
    
    source_feed.lastPolled = datetime.datetime.utcnow().replace(tzinfo=utc)
    #newCount = source_feed.unreadCount

    interval =  source_feed.interval

    headers = { "User-Agent": "FeedThing/3.2 (+http://%s; Updater; %d subscribers)" % (host_name,source_feed.num_subs),  } #identify ourselves 
    # "Cache-Control":"no-cache,max-age=0", "Pragma":"no-cache" -- just removed these. Think they were a solution to app-engine and actually counter-productive now


    if source_feed.ETag:
        headers["If-None-Match"] = str(source_feed.ETag)
    if source_feed.lastModified:
        headers["If-Modified-Since"] = str(source_feed.lastModified)
    response.write(headers)
    ret = None
    response.write("\nFetching %s" % source_feed.feedURL)
    try:
        ret = requests.get(source_feed.feedURL,headers=headers,allow_redirects=False,verify=False,timeout=20)
        source_feed.status_code = ret.status_code
        source_feed.lastResult = "Unhandled Case"
    except Exception as ex:
        print ex
        source_feed.lastResult = ("Fetch error:" + str(ex))[:255]
        source_feed.status_code = 0
        response.write("\nFetch error: " + str(ex))
    
    if ret:
        response.write("\nResult: %d" % ret.status_code)
                
    if ret == None or source_feed.status_code == 0:
        interval += 120
    elif ret.status_code < 200 or ret.status_code >= 500:
        #errors, impossible return codes
        interval += 120
        source_feed.lastResult = "Server error fetching feed (%d)" % ret.status_code
    elif ret.status_code == 404:
        #not found
        interval += 120
        source_feed.lastResult = "The feed could not be found"
    elif ret.status_code == 403 or ret.status_code == 410: #Forbidden or gone
        source_feed.live = False
        source_feed.lastResult = "Feed is no longer accessible (%d)" % ret.status_code
    elif ret.status_code >= 400 and ret.status_code < 500:
        #treat as bad request
        source_feed.live = False
        source_feed.lastResult = "Bad request (%d)" % ret.status_code
    elif ret.status_code == 304:
        #not modified
        interval += 5
        source_feed.lastResult = "Not modified"
        #source_feed.lastSuccess = datetime.datetime.utcnow().replace(tzinfo=utc) #in case we start auto unsubscribing long dead feeds
        
        if (datetime.datetime.utcnow().replace(tzinfo=utc) - source_feed.lastSuccess).days > 7:
            source_feed.lastResult = "Clearing etag/last modified due to lack of changes"
            source_feed.ETag = None
            source_feed.lastModified = None
    
    elif ret.status_code == 301: #permenant redirect
        try:

            newURL = ret.headers["Location"]
            
            if newURL[0] == "/":
                #find the domain from the feed
                start = source_feed.feedURL[:8]
                end = source_feed.feedURL[8:]
                if end.find("/") >= 0:
                    end = end[:end.find("/")]
                
                newURL = start + end + newURL


            source_feed.feedURL = newURL
            
            source_feed.lastResult = "Moved"
        except exception as Ex:
            response.write("error redirecting")
            source_feed.lastResult = "Error redirecting feed"
            interval += 60
            pass
    elif ret.status_code == 302 or ret.status_code == 303 or ret.status_code == 307: #Temporary redirect
        newURL = ""
        was302 = True
        try:
            newURL = ret.headers["Location"]
            
            if newURL[0] == "/":
                #find the domain from the feed
                start = source_feed.feedURL[:8]
                end = source_feed.feedURL[8:]
                if end.find("/") >= 0:
                    end = end[:end.find("/")]
                
                newURL = start + end + newURL
                
            
            ret = requests.get(newURL,headers=headers,allow_redirects=True,verify=False)
            source_feed.status_code = ret.status_code
            source_feed.lastResult = "Temporary Redirect to " + newURL

            
            if source_feed.last302url == newURL:
                #this is where we 302'd to last time
                td = datetime.datetime.utcnow().replace(tzinfo=utc) - source_feed.last302start
                if td > datetime.timedelta(days=60):
                    source_feed.feedURL = newURL
                    source_feed.last302url = " "

            else:
                source_feed.last302url = newURL
                source_feed.last302start = datetime.datetime.utcnow().replace(tzinfo=utc)

            source_feed.lastResult = "Temporary Redirect to " + newURL + " since " + source_feed.last302start.strftime("%d %B")


        except Exception as ex:     
            source_feed.lastResult = "Failed Redirection to " + newURL +  " " + str(ex)
            interval += 60
    
    #NOT ELIF, WE HAVE TO START THE IF AGAIN TO COPE WTIH 302
    if ret and ret.status_code >= 200 and ret.status_code < 300: #now we are not following redirects 302,303 and so forth are going to fail here, but what the hell :)

        # great!
        
        
        if was302:
            source_feed.ETag = None
            source_feed.lastModified = None
        else:
            try:
                source_feed.ETag = ret.headers["ETag"]
            except Exception as ex:
                source_feed.ETag = None                                   
            try:
                source_feed.lastModified = ret.headers["Last-Modified"]
            except Exception as ex:
                source_feed.lastModified = None                                   
        
        response.write("\nEtag:%s\nLast Mod:%s\n\n" % (source_feed.ETag,source_feed.lastModified))
        
        feed_body = ret.content.strip()
        
        content_type = "Not Set"
        if "Content-Type" in ret.headers:
            content_type = ret.headers["Content-Type"]
        
        if "xml" in content_type or feed_body[0:1] == "<":
            (ok,changed, interval) = parse_feed_xml(source_feed, feed_body, interval , response)
        elif "json" in content_type or feed_body[0:1] == "{":
            (ok,changed, interval) = parse_feed_json(source_feed, feed_body, interval, response)
        else:
            ok = False
            source_feed.lastResult = "Unknown Feed Type: " + content_type
            interval += 120 # we slow down when feeds look duff

        if ok and changed:
            interval /= 2
            source_feed.lastResult = " OK (updated)" #and temporary redirects
            source_feed.lastChange = datetime.datetime.utcnow().replace(tzinfo=utc)
            
            idx = source_feed.maxIndex
            # give indices to posts based on created date
            posts = Post.objects.filter(Q(source=source_feed) & Q(index=0)).order_by("created")
            for p in posts:
                idx += 1
                p.index = idx
                p.save()
                
            source_feed.maxIndex = idx

            
            
        elif ok:
            source_feed.lastResult = "OK"
            interval += 10 # we slow down feeds a little more that don't send headers we can use
            
        #source_feed.unreadCount = newCount
    

    #else:
    #   #should not be able to get here
    #   oops = "Gareth can't program! %d" % ret.status_code
    #   logging.error(oops)
    #   source_feed.lastResult = oops
        
    
    if interval < 60:
        interval = 60 #no less than 1 hour
    if interval > (60 * 60 * 24 * 3):
        interval = (60 * 60 * 24 * 3) #no more than 3 days
    
    response.write("\nUpdating interval from %d to %d\n" % (source_feed.interval,interval))
    source_feed.interval = interval
    td = datetime.timedelta(minutes=interval)
    source_feed.duePoll = datetime.datetime.utcnow().replace(tzinfo=utc) + td
    source_feed.save()
    
    ret = response.getvalue()
    response.close()
    return ret

    
def parse_feed_xml(source_feed, feed_content, interval, response):

    ok = True
    changed = False 

    #response.write(ret.content)           
    try:
        f = feedparser.parse(feed_content) #need to start checking feed parser errors here
        entries = f['entries']
        if len(entries):
            source_feed.lastSuccess = datetime.datetime.utcnow().replace(tzinfo=utc) #in case we start auto unsubscribing long dead feeds
        else:
            source_feed.lastResult = "Feed is empty"
            interval += 120
            ok = False

    except Exception as ex:
        source_feed.lastResult = "Feed Parse Error"
        entries = []
        interval += 120
        ok = False
    
    if ok:

        try:
            source_feed.siteURL = f.feed.link
            source_feed.name = f.feed.title
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
                p  = Post.objects.filter(source=source_feed).filter(guid=guid)[0]
                response.write("EXISTING " + guid + "\n")

            except Exception as ex:
                response.write("NEW " + guid + "\n")
                p = Post(index=0)
                p.found = datetime.datetime.utcnow().replace(tzinfo=utc)
                changed = True
                p.source = source_feed
    
            try:
                title = e.title
            except Exception as ex:
                title = ""
                        
            try:
                p.link = e.link
            except Exception as ex:
                p.link = ''
            p.title = title

            try:
        
                p.created  = datetime.datetime.fromtimestamp(time.mktime(e.date_parsed)).replace(tzinfo=utc)

            except Exception as ex:
                response.write("CREATED ERROR")     
                p.created  = datetime.datetime.utcnow().replace(tzinfo=utc)
        
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

    return (ok,changed,interval)
    
    
    
def parse_feed_json(source_feed, feed_content, interval, response):

    ok = True
    changed = False 

    try:
        f = json.loads(feed_content)
        entries = f['items']
        if len(entries):
            source_feed.lastSuccess = datetime.datetime.utcnow().replace(tzinfo=utc) #in case we start auto unsubscribing long dead feeds
        else:
            source_feed.lastResult = "Feed is empty"
            interval += 120
            ok = False

    except Exception as ex:
        source_feed.lastResult = "Feed Parse Error"
        entries = []
        interval += 120
        ok = False
    
    if ok:
    
        if "expired" in f and f["expired"]:
            # This feed says it is done
            # TODO: permanently disable
            # for now interval to max
            interval = (24*3*60)
            source_feed.lastResult = "This feed has expired"
            return (False,False,interval)

        try:
            source_feed.siteURL = f["home_page_url"]
            source_feed.name = f["title"]
        except Exception as ex:
            pass
    

        #response.write(entries)
        entries.reverse() # Entries are typically in reverse chronological order - put them in right order
        for e in entries:
            body = " "
            if "content_text" in e:
                body = e["content_text"]
            if "content_html" in e:
                body = e["content_html"] # prefer html over text
                

            try:
                guid = e["id"]
            except Exception as ex:
                try:
                    guid = e["url"]
                except Exception as ex:
                    m = hashlib.md5()
                    m.update(body.encode("utf-8"))
                    guid = m.hexdigest()
                    
            try:
                p  = Post.objects.filter(source=source_feed).filter(guid=guid)[0]
                response.write("EXISTING " + guid + "\n")

            except Exception as ex:
                response.write("NEW " + guid + "\n")
                p = Post(index=0)
                p.found = datetime.datetime.utcnow().replace(tzinfo=utc)
                changed = True
                p.source = source_feed
    
            try:
                title = e["title"]
            except Exception as ex:
                title = ""      
                
            # borrow the RSS parser's sanitizer
            body  = feedparser._sanitizeHTML(body, "utf-8") # TODO: validate charset ??
            title = feedparser._sanitizeHTML(title, "utf-8") # TODO: validate charset ??
            # no other fields are ever marked as |safe in the templates

                        
            try:
                p.link = e["url"]
            except Exception as ex:
                p.link = ''
            
            p.title = title

            try:
                p.created  = pyrfc3339.parse(e["date_published"])
            except Exception as ex:
                response.write("CREATED ERROR")     
                p.created  = datetime.datetime.utcnow().replace(tzinfo=utc)
        
        
            p.guid = guid
            try:
                p.author = e["author"]
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

    return (ok,changed,interval)