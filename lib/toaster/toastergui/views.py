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

import operator,re
import HTMLParser

from django.db.models import Q, Sum
from django.db import IntegrityError
from django.shortcuts import render, redirect
from orm.models import Build, Target, Task, Layer, Layer_Version, Recipe, LogMessage, Variable
from orm.models import Task_Dependency, Recipe_Dependency, Package, Package_File, Package_Dependency
from orm.models import Target_Installed_Package, Target_File, Target_Image_File
from django.views.decorators.cache import cache_control
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.utils import timezone
from django.utils.html import escape
from datetime import timedelta
from django.utils import formats
import json

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
    url = reverse(view, kwargs=kwargs)
    params = {}
    for i in g:
        params[i] = g[i]
    for i in mandatory_parameters:
        if not i in params:
            params[i] = mandatory_parameters[i]

    return redirect(url + "?%s" % urllib.urlencode(params), *args, **kwargs)

FIELD_SEPARATOR = ":"
VALUE_SEPARATOR = "!"
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
    return reduce(operator.and_, map(lambda x: __get_q_for_val(x, querydict[x]), [k for k in querydict]))

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
            invalid = "We have an invalid number of separators: " + input + " -> " + str(input_list)
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
        raise BaseException("Invalid ordering model:" + str(model) + str(invalid))

    filter_string, invalid = _validate_input(request.GET.get('filter', ''), model)
    if invalid:
        raise BaseException("Invalid filter " + str(invalid))

    search_term = request.GET.get('search', '')
    return (filter_string, search_term, ordering_string)


# returns a lazy-evaluated queryset for a filter/search/order combination
def _get_queryset(model, queryset, filter_string, search_term, ordering_string, ordering_secondary=''):
    if filter_string:
        filter_query = _get_filtering_query(filter_string)
        queryset = queryset.filter(filter_query)
    else:
        queryset = queryset.all()

    if search_term:
        queryset = _get_search_results(search_term, queryset, model)

    if ordering_string and queryset:
        column, order = ordering_string.split(':')
        if column == re.sub('-','',ordering_secondary):
            ordering_secondary=''
        if order.lower() == DESCENDING:
            column = '-' + column
        if ordering_secondary:
            queryset = queryset.order_by(column, ordering_secondary)
        else:
            queryset = queryset.order_by(column)

    # insure only distinct records (e.g. from multiple search hits) are returned
    return queryset.distinct()

# returns the value of entries per page and the name of the applied sorting field.
# if the value is given explicitly as a GET parameter it will be the first selected,
# otherwise the cookie value will be used.
def _get_parameters_values(request, default_count, default_order):
    pagesize = request.GET.get('count', request.COOKIES.get('count', default_count))
    orderby = request.GET.get('orderby', request.COOKIES.get('orderby', default_order))
    return (pagesize, orderby)


# set cookies for parameters. this is usefull in case parameters are set
# manually from the GET values of the link
def _save_parameters_cookies(response, pagesize, orderby, request):
    html_parser = HTMLParser.HTMLParser()
    response.set_cookie(key='count', value=pagesize, path=request.path)
    response.set_cookie(key='orderby', value=html_parser.unescape(orderby), path=request.path)
    return response

# shows the "all builds" page
def builds(request):
    template = 'build.html'
    # define here what parameters the view needs in the GET portion in order to
    # be able to display something.  'count' and 'page' are mandatory for all views
    # that use paginators.
    (pagesize, orderby) = _get_parameters_values(request, 10, 'completed_on:-')
    mandatory_parameters = { 'count': pagesize,  'page' : 1, 'orderby' : orderby }
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'all-builds', request.GET, mandatory_parameters)

    # boilerplate code that takes a request for an object type and returns a queryset
    # for that object type. copypasta for all needed table searches
    (filter_string, search_term, ordering_string) = _search_tuple(request, Build)
    queryset_all = Build.objects.exclude(outcome = Build.IN_PROGRESS)
    queryset_with_search = _get_queryset(Build, queryset_all, None, search_term, ordering_string, '-completed_on')
    queryset = _get_queryset(Build, queryset_all, filter_string, search_term, ordering_string, '-completed_on')

    # retrieve the objects that will be displayed in the table; builds a paginator and gets a page range to display
    build_info = _build_page_range(Paginator(queryset, pagesize), request.GET.get('page', 1))

    # build view-specific information; this is rendered specifically in the builds page, at the top of the page (i.e. Recent builds)
    build_mru = Build.objects.filter(completed_on__gte=(timezone.now()-timedelta(hours=24))).order_by("-started_on")[:3]

    # set up list of fstypes for each build
    fstypes_map = {};
    for build in build_info:
        targets = Target.objects.filter( build_id = build.id )
        comma = "";
        extensions = "";
        for t in targets:
            if ( not t.is_image ):
                continue
            tif = Target_Image_File.objects.filter( target_id = t.id )
            for i in tif:
                s=re.sub('.*tar.bz2', 'tar.bz2', i.file_name)
                if s == i.file_name:
                    s=re.sub('.*\.', '', i.file_name)
                if None == re.search(s,extensions):
                    extensions += comma + s
                    comma = ", "
        fstypes_map[build.id]=extensions

    # send the data to the template
    context = {
            # specific info for
                'mru' : build_mru,
            # TODO: common objects for all table views, adapt as needed
                'objects' : build_info,
                'objectname' : "builds",
                'default_orderby' : 'completed_on:-',
                'fstypes' : fstypes_map,
                'search_term' : search_term,
                'total_count' : queryset_with_search.count(),
            # Specifies the display of columns for the table, appearance in "Edit columns" box, toggling default show/hide, and specifying filters for columns
                'tablecols' : [
                {'name': 'Outcome',                                                # column with a single filter
                 'qhelp' : "The outcome tells you if a build successfully completed or failed",     # the help button content
                 'dclass' : "span2",                                                # indication about column width; comes from the design
                 'orderfield': _get_toggle_order(request, "outcome"),               # adds ordering by the field value; default ascending unless clicked from ascending into descending
                 'ordericon':_get_toggle_order_icon(request, "outcome"),
                  # filter field will set a filter on that column with the specs in the filter description
                  # the class field in the filter has no relation with clclass; the control different aspects of the UI
                  # still, it is recommended for the values to be identical for easy tracking in the generated HTML
                 'filter' : {'class' : 'outcome',
                             'label': 'Show:',
                             'options' : [
                                         ('Successful builds', 'outcome:' + str(Build.SUCCEEDED), queryset_with_search.filter(outcome=str(Build.SUCCEEDED)).count()),  # this is the field search expression
                                         ('Failed builds', 'outcome:'+ str(Build.FAILED), queryset_with_search.filter(outcome=str(Build.FAILED)).count()),
                                         ]
                            }
                },
                {'name': 'Target',                                                 # default column, disabled box, with just the name in the list
                 'qhelp': "This is the build target or build targets (i.e. one or more recipes or image recipes)",
                 'orderfield': _get_toggle_order(request, "target__target"),
                 'ordericon':_get_toggle_order_icon(request, "target__target"),
                },
                {'name': 'Machine',
                 'qhelp': "The machine is the hardware for which you are building a recipe or image recipe",
                 'orderfield': _get_toggle_order(request, "machine"),
                 'ordericon':_get_toggle_order_icon(request, "machine"),
                 'dclass': 'span3'
                },                           # a slightly wider column
                {'name': 'Started on', 'clclass': 'started_on', 'hidden' : 1,      # this is an unchecked box, which hides the column
                 'qhelp': "The date and time you started the build",
                 'orderfield': _get_toggle_order(request, "started_on", True),
                 'ordericon':_get_toggle_order_icon(request, "started_on"),
                 'filter' : {'class' : 'started_on',
                             'label': 'Show:',
                             'options' : [
                                         ("Today's builds" , 'started_on__gte:'+timezone.now().strftime("%Y-%m-%d"), queryset_with_search.filter(started_on__gte=timezone.now()).count()),
                                         ("Yesterday's builds", 'started_on__gte:'+(timezone.now()-timedelta(hours=24)).strftime("%Y-%m-%d"), queryset_with_search.filter(started_on__gte=(timezone.now()-timedelta(hours=24))).count()),
                                         ("This week's builds", 'started_on__gte:'+(timezone.now()-timedelta(days=7)).strftime("%Y-%m-%d"), queryset_with_search.filter(started_on__gte=(timezone.now()-timedelta(days=7))).count()),
                                         ]
                            }
                },
                {'name': 'Completed on',
                 'qhelp': "The date and time the build finished",
                 'orderfield': _get_toggle_order(request, "completed_on", True),
                 'ordericon':_get_toggle_order_icon(request, "completed_on"),
                 'orderkey' : 'completed_on',
                 'filter' : {'class' : 'completed_on',
                             'label': 'Show:',
                             'options' : [
                                         ("Today's builds", 'completed_on__gte:'+timezone.now().strftime("%Y-%m-%d"), queryset_with_search.filter(completed_on__gte=timezone.now()).count()),
                                         ("Yesterday's builds", 'completed_on__gte:'+(timezone.now()-timedelta(hours=24)).strftime("%Y-%m-%d"), queryset_with_search.filter(completed_on__gte=(timezone.now()-timedelta(hours=24))).count()),
                                         ("This week's builds", 'completed_on__gte:'+(timezone.now()-timedelta(days=7)).strftime("%Y-%m-%d"), queryset_with_search.filter(completed_on__gte=(timezone.now()-timedelta(days=7))).count()),
                                         ]
                            }
                },
                {'name': 'Failed tasks', 'clclass': 'failed_tasks',                # specifing a clclass will enable the checkbox
                 'qhelp': "How many tasks failed during the build",
                 'filter' : {'class' : 'failed_tasks',
                             'label': 'Show:',
                             'options' : [
                                         ('Builds with failed tasks', 'task_build__outcome:4', queryset_with_search.filter(task_build__outcome=4).count()),
                                         ('Builds without failed tasks', 'task_build__outcome:NOT4', queryset_with_search.filter(~Q(task_build__outcome=4)).count()),
                                         ]
                            }
                },
                {'name': 'Errors', 'clclass': 'errors_no',
                 'qhelp': "How many errors were encountered during the build (if any)",
                 'orderfield': _get_toggle_order(request, "errors_no", True),
                 'ordericon':_get_toggle_order_icon(request, "errors_no"),
                 'orderkey' : 'errors_no',
                 'filter' : {'class' : 'errors_no',
                             'label': 'Show:',
                             'options' : [
                                         ('Builds with errors', 'errors_no__gte:1', queryset_with_search.filter(errors_no__gte=1).count()),
                                         ('Builds without errors', 'errors_no:0', queryset_with_search.filter(errors_no=0).count()),
                                         ]
                            }
                },
                {'name': 'Warnings', 'clclass': 'warnings_no',
                 'qhelp': "How many warnings were encountered during the build (if any)",
                 'orderfield': _get_toggle_order(request, "warnings_no", True),
                 'ordericon':_get_toggle_order_icon(request, "warnings_no"),
                 'orderkey' : 'warnings_no',
                 'filter' : {'class' : 'warnings_no',
                             'label': 'Show:',
                             'options' : [
                                         ('Builds with warnings','warnings_no__gte:1', queryset_with_search.filter(warnings_no__gte=1).count()),
                                         ('Builds without warnings','warnings_no:0', queryset_with_search.filter(warnings_no=0).count()),
                                         ]
                            }
                },
                {'name': 'Time', 'clclass': 'time', 'hidden' : 1,
                 'qhelp': "How long it took the build to finish",
                 'orderfield': _get_toggle_order(request, "timespent", True),
                 'ordericon':_get_toggle_order_icon(request, "timespent"),
                 'orderkey' : 'timespent',
                },
                {'name': 'Log',
                 'dclass': "span4",
                 'qhelp': "Path to the build main log file",
                 'clclass': 'log', 'hidden': 1,
                 'orderfield': _get_toggle_order(request, "cooker_log_path"),
                 'ordericon':_get_toggle_order_icon(request, "cooker_log_path"),
                 'orderkey' : 'cooker_log_path',
                },
                {'name': 'Output', 'clclass': 'output',
                 'qhelp': "The root file system types produced by the build. You can find them in your <code>/build/tmp/deploy/images/</code> directory",
                    # TODO: compute image fstypes from Target_Image_File
                },
                ]
            }

    response = render(request, template, context)
    _save_parameters_cookies(response, pagesize, orderby, request)
    return response


