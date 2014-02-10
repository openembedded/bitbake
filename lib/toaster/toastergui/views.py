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

import operator

from django.db.models import Q
from django.shortcuts import render, redirect
from orm.models import Build, Target, Task, Layer, Layer_Version, Recipe, LogMessage, Variable
from orm.models import Task_Dependency, Recipe_Dependency, Package, Package_File, Package_Dependency
from orm.models import Target_Installed_Package
from django.views.decorators.cache import cache_control
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseBadRequest
from django.utils import timezone
from datetime import timedelta
from django.utils import formats

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

def _redirect_parameters(view, g, mandatory_parameters, *args, **kwargs):
    import urllib
    from django.core.urlresolvers import reverse
    url = reverse(view, kwargs=kwargs)
    params = {}
    for i in g:
        params[i] = g[i]
    for i in mandatory_parameters:
        if not i in params:
            params[i] = mandatory_parameters[i]

    return redirect(url + "?%s" % urllib.urlencode(params), *args, **kwargs)

FIELD_SEPARATOR = ":"
VALUE_SEPARATOR = ";"
DESCENDING = "-"

def __get_q_for_val(name, value):
    if "OR" in value:
        return reduce(operator.or_, map(lambda x: __get_q_for_val(name, x), [ x for x in value.split("OR") ]))
    if "AND" in value:
        return reduce(operator.and_, map(lambda x: __get_q_for_val(name, x), [ x for x in value.split("AND") ]))
    if value.startswith("NOT"):
        kwargs = { name : value.strip("NOT") }
        return ~Q(**kwargs)
    else:
        kwargs = { name : value }
        return Q(**kwargs)

def _get_filtering_query(filter_string):

    search_terms = filter_string.split(FIELD_SEPARATOR)
    keys = search_terms[0].split(VALUE_SEPARATOR)
    values = search_terms[1].split(VALUE_SEPARATOR)

    querydict = dict(zip(keys, values))
    return reduce(lambda x, y: x & y, map(lambda x: __get_q_for_val(k, querydict[k]),[k for k in querydict]))

def _get_toggle_order(request, orderkey, reverse = False):
    if reverse:
        return "%s:+" % orderkey if request.GET.get('orderby', "") == "%s:-" % orderkey else "%s:-" % orderkey
    else:
        return "%s:-" % orderkey if request.GET.get('orderby', "") == "%s:+" % orderkey else "%s:+" % orderkey

def _get_toggle_order_icon(request, orderkey):
    if request.GET.get('orderby', "") == "%s:+"%orderkey:
        return "down"
    elif request.GET.get('orderby', "") == "%s:-"%orderkey:
        return "up"
    else:
        return None

# we check that the input comes in a valid form that we can recognize
def _validate_input(input, model):

    invalid = None

    if input:
        input_list = input.split(FIELD_SEPARATOR)

        # Check we have only one colon
        if len(input_list) != 2:
            invalid = "We have an invalid number of separators"
            return None, invalid

        # Check we have an equal number of terms both sides of the colon
        if len(input_list[0].split(VALUE_SEPARATOR)) != len(input_list[1].split(VALUE_SEPARATOR)):
            invalid = "Not all arg names got values"
            return None, invalid + str(input_list)

        # Check we are looking for a valid field
        valid_fields = model._meta.get_all_field_names()
        for field in input_list[0].split(VALUE_SEPARATOR):
            if not reduce(lambda x, y: x or y, map(lambda x: field.startswith(x), [ x for x in valid_fields ])):
                return None, (field, [ x for x in valid_fields ])

    return input, invalid

# uses search_allowed_fields in orm/models.py to create a search query
# for these fields with the supplied input text
def _get_search_results(search_term, queryset, model):
    search_objects = []
    for st in search_term.split(" "):
        q_map = map(lambda x: Q(**{x+'__icontains': st}),
                model.search_allowed_fields)

        search_objects.append(reduce(operator.or_, q_map))
    search_object = reduce(operator.and_, search_objects)
    queryset = queryset.filter(search_object)

    return queryset


# function to extract the search/filter/ordering parameters from the request
# it uses the request and the model to validate input for the filter and orderby values
def _search_tuple(request, model):
    ordering_string, invalid = _validate_input(request.GET.get('orderby', ''), model)
    if invalid:
        raise BaseException("Invalid ordering " + str(invalid))

    filter_string, invalid = _validate_input(request.GET.get('filter', ''), model)
    if invalid:
        raise BaseException("Invalid filter " + str(invalid))

    search_term = request.GET.get('search', '')
    return (filter_string, search_term, ordering_string)


