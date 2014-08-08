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

from django.conf.urls import patterns, include, url
from django.views.generic import RedirectView
from django.views.decorators.cache import never_cache


# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # the api-s are not auto-discoverable
    url(r'^api/1.0/', include('bldviewer.api')),

    # Examples:
    # url(r'^toaster/', include('toaster.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),


    # if no application is selected, we have the magic toastergui app here
    url(r'^$', never_cache(RedirectView.as_view(url='/toastergui/'))),
)

import toastermain.settings
if toastermain.settings.MANAGED:
    urlpatterns = urlpatterns + [
        # Uncomment the next line to enable the admin:
        url(r'^admin/', include(admin.site.urls)),
    ]
# Automatically discover urls.py in various apps, beside our own
# and map module directories to the patterns

import os
currentdir = os.path.dirname(__file__)
for t in os.walk(os.path.dirname(currentdir)):
    if "urls.py" in t[2] and t[0] != currentdir:
        modulename = os.path.basename(t[0])
        urlpatterns.append( url(r'^' + modulename + '/', include ( modulename + '.urls')))
