#
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Toaster Implementation
#
# Copyright (C) 2015        Intel Corporation
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

from django.views.generic import View, TemplateView
from django.shortcuts import HttpResponse
from django.http import HttpResponseBadRequest
from django.core import serializers
from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from orm.models import Project, ProjectLayer, Layer_Version
from django.template import Context, Template
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import FieldError
from django.conf.urls import url, patterns

import urls
import types
import json
import collections
import operator


class ToasterTemplateView(TemplateView):
    def get_context_data(self, **kwargs):
      context = super(ToasterTemplateView, self).get_context_data(**kwargs)
      if 'pid' in kwargs:
          context['project'] = Project.objects.get(pk=kwargs['pid'])

          context['projectlayers'] = map(lambda prjlayer: prjlayer.layercommit.id, ProjectLayer.objects.filter(project=context['project']))

      if 'layerid' in kwargs:
          context['layerversion'] = Layer_Version.objects.get(pk=kwargs['layerid'])

      return context


class ToasterTable(View):
    def __init__(self):
        self.title = None
        self.queryset = None
        self.columns = []
        self.filters = {}
        self.total_count = 0
        self.static_context_extra = {}
        self.filter_actions = {}
        self.empty_state = "Sorry - no data found"
        self.default_orderby = ""

    def get(self, request, *args, **kwargs):
        self.setup_queryset(*args, **kwargs)

        # Put the project id into the context for the static_data_template
        if 'pid' in kwargs:
            self.static_context_extra['pid'] = kwargs['pid']

        cmd = kwargs['cmd']
        if cmd and 'filterinfo' in cmd:
            data = self.get_filter_info(request)
        else:
            # If no cmd is specified we give you the table data
            data = self.get_data(request, **kwargs)

        return HttpResponse(data, content_type="application/json")

    def get_filter_info(self, request):
        data = None

        self.setup_filters()

        search = request.GET.get("search", None)
        if search:
            self.apply_search(search)

        name = request.GET.get("name", None)
        if name is None:
            data = json.dumps(self.filters,
                              indent=2,
                              cls=DjangoJSONEncoder)
        else:
            for actions in self.filters[name]['filter_actions']:
                actions['count'] = self.filter_actions[actions['name']](count_only=True)

            # Add the "All" items filter action
            self.filters[name]['filter_actions'].insert(0, {
                'name' : 'all',
                'title' : 'All',
                'count' : self.queryset.count(),
            })

            data = json.dumps(self.filters[name],
                              indent=2,
                              cls=DjangoJSONEncoder)

            return data

    def setup_columns(self, *args, **kwargs):
        """ function to implement in the subclass which sets up the columns """
        pass
    def setup_filters(self, *args, **kwargs):
        """ function to implement in the subclass which sets up the filters """
        pass
    def setup_queryset(self, *args, **kwargs):
        """ function to implement in the subclass which sets up the queryset"""
        pass

    def add_filter(self, name, title, filter_actions):
        """Add a filter to the table.

        Args:
            name (str): Unique identifier of the filter.
            title (str): Title of the filter.
            filter_actions: Actions for all the filters.
        """
        self.filters[name] = {
          'title' : title,
          'filter_actions' : filter_actions,
        }

    def make_filter_action(self, name, title, action_function):
        """ Utility to make a filter_action """

        action = {
          'title' : title,
          'name' : name,
        }

        self.filter_actions[name] = action_function

        return action

    def add_column(self, title="", help_text="",
                   orderable=False, hideable=True, hidden=False,
                   field_name="", filter_name=None, static_data_name=None,
                   static_data_template=None):
        """Add a column to the table.

        Args:
            title (str): Title for the table header
            help_text (str): Optional help text to describe the column
            orderable (bool): Whether the column can be ordered.
                We order on the field_name.
            hideable (bool): Whether the user can hide the column
            hidden (bool): Whether the column is default hidden
            field_name (str or list): field(s) required for this column's data
            static_data_name (str, optional): The column's main identifier
                which will replace the field_name.
            static_data_template(str, optional): The template to be rendered
                as data
        """

        self.columns.append({'title' : title,
                             'help_text' : help_text,
                             'orderable' : orderable,
                             'hideable' : hideable,
                             'hidden' : hidden,
                             'field_name' : field_name,
                             'filter_name' : filter_name,
                             'static_data_name': static_data_name,
                             'static_data_template': static_data_template,
                            })

    def render_static_data(self, template, row):
        """Utility function to render the static data template"""

        context = {
          'extra' : self.static_context_extra,
          'data' : row,
        }

        context = Context(context)
        template = Template(template)

        return template.render(context)

    def apply_filter(self, filters):
        self.setup_filters()

        try:
            filter_name, filter_action = filters.split(':')
        except ValueError:
            return

        if "all" in filter_action:
            return

        try:
            self.filter_actions[filter_action]()
        except KeyError:
            print "Filter and Filter action pair not found"

    def apply_orderby(self, orderby):
        # Note that django will execute this when we try to retrieve the data
        self.queryset = self.queryset.order_by(orderby)

    def apply_search(self, search_term):
        """Creates a query based on the model's search_allowed_fields"""

        if not hasattr(self.queryset.model, 'search_allowed_fields'):
            print "Err Search fields aren't defined in the model"
            return

        search_queries = []
        for st in search_term.split(" "):
            q_map = [Q(**{field + '__icontains': st})
                     for field in self.queryset.model.search_allowed_fields]

            search_queries.append(reduce(operator.or_, q_map))

        search_queries = reduce(operator.and_, search_queries)
        print "applied the search to the queryset"
        self.queryset = self.queryset.filter(search_queries)

    def get_data(self, request, **kwargs):
        """Returns the data for the page requested with the specified
        parameters applied"""

        page_num = request.GET.get("page", 1)
        limit = request.GET.get("limit", 10)
        search = request.GET.get("search", None)
        filters = request.GET.get("filter", None)
        orderby = request.GET.get("orderby", None)

        # Make a unique cache name
        cache_name = self.__class__.__name__

        for key, val in request.GET.iteritems():
            cache_name = cache_name + str(key) + str(val)

        data = cache.get(cache_name)

        if data:
            return data

        self.setup_columns(**kwargs)

        if search:
            self.apply_search(search)
        if filters:
            self.apply_filter(filters)
        if orderby:
            self.apply_orderby(orderby)

        paginator = Paginator(self.queryset, limit)

        try:
            page = paginator.page(page_num)
        except EmptyPage:
            page = paginator.page(1)

        data = {
            'total' : self.queryset.count(),
            'default_orderby' : self.default_orderby,
            'columns' : self.columns,
            'rows' : [],
        }


        try:
            for row in page.object_list:
                #Use collection to maintain the order
                required_data = collections.OrderedDict()

                for col in self.columns:
                    field = col['field_name']
                    # Check if we need to process some static data
                    if "static_data_name" in col and col['static_data_name']:
                        required_data[col['static_data_name']] = self.render_static_data(col['static_data_template'], row)

                        # Overwrite the field_name with static_data_name
                        # so that this can be used as the html class name

                        col['field_name'] = col['static_data_name']
                    else:
                        model_data = row
                        # Traverse to any foriegn key in the object hierachy
                        for subfield in field.split("__"):
                            model_data = getattr(model_data, subfield)
                        # The field could be a function on the model so check
                        # If it is then call it
                        if isinstance(model_data, types.MethodType):
                          model_data = model_data()

                        required_data[field] = model_data

                data['rows'].append(required_data)

        except FieldError:
            print "Error: Requested field does not exist"


        data = json.dumps(data, indent=2, cls=DjangoJSONEncoder)
        cache.set(cache_name, data, 10)

        return data
