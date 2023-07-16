from rest_framework import generics

from ft.models import Subscription
from feeds.models import Post
from api.serializers import SubscriptionSerializer, PostSerializer
from rest_framework.pagination import PageNumberPagination


class PostsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class SubscriptionListView(generics.ListCreateAPIView):
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        """
        This view returns a list of all the subscriptions for the currently
        authenticated user.

        Returns empty list if user Anonymous
        """
        user = self.request.user

        if not user.is_anonymous:
            return Subscription.objects.filter(user=user)

        return Subscription.objects.none()
    
        
        
class SubscriptionView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        user = self.request.user

        if not user.is_anonymous:
            return Subscription.objects.filter(user=user)

        return Subscription.objects.none()
        
        
class UnreadPostsView(generics.ListAPIView):

    serializer_class = PostSerializer

    def get_queryset(self):
    
        user = self.request.user

        if not user.is_anonymous:
        
            sub = Subscription.objects.get(id=self.kwargs.get("pk"))
            
            if sub.user != user:
                return Post.objects.none()
        
            return Post.objects.filter(source=sub.source).filter(index__gt=sub.last_read)

        return Post.objects.none()
        


class PostsListView(generics.ListAPIView):

    serializer_class = PostSerializer
    pagination_class = PostsPagination

    def get_queryset(self):
    
        user = self.request.user

        if not user.is_anonymous:
        
            sub = Subscription.objects.get(id=self.kwargs.get("pk"))
            
            if sub.user != user:
                return Post.objects.none()
        
            return Post.objects.filter(source=sub.source).order_by("-index")

        return Post.objects.none()
        

