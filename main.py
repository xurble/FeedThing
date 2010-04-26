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


from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import users # Since this is a personal aggregator deployed on app engine, I think we can feel safe assuming that the user has a google account

import os
from google.appengine.ext.webapp import template
import time
import datetime

import feedparser
from google.appengine.api.urlfetch import fetch

from xml.dom import minidom

from google.appengine.ext import db

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

	
class Source(db.Model):
	
	name          = db.StringProperty()
	siteURL       = db.StringProperty()
	feedURL       = db.StringProperty()
	lastPolled    = db.DateTimeProperty()
	duePoll       = db.DateTimeProperty(required=True,auto_now_add=True)
	ETag          = db.StringProperty()
	lastModified  = db.StringProperty() # just pass this back and forward between server and me , no need to parse
	unreadCount   = db.IntegerProperty(required=True,default=0)
	lastResult    = db.StringProperty()
	interval      = db.IntegerProperty(required=True,default=60)
	lastSuccess   = db.DateTimeProperty(auto_now_add=True)
	live          = db.BooleanProperty(required=True,default=True)


class Post(db.Model):
	
	source        = db.ReferenceProperty(Source)
	title         = db.StringProperty()
	body          = db.TextProperty()
	link          = db.StringProperty()
	found         = db.DateTimeProperty(auto_now_add=True)
	created       = db.DateTimeProperty()
	tags          = db.StringProperty()
	guid          = db.StringProperty()
	author        = db.StringProperty()

	def taglist(self):
		return self.tags.split(",")


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

		ss = Source.gql("WHERE unreadCount > 0")

		self.vals["sources"] = ss
		render(self,"feeds.html")

class Help(webapp.RequestHandler):

	@page
	def get(self):

		render(self,"help.html")

class AddFeed(webapp.RequestHandler):

	@userpage
	def get(self):	
		self.vals["feed"] = self.request.get("feed")
		render(self,"addfeed.html")
	
class ImportOPML(webapp.RequestHandler):

	@userpage
	def post(self):
		self.response.headers["Content-Type"] = "text/plain"

		theFile = self.request.get("opml")

		
		dom = minidom.parseString(theFile)
		
		sources = dom.getElementsByTagName("outline")
		for s in sources:
			self.response.out.write("\n");
			self.response.out.write(s)		

			ns = Source()
			ns.siteURL = s.getAttribute("htmlUrl")
			ns.feedURL = s.getAttribute("xmlUrl")
			ns.name = s.getAttribute("title")
			ns.put()

		#TODO: Maybe some kind of page or simila :)
		self.response.out.write("OK");

class Reader(webapp.RequestHandler):
	def get(self):
		self.response.headers["Content-Type"] = "text/plain"
	
	
		sources = Source.gql("WHERE duePoll < :1 ORDER BY duePoll LIMIT 1",datetime.datetime.now())
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
			
				for e in f['entries']:
				
				
				
					try:
						guid = e.guid
					except:
						guid = e.link
				
					self.response.out.write(guid + "\n")
	
					try:
						p  = Post.gql("WHERE guid = :1",guid)[0]
					except:	
						p = Post()
						newCount += 1 # some people like to mark changed items as read, but I don't so this is the only current trigger for unreadness.
						
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
					try:
						p.body = e.content
					except:
						p.body = ""
					p.put()
					
					if changed:
						interval /= 2
						s.lastResult = "OK (updated)" #and temporary redirects
					else:
						s.lastResult = "OK"
						interval += 2 # we slow down feeds a little more that don't send headers we can use
					
				s.unreadCount = newCount
			

			else:
				#should not be able to get here
				s.lastResult = "Gareth can't program! %d" % ret.status_code
				
			
			if interval < 60:
				interval = 60 #no less than 1 hour
			if interval > 60 * 60 * 24:
				interval = 60 * 60 * 24 #no more than 1 day
			
			s.interval = interval
			td = datetime.timedelta(minutes=interval)
			s.duePoll = datetime.datetime.now() + td
			s.put()
			
			
			self.response.out.write("\n%s\n" % s.lastResult)		


			
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
  										,('/addfeed/',AddFeed)
  										,('/permissions/',Permissions)
  										,('/importopml/',ImportOPML)
 									,('/robots.txt',Robots)
 
  ],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