##
# build dashboard for a single build, coming in as argument
# Each build may contain multiple targets and each target
# may generate multiple image files. display them all.
#
def builddashboard( request, build_id ):
    template = "builddashboard.html"
    if Build.objects.filter( pk=build_id ).count( ) == 0 :
        return redirect( builds )
    build = Build.objects.filter( pk = build_id )[ 0 ];
    layerVersionId = Layer_Version.objects.filter( build = build_id );
    recipeCount = Recipe.objects.filter( layer_version__id__in = layerVersionId ).count( );
    tgts = Target.objects.filter( build_id = build_id ).order_by( 'target' );

    ##
    # set up custom target list with computed package and image data
    #

    targets = [ ]
    ntargets = 0
    hasImages = False
    targetHasNoImages = False
    for t in tgts:
        elem = { }
        elem[ 'target' ] = t
        if ( t.is_image ):
            hasImages = True
        npkg = 0
        pkgsz = 0
        pid= 0
        tp = Target_Installed_Package.objects.filter( target_id = t.id )
        package = None
        for p in tp:
            pid = p.package_id
            package = Package.objects.get( pk = p.package_id )
            pkgsz = pkgsz + package.size
            if ( package.installed_name ):
                npkg = npkg + 1
        elem[ 'npkg' ] = npkg
        elem[ 'pkgsz' ] = pkgsz
        ti = Target_Image_File.objects.filter( target_id = t.id )
        imageFiles = [ ]
        for i in ti:
            ndx = i.file_name.rfind( '/' )
            if ( ndx < 0 ):
                ndx = 0;
            f = i.file_name[ ndx + 1: ]
            imageFiles.append({ 'path': f, 'size' : i.file_size })
        if ( t.is_image and
             (( len( imageFiles ) <= 0 ) or ( len( t.license_manifest_path ) <= 0 ))):
            targetHasNoImages = True
        elem[ 'imageFiles' ] = imageFiles
        elem[ 'targetHasNoImages' ] = targetHasNoImages
        targets.append( elem )

    ##
    # how many packages in this build - ignore anonymous ones
    #

    packageCount = 0
    packages = Package.objects.filter( build_id = build_id )
    for p in packages:
        if ( p.installed_name ):
            packageCount = packageCount + 1

    context = {
            'build'           : build,
            'hasImages'       : hasImages,
            'ntargets'        : ntargets,
            'targets'         : targets,
            'recipecount'     : recipeCount,
            'packagecount'    : packageCount,
            'logmessages'     : LogMessage.objects.filter( build = build_id ),
    }
    return render( request, template, context )


def generateCoveredList( task ):
    revList = _find_task_revdep( task );
    list = { };
    for t in revList:
        if ( t.outcome == Task.OUTCOME_COVERED ):
            list.update( generateCoveredList( t ));
        else:
            list[ t.task_name ] = t;
    return( list );

def task( request, build_id, task_id ):
    template = "task.html"
    tasks = Task.objects.filter( pk=task_id )
    if tasks.count( ) == 0:
        return redirect( builds )
    task = tasks[ 0 ];
    dependencies = sorted(
        _find_task_dep( task ),
        key=lambda t:'%s_%s %s'%(t.recipe.name, t.recipe.version, t.task_name))
    reverse_dependencies = sorted(
        _find_task_revdep( task ),
        key=lambda t:'%s_%s %s'%( t.recipe.name, t.recipe.version, t.task_name ))
    coveredBy = '';
    if ( task.outcome == Task.OUTCOME_COVERED ):
        dict = generateCoveredList( task )
        coveredBy = [ ]
        for name, t in dict.items( ):
            coveredBy.append( t )
    log_head = ''
    log_body = ''
    if task.outcome == task.OUTCOME_FAILED:
        pass

    uri_list= [ ]
    variables = Variable.objects.filter(build=build_id)
    v=variables.filter(variable_name='SSTATE_DIR')
    if v.count > 0:
        uri_list.append(v[0].variable_value)
    v=variables.filter(variable_name='SSTATE_MIRRORS')
    if (v.count > 0):
        for mirror in v[0].variable_value.split('\\n'):
            s=re.sub('.* ','',mirror.strip(' \t\n\r'))
            if len(s): uri_list.append(s)

    context = {
            'build'           : Build.objects.filter( pk = build_id )[ 0 ],
            'object'          : task,
            'task'            : task,
            'covered_by'      : coveredBy,
            'deps'            : dependencies,
            'rdeps'           : reverse_dependencies,
            'log_head'        : log_head,
            'log_body'        : log_body,
            'showing_matches' : False,
            'uri_list'        : uri_list,
    }
    if request.GET.get( 'show_matches', "" ):
        context[ 'showing_matches' ] = True
        context[ 'matching_tasks' ] = Task.objects.filter(
            sstate_checksum=task.sstate_checksum ).filter(
            build__completed_on__lt=task.build.completed_on).exclude(
            order__isnull=True).exclude(outcome=Task.OUTCOME_NA).order_by('-build__completed_on')

    return render( request, template, context )


def recipe(request, build_id, recipe_id):
    template = "recipe.html"
    if Recipe.objects.filter(pk=recipe_id).count() == 0 :
        return redirect(builds)

    object = Recipe.objects.filter(pk=recipe_id)[0]
    layer_version = Layer_Version.objects.filter(pk=object.layer_version_id)[0]
    layer  = Layer.objects.filter(pk=layer_version.layer_id)[0]
    tasks  = Task.objects.filter(recipe_id = recipe_id, build_id = build_id).exclude(order__isnull=True).exclude(task_name__endswith='_setscene').exclude(outcome=Task.OUTCOME_NA)
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

def target_common( request, build_id, target_id, variant ):
    template = "target.html"
    (pagesize, orderby) = _get_parameters_values(request, 25, 'name:+')
    mandatory_parameters = { 'count': pagesize,  'page' : 1, 'orderby': orderby }
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters(
                    variant, request.GET, mandatory_parameters,
                    build_id = build_id, target_id = target_id )
    ( filter_string, search_term, ordering_string ) = _search_tuple( request, Package )

    # FUTURE:  get rid of nested sub-queries replacing with ManyToMany field
    queryset = Package.objects.filter(
                    size__gte = 0,
                    id__in = Target_Installed_Package.objects.filter(
                        target_id=target_id ).values( 'package_id' ))
    packages_sum =  queryset.aggregate( Sum( 'installed_size' ))
    queryset = _get_queryset(
            Package, queryset, filter_string, search_term, ordering_string, 'name' )
    packages = _build_page_range( Paginator(queryset, pagesize), request.GET.get( 'page', 1 ))

    # bring in package dependencies
    for p in packages.object_list:
        p.runtime_dependencies = p.package_dependencies_source.filter(
            target_id = target_id, dep_type=Package_Dependency.TYPE_TRDEPENDS )
        p.reverse_runtime_dependencies = p.package_dependencies_target.filter(
            target_id = target_id, dep_type=Package_Dependency.TYPE_TRDEPENDS )
    tc_package = {
        'name'       : 'Package',
        'qhelp'      : 'Packaged output resulting from building a recipe included in this image',
        'orderfield' : _get_toggle_order( request, "name" ),
        'ordericon'  : _get_toggle_order_icon( request, "name" ),
        }
    tc_packageVersion = {
        'name'       : 'Package version',
        'qhelp'      : 'The package version and revision',
        }
    tc_size = {
        'name'       : 'Size',
        'qhelp'      : 'The size of the package',
        'orderfield' : _get_toggle_order( request, "size", True ),
        'ordericon'  : _get_toggle_order_icon( request, "size" ),
        'orderkey'   : 'size',
        'clclass'    : 'size',
        'dclass'     : 'span2',
        }
    if ( variant == 'target' ):
        tc_size[ "hidden" ] = 0
    else:
        tc_size[ "hidden" ] = 1
    tc_sizePercentage = {
        'name'       : 'Size over total (%)',
        'qhelp'      : 'Proportion of the overall size represented by this package',
        'orderfield' : _get_toggle_order( request, "size" ),
        'ordericon'  : _get_toggle_order_icon( request, "size" ),
        'clclass'    : 'size_over_total',
        'hidden'     : 1,
        }
    tc_license = {
        'name'       : 'License',
        'qhelp'      : 'The license under which the package is distributed. Separate license names u\
sing | (pipe) means there is a choice between licenses. Separate license names using & (ampersand) m\
eans multiple licenses exist that cover different parts of the source',
        'orderfield' : _get_toggle_order( request, "license" ),
        'ordericon'  : _get_toggle_order_icon( request, "license" ),
        'orderkey'   : 'license',
        'clclass'    : 'license',
        }
    if ( variant == 'target' ):
        tc_license[ "hidden" ] = 1
    else:
        tc_license[ "hidden" ] = 0
    tc_dependencies = {
        'name'       : 'Dependencies',
        'qhelp'      : "Package runtime dependencies (other packages)",
        'clclass'    : 'depends',
        }
    if ( variant == 'target' ):
        tc_dependencies[ "hidden" ] = 0
    else:
        tc_dependencies[ "hidden" ] = 1
    tc_rdependencies = {
        'name'       : 'Reverse dependencies',
        'qhelp'      : 'Package run-time reverse dependencies (i.e. which other packages depend on t\
his package',
        'clclass'    : 'brought_in_by',
        }
    if ( variant == 'target' ):
        tc_rdependencies[ "hidden" ] = 0
    else:
        tc_rdependencies[ "hidden" ] = 1
    tc_recipe = {
        'name'       : 'Recipe',
        'qhelp'      : 'The name of the recipe building the package',
        'orderfield' : _get_toggle_order( request, "recipe__name" ),
        'ordericon'  : _get_toggle_order_icon( request, "recipe__name" ),
        'clclass'    : 'recipe_name',
        'hidden'     : 0,
        }
    tc_recipeVersion = {
        'name'       : 'Recipe version',
        'qhelp'      : 'Version and revision of the recipe building the package',
        'clclass'    : 'recipe_version',
        'hidden'     : 1,
        }
    tc_layer = {
        'name'       : 'Layer',
        'qhelp'      : 'The name of the layer providing the recipe that builds the package',
        'orderfield' : _get_toggle_order( request, "recipe__layer_version__layer__name" ),
        'ordericon'  : _get_toggle_order_icon( request, "recipe__layer_version__layer__name" ),
        'clclass'    : 'layer_name',
        'hidden'     : 1,
        }
    tc_layerBranch = {
        'name'       : 'Layer branch',
        'qhelp'      : 'The Git branch of the layer providing the recipe that builds the package',
        'orderfield' : _get_toggle_order( request, "recipe__layer_version__branch" ),
        'ordericon'  : _get_toggle_order_icon( request, "recipe__layer_version__branch" ),
        'clclass'    : 'layer_branch',
        'hidden'     : 1,
        }
    tc_layerCommit = {
        'name'       : 'Layer commit',
        'qhelp'      : 'The Git commit of the layer providing the recipe that builds the package',
        'clclass'    : 'layer_commit',
        'hidden'     : 1,
        }
    tc_layerDir = {
        'name':'Layer directory',
        'qhelp':'Location in disk of the layer providing the recipe that builds the package',
        'orderfield' : _get_toggle_order( request, "recipe__layer_version__layer__local_path" ),
        'ordericon'  : _get_toggle_order_icon( request, "recipe__layer_version__layer__local_path" )\
,
        'clclass'    : 'layer_directory',
        'hidden'     : 1,
        }
    context = {
        'objectname': variant,
        'build'                : Build.objects.filter( pk = build_id )[ 0 ],
        'target'               : Target.objects.filter( pk = target_id )[ 0 ],
        'objects'              : packages,
        'packages_sum'         : packages_sum[ 'installed_size__sum' ],
        'object_search_display': "packages included",
        'default_orderby'      : orderby,
        'tablecols'            : [
                    tc_package,
                    tc_packageVersion,
                    tc_license,
                    tc_size,
                    tc_sizePercentage,
                    tc_dependencies,
                    tc_rdependencies,
                    tc_recipe,
                    tc_recipeVersion,
                    tc_layer,
                    tc_layerBranch,
                    tc_layerCommit,
                    tc_layerDir,
                ]
        }

    response = render(request, template, context)
    _save_parameters_cookies(response, pagesize, orderby, request)
    return response