# returns a lazy-evaluated queryset for a filter/search/order combination
def _get_queryset(model, queryset, filter_string, search_term, ordering_string):
    if filter_string:
        filter_query = _get_filtering_query(filter_string)
        queryset = queryset.filter(filter_query)
    else:
        queryset = queryset.all()

    if search_term:
        queryset = _get_search_results(search_term, queryset, model)

    if ordering_string and queryset:
        column, order = ordering_string.split(':')
        if order.lower() == DESCENDING:
            queryset = queryset.order_by('-' + column)
        else:
            queryset = queryset.order_by(column)

    return queryset

# shows the "all builds" page
def builds(request):
    template = 'build.html'
    # define here what parameters the view needs in the GET portion in order to
    # be able to display something.  'count' and 'page' are mandatory for all views
    # that use paginators.
    mandatory_parameters = { 'count': 10,  'page' : 1};
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'all-builds', request.GET, mandatory_parameters)

    # boilerplate code that takes a request for an object type and returns a queryset
    # for that object type. copypasta for all needed table searches
    (filter_string, search_term, ordering_string) = _search_tuple(request, Build)
    queryset = Build.objects.exclude(outcome = Build.IN_PROGRESS)
    queryset = _get_queryset(Build, queryset, filter_string, search_term, ordering_string)

    # retrieve the objects that will be displayed in the table; builds a paginator and gets a page range to display
    build_info = _build_page_range(Paginator(queryset, request.GET.get('count', 10)),request.GET.get('page', 1))

    # build view-specific information; this is rendered specifically in the builds page, at the top of the page (i.e. Recent builds)
    build_mru = Build.objects.filter(completed_on__gte=(timezone.now()-timedelta(hours=24))).order_by("-started_on")[:3]
    for b in [ x for x in build_mru if x.outcome == Build.IN_PROGRESS ]:
        tf = Task.objects.filter(build = b)
        tfc = tf.count()
        if tfc > 0:
            b.completeper = tf.exclude(order__isnull=True).count()*100/tf.count()
        else:
            b.completeper = 0
        b.eta = timezone.now()
        if b.completeper > 0:
            b.eta += ((timezone.now() - b.started_on)*100/b.completeper)
        else:
            b.eta = 0

    # send the data to the template
    context = {
            # specific info for
                'mru' : build_mru,
            # TODO: common objects for all table views, adapt as needed
                'objects' : build_info,
                'objectname' : "builds",
            # Specifies the display of columns for the table, appearance in "Edit columns" box, toggling default show/hide, and specifying filters for columns
                'tablecols' : [
                {'name': 'Outcome ',                                                # column with a single filter
                 'qhelp' : "The outcome tells you if a build completed successfully or failed",     # the help button content
                 'dclass' : "span2",                                                # indication about column width; comes from the design
                 'orderfield': _get_toggle_order(request, "outcome"),               # adds ordering by the field value; default ascending unless clicked from ascending into descending
                  # filter field will set a filter on that column with the specs in the filter description
                  # the class field in the filter has no relation with clclass; the control different aspects of the UI
                  # still, it is recommended for the values to be identical for easy tracking in the generated HTML
                 'filter' : {'class' : 'outcome',
                             'label': 'Show:',
                             'options' : [
                                         ('Successful builds', 'outcome:' + str(Build.SUCCEEDED)),  # this is the field search expression
                                         ('Failed builds', 'outcome:'+ str(Build.FAILED)),
                                         ]
                            }
                },
                {'name': 'Target ',                                                 # default column, disabled box, with just the name in the list
                 'qhelp': "This is the build target(s): one or more recipes or image recipes",
                 'orderfield': _get_toggle_order(request, "target__target"),
                },
                {'name': 'Machine ',
                 'qhelp': "The machine is the hardware for which you are building",
                 'orderfield': _get_toggle_order(request, "machine"),
                 'dclass': 'span3'
                },                           # a slightly wider column
                {'name': 'Started on ', 'clclass': 'started_on', 'hidden' : 1,      # this is an unchecked box, which hides the column
                 'qhelp': "The date and time you started the build",
                 'orderfield': _get_toggle_order(request, "started_on", True),
                 'filter' : {'class' : 'started_on',
                             'label': 'Show:',
                             'options' : [
                                         ("Today's builds" , 'started_on__gte:'+timezone.now().strftime("%Y-%m-%d")),
                                         ("Yesterday's builds", 'started_on__gte:'+(timezone.now()-timedelta(hours=24)).strftime("%Y-%m-%d")),
                                         ("This week's builds", 'started_on__gte:'+(timezone.now()-timedelta(days=7)).strftime("%Y-%m-%d")),
                                         ]
                            }
                },
                {'name': 'Completed on ',
                 'qhelp': "The date and time the build finished",
                 'orderfield': _get_toggle_order(request, "completed_on", True),
                 'filter' : {'class' : 'completed_on', 
                             'label': 'Show:', 
                             'options' : [
                                         ("Today's builds", 'completed_on__gte:'+timezone.now().strftime("%Y-%m-%d")),
                                         ("Yesterday's builds", 'completed_on__gte:'+(timezone.now()-timedelta(hours=24)).strftime("%Y-%m-%d")),
                                         ("This week's builds", 'completed_on__gte:'+(timezone.now()-timedelta(days=7)).strftime("%Y-%m-%d")),
                                         ]
                            }
                },
                {'name': 'Failed tasks ', 'clclass': 'failed_tasks',                # specifing a clclass will enable the checkbox
                 'qhelp': "How many tasks failed during the build",
                 'filter' : {'class' : 'failed_tasks',
                             'label': 'Show:',
                             'options' : [
                                         ('Builds with failed tasks', 'task_build__outcome:4'),
                                         ('Builds without failed tasks', 'task_build__outcome:NOT4'),
                                         ]
                            }
                },
                {'name': 'Errors ', 'clclass': 'errors_no',
                 'qhelp': "How many errors were encountered during the build (if any)",
                 'orderfield': _get_toggle_order(request, "errors_no", True),
                 'filter' : {'class' : 'errors_no', 
                             'label': 'Show:', 
                             'options' : [
                                         ('Builds with errors', 'errors_no__gte:1'),
                                         ('Builds without errors', 'errors_no:0'),
                                         ]
                            }
                },
                {'name': 'Warnings', 'clclass': 'warnings_no',
                 'qhelp': "How many warnigns were encountered during the build (if any)",
                 'orderfield': _get_toggle_order(request, "warnings_no", True),
                 'filter' : {'class' : 'warnings_no', 
                             'label': 'Show:', 
                             'options' : [
                                         ('Builds with warnings','warnings_no__gte:1'),
                                         ('Builds without warnings','warnings_no:0'),
                                         ]
                            }
                },
                {'name': 'Time ', 'clclass': 'time', 'hidden' : 1,
                 'qhelp': "How long it took the build to finish",
                 'orderfield': _get_toggle_order(request, "timespent", True),
                },
                {'name': 'Log',
                 'dclass': "span4",
                 'qhelp': "The location in disk of the build main log file",
                 'clclass': 'log', 'hidden': 1,
                 'orderfield': _get_toggle_order(request, "cooker_log_path"),
                },
                {'name': 'Output', 'clclass': 'output',
                 'qhelp': "The root file system types produced by the build. You can find them in your <code>/build/tmp/deploy/images/</code> directory",
                 'orderfield': _get_toggle_order(request, "image_fstypes")
                },
                ]
            }

    return render(request, template, context)


