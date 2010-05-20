
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

	def _id(self):
		try:
			return self.key().id()
		except:
			return "new"
			
	id = property(_id)


class Post(db.Model):
	
	source        = db.ReferenceProperty(Source)
	title         = db.StringProperty()
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
