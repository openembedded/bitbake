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

from datetime import datetime
from django import template

register = template.Library()

@register.simple_tag
def time_difference(start_time, end_time):
    return end_time - start_time

@register.filter(name = 'timespent')
def timespent(build_object):
    tdsec = (build_object.completed_on - build_object.started_on).total_seconds()
    return "%02d:%02d:%02d" % (int(tdsec/3600), int((tdsec - tdsec/ 3600)/ 60), int(tdsec) % 60)

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
    return int(value) / int(arg)

@register.filter
def multiply(value, arg):
    return int(value) * int(arg)
