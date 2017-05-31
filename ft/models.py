from django.db import models

# Create your models here.

import time
import datetime
from urllib import urlencode
import logging
import sys
from django.utils.timezone import utc



from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin

from django.contrib.auth.models import BaseUserManager
from django.utils import timezone

class FTUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        today = timezone.now()

        if not email:
            raise ValueError('The given email address must be set')

        email = FTUserManager.normalize_email(email)
        user  = self.model(email=email,
                          is_staff=False, is_active=True, **extra_fields)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        u = self.create_user(email, password, **extra_fields)
        u.is_staff = True
        u.is_active = True
        u.is_superuser = True
        u.save(using=self._db)
        return u


class User(AbstractBaseUser, PermissionsMixin):

    email       = models.EmailField(unique=True, blank=False)
    name        = models.CharField(max_length=128, verbose_name="Full Name")
    salutation  = models.CharField(max_length=128, null=True,blank=True, verbose_name="What should we call you?")


    is_active   = models.BooleanField(default=True)
    is_admin    = models.BooleanField(default=False)
    is_staff    = models.BooleanField(default=False)
    

    USERNAME_FIELD = 'email'

    objects = FTUserManager()
    
    def __unicode__(self):
        return self.name
    
    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        if self.salutation is None:
            return self.name
        else:
            return self.salutation
            
        



class Source(models.Model):
    # This is an actual feed that we poll
    name          = models.CharField(max_length=255,blank=True,null=True)
    siteURL       = models.CharField(max_length=255,blank=True,null=True)
    feedURL       = models.CharField(max_length=255)
    lastPolled    = models.DateTimeField(max_length=255,blank=True,null=True)
    duePoll       = models.DateTimeField()
    ETag          = models.CharField(max_length=255,blank=True,null=True)
    lastModified  = models.CharField(max_length=255,blank=True,null=True) # just pass this back and forward between server and me , no need to parse
    
    lastResult    = models.CharField(max_length=255,blank=True,null=True)
    interval      = models.PositiveIntegerField(default=400)
    lastSuccess   = models.DateTimeField(null=True)
    lastChange    = models.DateTimeField(null=True)
    live          = models.BooleanField(default=True)
    status_code   = models.PositiveIntegerField(default=0)
    last302url    = models.CharField(max_length=255,default = " ")
    last302start  = models.DateTimeField(auto_now_add=True)
    
    maxIndex      = models.IntegerField(default=0)
    
    num_subs      = models.IntegerField(default=1)
    
    
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
            dd = datetime.datetime.utcnow().replace(tzinfo=utc) - self.lastChange
            
            days = int (dd.days/2)
            
            col = 255 - days
            if col < 0: col = 0
            
            css = "background-color:#ff%02x%02x" % (col,col)
            if col < 128:
                css += ";color:white"
            
        return css
        
    def healthBox(self):
        
        if not self.live:
            css="#ccc;"
        elif self.lastChange == None or self.lastSuccess == None:
            css="#F00;"
        else:
            dd = datetime.datetime.utcnow().replace(tzinfo=utc) - self.lastChange
            
            days = int (dd.days/2)
            
            red = days
            if red > 255:
                red = 255
            
            green = 255-days;
            if green < 0:
                green = 0
            
            css = "#%02x%02x00" % (red,green)
            
        return css
            

# A user subscription
class Subscription(models.Model):
    user     = models.ForeignKey(User)
    source   = models.ForeignKey(Source,blank=True,null=True) # null source means we are a folder
    parent   = models.ForeignKey('self',blank=True,null=True)
    lastRead = models.IntegerField(default=0)
    isRiver  = models.BooleanField(default=False)
    name     = models.CharField(max_length=255)
    
    def __unicode__(self):
        return u"'%s' for user %s" % (self.name, self.user.email)

    def unreadCount(self):
        if self.source:
            return self.source.maxIndex - self.lastRead
        else:
            try:
                return self._unreadCount 
            except:
                return -666
                
class Post(models.Model):
    
    source        = models.ForeignKey(Source,db_index=True)
    title         = models.TextField(blank=True)
    body          = models.TextField()
    link          = models.CharField(max_length=512,blank=True,null=True)
    found         = models.DateTimeField()
    created       = models.DateTimeField(db_index=True)
    guid          = models.CharField(max_length=255,blank=True,null=True,db_index=True)
    author        = models.CharField(max_length=255,blank=True,null=True)
    index         = models.IntegerField(db_index=True)

    def _titleURLEncoded(self):
        try:
            ret = urlencode({"X":self.title})
            if len(ret) > 2: ret = ret[2:]
        except:
            logging.info("Failed!")
            logging.info(sys.exc_info())
            ret = ""
        return ret
        
    titleURLEncoded = property(_titleURLEncoded)
    
    def __unicode__(self):
        return "%s: post %d, %s" % (self.source.displayName(),self.index,self.title)
