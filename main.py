#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import hashlib
import logging
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import users # Since this is a personal aggregator deployed on app engine, I think we can feel safe assuming that the user has a google account

import os
from google.appengine.ext.webapp import template

import feedparser
from google.appengine.api.urlfetch import fetch

from xml.dom import minidom

from model import *

import time
import datetime
from google.appengine.ext import db

from BeautifulSoup import BeautifulSoup
from urlparse import urljoin

from google.appengine.ext import deferred

from tasks import TaskThing


def o(req,msg):
	req.response.out.write(msg)

def render(req,templateFile):
	path = os.path.join(os.path.dirname(__file__), "templates", templateFile)
	req.response.out.write(template.render(path, req.vals))


def findUser(page):
	page.vals = {}
	page.user = users.get_current_user()
	page.vals["user"] = page.user
	if page.user:
		page.vals["logout"] = users.create_logout_url("/")
	
def page(func):
	def _page(*args,**kwargs):
		
		findUser(args[0])
		
		return func(*args,**kwargs)
		
	return _page



def userpage(func):
	def _up(*args,**kwargs):

		p = args[0]
		findUser(p)

		if p.user != None:
			if users.is_current_user_admin(): #must be admin - everything here is for the personal use of the owner
				return func(*args,**kwargs)
			else:
				p.redirect("/permissions/")				
		else:
			p.redirect(users.create_login_url(p.request.uri))
			return None
			
	return _up

	


class MainHandler(webapp.RequestHandler):
	@page
	def get(self):
		render(self,"index.html")

class Permissions(webapp.RequestHandler):
	@page
	def get(self):
		render(self,"permissions.html")

class Feeds(webapp.RequestHandler):
	@userpage
	def get(self):

		render(self,"feeds.html")

class FeedPane(webapp.RequestHandler):
	@userpage
	def get(self):

		render(self,"feedpane.html")


class FeedList(webapp.RequestHandler):
	@userpage
	def get(self):

		ss = Source.gql("WHERE unreadCount > 0")

		self.vals["sources"] = ss
		render(self,"feedlist.html")

class MobileFeeds(webapp.RequestHandler):
	@userpage
	def get(self):

		ss = Source.gql("WHERE unreadCount > 0")

		self.vals["sources"] = ss
		render(self,"mobile/index.html")


class Help(webapp.RequestHandler):

	@page
	def get(self):

		render(self,"help.html")

class AddFeed(webapp.RequestHandler):

	@userpage
	def get(self):
		f = self.request.get("feed")
		self.vals["feed"] = f
		render(self,"addfeed.html")
		
	@userpage
	def post(self):	
		f = self.request.get("feed")
		self.vals["feed"] = f
		ret = fetch(f)
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
					rethtml += '<form method="post" onsubmit="addFeed(%d); return false;"><input type="hidden" name="feed" id="feed-%d" value="%s">%s <input type="submit" value="Subscribe"></form>' % (feedcount,feedcount,urljoin(f,l['href']),name)
					f = urljoin(f,l['href']) # store this in case there is only one feed and we wind up importing it
					#TODO: need to accout for relative URLs here
			#if feedcount == 1:
				#just 1 feed found, let's import it now
				
			#	ret = fetch(f)
			#	isFeed = True
			if feedcount == 0:
				o(self,"No feeds found")
			else:
				o(self,rethtml)
				
		if isFeed:

			#TODO: need to check for dupe feed urls!
			
			s = Source.gql("WHERE feedURL = :1", f)
			#o(self,"s: %d/%s" % (s.count(),f))
			if s.count() > 0:
				o(self,"<div>Already subscribed to this feed </div>")
				return

			ff = feedparser.parse(ret.content) #need to start checking feed parser errors here
			ns = Source()
		
			ns.name = f
			try:
				ns.htmlUrl = ff.feed.link
				ns.name = ff.feed.title
			except:
				pass
			ns.feedURL = f
			ns.put()
			#you see really, I could parse out the items here and insert them rather than wait for them to come back round in the refresh cycle

			o(self,"<div>Imported feed %s</div>" % ns.name)