# build dashboard for a single build, coming in as argument
def builddashboard(request, build_id):
    template = "builddashboard.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'recipecount' : Recipe.objects.filter(layer_version__id__in=Layer_Version.objects.filter(build=build_id)).count()
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

    object = Recipe.objects.filter(pk=recipe_id)[0]
    layer_version = Layer_Version.objects.filter(pk=object.layer_version_id)[0]
    layer  = Layer.objects.filter(pk=layer_version.layer_id)[0]
    tasks  = Task.objects.filter(recipe_id = recipe_id).filter(build_id = build_id)
    packages = Package.objects.filter(recipe_id = recipe_id).filter(build_id = build_id).filter(size__gte=0)

    context = {
            'build'   : Build.objects.filter(pk=build_id)[0],
            'object'  : object,
            'layer_version' : layer_version,
            'layer'   : layer,
            'tasks'   : tasks,
            'packages': packages,
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
    template = 'tasks.html'
    mandatory_parameters = { 'count': 25,  'page' : 1, 'orderby':'order:+'};
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'tasks', request.GET, mandatory_parameters, build_id = build_id)
    (filter_string, search_term, ordering_string) = _search_tuple(request, Task)
    queryset = Task.objects.filter(build=build_id, order__gt=0)
    queryset = _get_queryset(Task, queryset, filter_string, search_term, ordering_string)

    tasks = _build_page_range(Paginator(queryset, request.GET.get('count', 100)),request.GET.get('page', 1))

