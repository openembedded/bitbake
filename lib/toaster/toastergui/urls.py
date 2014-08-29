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

urlpatterns = patterns('toastergui.views',
        # landing page
        url(r'^builds/$', 'builds', name='all-builds'),
        # build info navigation
        url(r'^build/(?P<build_id>\d+)$', 'builddashboard', name="builddashboard"),

        url(r'^build/(?P<build_id>\d+)/tasks/$', 'tasks', name='tasks'),
        url(r'^build/(?P<build_id>\d+)/tasks/(?P<task_id>\d+)/$', 'tasks_task', name='tasks_task'),
        url(r'^build/(?P<build_id>\d+)/task/(?P<task_id>\d+)$', 'task', name='task'),

        url(r'^build/(?P<build_id>\d+)/recipes/$', 'recipes', name='recipes'),
        url(r'^build/(?P<build_id>\d+)/recipe/(?P<recipe_id>\d+)$', 'recipe', name='recipe'),

        url(r'^build/(?P<build_id>\d+)/packages/$', 'bpackage', name='packages'),
        url(r'^build/(?P<build_id>\d+)/package/(?P<package_id>\d+)$', 'package_built_detail',
                name='package_built_detail'),
        url(r'^build/(?P<build_id>\d+)/package_built_dependencies/(?P<package_id>\d+)$',
            'package_built_dependencies', name='package_built_dependencies'),
        url(r'^build/(?P<build_id>\d+)/package_included_detail/(?P<target_id>\d+)/(?P<package_id>\d+)$',
            'package_included_detail', name='package_included_detail'),
        url(r'^build/(?P<build_id>\d+)/package_included_dependencies/(?P<target_id>\d+)/(?P<package_id>\d+)$',
            'package_included_dependencies', name='package_included_dependencies'),
        url(r'^build/(?P<build_id>\d+)/package_included_reverse_dependencies/(?P<target_id>\d+)/(?P<package_id>\d+)$',
            'package_included_reverse_dependencies', name='package_included_reverse_dependencies'),

        # images are known as targets in the internal model
        url(r'^build/(?P<build_id>\d+)/target/(?P<target_id>\d+)$', 'target', name='target'),
        url(r'^build/(?P<build_id>\d+)/target/(?P<target_id>\d+)/targetpkg$', 'targetpkg', name='targetpkg'),
        url(r'^dentries/build/(?P<build_id>\d+)/target/(?P<target_id>\d+)$', 'dirinfo_ajax', name='dirinfo_ajax'),
        url(r'^build/(?P<build_id>\d+)/target/(?P<target_id>\d+)/dirinfo$', 'dirinfo', name='dirinfo'),
        url(r'^build/(?P<build_id>\d+)/target/(?P<target_id>\d+)/dirinfo_filepath/(?P<file_path>(?:/[^/\n]+)*)$', 'dirinfo', name='dirinfo_filepath'),
        url(r'^build/(?P<build_id>\d+)/target/(?P<target_id>\d+)/packages$', 'tpackage', name='targetpackages'),
        url(r'^build/(?P<build_id>\d+)/configuration$', 'configuration', name='configuration'),
        url(r'^build/(?P<build_id>\d+)/configvars$', 'configvars', name='configvars'),
        url(r'^build/(?P<build_id>\d+)/buildtime$', 'buildtime', name='buildtime'),
        url(r'^build/(?P<build_id>\d+)/cpuusage$', 'cpuusage', name='cpuusage'),
        url(r'^build/(?P<build_id>\d+)/diskio$', 'diskio', name='diskio'),

        # image information dir - not yet implemented
        url(r'^build/(?P<build_id>\d+)/target/(?P<target_id>\d+)/packagefile/(?P<packagefile_id>\d+)$',
             'image_information_dir', name='image_information_dir'),


        # urls not linked from the dashboard
        url(r'^layerversions/(?P<layerversion_id>\d+)/recipes/.*$', 'layer_versions_recipes', name='layer_versions_recipes'),

        # project URLs
        url(r'^newproject/$', 'newproject', name='newproject'),
        url(r'^importlayer/$', 'importlayer', name='importlayer'),

        url(r'^layers/$', 'layers', name='layers'),
        url(r'^layer/(?P<layerid>\d+)/$', 'layerdetails', name='layerdetails'),
        url(r'^targets/$', 'targets', name='targets'),
        url(r'^machines/$', 'machines', name='machines'),

        url(r'^project/(?P<pid>\d+)/$', 'project', name='project'),
        url(r'^project/(?P<pid>\d+)/configuration$', 'projectconf', name='projectconf'),
        url(r'^project/(?P<pid>\d+)/builds$', 'projectbuilds', name='projectbuilds'),

        url(r'^xhr_projectbuild/(?P<pid>\d+)/$', 'xhr_projectbuild', name='xhr_projectbuild'),
        url(r'^xhr_projectedit/(?P<pid>\d+)/$', 'xhr_projectedit', name='xhr_projectedit'),


        # default redirection
        url(r'^$', RedirectView.as_view( url= 'builds/')),
)
