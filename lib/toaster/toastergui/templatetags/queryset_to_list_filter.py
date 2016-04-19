from django import template
import json

register = template.Library()

def queryset_to_list(queryset, fields):
    """
    Convert a queryset to a list; fields can be set to a comma-separated
    string of fields for each record included in the resulting list; if
    omitted, all fields are included for each record, e.g.

        {{ queryset | queryset_to_list:"id,name" }}

    will return a list like

        [{'id': 1, 'name': 'foo'}, ...]

    (providing queryset has id and name fields)
    """
    if fields:
        fields_list = [field.strip() for field in fields.split(',')]
        return list(queryset.values(*fields_list))
    else:
        return list(queryset.values())

register.filter('queryset_to_list', queryset_to_list)