# Per Belen - do not show the covering task
#    for t in tasks:
#        if t.outcome == Task.OUTCOME_COVERED:
#            t.provider = _find_task_provider(t)

    context = { 'objectname': 'tasks',
                'build': Build.objects.filter(pk=build_id)[0],
                'objects': tasks,
                'tablecols':[
                {
                    'name':'Order',
                    'qhelp':'The running sequence of each task in the build',
                    'orderfield': _get_toggle_order(request, "order"),
                    'ordericon':_get_toggle_order_icon(request, "order"),
                },
                {
                    'name':'Recipe',
                    'qhelp':'The name of the recipe to which each task applies',
                    'orderfield': _get_toggle_order(request, "recipe"),
                    'ordericon':_get_toggle_order_icon(request, "recipe"),
                },
                {
                    'name':'Recipe version',
                    'qhelp':'The version of the recipe to which each task applies',
                    'clclass': 'recipe_version',
                    'hidden' : 1,
                },
                {
                    'name':'Task',
                    'qhelp':'The name of the task',
                    'orderfield': _get_toggle_order(request, "task_name"),
                    'ordericon':_get_toggle_order_icon(request, "task_name"),
                },
                {
                    'name':'Executed',
                    'qhelp':"This value tells you if a task had to run in order to generate the task output (executed), or if the output was provided by another task and therefore the task didn't need to run (not executed)",
                    'orderfield': _get_toggle_order(request, "task_executed"),
                    'ordericon':_get_toggle_order_icon(request, "task_executed"),
                       'filter' : {
                               'class' : 'executed',
                               'label': 'Show:',
                               'options' : [
                                           ('Executed Tasks', 'task_executed:1'),
                                           ('Not Executed Tasks', 'task_executed:0'),
                                           ]
                               }

                },
                {
                    'name':'Outcome',
                    'qhelp':'This column tells you if executed tasks succeeded, failed or restored output from the <code>sstate-cache</code> directory or mirrors. It also tells you why not executed tasks did not need to run',
                    'orderfield': _get_toggle_order(request, "outcome"),
                    'ordericon':_get_toggle_order_icon(request, "outcome"),
                    'filter' : {
                               'class' : 'outcome',
                               'label': 'Show:',
                               'options' : [
                                           ('Succeeded Tasks', 'outcome:%d'%Task.OUTCOME_SUCCESS),
                                           ('Failed Tasks', 'outcome:%d'%Task.OUTCOME_FAILED),
                                           ('Cached Tasks', 'outcome:%d'%Task.OUTCOME_CACHED),
                                           ('Prebuilt Tasks', 'outcome:%d'%Task.OUTCOME_PREBUILT),
                                           ('Covered Tasks', 'outcome:%d'%Task.OUTCOME_COVERED),
                                           ('Empty Tasks', 'outcome:%d'%Task.OUTCOME_NA),
                                           ]
                               }

                },
                {
                    'name':'Cache attempt',
                    'qhelp':'This column tells you if a task tried to restore output from the <code>sstate-cache</code> directory or mirrors, and what was the result: Succeeded, Failed or File not in cache',
                    'orderfield': _get_toggle_order(request, "sstate_result"),
                    'ordericon':_get_toggle_order_icon(request, "sstate_result"),
                    'filter' : {
                               'class' : 'cache_attempt',
                               'label': 'Show:',
                               'options' : [
                                           ('Tasks with cache attempts', 'sstate_result:%d'%Task.SSTATE_NA),
                                           ("Tasks with 'File not in cache' attempts", 'sstate_result:%d'%Task.SSTATE_MISS),
                                           ("Tasks with 'Failed' cache attempts", 'sstate_result:%d'%Task.SSTATE_FAILED),
                                           ("Tasks with 'Succeeded' cache attempts", 'sstate_result:%d'%Task.SSTATE_RESTORED),
                                           ]
                               }

                },
                {
                    'name':'Time (secs)',
                    'qhelp':'How long it took the task to finish, expressed in seconds',
                    'orderfield': _get_toggle_order(request, "elapsed_time"),
                    'ordericon':_get_toggle_order_icon(request, "elapsed_time"),
                    'clclass': 'time_taken',
                    'hidden' : 1,
                },
                {
                    'name':'CPU usage',
                    'qhelp':'Task CPU utilisation, expressed as a percentage',
                    'orderfield': _get_toggle_order(request, "cpu_usage"),
                    'ordericon':_get_toggle_order_icon(request, "cpu_usage"),
                    'clclass': 'cpu_used',
                    'hidden' : 1,
                },
                {
                    'name':'Disk I/O (ms)',
                    'qhelp':'Number of miliseconds the task spent doing disk input and output',
                    'orderfield': _get_toggle_order(request, "disk_io"),
                    'ordericon':_get_toggle_order_icon(request, "disk_io"),
                    'clclass': 'disk_io',
                    'hidden' : 1,
                },
                {
                    'name':'Log',
                    'qhelp':'The location in disk of the task log file',
                    'orderfield': _get_toggle_order(request, "logfile"),
                    'ordericon':_get_toggle_order_icon(request, "logfile"),
                    'clclass': 'task_log',
                    'hidden' : 1,
                },
                ]}

    return render(request, template, context)