def target( request, build_id, target_id ):
    return( target_common( request, build_id, target_id, "target" ))

def targetpkg( request, build_id, target_id ):
    return( target_common( request, build_id, target_id, "targetpkg" ))

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
def dirinfo_ajax(request, build_id, target_id):
    top = request.GET.get('start', '/')
    return HttpResponse(_get_dir_entries(build_id, target_id, top))

from django.utils.functional import Promise
from django.utils.encoding import force_text
class LazyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Promise):
            return force_text(obj)
        return super(LazyEncoder, self).default(obj)

from toastergui.templatetags.projecttags import filtered_filesizeformat
import os
def _get_dir_entries(build_id, target_id, start):
    node_str = {
        Target_File.ITYPE_REGULAR   : '-',
        Target_File.ITYPE_DIRECTORY : 'd',
        Target_File.ITYPE_SYMLINK   : 'l',
        Target_File.ITYPE_SOCKET    : 's',
        Target_File.ITYPE_FIFO      : 'p',
        Target_File.ITYPE_CHARACTER : 'c',
        Target_File.ITYPE_BLOCK     : 'b',
    }
    response = []
    objects  = Target_File.objects.filter(target__exact=target_id, directory__path=start)
    target_packages = Target_Installed_Package.objects.filter(target__exact=target_id).values_list('package_id', flat=True)
    for o in objects:
        # exclude root inode '/'
        if o.path == '/':
            continue
        try:
            entry = {}
            entry['parent'] = start
            entry['name'] = os.path.basename(o.path)
            entry['fullpath'] = o.path

            # set defaults, not all dentries have packages
            entry['installed_package'] = None
            entry['package_id'] = None
            entry['package'] = None
            entry['link_to'] = None
            if o.inodetype == Target_File.ITYPE_DIRECTORY:
                entry['isdir'] = 1
                # is there content in directory
                entry['childcount'] = Target_File.objects.filter(target__exact=target_id, directory__path=o.path).all().count()
            else:
                entry['isdir'] = 0

                # resolve the file to get the package from the resolved file
                resolved_id = o.sym_target_id
                resolved_path = o.path
                if target_packages.count():
                    while resolved_id != "" and resolved_id != None:
                        tf = Target_File.objects.get(pk=resolved_id)
                        resolved_path = tf.path
                        resolved_id = tf.sym_target_id

                    thisfile=Package_File.objects.all().filter(path__exact=resolved_path, package_id__in=target_packages)
                    if thisfile.count():
                        p = Package.objects.get(pk=thisfile[0].package_id)
                        entry['installed_package'] = p.installed_name
                        entry['package_id'] = str(p.id)
                        entry['package'] = p.name
                # don't use resolved path from above, show immediate link-to
                if o.sym_target_id != "" and o.sym_target_id != None:
                    entry['link_to'] = Target_File.objects.get(pk=o.sym_target_id).path
            entry['size'] = filtered_filesizeformat(o.size)
            if entry['link_to'] != None:
                entry['permission'] = node_str[o.inodetype] + o.permission
            else:
                entry['permission'] = node_str[o.inodetype] + o.permission
            entry['owner'] = o.owner
            entry['group'] = o.group
            response.append(entry)

        except Exception as e:
            print "Exception ", e
            import traceback
            traceback.print_exc(e)
            pass

    # sort by directories first, then by name
    rsorted = sorted(response, key=lambda entry :  entry['name'])
    rsorted = sorted(rsorted, key=lambda entry :  entry['isdir'], reverse=True)
    return json.dumps(rsorted, cls=LazyEncoder)

def dirinfo(request, build_id, target_id, file_path=None):
    template = "dirinfo.html"
    objects = _get_dir_entries(build_id, target_id, '/')
    packages_sum = Package.objects.filter(id__in=Target_Installed_Package.objects.filter(target_id=target_id).values('package_id')).aggregate(Sum('installed_size'))
    dir_list = None
    if file_path != None:
        """
        Link from the included package detail file list page and is
        requesting opening the dir info to a specific file path.
        Provide the list of directories to expand and the full path to
        highlight in the page.
        """
        # Aassume target's path separator matches host's, that is, os.sep
        sep = os.sep
        dir_list = []
        head = file_path
        while head != sep:
            (head,tail) = os.path.split(head)
            if head != sep:
                dir_list.insert(0, head)

    context = { 'build': Build.objects.filter(pk=build_id)[0],
                'target': Target.objects.filter(pk=target_id)[0],
                'packages_sum': packages_sum['installed_size__sum'],
                'objects': objects,
                'dir_list': dir_list,
                'file_path': file_path,
              }
    return render(request, template, context)

def _find_task_dep(task):
    tp = []
    for p in Task_Dependency.objects.filter(task=task):
        if (p.depends_on.order > 0) and (p.depends_on.outcome != Task.OUTCOME_NA):
            tp.append(p.depends_on);
    return tp


def _find_task_revdep(task):
    tp = []
    for p in Task_Dependency.objects.filter(depends_on=task):
        if (p.task.order > 0) and (p.task.outcome != Task.OUTCOME_NA):
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

