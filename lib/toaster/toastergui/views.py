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

import operator

from django.db.models import Q
from django.shortcuts import render, redirect
from orm.models import Build, Target, Task, Layer, Layer_Version, Recipe, LogMessage, Variable
from orm.models import Task_Dependency, Recipe_Dependency, Package, Package_File, Package_Dependency
from orm.models import Target_Installed_Package
from django.views.decorators.cache import cache_control
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def _build_page_range(paginator, index = 1):
    try:
        page = paginator.page(index)
    except PageNotAnInteger:
        page = paginator.page(1)
    except  EmptyPage:
        page = paginator.page(paginator.num_pages)


    page.page_range = [page.number]
    crt_range = 0
    for i in range(1,5):
        if (page.number + i) <= paginator.num_pages:
            page.page_range = page.page_range + [ page.number + i]
            crt_range +=1
        if (page.number - i) > 0:
            page.page_range =  [page.number -i] + page.page_range
            crt_range +=1
        if crt_range == 4:
            break
    return page


def _verify_parameters(g, mandatory_parameters):
    miss = []
    for mp in mandatory_parameters:
        if not mp in g:
            miss.append(mp)
    if len(miss):
        return miss
    return None

def _redirect_parameters(view, g, mandatory_parameters):
    import urllib
    from django.core.urlresolvers import reverse
    url = reverse(view)
    params = {}
    for i in g:
        params[i] = g[i]
    for i in mandatory_parameters:
        if not i in params:
            params[i] = mandatory_parameters[i]

    return redirect(url + "?%s" % urllib.urlencode(params))


# shows the "all builds" page
def builds(request):
    template = 'build.html'
    # define here what parameters the view needs in the GET portion in order to
    # be able to display something.  'count' and 'page' are mandatory for all views
    # that use paginators.
    mandatory_parameters = { 'count': 10,  'page' : 1};
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( builds, request.GET, mandatory_parameters)

    # retrieve the objects that will be displayed in the table
    build_info = _build_page_range(Paginator(Build.objects.exclude(outcome = Build.IN_PROGRESS).order_by("-id"), request.GET.get('count', 10)),request.GET.get('page', 1))

    # build view-specific information; this is rendered specifically in the builds page
    build_mru = Build.objects.order_by("-started_on")[:3]
    for b in [ x for x in build_mru if x.outcome == Build.IN_PROGRESS ]:
        tf = Task.objects.filter(build = b)
        b.completeper = tf.exclude(order__isnull=True).count()*100/tf.count()
        from django.utils import timezone
        b.eta = timezone.now() + ((timezone.now() - b.started_on)*100/b.completeper)

    # send the data to the template
    context = {
            # specific info for
                'mru' : build_mru,
            # TODO: common objects for all table views, adapt as needed
                'objects' : build_info,
                'tablecols' : [
                {'name': 'Target ', 'clclass': 'target',},
                {'name': 'Machine ', 'clclass': 'machine'},
                {'name': 'Completed on ', 'clclass': 'completed_on'},
                {'name': 'Failed tasks ', 'clclass': 'failed_tasks'},
                {'name': 'Errors ', 'clclass': 'errors_no'},
                {'name': 'Warnings', 'clclass': 'warnings_no'},
                {'name': 'Output ', 'clclass': 'output'},
                {'name': 'Started on ', 'clclass': 'started_on', 'hidden' : 1},
                {'name': 'Time ', 'clclass': 'time', 'hidden' : 1},
                {'name': 'Output', 'clclass': 'output'},
                {'name': 'Log', 'clclass': 'log', 'hidden': 1},
            ]}

    return render(request, template, context)


# build dashboard for a single build, coming in as argument
def builddashboard(request, build_id):
    template = "builddashboard.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
    }
    return render(request, template, context)

def task(request, build_id, task_id):
    template = "singletask.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
    }
    return render(request, template, context)

def recipe(request, build_id, recipe_id):
    template = "recipe.html"
    if Recipe.objects.filter(pk=recipe_id).count() == 0 :
        return redirect(builds)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'object' : Recipe.objects.filter(pk=recipe_id)[0],
    }
    return render(request, template, context)

def package(request, build_id, package_id):
    template = "singlepackage.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
    }
    return render(request, template, context)

def target(request, build_id, target_id):
    template = "target.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
    }
    return render(request, template, context)



def _find_task_revdep(task):
    tp = []
    for p in Task_Dependency.objects.filter(depends_on=task):
        tp.append(p.task);
    return tp

def _find_task_provider(task):
    task_revdeps = _find_task_revdep(task)
    for tr in task_revdeps:
        if tr.outcome != Task.OUTCOME_COVERED:
            return tr
    for tr in task_revdeps:
        trc = _find_task_provider(tr)
        if trc is not None:
            return trc
    return None

def tasks(request, build_id):
    template = 'task.html'

    tasks = _build_page_range(Paginator(Task.objects.filter(build=build_id), 100),request.GET.get('page', 1))

    for t in tasks:
        if t.outcome == Task.OUTCOME_COVERED:
            t.provider = _find_task_provider(t)

    context = {'build': Build.objects.filter(pk=build_id)[0], 'objects': tasks}

    return render(request, template, context)

def recipes(request, build_id):
    template = 'recipe.html'

    recipes = _build_page_range(Paginator(Recipe.objects.filter(build_recipe=build_id), 100),request.GET.get('page', 1))

    context = {'build': Build.objects.filter(pk=build_id)[0], 'objects': recipes}

    return render(request, template, context)