class Unsubscribe(webapp.RequestHandler):
	@userpage
	def post(self,fid):

		t = TaskThing()
		deferred.defer(t.DeleteFeed,fid)


		o(self,"Unsubscribed")		
		
class ReadFeed(webapp.RequestHandler):
	@userpage
	def get(self,fid,format,count):
		
		if count == "all":
			count = "1000"
	
		s = Source.get_by_id(int(fid))
		posts = Post.gql("WHERE source = :1 and read = :2 ORDER by created LIMIT " + count,s,False) 
		pp = []
		for p in posts: #could really do with doing this on a deferred call
			p.read = True
			p.put()
			pp.append(p)
		if (s.unreadCount - int(count)) < 0:
			s.unreadCount = 0
		else:
			s.unreadCount = s.unreadCount - int(count)
		s.put()
		
		self.vals["source"] = s
		self.vals["posts"] = posts
		
		#t = TaskThing()
		#deferred.defer(t.MarkRead,pp)
		
		
		if format == "mobile":
			#self.vals["depth"] = int(self.request.get("depth")) +1
			render (self,"mobile/feed.html")
		else:
			render(self,"feed.html")
	
class ImportOPML(webapp.RequestHandler):

	# TODO: I don't think that this is the most robust import ever :)
	@userpage
	def post(self):

		theFile = self.request.get("opml")

		count = 0
		dom = minidom.parseString(theFile)
		imported  = []
		
		sources = dom.getElementsByTagName("outline")
		for s in sources:

			ns = Source()
			ns.siteURL = s.getAttribute("htmlUrl")
			ns.feedURL = s.getAttribute("xmlUrl") #probably best to see that there isn't a match here :)
			ns.name = s.getAttribute("title")
			ns.put()
			count += 1
			
			imported.append(ns)
		
		self.vals["imported"] = imported	
		self.vals["count"] = count	
		render(self,"importopml.html")


class Reader(webapp.RequestHandler):
	def get(self):
		self.response.headers["Content-Type"] = "text/plain"
	
	
		sources = Source.gql("WHERE duePoll < :1 ORDER BY duePoll LIMIT 2",datetime.datetime.now())
		o(self,"Update Q: %d\n\n" % sources.count())
		for s in sources:
		
			
			s.lastPolled = datetime.datetime.now()
			newCount = s.unreadCount
		
			interval = s.interval
		
			headers = { "User-Agent": "FeedThing/2.0", "Cache-Control":"no-cache,max-age=0", "Pragma":"no-cache" } #identify ourselves and also stop our requests getting picked up by google's cache
			if s.ETag:
				headers["If-None-Match"] = s.ETag
			if s.lastModified:
				headers["If-Modified-Since"] = s.lastModified
			o(self,headers)
			ret = None
			o(self,"\nFetching %s" % s.feedURL)
			try:
				ret = fetch(s.feedURL,headers=headers)
			except:
				s.lastResult = "Fetch error"
						
			
			if ret == None:
				interval += 120
				pass
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
				interval += 1
				s.lastResult = "Not modified"
				
			elif ret.status_code >= 200 and ret.status_code < 400:
				#great
				s.lastSuccess = datetime.datetime.now() #in case we start auto unsubscribing long dead feeds
				

				
				if ret.status_code == 301: #permanent redirect
					try:
						s.feedURL = s.headers["Location"]  #Hope they never send a relative URL here :)
					except:
						pass
				changed = False	
				
				try:
					s.ETag = ret.headers["ETag"]
				except:
					s.ETag = None									
				try:
					s.lastModified = ret.headers["Last-Modified"]
				except:
					s.lastModified = None									
				
				
				o(self,"\nEtag:%s\nLast Mod:%s\n\n" % (s.ETag,s.lastModified))
								
				f = feedparser.parse(ret.content) #need to start checking feed parser errors here

				try:
					s.siteURL = f.feed.link
					s.name = f.feed.title
				except:
					pass

				for e in f['entries']:
				
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
							m.update(body)
							guid = m.hexdigest()
									
					self.response.out.write(guid + "\n")
	
					try:
						p  = Post.gql("WHERE source = :1 AND guid = :2",s,guid)[0]
					except:	
						p = Post()
						newCount += 1 # some people like to mark changed items as read, but I don't so this is the only current trigger for unreadness.
						changed = True
					p.source = s
					
					#self.response.out.write(e)
					self.response.out.write(e.title + "\n")
					#self.response.out.write(e.link + "\n")
					#self.response.out.write(e.date_parsed + "\n")
					self.response.out.write(guid + "\n")
		
					try:
						p.link = e.link
					except:
						p.link = ''
					p.title = e.title
					#tags = [t["term"] for t in e.tags]
					#link.tags = ",".join(tags)
					try:
						p.created = datetime.datetime.fromtimestamp(time.mktime(e.date_parsed))
					except:
						p.created  = datetime.datetime.now()
						
					p.guid = guid
					try:
						p.author = e.author
					except:
						p.author = ""

					p.body = body						
					p.put()
					o(self,p.body)
				if changed:
					interval /= 2
					s.lastResult = "OK (updated)" #and temporary redirects
					s.lastChanged = datetime.datetime.now()
				else:
					s.lastResult = "OK"
					interval += 2 # we slow down feeds a little more that don't send headers we can use
					
				s.unreadCount = newCount
			

			else:
				#should not be able to get here
				oops = "Gareth can't program! %d" % ret.status_code
				logging.error(oops)
				s.lastResult = oops
				
			
			if interval < 60:
				interval = 60 #no less than 1 hour
			if interval > 60 * 60 * 24:
				interval = 60 * 60 * 24 #no more than 1 day
			
			o(self,"\nUpdating interval from %d to %d\n" % (s.interval,interval))
			s.interval = interval
			td = datetime.timedelta(minutes=interval)
			s.duePoll = datetime.datetime.now() + td
			s.put()
			
			
			self.response.out.write("\n%s\n" % s.lastResult)		