def tasks_common(request, build_id, variant, task_anchor):
# This class is shared between these pages
#
# Column    tasks  buildtime  diskio  cpuusage
# --------- ------ ---------- ------- ---------
# Cache      def
# CPU                                   min -
# Disk                         min -
# Executed   def     def       def      def
# Log
# Order      def +
# Outcome    def     def       def      def
# Recipe     min     min       min      min
# Version
# Task       min     min       min      min
# Time               min -
#
# 'min':on always, 'def':on by default, else hidden
# '+' default column sort up, '-' default column sort down

    anchor = request.GET.get('anchor', '')
    if not anchor:
        anchor=task_anchor

    # default ordering depends on variant
    if   'buildtime' == variant:
        title_variant='Time'
        object_search_display="time data"
        filter_search_display="tasks"
        (pagesize, orderby) = _get_parameters_values(request, 25, 'elapsed_time:-')
    elif 'diskio'    == variant:
        title_variant='Disk I/O'
        object_search_display="disk I/O data"
        filter_search_display="tasks"
        (pagesize, orderby) = _get_parameters_values(request, 25, 'disk_io:-')
    elif 'cpuusage'  == variant:
        title_variant='CPU usage'
        object_search_display="CPU usage data"
        filter_search_display="tasks"
        (pagesize, orderby) = _get_parameters_values(request, 25, 'cpu_usage:-')
    else :
        title_variant='Tasks'
        object_search_display="tasks"
        filter_search_display="tasks"
        (pagesize, orderby) = _get_parameters_values(request, 25, 'order:+')


    mandatory_parameters = { 'count': pagesize,  'page' : 1, 'orderby': orderby }

    template = 'tasks.html'
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        if task_anchor:
            mandatory_parameters['anchor']=task_anchor
        return _redirect_parameters( variant, request.GET, mandatory_parameters, build_id = build_id)
    (filter_string, search_term, ordering_string) = _search_tuple(request, Task)
    queryset_all = Task.objects.filter(build=build_id).exclude(order__isnull=True).exclude(outcome=Task.OUTCOME_NA)
    queryset_with_search = _get_queryset(Task, queryset_all, None , search_term, ordering_string, 'order')
    if ordering_string.startswith('outcome'):
        queryset = _get_queryset(Task, queryset_all, filter_string, search_term, 'order:+', 'order')
        queryset = sorted(queryset, key=lambda ur: (ur.outcome_text), reverse=ordering_string.endswith('-'))
    elif ordering_string.startswith('sstate_result'):
        queryset = _get_queryset(Task, queryset_all, filter_string, search_term, 'order:+', 'order')
        queryset = sorted(queryset, key=lambda ur: (ur.sstate_text), reverse=ordering_string.endswith('-'))
    else:
        queryset = _get_queryset(Task, queryset_all, filter_string, search_term, ordering_string, 'order')

    # compute the anchor's page
    if anchor:
        request.GET = request.GET.copy()
        del request.GET['anchor']
        i=0
        a=int(anchor)
        count_per_page=int(pagesize)
        for task in queryset.iterator():
            if a == task.order:
                new_page= (i / count_per_page ) + 1
                request.GET.__setitem__('page', new_page)
                mandatory_parameters['page']=new_page
                return _redirect_parameters( variant, request.GET, mandatory_parameters, build_id = build_id)
            i += 1

    tasks = _build_page_range(Paginator(queryset, pagesize),request.GET.get('page', 1))

    # define (and modify by variants) the 'tablecols' members
    tc_order={
        'name':'Order',
        'qhelp':'The running sequence of each task in the build',
        'clclass': 'order', 'hidden' : 1,
        'orderkey' : 'order',
        'orderfield':_get_toggle_order(request, "order"),
        'ordericon':_get_toggle_order_icon(request, "order")}
    if 'tasks' == variant: tc_order['hidden']='0'; del tc_order['clclass']
    tc_recipe={
        'name':'Recipe',
        'qhelp':'The name of the recipe to which each task applies',
        'orderkey' : 'recipe__name',
        'orderfield': _get_toggle_order(request, "recipe__name"),
        'ordericon':_get_toggle_order_icon(request, "recipe__name"),
    }
    tc_recipe_version={
        'name':'Recipe version',
        'qhelp':'The version of the recipe to which each task applies',
        'clclass': 'recipe_version', 'hidden' : 1,
    }
    tc_task={
        'name':'Task',
        'qhelp':'The name of the task',
        'orderfield': _get_toggle_order(request, "task_name"),
        'ordericon':_get_toggle_order_icon(request, "task_name"),
        'orderkey' : 'task_name',
    }
    tc_executed={
        'name':'Executed',
        'qhelp':"This value tells you if a task had to run (executed) in order to generate the task output, or if the output was provided by another task and therefore the task didn't need to run (not executed)",
        'clclass': 'executed', 'hidden' : 0,
        'orderfield': _get_toggle_order(request, "task_executed"),
        'ordericon':_get_toggle_order_icon(request, "task_executed"),
        'orderkey' : 'task_executed',
        'filter' : {
                   'class' : 'executed',
                   'label': 'Show:',
                   'options' : [
                               ('Executed Tasks', 'task_executed:1', queryset_with_search.filter(task_executed=1).count()),
                               ('Not Executed Tasks', 'task_executed:0', queryset_with_search.filter(task_executed=0).count()),
                               ]
                   }

    }
    tc_outcome={
        'name':'Outcome',
        'qhelp':"This column tells you if 'executed' tasks succeeded or failed. The column also tells you why 'not executed' tasks did not need to run",
        'clclass': 'outcome', 'hidden' : 0,
        'orderfield': _get_toggle_order(request, "outcome"),
        'ordericon':_get_toggle_order_icon(request, "outcome"),
        'orderkey' : 'outcome',
        'filter' : {
                   'class' : 'outcome',
                   'label': 'Show:',
                   'options' : [
                               ('Succeeded Tasks', 'outcome:%d'%Task.OUTCOME_SUCCESS, queryset_with_search.filter(outcome=Task.OUTCOME_SUCCESS).count(), "'Succeeded' tasks are those that ran and completed during the build" ),
                               ('Failed Tasks', 'outcome:%d'%Task.OUTCOME_FAILED, queryset_with_search.filter(outcome=Task.OUTCOME_FAILED).count(), "'Failed' tasks are those that ran but did not complete during the build"),
                               ('Cached Tasks', 'outcome:%d'%Task.OUTCOME_CACHED, queryset_with_search.filter(outcome=Task.OUTCOME_CACHED).count(), 'Cached tasks restore output from the <code>sstate-cache</code> directory or mirrors'),
                               ('Prebuilt Tasks', 'outcome:%d'%Task.OUTCOME_PREBUILT, queryset_with_search.filter(outcome=Task.OUTCOME_PREBUILT).count(),'Prebuilt tasks didn\'t need to run because their output was reused from a previous build'),
                               ('Covered Tasks', 'outcome:%d'%Task.OUTCOME_COVERED, queryset_with_search.filter(outcome=Task.OUTCOME_COVERED).count(), 'Covered tasks didn\'t need to run because their output is provided by another task in this build'),
                               ('Empty Tasks', 'outcome:%d'%Task.OUTCOME_EMPTY, queryset_with_search.filter(outcome=Task.OUTCOME_EMPTY).count(), 'Empty tasks have no executable content'),
                               ]
                   }

    }
    tc_log={
        'name':'Log',
        'qhelp':'Path to the task log file',
        'orderfield': _get_toggle_order(request, "logfile"),
        'ordericon':_get_toggle_order_icon(request, "logfile"),
        'orderkey' : 'logfile',
        'clclass': 'task_log', 'hidden' : 1,
    }
    tc_cache={
        'name':'Cache attempt',
        'qhelp':'This column tells you if a task tried to restore output from the <code>sstate-cache</code> directory or mirrors, and reports the result: Succeeded, Failed or File not in cache',
        'clclass': 'cache_attempt', 'hidden' : 0,
        'orderfield': _get_toggle_order(request, "sstate_result"),
        'ordericon':_get_toggle_order_icon(request, "sstate_result"),
        'orderkey' : 'sstate_result',
        'filter' : {
                   'class' : 'cache_attempt',
                   'label': 'Show:',
                   'options' : [
                               ('Tasks with cache attempts', 'sstate_result__gt:%d'%Task.SSTATE_NA, queryset_with_search.filter(sstate_result__gt=Task.SSTATE_NA).count(), 'Show all tasks that tried to restore ouput from the <code>sstate-cache</code> directory or mirrors'),
                               ("Tasks with 'File not in cache' attempts", 'sstate_result:%d'%Task.SSTATE_MISS,  queryset_with_search.filter(sstate_result=Task.SSTATE_MISS).count(), 'Show tasks that tried to restore output, but did not find it in the <code>sstate-cache</code> directory or mirrors'),
                               ("Tasks with 'Failed' cache attempts", 'sstate_result:%d'%Task.SSTATE_FAILED,  queryset_with_search.filter(sstate_result=Task.SSTATE_FAILED).count(), 'Show tasks that found the required output in the <code>sstate-cache</code> directory or mirrors, but could not restore it'),
                               ("Tasks with 'Succeeded' cache attempts", 'sstate_result:%d'%Task.SSTATE_RESTORED,  queryset_with_search.filter(sstate_result=Task.SSTATE_RESTORED).count(), 'Show tasks that successfully restored the required output from the <code>sstate-cache</code> directory or mirrors'),
                               ]
                   }

    }
    #if   'tasks' == variant: tc_cache['hidden']='0';
    tc_time={
        'name':'Time (secs)',
        'qhelp':'How long it took the task to finish in seconds',
        'orderfield': _get_toggle_order(request, "elapsed_time", True),
        'ordericon':_get_toggle_order_icon(request, "elapsed_time"),
        'orderkey' : 'elapsed_time',
        'clclass': 'time_taken', 'hidden' : 1,
    }
    if   'buildtime' == variant: tc_time['hidden']='0'; del tc_time['clclass']; tc_cache['hidden']='1';
    tc_cpu={
        'name':'CPU usage',
        'qhelp':'The percentage of task CPU utilization',
        'orderfield': _get_toggle_order(request, "cpu_usage", True),
        'ordericon':_get_toggle_order_icon(request, "cpu_usage"),
        'orderkey' : 'cpu_usage',
        'clclass': 'cpu_used', 'hidden' : 1,
    }
    if   'cpuusage' == variant: tc_cpu['hidden']='0'; del tc_cpu['clclass']; tc_cache['hidden']='1';
    tc_diskio={
        'name':'Disk I/O (ms)',
        'qhelp':'Number of miliseconds the task spent doing disk input and output',
        'orderfield': _get_toggle_order(request, "disk_io", True),
        'ordericon':_get_toggle_order_icon(request, "disk_io"),
        'orderkey' : 'disk_io',
        'clclass': 'disk_io', 'hidden' : 1,
    }
    if   'diskio' == variant: tc_diskio['hidden']='0'; del tc_diskio['clclass']; tc_cache['hidden']='1';


    context = { 'objectname': variant,
                'object_search_display': object_search_display,
                'filter_search_display': filter_search_display,
                'title': title_variant,
                'build': Build.objects.filter(pk=build_id)[0],
                'objects': tasks,
                'default_orderby' : orderby,
                'search_term': search_term,
                'total_count': queryset_with_search.count(),
                'tablecols':[
                    tc_order,
                    tc_recipe,
                    tc_recipe_version,
                    tc_task,
                    tc_executed,
                    tc_outcome,
                    tc_cache,
                    tc_time,
                    tc_cpu,
                    tc_diskio,
                    tc_log,
                ]}

    response = render(request, template, context)
    _save_parameters_cookies(response, pagesize, orderby, request)
    return response

def tasks(request, build_id):
    return tasks_common(request, build_id, 'tasks', '')

def tasks_task(request, build_id, task_id):
    return tasks_common(request, build_id, 'tasks', task_id)

def buildtime(request, build_id):
    return tasks_common(request, build_id, 'buildtime', '')

def diskio(request, build_id):
    return tasks_common(request, build_id, 'diskio', '')

def cpuusage(request, build_id):
    return tasks_common(request, build_id, 'cpuusage', '')


def recipes(request, build_id):
    template = 'recipes.html'
    (pagesize, orderby) = _get_parameters_values(request, 100, 'name:+')
    mandatory_parameters = { 'count': pagesize,  'page' : 1, 'orderby' : orderby }
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'recipes', request.GET, mandatory_parameters, build_id = build_id)
    (filter_string, search_term, ordering_string) = _search_tuple(request, Recipe)
    queryset = Recipe.objects.filter(layer_version__id__in=Layer_Version.objects.filter(build=build_id))
    queryset = _get_queryset(Recipe, queryset, filter_string, search_term, ordering_string, 'name')

    recipes = _build_page_range(Paginator(queryset, pagesize),request.GET.get('page', 1))

    # prefetch the forward and reverse recipe dependencies
    deps = { }; revs = { }
    queryset_dependency=Recipe_Dependency.objects.filter(recipe__layer_version__build_id = build_id)
    for recipe in recipes:
        deplist = [ ]
        for recipe_dep in [x for x in queryset_dependency if x.recipe_id == recipe.id]:
            deplist.append(recipe_dep)
        deps[recipe.id] = deplist
        revlist = [ ]
        for recipe_dep in [x for x in queryset_dependency if x.depends_on_id == recipe.id]:
            revlist.append(recipe_dep)
        revs[recipe.id] = revlist

    context = {
        'objectname': 'recipes',
        'build': Build.objects.filter(pk=build_id)[0],
        'objects': recipes,
        'default_orderby' : 'name:+',
        'recipe_deps' : deps,
        'recipe_revs' : revs,
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
                'qhelp':'Recipe build-time dependencies (i.e. other recipes)',
                'clclass': 'depends_on', 'hidden': 1,
            },
            {
                'name':'Reverse dependencies',
                'qhelp':'Recipe build-time reverse dependencies (i.e. the recipes that depend on this recipe)',
                'clclass': 'depends_by', 'hidden': 1,
            },
            {
                'name':'Recipe file',
                'qhelp':'Path to the recipe .bb file',
                'orderfield': _get_toggle_order(request, "file_path"),
                'ordericon':_get_toggle_order_icon(request, "file_path"),
                'orderkey' : 'file_path',
                'clclass': 'recipe_file', 'hidden': 0,
            },
            {
                'name':'Section',
                'qhelp':'The section in which recipes should be categorized',
                'orderfield': _get_toggle_order(request, "section"),
                'ordericon':_get_toggle_order_icon(request, "section"),
                'orderkey' : 'section',
                'clclass': 'recipe_section', 'hidden': 0,
            },
            {
                'name':'License',
                'qhelp':'The list of source licenses for the recipe. Multiple license names separated by the pipe character indicates a choice between licenses. Multiple license names separated by the ampersand character indicates multiple licenses exist that cover different parts of the source',
                'orderfield': _get_toggle_order(request, "license"),
                'ordericon':_get_toggle_order_icon(request, "license"),
                'orderkey' : 'license',
                'clclass': 'recipe_license', 'hidden': 0,
            },
            {
                'name':'Layer',
                'qhelp':'The name of the layer providing the recipe',
                'orderfield': _get_toggle_order(request, "layer_version__layer__name"),
                'ordericon':_get_toggle_order_icon(request, "layer_version__layer__name"),
                'orderkey' : 'layer_version__layer__name',
                'clclass': 'layer_version__layer__name', 'hidden': 0,
            },
            {
                'name':'Layer branch',
                'qhelp':'The Git branch of the layer providing the recipe',
                'orderfield': _get_toggle_order(request, "layer_version__branch"),
                'ordericon':_get_toggle_order_icon(request, "layer_version__branch"),
                'orderkey' : 'layer_version__branch',
                'clclass': 'layer_version__branch', 'hidden': 1,
            },
            {
                'name':'Layer commit',
                'qhelp':'The Git commit of the layer providing the recipe',
                'clclass': 'layer_version__layer__commit', 'hidden': 1,
            },
            {
                'name':'Layer directory',
                'qhelp':'Path to the layer prodiving the recipe',
                'orderfield': _get_toggle_order(request, "layer_version__layer__local_path"),
                'ordericon':_get_toggle_order_icon(request, "layer_version__layer__local_path"),
                'orderkey' : 'layer_version__layer__local_path',
                'clclass': 'layer_version__layer__local_path', 'hidden': 1,
            },
            ]
        }

    response = render(request, template, context)
    _save_parameters_cookies(response, pagesize, orderby, request)
    return response

