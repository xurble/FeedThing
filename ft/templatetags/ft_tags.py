from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='hoursmins')
def hoursmins(value):
  
    if value == None or value == "":
        return ""
    
    s = int(value) * 60
    
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return "%d:%02d" % (hours,minutes)
    
    
    
@register.filter(name='river')
def river(value):

    ret = ""
    parts = value.split("<")
    for part in parts:
        if ">" in part:
            ret += "".join(part.split(">")[1:])
        else:
            ret += part

    if len(ret) > 500:
        ret = ret[:500] 
        ret = ret[:ret.rfind(" ")] + " ..."

    return mark_safe(ret)
    
    
@register.filter(name='subscription_name')
def subscription_name(post, subscription_map):
    return subscription_map[post.source.id]