def configuration(request, build_id):
    template = 'configuration.html'
    variables = _build_page_range(Paginator(Variable.objects.filter(build=build_id), 50), request.GET.get('page', 1))
    context = {'build': Build.objects.filter(pk=build_id)[0], 'objects' : variables}
    return render(request, template, context)

def buildtime(request, build_id):
    template = "buildtime.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
    }
    return render(request, template, context)

def cpuusage(request, build_id):
    template = "cpuusage.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
    }
    return render(request, template, context)

def diskio(request, build_id):
    template = "diskio.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
    }
    return render(request, template, context)




def bpackage(request, build_id):
    template = 'bpackage.html'
    packages = Package.objects.filter(build = build_id)
    context = {'build': Build.objects.filter(pk=build_id)[0], 'objects' : packages}
    return render(request, template, context)

def bfile(request, build_id, package_id):
    template = 'bfile.html'
    files = Package_File.objects.filter(package = package_id)
    context = {'build': Build.objects.filter(pk=build_id)[0], 'objects' : files}
    return render(request, template, context)

def tpackage(request, build_id, target_id):
    template = 'package.html'
    packages = map(lambda x: x.package, list(Target_Installed_Package.objects.filter(target=target_id)))
    context = {'build': Build.objects.filter(pk=build_id)[0], 'objects' : packages}
    return render(request, template, context)

def layer(request):
    template = 'layer.html'
    layer_info = Layer.objects.all()

    for li in layer_info:
        li.versions = Layer_Version.objects.filter(layer = li)
        for liv in li.versions:
            liv.count = Recipe.objects.filter(layer_version__id = liv.id).count()

    context = {'objects': layer_info}

    return render(request, template, context)


def layer_versions_recipes(request, layerversion_id):
    template = 'recipe.html'
    recipes = Recipe.objects.filter(layer_version__id = layerversion_id)

    context = {'objects': recipes,
            'layer_version' : Layer_Version.objects.filter( id = layerversion_id )[0]
    }

    return render(request, template, context)

#### API

import json
from django.core import serializers
from django.http import HttpResponse, HttpResponseBadRequest


def model_explorer(request, model_name):

    DESCENDING = 'desc'
    response_data = {}
    model_mapping = {
        'build': Build,
        'target': Target,
        'task': Task,
        'task_dependency': Task_Dependency,
        'package': Package,
        'layer': Layer,
        'layerversion': Layer_Version,
        'recipe': Recipe,
        'recipe_dependency': Recipe_Dependency,
        'package': Package,
        'package_dependency': Package_Dependency,
        'build_file': Package_File,
        'variable': Variable,
        'logmessage': LogMessage,
        }

    if model_name not in model_mapping.keys():
        return HttpResponseBadRequest()

    model = model_mapping[model_name]

    try:
        limit = int(request.GET.get('limit', 0))
    except ValueError:
        limit = 0

    try:
        offset = int(request.GET.get('offset', 0))
    except ValueError:
        offset = 0

    ordering_string, invalid = _validate_input(request.GET.get('orderby', ''),
                                               model)
    if invalid:
        return HttpResponseBadRequest()

    filter_string, invalid = _validate_input(request.GET.get('filter', ''),
                                             model)
    if invalid:
        return HttpResponseBadRequest()

    search_term = request.GET.get('search', '')

    if filter_string:
        filter_terms = _get_filtering_terms(filter_string)
        try:
            queryset = model.objects.filter(**filter_terms)
        except ValueError:
            queryset = []
    else:
        queryset = model.objects.all()

    if search_term:
        queryset = _get_search_results(search_term, queryset, model)

    if ordering_string and queryset:
        column, order = ordering_string.split(':')
        if order.lower() == DESCENDING:
            queryset = queryset.order_by('-' + column)
        else:
            queryset = queryset.order_by(column)

    if offset and limit:
        queryset = queryset[offset:(offset+limit)]
    elif offset:
        queryset = queryset[offset:]
    elif limit:
        queryset = queryset[:limit]

    if queryset:
        response_data['count'] = queryset.count()
    else:
        response_data['count'] = 0
    response_data['list'] = serializers.serialize('json', queryset)
#    response_data = serializers.serialize('json', queryset)

    return HttpResponse(json.dumps(response_data),
                        content_type='application/json')

def _get_filtering_terms(filter_string):

    search_terms = filter_string.split(":")
    keys = search_terms[0].split(',')
    values = search_terms[1].split(',')

    return dict(zip(keys, values))

def _validate_input(input, model):

    invalid = 0

    if input:
        input_list = input.split(":")

        # Check we have only one colon
        if len(input_list) != 2:
            invalid = 1
            return None, invalid

        # Check we have an equal number of terms both sides of the colon
        if len(input_list[0].split(',')) != len(input_list[1].split(',')):
            invalid = 1
            return None, invalid

        # Check we are looking for a valid field
        valid_fields = model._meta.get_all_field_names()
        for field in input_list[0].split(','):
            if field not in valid_fields:
                invalid = 1
                return None, invalid

    return input, invalid

def _get_search_results(search_term, queryset, model):
    search_objects = []
    for st in search_term.split(" "):
        q_map = map(lambda x: Q(**{x+'__icontains': st}),
                model.search_allowed_fields)

        search_objects.append(reduce(operator.or_, q_map))
    search_object = reduce(operator.and_, search_objects)
    queryset = queryset.filter(search_object)

    return queryset
