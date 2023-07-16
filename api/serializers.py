

from ft.models import Subscription
from feeds.models import Post, Enclosure
from rest_framework import serializers


class SubscriptionSerializer(serializers.HyperlinkedModelSerializer):

    source_id = serializers.IntegerField()
    source_url = serializers.CharField(source='source.feed_url', read_only=True)
    site_url = serializers.CharField(source='source.site_url', read_only=True)
    entries  = serializers.IntegerField(source='source.max_index', read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "name", "source_id", "source_url", "site_url", "is_river", "entries", "last_read"]
        
        
class EnclosureSerializer(serializers.HyperlinkedModelSerializer):
    
    class Meta:
        model = Enclosure
        fields = ["id", "href", "type"]
                

class PostSerializer(serializers.HyperlinkedModelSerializer):

    enclosures = EnclosureSerializer(many=True, read_only=True)
    
    class Meta:
        model = Post
        fields = ["id", "title", "body", "link", "created", "index", "image_url", "enclosures"]
        
        
