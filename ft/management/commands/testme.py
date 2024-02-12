
from django.core.management.base import BaseCommand, CommandError

from feeds.utils import read_feed
from feeds.models import Source
from feeds.models import Subscription as NewSubscription
from ft.models import Subscription as OldSubscription
from ft.models import SavedPost

class Command(BaseCommand):
    help = 'For testing'

    def handle(self, *args, **options):

        SavedPost.objects.all().delete()

        NewSubscription.objects.all().delete()

        old_subs = list(OldSubscription.objects.all())
        new_subs = []

        for o in old_subs:
            n = NewSubscription()
            n.user      = o.user
            n.source    = o.source
            #n.parent    = o.parent
            n.last_read = o.last_read
            n.is_river  = o.is_river
            n.name      = o.name
            n.save()
            n.old_id = o.id
            o.new_id = n.id
            new_subs.append(n)


        for o in old_subs:
            if o.parent_id is not None:
                new_parent = None
                new_child  = None
                for n in new_subs:
                    if n.old_id == o.parent_id:
                        new_parent = n
                    if n.id == o.new_id:
                        new_child = n
                assert new_parent and new_child
                new_child.parent = new_parent
                new_child.save()








