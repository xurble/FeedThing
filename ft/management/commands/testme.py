
from django.core.management.base import BaseCommand, CommandError

from feeds.utils import read_feed
from feeds.models import Source

class Command(BaseCommand):
    help = 'For testing'

    def handle(self, *args, **options):


        src = Source(name="Test", feed_url="https://blog.pint.org.uk/feeds/posts/default?alt=rss", interval=0)

        src.save()
        import pdb; pdb.set_trace()
        read_feed(src)    

        
        