def recipes(request, build_id):
    template = 'recipes.html'
    mandatory_parameters = { 'count': 100,  'page' : 1, 'orderby':'name:+'};
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'recipes', request.GET, mandatory_parameters, build_id = build_id)
    (filter_string, search_term, ordering_string) = _search_tuple(request, Recipe)
    queryset = Recipe.objects.filter(layer_version__id__in=Layer_Version.objects.filter(build=build_id))
    queryset = _get_queryset(Recipe, queryset, filter_string, search_term, ordering_string)

    recipes = _build_page_range(Paginator(queryset, request.GET.get('count', 100)),request.GET.get('page', 1))

    context = {
        'objectname': 'recipes',
        'build': Build.objects.filter(pk=build_id)[0],
        'objects': recipes,
        'tablecols':[
            {
                'name':'Recipe',
                'qhelp':'Information about a single piece of software, including where to download the source, configuration options, how to compile the source files and how to package the compiled output',
                'orderfield': _get_toggle_order(request, "name"),
                'ordericon':_get_toggle_order_icon(request, "name"),
            },
            {
                'name':'Recipe version',
                'qhelp':'The recipe version and revision',
            },
            {
                'name':'Dependencies',
                'qhelp':'Recipe build-time dependencies (other recipes)',
                'clclass': 'depends_on', 'hidden': 1,
            },
            {
                'name':'Reverse dependencies',
                'qhelp':'Recipe build-time reverse dependencies (i.e. which other recipes depend on this recipe)',
                'clclass': 'depends_by', 'hidden': 1,
            },
            {
                'name':'Recipe file',
                'qhelp':'Location in disk of the recipe .bb file',
                'orderfield': _get_toggle_order(request, "file_path"),
                'ordericon':_get_toggle_order_icon(request, "file_path"),
                'clclass': 'recipe_file', 'hidden': 0,
            },
            {
                'name':'Section',
                'qhelp':'The section in which packages should be categorised. There are 5 sections: base, console, utils, devel and libs',
                'orderfield': _get_toggle_order(request, "section"),
                'ordericon':_get_toggle_order_icon(request, "section"),
                'clclass': 'recipe_section', 'hidden': 0,
            },
            {
                'name':'License',
                'qhelp':'The list of source licenses for the recipe. Separate license names using | (pipe) means there is a choice between licenses. Separate license names using & (ampersand) means multiple licenses exist that cover different parts of the source',
                'orderfield': _get_toggle_order(request, "license"),
                'ordericon':_get_toggle_order_icon(request, "license"),
                'clclass': 'recipe_license', 'hidden': 0,
            },
            {
                'name':'Layer',
                'qhelp':'The name of the layer prodiving the recipe',
                'orderfield': _get_toggle_order(request, "layer_version__layer__name"),
                'ordericon':_get_toggle_order_icon(request, "layer_version__layer__name"),
                'clclass': 'layer_version__layer__name', 'hidden': 0,
            },
            {
                'name':'Layer branch',
                'qhelp':'The Git branch of the layer prodiving the recipe',
                'orderfield': _get_toggle_order(request, "layer_version__branch"),
                'ordericon':_get_toggle_order_icon(request, "layer_version__branch"),
                'clclass': 'layer_version__branch', 'hidden': 1,
            },
            {
                'name':'Layer commit',
                'qhelp':'The Git commit of the layer prodiving the recipe',
                'clclass': 'layer_version__layer__commit', 'hidden': 1,
            },
            {
                'name':'Layer directory',
                'qhelp':'Location in disk of the layer prodiving the recipe',
                'orderfield': _get_toggle_order(request, "layer_version__layer__local_path"),
                'ordericon':_get_toggle_order_icon(request, "layer_version__layer__local_path"),
                'clclass': 'layer_version__layer__local_path', 'hidden': 1,
            },
            ]
        }

    return render(request, template, context)


