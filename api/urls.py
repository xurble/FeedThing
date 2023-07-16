from django.urls import include, path
from rest_framework import routers
from api import views



urlpatterns = [

    path('subscriptions/', views.SubscriptionListView.as_view()),
    path('subscriptions/<int:pk>/', views.SubscriptionView.as_view()),  
    path('subscriptions/<int:pk>/unread/', views.UnreadPostsView.as_view()), 
    path('subscriptions/<int:pk>/posts/', views.PostsListView.as_view()), 
    
]
