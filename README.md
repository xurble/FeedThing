FeedThing
=========

FeedThing is a django-based feed reader.  I created it when Bloglines was shutting down because I didn't like Google Reader and then of course that shut down anyway.

FeedThing supports all common feed flavours - RSS, Atom and JSON Feed.  It works just as well on mobile as on desktop browsers.

FeedThing treats feeds in the specific manner that I believe to be right.  

- Regular (I want to read everything by this author) feeds are displayed with all the unread posts in *chronological* order.
- High traffic news feeds display all the posts in *reverse chronological* order, paginated 20 posts to a page.
- Regular feeds that have been read up to date display their old posts in *reverse chronological* order, paginated.
 
So you can use FeedThing as both a catch-up, never-miss-a-post service, and a Dave Winer-esque river of news _at the same time_.

Feeds can be placed into folders in which case all the feeds in the folder are treated as if they were a single feed.  There is no further nesting, folders are a single level deep.

A single FeedThing installation can support multiple users, each with their own settings and list of feeds.  Embarrassingly, there is no UI to create those users just now.

Altough I have used this as my daily feed reader for years, it is rather unfinished.  Specifically there are features that I feel a feed reader should have that are started but not really done, or done in a half-arsed way.

Enjoy.

Installation
============

FeedThing is a pretty simple Python 3 / Django 2.2 application.  There are a few external dependencies that need pip installing (listed in requirements.txt)

The django `settings.py` file  is not quite complete.  It imports some of its settings from `settings_server.py` which is listed in `.gitignore` because it is installation specific.  There is an example 

Once it is running, in order to keep it ticking over and reading feeds, something needs to keep hitting `/refresh/` or, better still, calling the management command `manage.py refreshfeeds`

I have that set up as a cron job every five minutes.  This is a cheesy way to work around the severe lameness of my current hosting.

If you were to run it on something sensible, you'd probably want to use Celery or similar.

User management is not done yet.  Make yourself a login using `manage.py createsuperuser`

And that's it.

