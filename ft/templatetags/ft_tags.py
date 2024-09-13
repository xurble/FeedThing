from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="hoursmins")
def hoursmins(value):
    if value is None or value == "":
        return ""

    s = int(value) * 60

    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)

    return "%d:%02d" % (hours, minutes)


@register.filter(name="river")
def river(value):
    ret = ""
    parts = value.split("<")
    for part in parts:
        if ">" in part:
            # Guardian sub-head in feed fixer :)
            if part == "/p>" and not ret.strip()[-1:] in ".,\"'!?:;…)]}&*>":
                ret = ret.strip() + ". "
            ret += "".join(part.split(">")[1:])
        else:
            ret += part
        ret += " "

    if len(ret) > 500:
        ret = ret[:500]
        ret = ret[: ret.rfind(" ")] + "&hellip;"

    return mark_safe(ret)


@register.filter(name="subscription_name")
def subscription_name(post, subscription_map):
    return subscription_map[post.source.id]


@register.filter(name="fix_body")
def fix_body(body):
    body = body.replace(
        "<iframe",
        "<iframe allowfullscreen frameborder='0' sandbox='allow-same-origin allow-scripts' ",
    )
    if "<iframe" in body:
        # not today youtube!
        body = body.replace("autoplay=1", "")
    body = body.replace("<img", "<img onerror='imgError(this);' ")

    return mark_safe(body)


@register.filter(name="starstyle")
def starstyle(post, user):
    if post.savedpost_set.filter(user=user).count() > 0:
        return "fas"
    else:
        return "far"
