from django import template
from django.utils.translation import get_language
from django.templatetags.static import static

register = template.Library()

@register.simple_tag
def pdf_url(name):
    lang = get_language() or 'uz'
    lang_code = lang.split('-')[0]
    return static(f'docs/{name}_{lang_code}.pdf')