class Manifest(webapp.RequestHandler):
	def get(self):
		self.response.headers["Content-Type"] = "text/cache-manifest"
		self.response.headers.add_header("Expires", "Sun, 01 Jan 2012 16:00:00 GMT")
		self.response.out.write("""CACHE MANIFEST
# THIS MANISFEST SHOULD CACHE THE FILES REQUIRED FOR THE 
# MOBILE VERSION LOCALLY SO THAT IT ALL WORKS A BIT FASTER
/static/jqt/jquery.1.4.2.js
/static/jqt/jqtouch.js
/static/jqt/jqtouch.css
/static/jqt/themes/jqt/theme.css
/static/jqt/themes/jqt/img/back_button_clicked.png
/static/jqt/themes/jqt/img/button_clicked.png
/static/jqt/themes/jqt/img/toolbar.png		
/static/jqt/themes/jqt/img/button.png
/static/jqt/themes/jqt/img/blueButton.png
/static/jqt/themes/jqt/img/back_button.png
/static/jqt/themes/jqt/img/whiteButton.png
/static/jqt/themes/jqt/img/grayButton.png
/static/jqt/themes/jqt/img/on_off.png
/static/jqt/themes/jqt/img/chevron.png	
/static/jqt/themes/jqt/img/chevron_circle.png
/static/jqt/themes/jqt/img/loading.gif
""")

			
class Robots(webapp.RequestHandler):
	def get(self):
		self.response.headers["Content-Type"] = "text/plain"
		self.response.headers.add_header("Expires", "Sun, 01 Jan 2012 16:00:00 GMT")
		self.response.out.write("""
User-agent: *
Disallow: /

""")


def main():
	application = webapp.WSGIApplication([('/', MainHandler),
											('/refresh/',Reader)
											,('/help/',Help)
											,('/feeds/',Feeds)
											,('/feedlist/',FeedList)
											,('/feedpane/',FeedPane)
											,('/addfeed/',AddFeed)
											,('/permissions/',Permissions)
											,('/importopml/',ImportOPML)
											,('/read/(.*)/(.*)/(.*)/',ReadFeed)
											,('/feed/(.*)/unsubscribe/',Unsubscribe)
											,('/m/',MobileFeeds)
											,('/m/manifest/',Manifest)
											,('/robots.txt',Robots)

										],
										debug=True)
	util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
