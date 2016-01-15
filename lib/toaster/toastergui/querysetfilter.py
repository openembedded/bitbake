class QuerysetFilter(object):
    """ Filter for a queryset """

    def __init__(self, criteria=None):
        self.criteria = None
        if criteria:
            self.set_criteria(criteria)

    def set_criteria(self, criteria):
        """
        criteria is an instance of django.db.models.Q;
        see https://docs.djangoproject.com/en/1.9/ref/models/querysets/#q-objects
        """
        self.criteria = criteria

    def filter(self, queryset):
        """
        Filter queryset according to the criteria for this filter,
        returning the filtered queryset
        """
        if self.criteria:
            return queryset.filter(self.criteria)
        else:
            return queryset
