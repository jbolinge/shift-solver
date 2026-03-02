"""Custom template tags for the shift-solver web UI."""

from django import template
from django.utils.html import format_html

register = template.Library()

BADGE_COLORS = {
    "green": "bg-green-100 text-green-800",
    "red": "bg-red-100 text-red-800",
    "yellow": "bg-yellow-100 text-yellow-800",
    "blue": "bg-blue-100 text-blue-800",
    "gray": "bg-gray-100 text-gray-800",
    "indigo": "bg-indigo-100 text-indigo-800",
    "purple": "bg-purple-100 text-purple-800",
}


@register.simple_tag
def status_badge(text, color="gray"):
    """Render a styled status badge.

    Usage: {% status_badge "Active" "green" %}
    """
    classes = BADGE_COLORS.get(color, BADGE_COLORS["gray"])
    return format_html(
        '<span class="inline-flex items-center rounded-full px-2.5 py-0.5 '
        'text-xs font-medium {}">{}</span>',
        classes,
        text,
    )


@register.inclusion_tag("partials/_field.html")
def render_field(field):
    """Render a complete form field with label, widget, help text, and errors.

    Usage: {% render_field form.name %}
    """
    return {"field": field}
