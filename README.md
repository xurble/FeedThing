FeedThing
=========

FeedThing is a django-based feed reader.  

FeedThing supports all common feed flavours - RSS, Atom and JSON Feed.

A single FeedThing installation can support multiple users, although there isn't actually a way to create new users just now.

Installation
============

FeedThing is a pretty simple django (1.11) application.  There are a few external dependencies that need pip installing (listed in requirements.txt)

Once it is running, in order to keep it ticking over and reading feeds, something needs to keep hitting /refresh/

I have that set up as a cron job using curl that fires every five minutes.  This is a cheesy way to work around the severe lameness of my current hosting.

If you were to run it on something sensible, you'd probably want to use Celery or similar.

User management is not done yet.  Make yourself a login using manage.py createsuperuser

And that's it.

