from django.urls import path, include
from ft import views

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = [

    path('admin/', admin.site.urls),

    path('.well-known/<uri>', views.well_known_uris, name='well_known'),

    path('accounts/', include('allauth.urls')),

    path('', views.index, name="home"),
    path('refresh/', views.read_request_listener, name="refresh"),
    path('help/', views.help, name="help"),
    path('feeds/', views.feeds, name="feeds"),
    path('allfeeds/', views.allfeeds, name="allfeeds"),
    path('feeds/river/', views.user_river, name="userriver"),

    path('addfeed/', views.addfeed, name="addfeed"),
    path('importopml/', views.importopml),
    path('feedgarden/', views.feedgarden),

    path('downloadfeeds/', views.downloadfeeds),

    path('settings/', views.user_settings, name='settings'),

    path('read/<int:fid>/', views.readfeed),

    path('post/<int:pid>/save/', views.savepost, name="savepost"),
    path('post/<int:pid>/forget/', views.forgetpost, name="forgetpost"),

    path('saved/', views.savedposts, name="savedposts"),

    path('manage/', views.managefeeds, name="manage"),
    # path('subscription/list/', views.subscriptionlist),

    path('subscription/<int:sid>/unsubscribe/', views.unsubscribefeed),
    path('subscription/<int:sid>/details/', views.subscriptiondetails),
    path('subscription/<int:sid>/rename/', views.subscriptionrename),
    path('subscription/<int:sid>/promote/', views.promote),
    path('subscription/<int:sid>/addto/<int:tid>/', views.addto),

    path('feed/<int:fid>/revive/', views.revivefeed),
    # (r'^feed/<int:fid>/kill/',killfeed),
    path('feed/<int:fid>/test/', views.testfeed),

]
