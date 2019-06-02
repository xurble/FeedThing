import feedparser
from django.db.models import Q

from .models import *

import time
import datetime

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests
import io
import pyrfc3339
import json
import traceback

from django.conf import settings

import hashlib


def fix_relative(html,url):

    """ this is fucking cheesy """
    try:
        base = "/".join(url.split("/")[:3])

        html = html.replace("src='/", "src='%s/" % base)
        html = html.replace('src="/', 'src="%s/' % base)
    
    except Exception as ex:
        print(ex)    

    return html
    
    
        

def update_feeds(response, host_name, max_feeds=3):

    if  response is None:
        response = io.StringIO()

    todo = Source.objects.filter(Q(due_poll__lt = datetime.datetime.utcnow()) & Q(live = True))
    
    response.write("Queue size is {}".format(todo.count()))

    sources = todo.order_by("due_poll")[:max_feeds]

    response.write("\nProcessing %d\n\n" % sources.count())


    for s in sources:
        
        read_feed(response, s, host_name)
        
    
    
def read_feed(response, source_feed, host_name):

    was302 = False
    
    response.write("\n\n------------------------------\n\n")
    
    source_feed.last_polled = datetime.datetime.utcnow().replace(tzinfo=utc)
    #newCount = source_feed.undread_count

    interval =  source_feed.interval

    headers = { "User-Agent": "FeedThing/3.3 (+http://%s; Updater; %d subscribers)" % (host_name,source_feed.num_subs),  } #identify ourselves 
    # "Cache-Control":"no-cache,max-age=0", "Pragma":"no-cache" -- just removed these. Think they were a solution to app-engine and actually counter-productive now


    """ proxies = {}
    proxy_list  = None
    proxy = None
    if source_feed.needs_proxy : # Fuck you cloudflare. 
        try:
            if WebProxy.objects.count() == 0:
                find_proxies()
            
            proxy = WebProxy.objects.all()[0]
            
            proxies = {
              'http': proxy.address,
              'https': proxy.address,
            }
            # OK so if this works we should start scraping open proxy lists not hardcoding :)
        except:
            pass    
"""
    if source_feed.etag:
        headers["If-None-Match"] = str(source_feed.etag)
    if source_feed.last_modified:
        headers["If-Modified-Since"] = str(source_feed.last_modified)

    ret = None
    response.write("\nFetching %s" % source_feed.feed_url)
    try:
        ret = requests.get(source_feed.feed_url,headers=headers,allow_redirects=False,verify=False,timeout=20)
        source_feed.status_code = ret.status_code
        source_feed.last_result = "Unhandled Case"
        response.write("\nResult: %d" % ret.status_code)
    except Exception as ex:
        print(ex)
        source_feed.last_result = ("Fetch error:" + str(ex))[:255]
        source_feed.status_code = 0
        response.write("\nFetch error: " + str(ex))


        
    if ret == None and source_feed.status_code == 1:   
        pass
    elif ret == None or source_feed.status_code == 0:
        interval += 120
    elif ret.status_code < 200 or ret.status_code >= 500:
        #errors, impossible return codes
        interval += 120
        source_feed.last_result = "Server error fetching feed (%d)" % ret.status_code
    elif ret.status_code == 404:
        #not found
        interval += 120
        source_feed.last_result = "The feed could not be found"
    elif ret.status_code == 403 or ret.status_code == 410: #Forbidden or gone

        if "Cloudflare" in ret.text or ("Server" in ret.headers and "cloudflare" in ret.headers["Server"]):
            if source_feed.needs_proxy and proxy is not None:
                # we are already proxied - this proxy on cloudflare's shit list too?
                proxy.delete()
                response.write("\Proxy seemed to also be blocked, burning")
                interval /= 2
                source_feed.last_result = "Proxy kind of worked but still got cloudflared."
            else:            
                source_feed.needs_proxy = True
                source_feed.last_result = "Blocked by Cloudflare, will try via proxy next time."
        else:
            source_feed.live = False
            source_feed.last_result = "Feed is no longer accessible (%d)" % ret.status_code
    elif ret.status_code >= 400 and ret.status_code < 500:
        #treat as bad request
        source_feed.live = False
        source_feed.last_result = "Bad request (%d)" % ret.status_code
    elif ret.status_code == 304:
        #not modified
        interval += 5
        source_feed.last_result = "Not modified"
        source_feed.last_success = datetime.datetime.utcnow().replace(tzinfo=utc)
        
        if source_feed.last_success and (datetime.datetime.utcnow().replace(tzinfo=utc) - source_feed.last_success).days > 7:
            source_feed.last_result = "Clearing etag/last modified due to lack of changes"
            source_feed.etag = None
            source_feed.last_modified = None
        
        
    
    elif ret.status_code == 301: #permenant redirect
        newURL = ""
        try:
            if "Location" in ret.headers:
                newURL = ret.headers["Location"]
            
                if newURL[0] == "/":
                    #find the domain from the feed
                    
                    base = "/".join(source_feed.feed_url.split("/")[:3])
                    
                
                    newURL = base + newURL


                source_feed.feed_url = newURL
            
                source_feed.last_result = "Moved"
            else:
                source_feed.last_result = "Feed has moved but no location provided"
        except exception as Ex:
            response.write("error redirecting")
            source_feed.last_result = "Error redirecting feed to " + newURL  
            interval += 60
            pass
    elif ret.status_code == 302 or ret.status_code == 303 or ret.status_code == 307: #Temporary redirect
        newURL = ""
        was302 = True
        try:
            newURL = ret.headers["Location"]
            
            if newURL[0] == "/":
                #find the domain from the feed
                start = source_feed.feed_url[:8]
                end = source_feed.feed_url[8:]
                if end.find("/") >= 0:
                    end = end[:end.find("/")]
                
                newURL = start + end + newURL
                
            
            ret = requests.get(newURL,headers=headers,allow_redirects=True,verify=False, timeout=20)
            source_feed.status_code = ret.status_code
            source_feed.last_result = "Temporary Redirect to " + newURL

            
            if source_feed.last302url == newURL:
                #this is where we 302'd to last time
                td = datetime.datetime.utcnow().replace(tzinfo=utc) - source_feed.last302start
                if td > datetime.timedelta(days=60):
                    source_feed.feed_url = newURL
                    source_feed.last302url = " "

            else:
                source_feed.last302url = newURL
                source_feed.last302start = datetime.datetime.utcnow().replace(tzinfo=utc)

            source_feed.last_result = "Temporary Redirect to " + newURL + " since " + source_feed.last302start.strftime("%d %B")


        except Exception as ex:     
            source_feed.last_result = "Failed Redirection to " + newURL +  " " + str(ex)
            interval += 60
    
    #NOT ELIF, WE HAVE TO START THE IF AGAIN TO COPE WTIH 302
    if ret and ret.status_code >= 200 and ret.status_code < 300: #now we are not following redirects 302,303 and so forth are going to fail here, but what the hell :)

        # great!
        
        
        if was302:
            source_feed.etag = None
            source_feed.last_modified = None
        else:
            try:
                source_feed.etag = ret.headers["etag"]
            except Exception as ex:
                source_feed.etag = None                                   
            try:
                source_feed.last_modified = ret.headers["Last-Modified"]
            except Exception as ex:
                source_feed.last_modified = None                                   
        
        response.write("\netag:%s\nLast Mod:%s\n\n" % (source_feed.etag,source_feed.last_modified))
        
        feed_body = ret.text.strip()
        
        content_type = "Not Set"
        if "Content-Type" in ret.headers:
            content_type = ret.headers["Content-Type"]
        
        if "xml" in content_type or feed_body[0:1] == "<":
            (ok,changed, interval) = parse_feed_xml(source_feed, feed_body, interval , response)
        elif "json" in content_type or feed_body[0:1] == "{":
            (ok,changed, interval) = parse_feed_json(source_feed, feed_body, interval, response)
        else:
            ok = False
            source_feed.last_result = "Unknown Feed Type: " + content_type
            interval += 120 # we slow down when feeds look duff

        if ok and changed:
            interval /= 2
            source_feed.last_result = " OK (updated)" #and temporary redirects
            source_feed.last_change = datetime.datetime.utcnow().replace(tzinfo=utc)
            
            idx = source_feed.max_index
            # give indices to posts based on created date
            posts = Post.objects.filter(Q(source=source_feed) & Q(index=0)).order_by("created")
            for p in posts:
                idx += 1
                p.index = idx
                p.save()
                
            source_feed.max_index = idx

            
            
        elif ok:
            source_feed.last_result = "OK"
            interval += 10 # we slow down feeds a little more that don't send headers we can use
            
        #source_feed.undread_count = newCount
    

    #else:
    #   #should not be able to get here
    #   oops = "Gareth can't program! %d" % ret.status_code
    #   logging.error(oops)
    #   source_feed.last_result = oops
        
    
    if interval < 60:
        interval = 60 #no less than 1 hour
    if interval > (60 * 24):
        interval = (60 * 24) #no more than 1 day  
    
    response.write("\nUpdating interval from %d to %d\n" % (source_feed.interval,interval))
    source_feed.interval = interval
    td = datetime.timedelta(minutes=interval)
    source_feed.due_poll = datetime.datetime.utcnow().replace(tzinfo=utc) + td
    source_feed.save()
    

    
