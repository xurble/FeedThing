
import time
import datetime
from google.appengine.ext import db


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
	lastChange    = db.DateTimeProperty(auto_now_add=True)
	live          = db.BooleanProperty(required=True,default=True)
	
	def bestLink(self):
		#the html link else hte feed link
		if self.siteURL == None or self.siteURL == '':
			return self.feedURL
		else:
			return self.siteURL
			
	def displayName(self):
		if self.name == None or self.name == "":
			return self.bestLink()
		else:
			return self.name
			
	def gardenStyle(self):
		
		dd = datetime.datetime.now() - self.lastChange
		
		days = int (dd.days/2)
		
		col = 255 - days
		if col < 0: col = 0
		
		css = "background-color:#ff%02x%02x" % (col,col)
		if col < 128:
			css += ";color:white"
			
		return css
			
	def _id(self):
		try:
			return self.key().id()
		except:
			return "new"
			
	id = property(_id)


class Post(db.Model):
	
	source        = db.ReferenceProperty(Source)
	title         = db.StringProperty(multiline=True)
	body          = db.TextProperty()
	link          = db.StringProperty()
	found         = db.DateTimeProperty(auto_now_add=True)
	created       = db.DateTimeProperty()
	guid          = db.StringProperty()
	author        = db.StringProperty()
	read          = db.BooleanProperty(required=True,default=False)

	def _id(self):
		try:
			return self.key().id()
		except:
			return "new"
			
	id = property(_id)
