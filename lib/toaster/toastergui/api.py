#
# BitBake Toaster Implementation
#
# Copyright (C) 2016        Intel Corporation
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


# Temporary home for the UI's misc API

from orm.models import Project, ProjectTarget
from bldcontrol.models import BuildRequest
from bldcontrol import bbcontroller
from django.http import HttpResponse, JsonResponse
from django.views.generic import View


class XhrBuildRequest(View):

    def get(self, request, *args, **kwargs):
        return HttpResponse()

    def post(self, request, *args, **kwargs):
        """ Process HTTP POSTs which make build requests """

        project = Project.objects.get(pk=kwargs['pid'])

        if 'buildCancel' in request.POST:
            for i in request.POST['buildCancel'].strip().split(" "):
                try:
                    br = BuildRequest.objects.select_for_update().get(project = project, pk = i, state__lte = BuildRequest.REQ_QUEUED)
                    br.state = BuildRequest.REQ_DELETED
                    br.save()
                except BuildRequest.DoesNotExist:
                    pass

        if 'buildDelete' in request.POST:
            for i in request.POST['buildDelete'].strip().split(" "):
                try:
                    BuildRequest.objects.select_for_update().get(project = project, pk = i, state__lte = BuildRequest.REQ_DELETED).delete()
                except BuildRequest.DoesNotExist:
                    pass

        if 'targets' in request.POST:
            ProjectTarget.objects.filter(project = project).delete()
            s = str(request.POST['targets'])
            for t in s.translate(None, ";%|\"").split(" "):
                if ":" in t:
                    target, task = t.split(":")
                else:
                    target = t
                    task = ""
                ProjectTarget.objects.create(project = project,
                                             target = target,
                                             task = task)
            project.schedule_build()

        # redirect back to builds page so any new builds in progress etc.
        # are visible
        response = HttpResponse()
        response.status_code = 302
        response['Location'] = request.build_absolute_uri()
        return response