def configuration(request, build_id):
    template = 'configuration.html'
    context = {'build': Build.objects.filter(pk=build_id)[0]}
    return render(request, template, context)


def configvars(request, build_id):
    template = 'configvars.html'
    mandatory_parameters = { 'count': 100,  'page' : 1};
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'configvars', request.GET, mandatory_parameters, build_id = build_id)

    (filter_string, search_term, ordering_string) = _search_tuple(request, Variable)
    queryset = Variable.objects.filter(build=build_id)
    queryset = _get_queryset(Variable, queryset, filter_string, search_term, ordering_string)

    variables = _build_page_range(Paginator(queryset, request.GET.get('count', 50)), request.GET.get('page', 1))

    context = {
                'build': Build.objects.filter(pk=build_id)[0],
                'objects' : variables,
            # Specifies the display of columns for the table, appearance in "Edit columns" box, toggling default show/hide, and specifying filters for columns
                'tablecols' : [
                {'name': 'Variable ',
                 'qhelp': "Base variable expanded name",
                 'clclass' : 'variable',
                 'dclass' : "span3",
                 'orderfield': _get_toggle_order(request, "variable_name"),
                },
                {'name': 'Value ',
                 'qhelp': "The value assigned to the variable",
                 'clclass': 'variable_value',
                 'dclass': "span4",
                 'orderfield': _get_toggle_order(request, "variable_value"),
                },
                {'name': 'Configuration file(s) ',
                 'qhelp': "The configuration file(s) that touched the variable value",
                 'clclass': 'file',
                 'dclass': "span6",
                 'orderfield': _get_toggle_order(request, "variable_vhistory__file_name"),
                 'filter' : { 'class': 'file', 'label' : 'Show only', 'options' : {
                        }
                 }
                },
                {'name': 'Description ',
                 'qhelp': "A brief explanation of a variable",
                 'clclass': 'description',
                 'dclass': "span5",
                 'orderfield': _get_toggle_order(request, "description"),
                 'filter' : { 'class' : 'description', 'label' : 'No', 'options' : {
                        }
                 },
                }
                ]
            }

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
    mandatory_parameters = { 'count': 100,  'page' : 1, 'orderby':'name:+'};
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'packages', request.GET, mandatory_parameters, build_id = build_id)
    (filter_string, search_term, ordering_string) = _search_tuple(request, Package)
    queryset = Package.objects.filter(build = build_id).filter(size__gte=0)
    queryset = _get_queryset(Package, queryset, filter_string, search_term, ordering_string)

    packages = _build_page_range(Paginator(queryset, request.GET.get('count', 100)),request.GET.get('page', 1))

    context = {
        'objectname': 'packages',
        'build': Build.objects.filter(pk=build_id)[0],
        'objects' : packages,
        'tablecols':[
            {
                'name':'Package',
                'qhelp':'Packaged output resulting from building a recipe',
                'orderfield': _get_toggle_order(request, "name"),
                'ordericon':_get_toggle_order_icon(request, "name"),
            },
            {
                'name':'Package version',
                'qhelp':'The package version and revision',
            },
            {
                'name':'Size',
                'qhelp':'The size of the package',
                'orderfield': _get_toggle_order(request, "size"),
                'ordericon':_get_toggle_order_icon(request, "size"),
                'clclass': 'size', 'hidden': 0,
            },
            {
                'name':'License',
                'qhelp':'The license under which the package is distributed. Separate license names using | (pipe) means there is a choice between licenses. Separate license names using & (ampersand) means multiple licenses exist that cover different parts of the source',
                'orderfield': _get_toggle_order(request, "license"),
                'ordericon':_get_toggle_order_icon(request, "license"),
                'clclass': 'license', 'hidden': 1,
            },
            {
                'name':'Recipe',
                'qhelp':'The name of the recipe building the package',
                'orderfield': _get_toggle_order(request, "recipe__name"),
                'ordericon':_get_toggle_order_icon(request, "recipe__name"),
                'clclass': 'recipe__name', 'hidden': 0,
            },
            {
                'name':'Recipe version',
                'qhelp':'Version and revision of the recipe building the package',
                'clclass': 'recipe__version', 'hidden': 1,
            },
            {
                'name':'Layer',
                'qhelp':'The name of the layer providing the recipe that builds the package',
                'orderfield': _get_toggle_order(request, "recipe__layer_version__layer__name"),
                'ordericon':_get_toggle_order_icon(request, "recipe__layer_version__layer__name"),
                'clclass': 'recipe__layer_version__layer__name', 'hidden': 1,
            },
            {
                'name':'Layer branch',
                'qhelp':'The Git branch of the layer providing the recipe that builds the package',
                'orderfield': _get_toggle_order(request, "recipe__layer_version__branch"),
                'ordericon':_get_toggle_order_icon(request, "recipe__layer_version__branch"),
                'clclass': 'recipe__layer_version__branch', 'hidden': 1,
            },
            {
                'name':'Layer commit',
                'qhelp':'The Git commit of the layer providing the recipe that builds the package',
                'clclass': 'recipe__layer_version__layer__commit', 'hidden': 1,
            },
            {
                'name':'Layer directory',
                'qhelp':'Location in disk of the layer providing the recipe that builds the package',
                'orderfield': _get_toggle_order(request, "recipe__layer_version__layer__local_path"),
                'ordericon':_get_toggle_order_icon(request, "recipe__layer_version__layer__local_path"),
                'clclass': 'recipe__layer_version__layer__local_path', 'hidden': 1,
            },
            ]
        }

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

