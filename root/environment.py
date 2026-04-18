from django.templatetags.static import static
from django.urls import reverse
from django.utils import translation
from jinja2 import Environment

def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': static,
        'url': reverse,
    })
    env.install_gettext_translations(translation, newstyle=False)
    return env
