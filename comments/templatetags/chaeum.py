from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# 24x24 선(stroke) 아이콘 경로 모음
ICONS = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "home": '<path d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H5a1 1 0 0 1-1-1z"/>',
    "collapse": '<path d="m11 17-5-5 5-5M18 17l-5-5 5-5"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "send": '<path d="M12 19V5M5.5 11.5 12 5l6.5 6.5"/>',
    "external": '<path d="M14 4h6v6M10 14 20 4M19 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4"/>',
    "braces": '<path d="M8 4H7a2 2 0 0 0-2 2v4a2 2 0 0 1-2 2 2 2 0 0 1 2 2v4a2 2 0 0 0 2 2h1'
              'M16 4h1a2 2 0 0 1 2 2v4a2 2 0 0 0 2 2 2 2 0 0 0-2 2v4a2 2 0 0 1-2 2h-1"/>',
    "database": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6'
                'M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
    "sparkles": '<path d="M11 3c.6 4.4 2.6 6.4 7 7-4.4.6-6.4 2.6-7 7-.6-4.4-2.6-6.4-7-7 4.4-.6 6.4-2.6 7-7z"/>'
                '<path d="M19 15.5c.3 1.6 1 2.2 2.5 2.5-1.5.3-2.2 1-2.5 2.5-.3-1.5-1-2.2-2.5-2.5 1.5-.3 2.2-1 2.5-2.5z"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "chart": '<path d="M4 4v16h16"/><path d="m8 15 3.5-4 3 3L20 7"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "layers": '<path d="m12 4 8.5 4.5L12 13 3.5 8.5z"/><path d="m3.5 12.5 8.5 4.5 8.5-4.5"/>',
    "status": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/>',
    "alert": '<path d="M12 4 3 19.5h18z"/><path d="M12 10v4M12 17v.01"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/>'
            '<path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "board": '<rect x="3.5" y="4" width="5" height="16" rx="1.5"/><rect x="10.5" y="4" width="5" height="11" rx="1.5"/>'
             '<rect x="17.5" y="4" width="3" height="7" rx="1.5"/>',
    "compare": '<path d="M7 4 3 8l4 4M3 8h13M17 12l4 4-4 4M21 16H8"/>',
}


@register.simple_tag
def icon(name, size=16):
    """{% icon 'search' %} -> 인라인 SVG 아이콘"""
    return format_html(
        '<svg class="icon" width="{}" height="{}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>',
        size, size, mark_safe(ICONS[name]),
    )
