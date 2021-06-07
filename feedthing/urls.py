from django.urls import path, include
from django.conf.urls import url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()


from ft.views import *

urlpatterns = [

    path('admin/', admin.site.urls),

    path('.well-known/<uri>', well_known_uris, name='well_known'),


    url(r'^$', index, name="home"),
    url(r'^refresh/$', read_request_listener, name="refresh"),
    url(r'^help/$', help, name="help"),
    url(r'^feeds/$', feeds, name="feeds"),
    url(r'^allfeeds/$', allfeeds, name="allfeeds"),

    url(r'^addfeed/$', addfeed, name="addfeed"),
    url(r'^importopml/$', importopml),
    url(r'^feedgarden/$', feedgarden),

    url(r'^downloadfeeds/$', downloadfeeds),

    path('settings/', user_settings, name='settings'),

    path('accounts/', include('django.contrib.auth.urls')),
    

    url(r'^read/(?P<fid>.*)/', readfeed),

    url(r'^post/(?P<pid>.*)/save/$',savepost, name="savepost"),
    url(r'^post/(?P<pid>.*)/forget/$',forgetpost, name="forgetpost"),

    url(r'^saved/$',savedposts, name="savedposts"),
    


    url(r'^manage/$',managefeeds),
    url(r'^subscription/list/$',subscriptionlist),
    
    url(r'^subscription/(?P<sid>.*)/unsubscribe/$',unsubscribefeed),
    url(r'^subscription/(?P<sid>.*)/details/$',subscriptiondetails),
    url(r'^subscription/(?P<sid>.*)/rename/$',subscriptionrename),
    url(r'^subscription/(?P<sid>.*)/promote/$',promote),
    url(r'^subscription/(?P<sid>.*)/addto/(?P<tid>.*)/$',addto),


    url(r'^feed/(?P<fid>.*)/revive/$',revivefeed),
    #(r'^feed/(?P<fid>.*)/kill/$',killfeed),
    url(r'^feed/(?P<fid>.*)/test/$',testfeed),
    
]