def configuration(request, build_id):
    template = 'configuration.html'

    variables = Variable.objects.filter(build=build_id)
    BB_VERSION=variables.filter(variable_name='BB_VERSION')[0].variable_value
    BUILD_SYS=variables.filter(variable_name='BUILD_SYS')[0].variable_value
    NATIVELSBSTRING=variables.filter(variable_name='NATIVELSBSTRING')[0].variable_value
    TARGET_SYS=variables.filter(variable_name='TARGET_SYS')[0].variable_value
    MACHINE=variables.filter(variable_name='MACHINE')[0].variable_value
    DISTRO=variables.filter(variable_name='DISTRO')[0].variable_value
    DISTRO_VERSION=variables.filter(variable_name='DISTRO_VERSION')[0].variable_value
    TUNE_FEATURES=variables.filter(variable_name='TUNE_FEATURES')[0].variable_value
    TARGET_FPU=variables.filter(variable_name='TARGET_FPU')[0].variable_value

    targets = Target.objects.filter(build=build_id)

    context = {
                'objectname': 'configuration',
                'object_search_display':'variables',
                'filter_search_display':'variables',
                'build': Build.objects.filter(pk=build_id)[0],
                'BB_VERSION':BB_VERSION,
                'BUILD_SYS':BUILD_SYS,
                'NATIVELSBSTRING':NATIVELSBSTRING,
                'TARGET_SYS':TARGET_SYS,
                'MACHINE':MACHINE,
                'DISTRO':DISTRO,
                'DISTRO_VERSION':DISTRO_VERSION,
                'TUNE_FEATURES':TUNE_FEATURES,
                'TARGET_FPU':TARGET_FPU,
                'targets':targets,
        }
    return render(request, template, context)


def configvars(request, build_id):
    template = 'configvars.html'
    (pagesize, orderby) = _get_parameters_values(request, 100, 'variable_name:+')
    mandatory_parameters = { 'count': pagesize,  'page' : 1, 'orderby' : orderby, 'filter' : 'description__regex:.+' }
    retval = _verify_parameters( request.GET, mandatory_parameters )
    (filter_string, search_term, ordering_string) = _search_tuple(request, Variable)
    if retval:
        # if new search, clear the default filter
        if search_term and len(search_term):
            mandatory_parameters['filter']=''
        return _redirect_parameters( 'configvars', request.GET, mandatory_parameters, build_id = build_id)

    queryset = Variable.objects.filter(build=build_id).exclude(variable_name__istartswith='B_').exclude(variable_name__istartswith='do_')
    queryset_with_search =  _get_queryset(Variable, queryset, None, search_term, ordering_string, 'variable_name').exclude(variable_value='',vhistory__file_name__isnull=True)
    queryset = _get_queryset(Variable, queryset, filter_string, search_term, ordering_string, 'variable_name')
    # remove records where the value is empty AND there are no history files
    queryset = queryset.exclude(variable_value='',vhistory__file_name__isnull=True)

    variables = _build_page_range(Paginator(queryset, pagesize), request.GET.get('page', 1))

    # show all matching files (not just the last one)
    file_filter= search_term + ":"
    if filter_string.find('/conf/') > 0:
        file_filter += 'conf/(local|bblayers).conf'
    if filter_string.find('conf/machine/') > 0:
        file_filter += 'conf/machine/'
    if filter_string.find('conf/distro/') > 0:
        file_filter += 'conf/distro/'
    if filter_string.find('/bitbake.conf') > 0:
        file_filter += '/bitbake.conf'
    build_dir=re.sub("/tmp/log/.*","",Build.objects.filter(pk=build_id)[0].cooker_log_path)

    context = {
                'objectname': 'configvars',
                'object_search_display':'BitBake variables',
                'filter_search_display':'variables',
                'file_filter': file_filter,
                'build': Build.objects.filter(pk=build_id)[0],
                'objects' : variables,
                'total_count':queryset_with_search.count(),
                'default_orderby' : 'variable_name:+',
                'search_term':search_term,
            # Specifies the display of columns for the table, appearance in "Edit columns" box, toggling default show/hide, and specifying filters for columns
                'tablecols' : [
                {'name': 'Variable',
                 'qhelp': "BitBake is a generic task executor that considers a list of tasks with dependencies and handles metadata that consists of variables in a certain format that get passed to the tasks",
                 'orderfield': _get_toggle_order(request, "variable_name"),
                 'ordericon':_get_toggle_order_icon(request, "variable_name"),
                },
                {'name': 'Value',
                 'qhelp': "The value assigned to the variable",
                 'dclass': "span4",
                },
                {'name': 'Set in file',
                 'qhelp': "The last configuration file that touched the variable value",
                 'clclass': 'file', 'hidden' : 0,
                 'orderkey' : 'vhistory__file_name',
                 'filter' : {
                    'class' : 'vhistory__file_name',
                    'label': 'Show:',
                    'options' : [
                               ('Local configuration variables', 'vhistory__file_name__contains:'+build_dir+'/conf/',queryset_with_search.filter(vhistory__file_name__contains=build_dir+'/conf/').count(), 'Select this filter to see variables set by the <code>local.conf</code> and <code>bblayers.conf</code> configuration files inside the <code>/build/conf/</code> directory'),
                               ('Machine configuration variables', 'vhistory__file_name__contains:conf/machine/',queryset_with_search.filter(vhistory__file_name__contains='conf/machine').count(), 'Select this filter to see variables set by the configuration file(s) inside your layers <code>/conf/machine/</code> directory'),
                               ('Distro configuration variables', 'vhistory__file_name__contains:conf/distro/',queryset_with_search.filter(vhistory__file_name__contains='conf/distro').count(), 'Select this filter to see variables set by the configuration file(s) inside your layers <code>/conf/distro/</code> directory'),
                               ('Layer configuration variables', 'vhistory__file_name__contains:conf/layer.conf',queryset_with_search.filter(vhistory__file_name__contains='conf/layer.conf').count(), 'Select this filter to see variables set by the <code>layer.conf</code> configuration file inside your layers'),
                               ('bitbake.conf variables', 'vhistory__file_name__contains:/bitbake.conf',queryset_with_search.filter(vhistory__file_name__contains='/bitbake.conf').count(), 'Select this filter to see variables set by the <code>bitbake.conf</code> configuration file'),
                               ]
                             },
                },
                {'name': 'Description',
                 'qhelp': "A brief explanation of the variable",
                 'clclass': 'description', 'hidden' : 0,
                 'dclass': "span4",
                 'filter' : {
                    'class' : 'description',
                    'label': 'Show:',
                    'options' : [
                               ('Variables with description', 'description__regex:.+', queryset_with_search.filter(description__regex='.+').count(), 'We provide descriptions for the most common BitBake variables. The list of descriptions lives in <code>meta/conf/documentation.conf</code>'),
                               ]
                            },
                },
                ],
            }

    response = render(request, template, context)
    _save_parameters_cookies(response, pagesize, orderby, request)
    return response

def bpackage(request, build_id):
    template = 'bpackage.html'
    (pagesize, orderby) = _get_parameters_values(request, 100, 'name:+')
    mandatory_parameters = { 'count' : pagesize,  'page' : 1, 'orderby' : orderby }
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'packages', request.GET, mandatory_parameters, build_id = build_id)
    (filter_string, search_term, ordering_string) = _search_tuple(request, Package)
    queryset = Package.objects.filter(build = build_id).filter(size__gte=0)
    queryset = _get_queryset(Package, queryset, filter_string, search_term, ordering_string, 'name')

    packages = _build_page_range(Paginator(queryset, pagesize),request.GET.get('page', 1))

    context = {
        'objectname': 'packages built',
        'build': Build.objects.filter(pk=build_id)[0],
        'objects' : packages,
        'default_orderby' : 'name:+',
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
                'orderfield': _get_toggle_order(request, "size", True),
                'ordericon':_get_toggle_order_icon(request, "size"),
                'orderkey' : 'size',
                'clclass': 'size', 'hidden': 0,
                'dclass' : 'span2',
            },
            {
                'name':'License',
                'qhelp':'The license under which the package is distributed. Multiple license names separated by the pipe character indicates a choice between licenses. Multiple license names separated by the ampersand character indicates multiple licenses exist that cover different parts of the source',
                'orderfield': _get_toggle_order(request, "license"),
                'ordericon':_get_toggle_order_icon(request, "license"),
                'orderkey' : 'license',
                'clclass': 'license', 'hidden': 1,
            },
            {
                'name':'Recipe',
                'qhelp':'The name of the recipe building the package',
                'orderfield': _get_toggle_order(request, "recipe__name"),
                'ordericon':_get_toggle_order_icon(request, "recipe__name"),
                'orderkey' : 'recipe__name',
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
                'orderkey' : 'recipe__layer_version__layer__name',
                'clclass': 'recipe__layer_version__layer__name', 'hidden': 1,
            },
            {
                'name':'Layer branch',
                'qhelp':'The Git branch of the layer providing the recipe that builds the package',
                'orderfield': _get_toggle_order(request, "recipe__layer_version__branch"),
                'ordericon':_get_toggle_order_icon(request, "recipe__layer_version__branch"),
                'orderkey' : 'recipe__layer_version__layer__branch',
                'clclass': 'recipe__layer_version__branch', 'hidden': 1,
            },
            {
                'name':'Layer commit',
                'qhelp':'The Git commit of the layer providing the recipe that builds the package',
                'clclass': 'recipe__layer_version__layer__commit', 'hidden': 1,
            },
            {
                'name':'Layer directory',
                'qhelp':'Path to the layer providing the recipe that builds the package',
                'orderfield': _get_toggle_order(request, "recipe__layer_version__layer__local_path"),
                'ordericon':_get_toggle_order_icon(request, "recipe__layer_version__layer__local_path"),
                'orderkey' : 'recipe__layer_version__layer__local_path',
                'clclass': 'recipe__layer_version__layer__local_path', 'hidden': 1,
            },
            ]
        }

    response = render(request, template, context)
    _save_parameters_cookies(response, pagesize, orderby, request)
    return response

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
def _get_package_dependencies(package_id, target_id = INVALID_KEY):
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

        if target_id != INVALID_KEY:
                dep['alias'] = _get_package_alias(dep_package)

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
def _get_package_reverse_dep_count(package, target_id):
    return package.package_dependencies_target.filter(target_id__exact=target_id, dep_type__exact = Package_Dependency.TYPE_TRDEPENDS).count()

