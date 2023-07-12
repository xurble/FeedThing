from django.urls import path, include

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()


from ft.views import *

urlpatterns = [

    path('admin/', admin.site.urls),

    path('.well-known/<uri>', well_known_uris, name='well_known'),


    path('', index, name="home"),
    path('refresh/', read_request_listener, name="refresh"),
    path('help/', help, name="help"),
    path('feeds/', feeds, name="feeds"),
    path('allfeeds/', allfeeds, name="allfeeds"),

    path('addfeed/', addfeed, name="addfeed"),
    path('importopml/', importopml),
    path('feedgarden/', feedgarden),

    path('downloadfeeds/', downloadfeeds),

    path('settings/', user_settings, name='settings'),

    path('accounts/', include('django.contrib.auth.urls')),
    

    path('read/<int:fid>/', readfeed),

    path('post/<int:pid>/save/',savepost, name="savepost"),
    path('post/<int:pid>/forget/',forgetpost, name="forgetpost"),

    path('saved/',savedposts, name="savedposts"),
    


    path('manage/',managefeeds),
    path('subscription/list/',subscriptionlist),
    
    path('subscription/<int:sid>/unsubscribe/',unsubscribefeed),
    path('subscription/<int:sid>/details/',subscriptiondetails),
    path('subscription/<int:sid>/rename/',subscriptionrename),
    path('subscription/<int:sid>/promote/',promote),
    path('subscription/<int:sid>/addto/<int:tid>/',addto),


    path('feed/<int:fid>/revive/',revivefeed),
    #(r'^feed/<int:fid>/kill/',killfeed),
    path('feed/<int:fid>/test/',testfeed),
    
]
