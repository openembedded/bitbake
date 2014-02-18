#
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Toaster Implementation
#
# Copyright (C) 2013        Intel Corporation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from datetime import datetime, timedelta
import re
from django import template
from django.utils import timezone
from django.template.defaultfilters import filesizeformat

register = template.Library()

@register.simple_tag
def time_difference(start_time, end_time):
    return end_time - start_time

@register.filter(name = 'sectohms')
def sectohms(time):
    try:
        tdsec = int(time)
    except ValueError:
        tdsec = 0
    hours = int(tdsec / 3600)
    return "%02d:%02d:%02d" % (hours, int((tdsec - (hours * 3600))/ 60), int(tdsec) % 60)

@register.assignment_tag
def query(qs, **kwargs):
    """ template tag which allows queryset filtering. Usage:
          {% query books author=author as mybooks %}
          {% for book in mybooks %}
            ...
          {% endfor %}
    """
    return qs.filter(**kwargs)

@register.filter
def divide(value, arg):
    if int(arg) == 0:
        return -1
    return int(value) / int(arg)

@register.filter
def multiply(value, arg):
    return int(value) * int(arg)

@register.assignment_tag
def datecompute(delta, start = timezone.now()):
    return start + timedelta(delta)


@register.filter(name = 'sortcols')
def sortcols(tablecols):
    return sorted(tablecols, key = lambda t: t['name'])

@register.filter
def task_color(task_object, show_green=False):
    """ Return css class depending on Task execution status and execution outcome.
        By default, green is not returned for executed and successful tasks;
        show_green argument should be True to get green color.
    """
    if not task_object.task_executed:
        return 'class=muted'
    elif task_object.outcome == task_object.OUTCOME_FAILED:
        return 'class=error'
    elif task_object.outcome == task_object.OUTCOME_SUCCESS and show_green:
        return 'class=green'
    else:
        return ''

@register.filter
def filtered_icon(options, filter):
    """Returns btn-primary if the filter matches one of the filter options
    """
    for option in options:
        if filter == option[1]:
            return "btn-primary"
    return ""

@register.filter
def filtered_tooltip(options, filter):
    """Returns tooltip for the filter icon if the filter matches one of the filter options
    """
    for option in options:
        if filter == option[1]:
            return "Showing only %s"%option[0]
    return ""

@register.filter
def format_none_and_zero(value):
    """Return empty string if the value is None, zero or Not Applicable
    """
    return "" if (not value) or (value == 0) or (value == "0") or (value == 'Not Applicable') else value

@register.filter
def filtered_filesizeformat(value):
    """Change output from fileformatsize to suppress trailing '.0' and change 'bytes' to 'B'
    """
    return filesizeformat(value).replace("bytes", "B").replace(".0", "")

@register.filter
def filtered_packagespec(value):
    """Strip off empty version and revision"""
    return re.sub(r'(--$)', '', value)

@register.filter
def check_filter_status(options, filter):
    """Check if the active filter is among the available options, and return 'checked'
       if filter is not active.
       Used in FilterDialog to select the first radio button if the filter is not active.
    """
    for option in options:
        if filter == option[1]:
            return ""
    return "checked"
