from django.db import models

# Create your models here.

import time
import datetime
from urllib import urlencode
import logging
import sys

class Source(models.Model):
    
    name          = models.CharField(max_length=255,blank=True,null=True)
    siteURL       = models.CharField(max_length=255,blank=True,null=True)
    feedURL       = models.CharField(max_length=255,blank=True,null=True)
    lastPolled    = models.DateTimeField(max_length=255,blank=True,null=True)
    duePoll       = models.DateTimeField(default=datetime.datetime.now)
    ETag          = models.CharField(max_length=255,blank=True,null=True)
    lastModified  = models.CharField(max_length=255,blank=True,null=True) # just pass this back and forward between server and me , no need to parse
    unreadCount   = models.PositiveIntegerField(default=0)
    lastResult    = models.CharField(max_length=255,blank=True,null=True)
    interval      = models.PositiveIntegerField(default=400)
    lastSuccess   = models.DateTimeField(null=True)
    lastChange    = models.DateTimeField(null=True)
    live          = models.BooleanField(default=True)
    status_code   = models.PositiveIntegerField(default=0)
    last302url    = models.CharField(max_length=255,default = " ")
    last302start  = models.DateTimeField(default=datetime.datetime.now)
    inRiver       = models.BooleanField(default=False)
    
    def __unicode__(self):
        return self.displayName()
    
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
        
        
        
        if not self.live:
            css="background-color:#ccc;"
        elif self.lastChange == None or self.lastSuccess == None:
            css="background-color:#D00;color:white"
        else:
            dd = datetime.datetime.now() - self.lastChange
            
            days = int (dd.days/2)
            
            col = 255 - days
            if col < 0: col = 0
            
            css = "background-color:#ff%02x%02x" % (col,col)
            if col < 128:
                css += ";color:white"
            
        return css
            



class Post(models.Model):
    
    source        = models.ForeignKey(Source)
    title         = models.TextField()
    body          = models.TextField()
    link          = models.CharField(max_length=255,blank=True,null=True)
    found         = models.DateTimeField(default=datetime.datetime.now)
    created       = models.DateTimeField(default=datetime.datetime.now)
    guid          = models.CharField(max_length=255,blank=True,null=True)
    author        = models.CharField(max_length=255,blank=True,null=True)
    read          = models.BooleanField(default=False)
    keep          = models.BooleanField(default=False)

    def _titleURLEncoded(self):
        logging.info("ENCODING:")
        logging.info(self.title)
        try:
            ret = urlencode({"X":self.title})
            if len(ret) > 2: ret = ret[2:]
        except:
            logging.info("Failed!")
            logging.info(sys.exc_info())
            ret = ""
        return ret
        
    titleURLEncoded = property(_titleURLEncoded)