def parse_feed_xml(source_feed, feed_content, interval, response):

    ok = True
    changed = False 

    #response.write(ret.content)           
    try:
        f = feedparser.parse(feed_content) #need to start checking feed parser errors here
        entries = f['entries']
        if len(entries):
            source_feed.last_success = datetime.datetime.utcnow().replace(tzinfo=utc) #in case we start auto unsubscribing long dead feeds
        else:
            source_feed.last_result = "Feed is empty"
            interval += 120
            ok = False

    except Exception as ex:
        source_feed.last_result = "Feed Parse Error"
        entries = []
        interval += 120
        ok = False
    
    if ok:

        try:
            source_feed.site_url = f.feed.link
            source_feed.name = f.feed.title
        except Exception as ex:
            pass
    

        #response.write(entries)
        entries.reverse() # Entries are typically in reverse chronological order - put them in right order
        for e in entries:
            try:
                if e.content[0].type == "text/plain":
                    raise
                body = e.content[0].value
            except Exception as ex:
                try:
                    body = e.summary                    
                except Exception as ex:
                    body = " "

            body = fix_relative(body, source_feed.site_url)



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
        
                p.created  = datetime.datetime.fromtimestamp(time.mktime(e.published_parsed)).replace(tzinfo=utc)

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
                traceback.print_tb(sys.exc_info()[2],file=response)

    return (ok,changed,interval)
    
    
    
def parse_feed_json(source_feed, feed_content, interval, response):

    ok = True
    changed = False 

    try:
        f = json.loads(feed_content)
        entries = f['items']
        if len(entries):
            source_feed.last_success = datetime.datetime.utcnow().replace(tzinfo=utc) #in case we start auto unsubscribing long dead feeds
        else:
            source_feed.last_result = "Feed is empty"
            interval += 120
            ok = False

    except Exception as ex:
        source_feed.last_result = "Feed Parse Error"
        entries = []
        interval += 120
        ok = False
    
    if ok:
    
        if "expired" in f and f["expired"]:
            # This feed says it is done
            # TODO: permanently disable
            # for now interval to max
            interval = (24*3*60)
            source_feed.last_result = "This feed has expired"
            return (False,False,interval)

        try:
            source_feed.site_url = f["home_page_url"]
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
                
            body = fix_relative(body,source_feed.site_url)

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
            body  = feedparser._sanitizeHTML(body, "utf-8", 'text/html') # TODO: validate charset ??
            title = feedparser._sanitizeHTML(title, "utf-8", 'text/html') # TODO: validate charset ??
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
                traceback.print_tb(sys.exc_info()[2],file=response)

    return (ok,changed,interval)