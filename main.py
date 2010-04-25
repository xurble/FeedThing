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
import os
from google.appengine.ext.webapp import template
import time
import datetime

import feedparser
from google.appengine.api.urlfetch import fetch

from xml.dom import minidom

from google.appengine.ext import db


def render(req,templateFile):
	path = os.path.join(os.path.dirname(__file__), "templates", templateFile)
	req.response.out.write(template.render(path, req.vals))


	
class Source(db.Model):
	
	name          = db.StringProperty()
	siteURL       = db.StringProperty()
	feedURL       = db.StringProperty()
	lastPolled    = db.DateTimeProperty()
	duePoll       = db.DateTimeProperty(required=True,auto_now_add=True)
	eTag          = db.StringProperty()
	lastModified  = db.DateTimeProperty()
	unreadCount   = db.IntegerProperty(required=True,default=0)


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

  def get(self):
  
 	self.vals = {}	
  	ss = Source.gql("WHERE unreadCount > 0")
  	
  	self.vals["sources"] = ss
	render(self,"index.html")

class Help(webapp.RequestHandler):

  def get(self):
  
  	self.vals = { }
	render(self,"help.html")
	
	
class ImportOPML(webapp.RequestHandler):

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

		self.response.out.write("OK");

class Reader(webapp.RequestHandler):
	def get(self):
		self.response.headers["Content-Type"] = "text/plain"
	
	
		sources = Source.gql("WHERE duePoll < :1 ORDER BY duePoll LIMIT 1",datetime.datetime.now())
		for s in sources:
		
			newCount = s.unreadCount
		
			td = datetime.timedelta(hours=4)
			s.duePoll = datetime.datetime.now() + td
			s.lastPolled = datetime.datetime.now()
			s.put()
		
			content = fetch(s.feedURL).content  #need all that etag last modified stuff
			f = feedparser.parse(content)
		
			self.response.out.write("\n\n")		
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
				self.response.out.write(e.link + "\n")
				#self.response.out.write(e.date_parsed + "\n")
				self.response.out.write(guid + "\n")
	
				p.link = e.link
				p.title = e.title
				#tags = [t["term"] for t in e.tags]
				#link.tags = ",".join(tags)
				p.created = datetime.datetime.fromtimestamp(time.mktime(e.date_parsed))
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
			s.unreadCount = newCount
			s.put()

			
			self.response.out.write("\n\n")		


			
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
  										,('/importopml/',ImportOPML)
 									,('/robots.txt',Robots)
 
  ],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