# Return the count of the packages that this package_id is dependent on.
# Use one of the two RDEPENDS types, either TRDEPENDS if the package was
# installed, or else RDEPENDS if only built.
def _get_package_dependency_count(package, target_id, is_installed):
    if is_installed :
        return package.package_dependencies_source.filter(target_id__exact = target_id,
            dep_type__exact = Package_Dependency.TYPE_TRDEPENDS).count()
    else :
        return package.package_dependencies_source.filter(dep_type__exact = Package_Dependency.TYPE_RDEPENDS).count()

def _get_package_alias(package):
    alias = package.installed_name
    if alias != None and alias != '' and alias != package.name:
        return alias
    else:
        return ''

def _get_fullpackagespec(package):
    r = package.name
    version_good = package.version != None and  package.version != ''
    revision_good = package.revision != None and package.revision != ''
    if version_good or revision_good:
        r += '_'
        if version_good:
            r += package.version
            if revision_good:
                r += '-'
        if revision_good:
            r += package.revision
    return r

def package_built_detail(request, build_id, package_id):
    template = "package_built_detail.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)

    # follow convention for pagination w/ search although not used for this view
    queryset = Package_File.objects.filter(package_id__exact=package_id)
    (pagesize, orderby) = _get_parameters_values(request, 25, 'path:+')
    mandatory_parameters = { 'count': pagesize,  'page' : 1, 'orderby' : orderby }
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'package_built_detail', request.GET, mandatory_parameters, build_id = build_id, package_id = package_id)

    (filter_string, search_term, ordering_string) = _search_tuple(request, Package_File)
    paths = _get_queryset(Package_File, queryset, filter_string, search_term, ordering_string, 'path')

    package = Package.objects.filter(pk=package_id)[0]
    package.fullpackagespec = _get_fullpackagespec(package)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'package' : package,
            'dependency_count' : _get_package_dependency_count(package, -1, False),
            'objects' : paths,
            'tablecols':[
                {
                    'name':'File',
                    'orderfield': _get_toggle_order(request, "path"),
                    'ordericon':_get_toggle_order_icon(request, "path"),
                },
                {
                    'name':'Size',
                    'orderfield': _get_toggle_order(request, "size", True),
                    'ordericon':_get_toggle_order_icon(request, "size"),
                    'dclass': 'sizecol span2',
                },
            ]
    }
    if paths.all().count() < 2:
        context['disable_sort'] = True;

    response = render(request, template, context)
    _save_parameters_cookies(response, pagesize, orderby, request)
    return response

def package_built_dependencies(request, build_id, package_id):
    template = "package_built_dependencies.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
         return redirect(builds)

    package = Package.objects.filter(pk=package_id)[0]
    package.fullpackagespec = _get_fullpackagespec(package)
    dependencies = _get_package_dependencies(package_id)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'package' : package,
            'runtime_deps' : dependencies['runtime_deps'],
            'other_deps' :   dependencies['other_deps'],
            'dependency_count' : _get_package_dependency_count(package, -1,  False)
    }
    return render(request, template, context)


def package_included_detail(request, build_id, target_id, package_id):
    template = "package_included_detail.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)

    # follow convention for pagination w/ search although not used for this view
    (pagesize, orderby) = _get_parameters_values(request, 25, 'path:+')
    mandatory_parameters = { 'count': pagesize,  'page' : 1, 'orderby' : orderby }
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'package_included_detail', request.GET, mandatory_parameters, build_id = build_id, target_id = target_id, package_id = package_id)
    (filter_string, search_term, ordering_string) = _search_tuple(request, Package_File)

    queryset = Package_File.objects.filter(package_id__exact=package_id)
    paths = _get_queryset(Package_File, queryset, filter_string, search_term, ordering_string, 'path')

    package = Package.objects.filter(pk=package_id)[0]
    package.fullpackagespec = _get_fullpackagespec(package)
    package.alias = _get_package_alias(package)
    target = Target.objects.filter(pk=target_id)[0]
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'target'  : target,
            'package' : package,
            'reverse_count' : _get_package_reverse_dep_count(package, target_id),
            'dependency_count' : _get_package_dependency_count(package, target_id, True),
            'objects': paths,
            'tablecols':[
                {
                    'name':'File',
                    'orderfield': _get_toggle_order(request, "path"),
                    'ordericon':_get_toggle_order_icon(request, "path"),
                },
                {
                    'name':'Size',
                    'orderfield': _get_toggle_order(request, "size", True),
                    'ordericon':_get_toggle_order_icon(request, "size"),
                    'dclass': 'sizecol span2',
                },
            ]
    }
    if paths.all().count() < 2:
        context['disable_sort'] = True
    response = render(request, template, context)
    _save_parameters_cookies(response, pagesize, orderby, request)
    return response

def package_included_dependencies(request, build_id, target_id, package_id):
    template = "package_included_dependencies.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)

    package = Package.objects.filter(pk=package_id)[0]
    package.fullpackagespec = _get_fullpackagespec(package)
    package.alias = _get_package_alias(package)
    target = Target.objects.filter(pk=target_id)[0]

    dependencies = _get_package_dependencies(package_id, target_id)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'package' : package,
            'target' : target,
            'runtime_deps' : dependencies['runtime_deps'],
            'other_deps' :   dependencies['other_deps'],
            'reverse_count' : _get_package_reverse_dep_count(package, target_id),
            'dependency_count' : _get_package_dependency_count(package, target_id, True)
    }
    return render(request, template, context)

def package_included_reverse_dependencies(request, build_id, target_id, package_id):
    template = "package_included_reverse_dependencies.html"
    if Build.objects.filter(pk=build_id).count() == 0 :
        return redirect(builds)

    (pagesize, orderby) = _get_parameters_values(request, 25, 'package__name:+')
    mandatory_parameters = { 'count': pagesize,  'page' : 1, 'orderby': orderby }
    retval = _verify_parameters( request.GET, mandatory_parameters )
    if retval:
        return _redirect_parameters( 'package_included_reverse_dependencies', request.GET, mandatory_parameters, build_id = build_id, target_id = target_id, package_id = package_id)
    (filter_string, search_term, ordering_string) = _search_tuple(request, Package_File)

    queryset = Package_Dependency.objects.select_related('depends_on__name', 'depends_on__size').filter(depends_on=package_id, target_id=target_id, dep_type=Package_Dependency.TYPE_TRDEPENDS)
    objects = _get_queryset(Package_Dependency, queryset, filter_string, search_term, ordering_string, 'package__name')

    package = Package.objects.filter(pk=package_id)[0]
    package.fullpackagespec = _get_fullpackagespec(package)
    package.alias = _get_package_alias(package)
    target = Target.objects.filter(pk=target_id)[0]
    for o in objects:
        if o.package.version != '':
            o.package.version += '-' + o.package.revision
        o.alias = _get_package_alias(o.package)
    context = {
            'build' : Build.objects.filter(pk=build_id)[0],
            'package' : package,
            'target' : target,
            'objects' : objects,
            'reverse_count' : _get_package_reverse_dep_count(package, target_id),
            'dependency_count' : _get_package_dependency_count(package, target_id, True),
            'tablecols':[
                {
                    'name':'Package',
                    'orderfield': _get_toggle_order(request, "package__name"),
                    'ordericon': _get_toggle_order_icon(request, "package__name"),
                },
                {
                    'name':'Version',
                },
                {
                    'name':'Size',
                    'orderfield': _get_toggle_order(request, "package__size", True),
                    'ordericon': _get_toggle_order_icon(request, "package__size"),
                    'dclass': 'sizecol span2',
                },
            ]
    }
    if objects.all().count() < 2:
        context['disable_sort'] = True
    response = render(request, template, context)
    _save_parameters_cookies(response, pagesize, orderby, request)
    return response

def image_information_dir(request, build_id, target_id, packagefile_id):
    # stubbed for now
    return redirect(builds)


import toastermain.settings


