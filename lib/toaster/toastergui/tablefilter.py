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
from django.db.models import Q, Max, Min
from django.utils import dateparse, timezone

class TableFilter(object):
    """
    Stores a filter for a named field, and can retrieve the action
    requested from the set of actions for that filter
    """

    def __init__(self, name, title):
        self.name = name
        self.title = title
        self.__filter_action_map = {}

    def add_action(self, action):
        self.__filter_action_map[action.name] = action

    def get_action(self, action_name):
        return self.__filter_action_map[action_name]

    def to_json(self, queryset):
        """
        Dump all filter actions as an object which can be JSON serialised;
        this is used to generate the JSON for processing in
        table.js / filterOpenClicked()
        """
        filter_actions = []

        # add the "all" pseudo-filter action, which just selects the whole
        # queryset
        filter_actions.append({
            'action_name' : 'all',
            'title' : 'All',
            'type': 'toggle',
            'count' : queryset.count()
        })

        # add other filter actions
        for action_name, filter_action in self.__filter_action_map.iteritems():
            obj = filter_action.to_json(queryset)
            obj['action_name'] = action_name
            filter_actions.append(obj)

        return {
            'name': self.name,
            'title': self.title,
            'filter_actions': filter_actions
        }

class TableFilterAction(object):
    """
    A filter action which displays in the filter popup for a ToasterTable
    and uses an associated QuerysetFilter to filter the queryset for that
    ToasterTable
    """

    def __init__(self, name, title, queryset_filter):
        self.name = name
        self.title = title
        self.queryset_filter = queryset_filter

        # set in subclasses
        self.type = None

    def set_filter_params(self, params):
        """
        params: (str) a string of extra parameters for the action;
        the structure of this string depends on the type of action;
        it's ignored for a toggle filter action, which is just on or off
        """
        if not params:
            return

    def filter(self, queryset):
        return self.queryset_filter.filter(queryset)

    def to_json(self, queryset):
        """ Dump as a JSON object """
        return {
            'title': self.title,
            'type': self.type,
            'count': self.queryset_filter.count(queryset)
        }

class TableFilterActionToggle(TableFilterAction):
    """
    A single filter action which will populate one radio button of
    a ToasterTable filter popup; this filter can either be on or off and
    has no other parameters
    """

    def __init__(self, *args):
        super(TableFilterActionToggle, self).__init__(*args)
        self.type = 'toggle'

class TableFilterActionDateRange(TableFilterAction):
    """
    A filter action which will filter the queryset by a date range.
    The date range can be set via set_params()
    """

    def __init__(self, name, title, field, queryset_filter):
        """
        field: the field to find the max/min range from in the queryset
        """
        super(TableFilterActionDateRange, self).__init__(
            name,
            title,
            queryset_filter
        )

        self.type = 'daterange'
        self.field = field

    def set_filter_params(self, params):
        """
        params: (str) a string of extra parameters for the filtering
        in the format "2015-12-09,2015-12-11" (from,to); this is passed in the
        querystring and used to set the criteria on the QuerysetFilter
        associated with this action
        """

        # if params are invalid, return immediately, resetting criteria
        # on the QuerysetFilter
        try:
            from_date_str, to_date_str = params.split(',')
        except ValueError:
            self.queryset_filter.set_criteria(None)
            return

        # one of the values required for the filter is missing, so set
        # it to the one which was supplied
        if from_date_str == '':
            from_date_str = to_date_str
        elif to_date_str == '':
            to_date_str = from_date_str

        date_from_naive = dateparse.parse_datetime(from_date_str + ' 00:00:00')
        date_to_naive = dateparse.parse_datetime(to_date_str + ' 23:59:59')

        tz = timezone.get_default_timezone()
        date_from = timezone.make_aware(date_from_naive, tz)
        date_to = timezone.make_aware(date_to_naive, tz)

        args = {}
        args[self.field + '__gte'] = date_from
        args[self.field + '__lte'] = date_to

        criteria = Q(**args)
        self.queryset_filter.set_criteria(criteria)

    def to_json(self, queryset):
        """ Dump as a JSON object """
        data = super(TableFilterActionDateRange, self).to_json(queryset)

        # additional data about the date range covered by the queryset's
        # records, retrieved from its <field> column
        data['min'] = queryset.aggregate(Min(self.field))[self.field + '__min']
        data['max'] = queryset.aggregate(Max(self.field))[self.field + '__max']

        # a range filter has a count of None, as the number of records it
        # will select depends on the date range entered
        data['count'] = None

        return data

class TableFilterMap(object):
    """
    Map from field names to TableFilter objects for those fields
    """

    def __init__(self):
        self.__filters = {}

    def add_filter(self, filter_name, table_filter):
        """ table_filter is an instance of Filter """
        self.__filters[filter_name] = table_filter

    def get_filter(self, filter_name):
        return self.__filters[filter_name]

    def to_json(self, queryset):
        data = {}

        for filter_name, table_filter in self.__filters.iteritems():
            data[filter_name] = table_filter.to_json()

        return data
