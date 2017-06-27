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

    value = value.replace("<img", "<!")
    
    if len(value) > 500:
        value = value[:500] + " ..."


    return mark_safe(value)