# A set of dependency types valid for both included and built package views
OTHER_DEPENDS_BASE = [
    Package_Dependency.TYPE_RSUGGESTS,
    Package_Dependency.TYPE_RPROVIDES,
    Package_Dependency.TYPE_RREPLACES,
    Package_Dependency.TYPE_RCONFLICTS,
    ]

# value for invalid row id
INVALID_KEY = -1

"""
Given a package id, target_id retrieves two sets of this image and package's
dependencies.  The return value is a dictionary consisting of two other
lists: a list of 'runtime' dependencies, that is, having RDEPENDS
values in source package's recipe, and a list of other dependencies, that is
the list of possible recipe variables as found in OTHER_DEPENDS_BASE plus
the RRECOMENDS or TRECOMENDS value.
The lists are built in the sort order specified for the package runtime
dependency views.
"""
def get_package_dependencies(package_id, target_id = INVALID_KEY):
    runtime_deps = []
    other_deps = []
    other_depends_types = OTHER_DEPENDS_BASE

    if target_id != INVALID_KEY :
        rdepends_type = Package_Dependency.TYPE_TRDEPENDS
        other_depends_types +=  [Package_Dependency.TYPE_TRECOMMENDS]
    else :
        rdepends_type = Package_Dependency.TYPE_RDEPENDS
        other_depends_types += [Package_Dependency.TYPE_RRECOMMENDS]

    package = Package.objects.get(pk=package_id)
    if target_id != INVALID_KEY :
        alldeps = package.package_dependencies_source.filter(target_id__exact = target_id)
    else :
        alldeps = package.package_dependencies_source.all()
    for idep in alldeps:
        dep_package = Package.objects.get(pk=idep.depends_on_id)
        dep_entry = Package_Dependency.DEPENDS_DICT[idep.dep_type]
        if dep_package.version == '' :
            version = ''
        else :
            version = dep_package.version + "-" + dep_package.revision
        installed = False
        if target_id != INVALID_KEY :
            if Target_Installed_Package.objects.filter(target_id__exact = target_id, package_id__exact = dep_package.id).count() > 0:
                installed = True
        dep =   {
                'name' : dep_package.name,
                'version' : version,
                'size' : dep_package.size,
                'dep_type' : idep.dep_type,
                'dep_type_display' : dep_entry[0].capitalize(),
                'dep_type_help' : dep_entry[1] % (dep_package.name, package.name),
                'depends_on_id' : dep_package.id,
                'installed' : installed,
                }
        if idep.dep_type == rdepends_type :
            runtime_deps.append(dep)
        elif idep.dep_type in other_depends_types :
            other_deps.append(dep)

    rdep_sorted = sorted(runtime_deps, key=lambda k: k['name'])
    odep_sorted = sorted(
            sorted(other_deps, key=lambda k: k['name']),
            key=lambda k: k['dep_type'])
    retvalues = {'runtime_deps' : rdep_sorted, 'other_deps' : odep_sorted}
    return retvalues