# we have a set of functions if we're in managed mode, or
# a default "page not available" simple functions for interactive mode
if toastermain.settings.MANAGED:

    from django.contrib.auth.models import User
    from django.contrib.auth import authenticate, login
    from django.contrib.auth.decorators import login_required

    from orm.models import Project, ProjectLayer, ProjectTarget, ProjectVariable
    from orm.models import Branch, LayerSource, ToasterSetting, Release, Machine
    from bldcontrol.models import BuildRequest

    import traceback

    class BadParameterException(Exception): pass        # error thrown on invalid POST requests

    # the context processor that supplies data used across all the pages
    def managedcontextprocessor(request):
        ret = {
            "projects": Project.objects.all(),
            "MANAGED" : toastermain.settings.MANAGED
        }
        if 'project_id' in request.session:
            ret['project'] = Project.objects.get(pk = request.session['project_id'])
        return ret

    # new project
    def newproject(request):
        template = "newproject.html"
        context = {
            'email': request.user.email if request.user.is_authenticated() else '',
            'username': request.user.username if request.user.is_authenticated() else '',
            'releases': Release.objects.order_by("id"),
            'defaultbranch': ToasterSetting.objects.get(name = "DEFAULT_RELEASE").value,
        }


        if request.method == "GET":
            # render new project page
            return render(request, template, context)
        elif request.method == "POST":
            mandatory_fields = ['projectname', 'email', 'username', 'projectversion']
            try:
                # make sure we have values for all mandatory_fields
                if reduce( lambda x, y: x or y, map(lambda x: len(request.POST.get(x, '')) == 0, mandatory_fields)):
                # set alert for missing fields
                    raise BadParameterException("Fields missing: " +
            ", ".join([x for x in mandatory_fields if len(request.POST.get(x, '')) == 0 ]))

                if not request.user.is_authenticated():
                    user = authenticate(username = request.POST['username'], password = 'nopass')
                    if user is None:
                        user = User.objects.create_user(username = request.POST['username'], email = request.POST['email'], password = "nopass")

                        user = authenticate(username = user.username, password = 'nopass')
                    login(request, user)

                #  save the project
                prj = Project.objects.create_project(name = request.POST['projectname'],
                    release = Release.objects.get(pk = request.POST['projectversion']))
                prj.user_id = request.user.pk
                prj.save()
                return redirect(reverse(project, args = (prj.pk,)))

            except (IntegrityError, BadParameterException) as e:
                # fill in page with previously submitted values
                map(lambda x: context.__setitem__(x, request.POST.get(x, "-- missing")), mandatory_fields)
                if isinstance(e, IntegrityError) and "username" in str(e):
                    context['alert'] = "Your chosen username is already used"
                else:
                    context['alert'] = str(e)
                return render(request, template, context)

        raise Exception("Invalid HTTP method for this page")

    # Shows the edit project page
    def project(request, pid):
        template = "project.html"
        try:
            prj = Project.objects.get(id = pid)
        except Project.DoesNotExist:
            return HttpResponseNotFound("<h1>Project id " + pid + " is unavailable</h1>")

        try:
            puser = User.objects.get(id = prj.user_id)
        except User.DoesNotExist:
            puser = None

        # we use implicit knowledge of the current user's project to filter layer information, e.g.
        request.session['project_id'] = prj.id

        context = {
            "project" : prj,
            #"buildrequests" : prj.buildrequest_set.filter(state=BuildRequest.REQ_QUEUED),
            "buildrequests" : map(lambda x: (x, {"machine" : x.brvariable_set.filter(name="MACHINE")[0]}), prj.buildrequest_set.filter(state__lt = BuildRequest.REQ_INPROGRESS).order_by("-pk")),
            "builds" : prj.build_set.all(),
            "puser": puser,
        }
        try:
            context["machine"] = prj.projectvariable_set.get(name="MACHINE").value
        except ProjectVariable.DoesNotExist:
            context["machine"] = "-- not set yet"

        try:
            context["distro"] = prj.projectvariable_set.get(name="DISTRO").value
        except ProjectVariable.DoesNotExist:
            context["distro"] = "-- not set yet"


        return render(request, template, context)

    import json

    def xhr_projectbuild(request, pid):
        try:
            if request.method != "POST":
                raise BadParameterException("invalid method")
            prj = Project.objects.get(id = pid)

            if prj.projecttarget_set.count() == 0:
                raise BadParameterException("no targets selected")

            br = prj.schedule_build()
            return HttpResponse(json.dumps({"error":"ok",
                "brtarget" : map(lambda x: x.target, br.brtarget_set.all()),
                "machine" : br.brvariable_set.get(name="MACHINE").value,

            }), content_type = "application/json")
        except Exception as e:
            return HttpResponse(json.dumps({"error":str(e) + "\n" + traceback.format_exc()}), content_type = "application/json")

    def xhr_projectedit(request, pid):
        try:
            prj = Project.objects.get(id = pid)
            # add targets
            if 'targetAdd' in request.POST:
                for t in request.POST['targetAdd'].strip().split(" "):
                    if ":" in t:
                        target, task = t.split(":")
                    else:
                        target = t
                        task = ""

                    pt, created = ProjectTarget.objects.get_or_create(project = prj, target = target, task = task)
            # remove targets
            if 'targetDel' in request.POST:
                for t in request.POST['targetDel'].strip().split(" "):
                    pt = ProjectTarget.objects.get(pk = int(t)).delete()

            # add layers

            # remove layers

            # return all project settings
            return HttpResponse(json.dumps( {
                "error": "ok",
                "layers": map(lambda x: (x.layercommit.layer.name, x.layercommit.layer.layer_index_url), prj.projectlayer_set.all()),
                "targets" : map(lambda x: {"target" : x.target, "task" : x.task, "pk": x.pk}, prj.projecttarget_set.all()),
                "variables": map(lambda x: (x.name, x.value), prj.projectvariable_set.all()),
                }), content_type = "application/json")

        except Exception as e:
            return HttpResponse(json.dumps({"error":str(e) + "\n" + traceback.format_exc()}), content_type = "application/json")

    def importlayer(request):
        template = "importlayer.html"
        context = {
        }
        return render(request, template, context)

    def layers(request):
        template = "layers.html"
        # define here what parameters the view needs in the GET portion in order to
        # be able to display something.  'count' and 'page' are mandatory for all views
        # that use paginators.
        mandatory_parameters = { 'count': 10,  'page' : 1, 'orderby' : 'layer__name:+' };
        retval = _verify_parameters( request.GET, mandatory_parameters )
        if retval:
            return _redirect_parameters( 'layers', request.GET, mandatory_parameters)

        # boilerplate code that takes a request for an object type and returns a queryset
        # for that object type. copypasta for all needed table searches
        (filter_string, search_term, ordering_string) = _search_tuple(request, Layer_Version)

        queryset_all = Layer_Version.objects.all()
        if 'project_id' in request.session:
            queryset_all = queryset_all.filter(up_branch__in = Branch.objects.filter(name = Project.objects.get(pk = request.session['project_id']).release.name))

        queryset_with_search = _get_queryset(Layer_Version, queryset_all, None, search_term, ordering_string, '-layer__name')
        queryset = _get_queryset(Layer_Version, queryset_all, filter_string, search_term, ordering_string, '-layer__name')

        # retrieve the objects that will be displayed in the table; layers a paginator and gets a page range to display
        layer_info = _build_page_range(Paginator(queryset, request.GET.get('count', 10)),request.GET.get('page', 1))


        context = {
            'objects' : layer_info,
            'objectname' : "layers",
            'default_orderby' : 'layer__name:+',
            'total_count': queryset_with_search.count(),

            'tablecols' : [
                {   'name': 'Layer',
                    'orderfield': _get_toggle_order(request, "layer__name"),
                    'ordericon' : _get_toggle_order_icon(request, "layer__name"),
                },
                {   'name': 'Description',
                    'dclass': 'span4',
                    'clclass': 'description',
                },
                {   'name': 'Layer source',
                    'clclass': 'source',
                    'qhelp': "Where the layer is coming from, for example, if it's part of the OpenEmbedded collection of layers or if it's a layer you have imported",
                    'orderfield': _get_toggle_order(request, "layer_source__name"),
                    'ordericon': _get_toggle_order_icon(request, "layer_source__name"),
                    'filter': {
                        'class': 'layer',
                        'label': 'Show:',
                        'options': map(lambda x: (x.name, 'layer_source__pk:' + str(x.id), queryset_with_search.filter(layer_source__pk = x.id).count() ), LayerSource.objects.all()),
                    }
                },
                {   'name': 'Git repository URL',
                    'dclass': 'span6',
                    'clclass': 'git-repo', 'hidden': 1,
                    'qhelp': "The Git repository for the layer source code",
                },
                {   'name': 'Subdirectory',
                    'clclass': 'git-subdir',
                    'hidden': 1,
                    'qhelp': "The layer directory within the Git repository",
                },
                {   'name': 'Branch, tag o commit',
                    'clclass': 'branch',
                    'qhelp': "The Git branch of the layer. For the layers from the OpenEmbedded source, the branch matches the Yocto Project version you selected for this project",
                },
                {   'name': 'Dependencies',
                    'clclass': 'dependencies',
                    'qhelp': "Other layers a layer depends upon",
                },
                {   'name': 'Add | Delete',
                    'dclass': 'span2',
                    'qhelp': "Add or delete layers to / from your project ",
                },

            ]
        }

        return render(request, template, context)

    def layerdetails(request, layerid):
        template = "layerdetails.html"
        context = {
            'layerversion': Layer_Version.objects.get(pk = layerid),
        }
        return render(request, template, context)

    def targets(request):
        template = "targets.html"
        # define here what parameters the view needs in the GET portion in order to
        # be able to display something.  'count' and 'page' are mandatory for all views
        # that use paginators.
        mandatory_parameters = { 'count': 10,  'page' : 1, 'orderby' : 'name:+' };
        retval = _verify_parameters( request.GET, mandatory_parameters )
        if retval:
            return _redirect_parameters( 'targets', request.GET, mandatory_parameters)

        # boilerplate code that takes a request for an object type and returns a queryset
        # for that object type. copypasta for all needed table searches
        (filter_string, search_term, ordering_string) = _search_tuple(request, Recipe)

        queryset_all = Recipe.objects.all()
        if 'project_id' in request.session:
            queryset_all = queryset_all.filter(Q(layer_version__up_branch__in = Branch.objects.filter(name = Project.objects.get(pk=request.session['project_id']).release.name)) | Q(layer_version__build__in = Project.objects.get(pk = request.session['project_id']).build_set.all()))

        queryset_with_search = _get_queryset(Recipe, queryset_all, None, search_term, ordering_string, '-name')
        queryset = _get_queryset(Recipe, queryset_all, filter_string, search_term, ordering_string, '-name')

        # retrieve the objects that will be displayed in the table; targets a paginator and gets a page range to display
        target_info = _build_page_range(Paginator(queryset, request.GET.get('count', 10)),request.GET.get('page', 1))


        context = {
            'objects' : target_info,
            'objectname' : "targets",
            'default_orderby' : 'name:+',
            'total_count': queryset_with_search.count(),

            'tablecols' : [
                {   'name': 'Target',
                    'orderfield': _get_toggle_order(request, "name"),
                    'ordericon' : _get_toggle_order_icon(request, "name"),
                },
                {   'name': 'Target version',
                    'dclass': 'span2',
                },
                {   'name': 'Description',
                    'dclass': 'span5',
                    'clclass': 'description',
                },
                {   'name': 'Recipe file',
                    'clclass': 'recipe-file',
                    'hidden': 1,
                    'dclass': 'span5',
                },
                {   'name': 'Section',
                    'clclass': 'target-section',
                    'hidden': 1,
                },
                {   'name': 'License',
                    'clclass': 'license',
                    'hidden': 1,
                },
                {   'name': 'Layer',
                    'clclass': 'layer',
                },
                {   'name': 'Layer source',
                    'clclass': 'source',
                    'qhelp': "Where the target is coming from, for example, if it's part of the OpenEmbedded collection of targets or if it's a target you have imported",
                    'orderfield': _get_toggle_order(request, "layer_source__name"),
                    'ordericon': _get_toggle_order_icon(request, "layer_source__name"),
                    'filter': {
                        'class': 'target',
                        'label': 'Show:',
                        'options': map(lambda x: (x.name, 'layer_source__pk:' + str(x.id), queryset_with_search.filter(layer_source__pk = x.id).count() ), LayerSource.objects.all()),
                    }
                },
                {   'name': 'Branch, tag or commit',
                    'clclass': 'branch',
                    'hidden': 1,
                },
                {   'name': 'Build',
                    'dclass': 'span2',
                    'qhelp': "Add or delete targets to / from your project ",
                },

            ]
        }

        return render(request, template, context)

    def machines(request):
        template = "machines.html"
        # define here what parameters the view needs in the GET portion in order to
        # be able to display something.  'count' and 'page' are mandatory for all views
        # that use paginators.
        mandatory_parameters = { 'count': 10,  'page' : 1, 'orderby' : 'name:+' };
        retval = _verify_parameters( request.GET, mandatory_parameters )
        if retval:
            return _redirect_parameters( 'machines', request.GET, mandatory_parameters)

        # boilerplate code that takes a request for an object type and returns a queryset
        # for that object type. copypasta for all needed table searches
        (filter_string, search_term, ordering_string) = _search_tuple(request, Machine)

        queryset_all = Machine.objects.all()
