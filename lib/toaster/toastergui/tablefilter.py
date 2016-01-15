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

class TableFilter(object):
    """
    Stores a filter for a named field, and can retrieve the action
    requested for that filter
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

class TableFilterActionToggle(object):
    """
    Stores a single filter action which will populate one radio button of
    a ToasterTable filter popup; this filter can either be on or off and
    has no other parameters
    """

    def __init__(self, name, title, queryset_filter):
        self.name = name
        self.title = title
        self.__queryset_filter = queryset_filter
        self.type = 'toggle'

    def set_params(self, params):
        """
        params: (str) a string of extra parameters for the action;
        the structure of this string depends on the type of action;
        it's ignored for a toggle filter action, which is just on or off
        """
        pass

    def filter(self, queryset):
        return self.__queryset_filter.filter(queryset)

    def to_json(self, queryset):
        """ Dump as a JSON object """
        return {
            'title': self.title,
            'type': self.type,
            'count': self.__queryset_filter.count(queryset)
        }

class TableFilterMap(object):
    """
    Map from field names to Filter objects for those fields
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
