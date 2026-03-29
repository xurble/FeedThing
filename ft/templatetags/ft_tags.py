import nh3
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

BODY_ALLOWED_TAGS = {
    "a", "abbr", "acronym", "address", "article", "aside",
    "audio", "b", "big", "blockquote", "br", "caption", "center",
    "cite", "code", "col", "colgroup", "dd", "del", "details",
    "dfn", "div", "dl", "dt", "em", "figcaption", "figure",
    "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr",
    "i", "iframe", "img", "ins", "kbd", "li", "mark", "nav",
    "ol", "p", "picture", "pre", "q", "s", "samp", "section",
    "small", "source", "span", "strong", "sub", "summary", "sup",
    "table", "tbody", "td", "tfoot", "th", "thead", "time", "tr",
    "tt", "u", "ul", "var", "video",
}

BODY_ALLOWED_ATTRIBUTES = {
    "*": {"class", "id", "title", "lang", "dir"},
    "a": {"href", "hreflang"},
    "img": {"src", "alt", "loading"},
    "iframe": {"src", "sandbox", "allowfullscreen", "frameborder"},
    "video": {"src", "controls", "preload", "poster"},
    "audio": {"src", "controls", "preload"},
    "source": {"src", "type"},
    "blockquote": {"cite"},
    "q": {"cite"},
    "ol": {"start", "type"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "col": {"span"},
    "colgroup": {"span"},
    "del": {"cite", "datetime"},
    "ins": {"cite", "datetime"},
    "time": {"datetime"},
}

TITLE_ALLOWED_TAGS = {"b", "i", "em", "strong", "code", "span", "sub", "sup"}

TITLE_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {}


def _sanitize_body(html):
    return nh3.clean(
        html,
        tags=BODY_ALLOWED_TAGS,
        attributes=BODY_ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
    )


def _sanitize_title(html):
    return nh3.clean(
        html,
        tags=TITLE_ALLOWED_TAGS,
        attributes=TITLE_ALLOWED_ATTRIBUTES,
    )


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
    text = nh3.clean(value, tags=set())

    if len(text) > 500:
        text = text[:500]
        space = text.rfind(" ")
        if space > 0:
            text = text[:space]
        text += "\u2026"

    return text


@register.filter(name="subscription_name")
def subscription_name(post, subscription_map):
    return subscription_map[post.source.id]


@register.filter(name="fix_body")
def fix_body(body):
    body = _sanitize_body(body)

    body = body.replace(
        "<iframe",
        "<iframe allowfullscreen frameborder='0' sandbox='allow-scripts' ",
    )
    if "<iframe" in body:
        body = body.replace("autoplay=1", "")
    body = body.replace("<img", "<img onerror='imgError(this);' ")

    return mark_safe(body)


@register.filter(name="safe_title")
def safe_title(value):
    return mark_safe(_sanitize_title(value))


@register.filter(name="starstyle")
def starstyle(post, user):
    if post.savedpost_set.filter(user=user).count() > 0:
        return "fas"
    else:
        return "far"
