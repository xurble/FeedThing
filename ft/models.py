from django.db import models

# Create your models here.

import time
import datetime
from urllib.parse import urlencode
import logging
import sys
from django.utils.timezone import utc

from django.conf import settings

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin

from django.contrib.auth.models import BaseUserManager
from django.utils import timezone

if settings.USE_FEEDS:
    from feeds.models import Post, Source, Enclosure

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
    
    def __str__(self):
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

        

# A user subscription
class Subscription(models.Model):
    user      = models.ForeignKey(User, on_delete=models.CASCADE)
    source    = models.ForeignKey(Source,blank=True,null=True, on_delete=models.CASCADE) # null source means we are a folder
    parent    = models.ForeignKey('self',blank=True,null=True, on_delete=models.CASCADE)
    last_read = models.IntegerField(default=0)
    is_river  = models.BooleanField(default=False)
    name      = models.CharField(max_length=255)
    
    def __str__(self):
        return "'%s' for user %s" % (self.name, self.user.email)

    @property
    def undread_count(self):
        if self.source:
            return self.source.max_index - self.last_read
        else:
            try:
                return self._undread_count 
            except:
                return -666
                

class SavedPost(models.Model):

    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    post         = models.ForeignKey(Post, on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, null=True, on_delete=models.CASCADE)
    
    date_saved = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_saved']
        unique_together = (("post", "user"),)
        
        
