
import os

SITE_ROOT = os.path.dirname(os.path.realpath(__file__))


ALLOWED_HOSTS = ['localhost'] # change this to your servers domain

FEEDS_SERVER = 'https://example.com/' # change this to where you are running  -  it's in the user agent string used when polling sites
FEEDS_CLOUDFLARE_WORKER = None   # You will need a cloudflare account with the django-feed-reader cloudflare worker installed to use this setting



# this is where collectstatic will gather its files
STATIC_ROOT = os.path.join(SITE_ROOT, "..", "static")

DEBUG = False # or true if you are running locally

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'feedthing',                      # Or path to database file if using sqlite3.
        'USER': 'auser',                      # Not used with sqlite3.
        'PASSWORD': 'apassword',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
        'OPTIONS': {
                 'init_command': 'SET default_storage_engine=INNODB',
              }        
  }
}
    
# Make this unique, and don't share it with anybody.
SECRET_KEY = 'BigLongStringOfCharactersHere'
