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

urlpatterns = patterns('bldviewer.views',
        url(r'^builds/$', 'build', name='simple-all-builds'),
        url(r'^build/(?P<build_id>\d+)/task/$', 'task', name='simple-task'),
        url(r'^build/(?P<build_id>\d+)/packages/$', 'bpackage', name='simple-bpackage'),
        url(r'^build/(?P<build_id>\d+)/package/(?P<package_id>\d+)/files/$', 'bfile', name='simple-bfile'),
        url(r'^build/(?P<build_id>\d+)/target/(?P<target_id>\d+)/packages/$', 'tpackage', name='simple-tpackage'),
        url(r'^build/(?P<build_id>\d+)/configuration/$', 'configuration', name='simple-configuration'),
        url(r'^layers/$', 'layer', name='simple-all-layers'),
        url(r'^layerversions/(?P<layerversion_id>\d+)/recipes/.*$', 'layer_versions_recipes', name='simple-layer_versions_recipes'),
        url(r'^$', RedirectView.as_view( url= 'builds/')),
)
