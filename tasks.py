


from google.appengine.ext import webapp
from google.appengine.ext import deferred
from google.appengine.runtime import DeadlineExceededError
from google.appengine.ext.webapp import template

from model import *

import logging



		
class TaskThing(object):		
		
	def DeleteFeed(self,fid):


		feed = Source.get_by_id(int(fid))
		
		posts = Post.gql("WHERE source = :1",feed)
		
	
		
		if posts.count() == 0:
			feed.delete()
			return
		try:
			for p in posts:
				p.delete()
		except DeadlineExceededError:
			#didn't manage to finish (can't imagine this happening)
			logging.info("Deadline exceeded")
			pass
			
		logging.info("Rescheduling feed delete")
		deferred.defer(self.DeleteFeed,fid) 
		
	
		
	def MarkRead(self,posts):		
		logging.info(posts)
		
		try:
			while len(posts) > 0:
				p = posts.pop()
				p.read = True
				p.put()
			return
		except DeadlineExceededError:
			#didn't manage to finish (can't imagine this happening)
			logging.info("MarkRead: Deadline exceeded")
			pass
			
		deferred.defer(self.MarkRead,posts) 
