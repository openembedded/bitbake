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
import re

from orm.models import Project, ProjectTarget, Build, Layer_Version
from orm.models import LayerVersionDependency, LayerSource, ProjectLayer
from bldcontrol.models import BuildRequest
from bldcontrol import bbcontroller
from django.http import HttpResponse, JsonResponse
from django.views.generic import View
from django.core.urlresolvers import reverse


def error_response(error):
    return JsonResponse({"error": error})


class XhrBuildRequest(View):

    def get(self, request, *args, **kwargs):
        return HttpResponse()

    def post(self, request, *args, **kwargs):
        """
          Build control

          Entry point: /xhr_buildrequest/<project_id>
          Method: POST

          Args:
              id: id of build to change
              buildCancel = build_request_id ...
              buildDelete = id ...
              targets = recipe_name ...

          Returns:
              {"error": "ok"}
            or
              {"error": <error message>}
        """

        project = Project.objects.get(pk=kwargs['pid'])

        if 'buildCancel' in request.POST:
            for i in request.POST['buildCancel'].strip().split(" "):
                try:
                    br = BuildRequest.objects.get(project=project, pk=i)

                    try:
                        bbctrl = bbcontroller.BitbakeController(br.environment)
                        bbctrl.forceShutDown()
                    except:
                        # We catch a bunch of exceptions here because
                        # this is where the server has not had time to start up
                        # and the build request or build is in transit between
                        # processes.
                        # We can safely just set the build as cancelled
                        # already as it never got started
                        build = br.build
                        build.outcome = Build.CANCELLED
                        build.save()

                    # We now hand over to the buildinfohelper to update the
                    # build state once we've finished cancelling
                    br.state = BuildRequest.REQ_CANCELLING
                    br.save()

                except BuildRequest.DoesNotExist:
                    return error_response('No such build id %s' % i)

            return error_response('ok')

        if 'buildDelete' in request.POST:
            for i in request.POST['buildDelete'].strip().split(" "):
                try:
                    BuildRequest.objects.select_for_update().get(
                        project=project,
                        pk=i,
                        state__lte=BuildRequest.REQ_DELETED).delete()

                except BuildRequest.DoesNotExist:
                    pass
            return error_response("ok")

        if 'targets' in request.POST:
            ProjectTarget.objects.filter(project=project).delete()
            s = str(request.POST['targets'])
            for t in re.sub(r'[;%|"]', '', s).split(" "):
                if ":" in t:
                    target, task = t.split(":")
                else:
                    target = t
                    task = ""
                ProjectTarget.objects.create(project=project,
                                             target=target,
                                             task=task)
            project.schedule_build()

            return error_response('ok')

        response = HttpResponse()
        response.status_code = 500
        return response


class XhrLayer(View):
    """ Get and Update Layer information """

    def post(self, request, *args, **kwargs):
        """
          Update a layer

          Entry point: /xhr_layer/<layerversion_id>
          Method: POST

          Args:
              vcs_url, dirpath, commit, up_branch, summary, description

              add_dep = append a layerversion_id as a dependency
              rm_dep = remove a layerversion_id as a depedency
          Returns:
              {"error": "ok"}
            or
              {"error": <error message>}
        """

        try:
            # We currently only allow Imported layers to be edited
            layer_version = Layer_Version.objects.get(
                id=kwargs['layerversion_id'],
                project=kwargs['pid'],
                layer_source=LayerSource.TYPE_IMPORTED)

        except Layer_Version.DoesNotExist:
            return error_response("Cannot find imported layer to update")

        if "vcs_url" in request.POST:
            layer_version.layer.vcs_url = request.POST["vcs_url"]
        if "dirpath" in request.POST:
            layer_version.dirpath = request.POST["dirpath"]
        if "commit" in request.POST:
            layer_version.commit = request.POST["commit"]
            layer_version.branch = request.POST["commit"]
        if "summary" in request.POST:
            layer_version.layer.summary = request.POST["summary"]
        if "description" in request.POST:
            layer_version.layer.description = request.POST["description"]

        if "add_dep" in request.POST:
            lvd = LayerVersionDependency(
                layer_version=layer_version,
                depends_on_id=request.POST["add_dep"])
            lvd.save()

        if "rm_dep" in request.POST:
            rm_dep = LayerVersionDependency.objects.get(
                layer_version=layer_version,
                depends_on_id=request.POST["rm_dep"])
            rm_dep.delete()

        try:
            layer_version.layer.save()
            layer_version.save()
        except Exception as e:
            return error_response("Could not update layer version entry: %s"
                                  % e)

        return JsonResponse({"error": "ok"})

    def delete(self, request, *args, **kwargs):
        try:
            # We currently only allow Imported layers to be deleted
            layer_version = Layer_Version.objects.get(
                id=kwargs['layerversion_id'],
                project=kwargs['pid'],
                layer_source=LayerSource.TYPE_IMPORTED)
        except Layer_Version.DoesNotExist:
            return error_response("Cannot find imported layer to delete")

        try:
            ProjectLayer.objects.get(project=kwargs['pid'],
                                     layercommit=layer_version).delete()
        except ProjectLayer.DoesNotExist:
            pass

        layer_version.layer.delete()
        layer_version.delete()

        return JsonResponse({
            "error": "ok",
            "redirect": reverse('project', args=(kwargs['pid'],))
        })