# Return the count of packages dependent on package for this target_id image
def get_package_reverse_dep_count(package, target_id):
    return package.package_dependencies_target.filter(target_id__exact=target_id, dep_type__exact = Package_Dependency.TYPE_TRDEPENDS).count()

# Return the count of the packages that this package_id is dependent on.
# Use one of the two RDEPENDS types, either TRDEPENDS if the package was
# installed, or else RDEPENDS if only built.
def get_package_dependency_count(package, target_id, is_installed):
    if is_installed :
        return package.package_dependencies_source.filter(target_id__exact = target_id,
            dep_type__exact = Package_Dependency.TYPE_TRDEPENDS).count()
    else :
        return package.package_dependencies_source.filter(dep_type__exact = Package_Dependency.TYPE_RDEPENDS).count()

def package_built_detail(request, build_id, package_id):
    template = "package_built_detail.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)
    package = Package.objects.filter(pk=package_id)[0]
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'package' : package,
            'dependency_count' : get_package_dependency_count(package, -1, False),
    }
    return render(request, template, context)

def package_built_dependencies(request, build_id, package_id):
    template = "package_built_dependencies.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
         return redirect(builds)

    package = Package.objects.filter(pk=package_id)[0]
    dependencies = get_package_dependencies(package_id)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'package' : package,
            'runtime_deps' : dependencies['runtime_deps'],
            'other_deps' :   dependencies['other_deps'],
            'dependency_count' : get_package_dependency_count(package, -1,  False)
    }
    return render(request, template, context)


def package_included_detail(request, build_id, target_id, package_id):
    template = "package_included_detail.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)

    package = Package.objects.filter(pk=package_id)[0]
    target = Target.objects.filter(pk=target_id)[0]
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'target'  : target,
            'package' : package,
            'reverse_count' : get_package_reverse_dep_count(package, target_id),
            'dependency_count' : get_package_dependency_count(package, target_id, True)
    }
    return render(request, template, context)

def package_included_dependencies(request, build_id, target_id, package_id):
    template = "package_included_dependencies.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)

    package = Package.objects.filter(pk=package_id)[0]
    target = Target.objects.filter(pk=target_id)[0]

    dependencies = get_package_dependencies(package_id, target_id)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'package' : package,
            'target' : target,
            'runtime_deps' : dependencies['runtime_deps'],
            'other_deps' :   dependencies['other_deps'],
            'reverse_count' : get_package_reverse_dep_count(package, target_id),
            'dependency_count' : get_package_dependency_count(package, target_id, True)
    }
    return render(request, template, context)

def package_included_reverse_dependencies(request, build_id, target_id, package_id):
    template = "package_included_reverse_dependencies.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)

    package = Package.objects.filter(pk=package_id)[0]
    target = Target.objects.filter(pk=target_id)[0]

    reverse_deps = []
    alldeps = package.package_dependencies_target.filter(target_id__exact=target_id)
    for idep in alldeps:
        dep_package = Package.objects.get(pk=idep.package_id)
        version = dep_package.version
        if version  != '' :
            version += '-' + dep_package.revision
        dep = {
                'name' : dep_package.name,
                'dependent_id' : dep_package.id,
                'version' : version,
                'size' : dep_package.size
        }
        if idep.dep_type == Package_Dependency.TYPE_TRDEPENDS :
            reverse_deps.append(dep)

    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'package' : package,
            'target' : target,
            'reverse_deps' : reverse_deps,
            'reverse_count' : get_package_reverse_dep_count(package, target_id),
            'dependency_count' : get_package_dependency_count(package, target_id, True)
    }
    return render(request, template, context)

def image_information_dir(request, build_id, target_id, packagefile_id):
    # stubbed for now
    return redirect(builds)