#        if 'project_id' in request.session:
#            queryset_all = queryset_all.filter(Q(layer_version__up_branch__in = Branch.objects.filter(name = Project.objects.get(request.session['project_id']).release.name)) | Q(layer_version__build__in = Project.objects.get(request.session['project_id']).build_set.all()))

        queryset_with_search = _get_queryset(Machine, queryset_all, None, search_term, ordering_string, '-name')
        queryset = _get_queryset(Machine, queryset_all, filter_string, search_term, ordering_string, '-name')

        # retrieve the objects that will be displayed in the table; machines a paginator and gets a page range to display
        machine_info = _build_page_range(Paginator(queryset, request.GET.get('count', 10)),request.GET.get('page', 1))


        context = {
            'objects' : machine_info,
            'objectname' : "machines",
            'default_orderby' : 'name:+',
            'total_count': queryset_with_search.count(),

            'tablecols' : [
                {   'name': 'Machine',
                    'orderfield': _get_toggle_order(request, "name"),
                    'ordericon' : _get_toggle_order_icon(request, "name"),
                },
                {   'name': 'Description',
                    'dclass': 'span5',
                    'clclass': 'description',
                },
                {   'name': 'Machine file',
                    'clclass': 'machine-file',
                    'hidden': 1,
                },
                {   'name': 'Layer',
                    'clclass': 'layer',
                },
                {   'name': 'Layer source',
                    'clclass': 'source',
                    'qhelp': "Where the machine is coming from, for example, if it's part of the OpenEmbedded collection of machines or if it's a machine you have imported",
                    'orderfield': _get_toggle_order(request, "layer_source__name"),
                    'ordericon': _get_toggle_order_icon(request, "layer_source__name"),
                    'filter': {
                        'class': 'machine',
                        'label': 'Show:',
                        'options': map(lambda x: (x.name, 'layer_source__pk:' + str(x.id), queryset_with_search.filter(layer_source__pk = x.id).count() ), LayerSource.objects.all()),
                    }
                },
                {   'name': 'Branch, tag or commit',
                    'clclass': 'branch',
                    'hidden': 1,
                },
                {   'name': 'Select',
                    'dclass': 'span2',
                    'qhelp': "Add or delete machines to / from your project ",
                },

            ]
        }

        return render(request, template, context)

    def projectconf(request, pid):
        template = "projectconf.html"
        context = {
            'configvars': ProjectVariable.objects.filter(project_id = pid),
        }
        return render(request, template, context)

    def projectbuilds(request, pid):
        template = 'projectbuilds.html'
        # define here what parameters the view needs in the GET portion in order to
        # be able to display something.  'count' and 'page' are mandatory for all views
        # that use paginators.
        mandatory_parameters = { 'count': 10,  'page' : 1, 'orderby' : 'completed_on:-' };
        retval = _verify_parameters( request.GET, mandatory_parameters )

        # boilerplate code that takes a request for an object type and returns a queryset
        # for that object type. copypasta for all needed table searches
        (filter_string, search_term, ordering_string) = _search_tuple(request, Build)
        queryset_all = Build.objects.all.exclude(outcome = Build.IN_PROGRESS)
        queryset_with_search = _get_queryset(Build, queryset_all, None, search_term, ordering_string, '-completed_on')
        queryset = _get_queryset(Build, queryset_all, filter_string, search_term, ordering_string, '-completed_on')

        # retrieve the objects that will be displayed in the table; builds a paginator and gets a page range to display
        build_info = _build_page_range(Paginator(queryset, request.GET.get('count', 10)),request.GET.get('page', 1))


        # set up list of fstypes for each build
        fstypes_map = {};
        for build in build_info:
            targets = Target.objects.filter( build_id = build.id )
            comma = "";
            extensions = "";
            for t in targets:
                if ( not t.is_image ):
                    continue
                tif = Target_Image_File.objects.filter( target_id = t.id )
                for i in tif:
                    s=re.sub('.*tar.bz2', 'tar.bz2', i.file_name)
                    if s == i.file_name:
                        s=re.sub('.*\.', '', i.file_name)
                    if None == re.search(s,extensions):
                        extensions += comma + s
                        comma = ", "
            fstypes_map[build.id]=extensions

        # send the data to the template
        context = {
                    'objects' : build_info,
                    'objectname' : "builds",
                    'default_orderby' : 'completed_on:-',
                    'fstypes' : fstypes_map,
                    'search_term' : search_term,
                    'total_count' : queryset_with_search.count(),
                # Specifies the display of columns for the table, appearance in "Edit columns" box, toggling default show/hide, and specifying filters for columns
                    'tablecols' : [
                    {'name': 'Outcome',                                                # column with a single filter
                     'qhelp' : "The outcome tells you if a build successfully completed or failed",     # the help button content
                     'dclass' : "span2",                                                # indication about column width; comes from the design
                     'orderfield': _get_toggle_order(request, "outcome"),               # adds ordering by the field value; default ascending unless clicked from ascending into descending
                     'ordericon':_get_toggle_order_icon(request, "outcome"),
                      # filter field will set a filter on that column with the specs in the filter description
                      # the class field in the filter has no relation with clclass; the control different aspects of the UI
                      # still, it is recommended for the values to be identical for easy tracking in the generated HTML
                     'filter' : {'class' : 'outcome',
                                 'label': 'Show:',
                                 'options' : [
                                             ('Successful builds', 'outcome:' + str(Build.SUCCEEDED), queryset_with_search.filter(outcome=str(Build.SUCCEEDED)).count()),  # this is the field search expression
                                             ('Failed builds', 'outcome:'+ str(Build.FAILED), queryset_with_search.filter(outcome=str(Build.FAILED)).count()),
                                             ]
                                }
                    },
                    {'name': 'Target',                                                 # default column, disabled box, with just the name in the list
                     'qhelp': "This is the build target or build targets (i.e. one or more recipes or image recipes)",
                     'orderfield': _get_toggle_order(request, "target__target"),
                     'ordericon':_get_toggle_order_icon(request, "target__target"),
                    },
                    {'name': 'Machine',
                     'qhelp': "The machine is the hardware for which you are building a recipe or image recipe",
                     'orderfield': _get_toggle_order(request, "machine"),
                     'ordericon':_get_toggle_order_icon(request, "machine"),
                     'dclass': 'span3'
                    },                           # a slightly wider column
                    {'name': 'Started on', 'clclass': 'started_on', 'hidden' : 1,      # this is an unchecked box, which hides the column
                     'qhelp': "The date and time you started the build",
                     'orderfield': _get_toggle_order(request, "started_on", True),
                     'ordericon':_get_toggle_order_icon(request, "started_on"),
                     'filter' : {'class' : 'started_on',
                                 'label': 'Show:',
                                 'options' : [
                                             ("Today's builds" , 'started_on__gte:'+timezone.now().strftime("%Y-%m-%d"), queryset_with_search.filter(started_on__gte=timezone.now()).count()),
                                             ("Yesterday's builds", 'started_on__gte:'+(timezone.now()-timedelta(hours=24)).strftime("%Y-%m-%d"), queryset_with_search.filter(started_on__gte=(timezone.now()-timedelta(hours=24))).count()),
                                             ("This week's builds", 'started_on__gte:'+(timezone.now()-timedelta(days=7)).strftime("%Y-%m-%d"), queryset_with_search.filter(started_on__gte=(timezone.now()-timedelta(days=7))).count()),
                                             ]
                                }
                    },
                    {'name': 'Completed on',
                     'qhelp': "The date and time the build finished",
                     'orderfield': _get_toggle_order(request, "completed_on", True),
                     'ordericon':_get_toggle_order_icon(request, "completed_on"),
                     'orderkey' : 'completed_on',
                     'filter' : {'class' : 'completed_on',
                                 'label': 'Show:',
                                 'options' : [
                                             ("Today's builds", 'completed_on__gte:'+timezone.now().strftime("%Y-%m-%d"), queryset_with_search.filter(completed_on__gte=timezone.now()).count()),
                                             ("Yesterday's builds", 'completed_on__gte:'+(timezone.now()-timedelta(hours=24)).strftime("%Y-%m-%d"), queryset_with_search.filter(completed_on__gte=(timezone.now()-timedelta(hours=24))).count()),
                                             ("This week's builds", 'completed_on__gte:'+(timezone.now()-timedelta(days=7)).strftime("%Y-%m-%d"), queryset_with_search.filter(completed_on__gte=(timezone.now()-timedelta(days=7))).count()),
                                             ]
                                }
                    },
                    {'name': 'Failed tasks', 'clclass': 'failed_tasks',                # specifing a clclass will enable the checkbox
                     'qhelp': "How many tasks failed during the build",
                     'filter' : {'class' : 'failed_tasks',
                                 'label': 'Show:',
                                 'options' : [
                                             ('Builds with failed tasks', 'task_build__outcome:4', queryset_with_search.filter(task_build__outcome=4).count()),
                                             ('Builds without failed tasks', 'task_build__outcome:NOT4', queryset_with_search.filter(~Q(task_build__outcome=4)).count()),
                                             ]
                                }
                    },
                    {'name': 'Errors', 'clclass': 'errors_no',
                     'qhelp': "How many errors were encountered during the build (if any)",
                     'orderfield': _get_toggle_order(request, "errors_no", True),
                     'ordericon':_get_toggle_order_icon(request, "errors_no"),
                     'orderkey' : 'errors_no',
                     'filter' : {'class' : 'errors_no',
                                 'label': 'Show:',
                                 'options' : [
                                             ('Builds with errors', 'errors_no__gte:1', queryset_with_search.filter(errors_no__gte=1).count()),
                                             ('Builds without errors', 'errors_no:0', queryset_with_search.filter(errors_no=0).count()),
                                             ]
                                }
                    },
                    {'name': 'Warnings', 'clclass': 'warnings_no',
                     'qhelp': "How many warnings were encountered during the build (if any)",
                     'orderfield': _get_toggle_order(request, "warnings_no", True),
                     'ordericon':_get_toggle_order_icon(request, "warnings_no"),
                     'orderkey' : 'warnings_no',
                     'filter' : {'class' : 'warnings_no',
                                 'label': 'Show:',
                                 'options' : [
                                             ('Builds with warnings','warnings_no__gte:1', queryset_with_search.filter(warnings_no__gte=1).count()),
                                             ('Builds without warnings','warnings_no:0', queryset_with_search.filter(warnings_no=0).count()),
                                             ]
                                }
                    },
                    {'name': 'Time', 'clclass': 'time', 'hidden' : 1,
                     'qhelp': "How long it took the build to finish",
                     'orderfield': _get_toggle_order(request, "timespent", True),
                     'ordericon':_get_toggle_order_icon(request, "timespent"),
                     'orderkey' : 'timespent',
                    },
                    {'name': 'Log',
                     'dclass': "span4",
                     'qhelp': "Path to the build main log file",
                     'clclass': 'log', 'hidden': 1,
                     'orderfield': _get_toggle_order(request, "cooker_log_path"),
                     'ordericon':_get_toggle_order_icon(request, "cooker_log_path"),
                     'orderkey' : 'cooker_log_path',
                    },
                    {'name': 'Output', 'clclass': 'output',
                     'qhelp': "The root file system types produced by the build. You can find them in your <code>/build/tmp/deploy/images/</code> directory",
                    },
                    ]
                }

        return render(request, template, context)
else:
    # these are pages that are NOT available in interactive mode
    def managedcontextprocessor(request):
        return {
            "projects": [],
            "MANAGED" : toastermain.settings.MANAGED
        }

    def newproject(request):
        raise Exception("page not available in interactive mode")

    def project(request, pid):
        raise Exception("page not available in interactive mode")

    def xhr_projectbuild(request, pid):
        raise Exception("page not available in interactive mode")

    def xhr_projectedit(request, pid):
        raise Exception("page not available in interactive mode")

    def importlayer(request):
        raise Exception("page not available in interactive mode")

    def layers(request):
        raise Exception("page not available in interactive mode")

    def layerdetails(request):
        raise Exception("page not available in interactive mode")

    def targets(request):
        raise Exception("page not available in interactive mode")

    def targetdetails(request):
        raise Exception("page not available in interactive mode")

    def machines(request):
        raise Exception("page not available in interactive mode")

    def projectconf(request):
        raise Exception("page not available in interactive mode")

    def projectbuilds(request):
        raise Exception("page not available in interactive mode")
