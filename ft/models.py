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
            
        
class WebProxy(models.Model):
    # this class if for Cloudflare avoidance and contains a list of potential
    # web proxies that we can try, scraped from the internet
    address = models.CharField(max_length=255)
    

class Source(models.Model):
    # This is an actual feed that we poll
    name          = models.CharField(max_length=255,blank=True,null=True)
    site_url      = models.CharField(max_length=255,blank=True,null=True)
    feed_url      = models.CharField(max_length=255)
    last_polled   = models.DateTimeField(max_length=255,blank=True,null=True)
    due_poll      = models.DateTimeField()
    etag          = models.CharField(max_length=255,blank=True,null=True)
    last_modified = models.CharField(max_length=255,blank=True,null=True) # just pass this back and forward between server and me , no need to parse
    
    last_result   = models.CharField(max_length=255,blank=True,null=True)
    interval      = models.PositiveIntegerField(default=400)
    last_success  = models.DateTimeField(null=True)
    last_change   = models.DateTimeField(null=True)
    live          = models.BooleanField(default=True)
    status_code   = models.PositiveIntegerField(default=0)
    last302url    = models.CharField(max_length=255,default = " ")
    last302start  = models.DateTimeField(auto_now_add=True)
    
    max_index     = models.IntegerField(default=0)
    
    num_subs      = models.IntegerField(default=1)
    
    needs_proxy   = models.BooleanField(default=False)
    
    
    def __unicode__(self):
        return self.display_name
    
    @property
    def best_link(self):
        #the html link else hte feed link
        if self.site_url == None or self.site_url == '':
            return self.feed_url
        else:
            return self.site_url

    @property
    def display_name(self):
        if self.name == None or self.name == "":
            return self.best_link
        else:
            return self.name
    
    @property
    def garden_style(self):
        
        
        
        if not self.live:
            css="background-color:#ccc;"
        elif self.last_change == None or self.last_success == None:
            css="background-color:#D00;color:white"
        else:
            dd = datetime.datetime.utcnow().replace(tzinfo=utc) - self.last_change
            
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
        elif self.last_change == None or self.last_success == None:
            css="#F00;"
        else:
            dd = datetime.datetime.utcnow().replace(tzinfo=utc) - self.last_change
            
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
    user      = models.ForeignKey(User)
    source    = models.ForeignKey(Source,blank=True,null=True) # null source means we are a folder
    parent    = models.ForeignKey('self',blank=True,null=True)
    last_read = models.IntegerField(default=0)
    is_river  = models.BooleanField(default=False)
    name      = models.CharField(max_length=255)
    
    def __unicode__(self):
        return u"'%s' for user %s" % (self.name, self.user.email)

    @property
    def undread_count(self):
        if self.source:
            return self.source.max_index - self.last_read
        else:
            try:
                return self._undread_count 
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
        
    
    def __unicode__(self):
        return "%s: post %d, %s" % (self.source.display_name,self.index,self.title)


class SavedPost(models.Model):

    user         = models.ForeignKey(User)
    post         = models.ForeignKey(Post)
    subscription = models.ForeignKey(Subscription, null=True)
    
    date_saved = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_saved']
        unique_together = (("post", "user"),)