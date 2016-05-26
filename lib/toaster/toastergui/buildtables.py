#
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Toaster Implementation
#
# Copyright (C) 2016 Intel Corporation
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

from orm.models import Build
import toastergui.tables as tables

from toastergui.widgets import ToasterTable


class BuildTablesMixin(ToasterTable):
    def get_context_data(self, **kwargs):
        # We need to be explicit about which superclass we're calling here
        # Otherwise the MRO gets in a right mess
        context = ToasterTable.get_context_data(self, **kwargs)
        context['build'] = Build.objects.get(pk=kwargs['build_id'])
        return context


class BuiltPackagesTableBase(tables.PackagesTable):
    """ Table to display all the packages built in a build """
    def __init__(self, *args, **kwargs):
        super(BuiltPackagesTableBase, self).__init__(*args, **kwargs)
        self.title = "Packages built"
        self.default_orderby = "name"

    def setup_queryset(self, *args, **kwargs):
        build = Build.objects.get(pk=kwargs['build_id'])
        self.static_context_extra['build'] = build
        self.queryset = build.package_set.all().exclude(recipe=None)
        self.queryset = self.queryset.order_by(self.default_orderby)

    def setup_columns(self, *args, **kwargs):
        super(BuiltPackagesTableBase, self).setup_columns(*args, **kwargs)

        def pkg_link_template(val):
            """ return the template used for the link with the val as the
            element value i.e. inside the <a></a>"""

            return ('''
                    <a href="
                    {%% url "package_built_detail" extra.build.pk data.pk %%}
                    ">%s</a>
                    ''' % val)

        def recipe_link_template(val):
            return ('''
                    {%% if data.recipe %%}
                    <a href="
                    {%% url "recipe" extra.build.pk data.recipe.pk %%}
                    ">%(value)s</a>
                    {%% else %%}
                    %(value)s
                    {%% endif %%}
                    ''' % {'value': val})

        add_pkg_link_to = ['name', 'version', 'size', 'license']
        add_recipe_link_to = ['recipe__name', 'recipe__version']

        # Add the recipe and pkg build links to the required columns
        for column in self.columns:
            # Convert to template field style accessors
            tmplv = column['field_name'].replace('__', '.')
            tmplv = "{{data.%s}}" % tmplv

            if column['field_name'] in add_pkg_link_to:
                # Don't overwrite an existing template
                if column['static_data_template']:
                    column['static_data_template'] =\
                        pkg_link_template(column['static_data_template'])
                else:
                    column['static_data_template'] = pkg_link_template(tmplv)

                column['static_data_name'] = column['field_name']

            elif column['field_name'] in add_recipe_link_to:
                # Don't overwrite an existing template
                if column['static_data_template']:
                    column['static_data_template'] =\
                        recipe_link_template(column['static_data_template'])
                else:
                    column['static_data_template'] =\
                        recipe_link_template(tmplv)
                column['static_data_name'] = column['field_name']

        self.add_column(title="Layer",
                        field_name="recipe__layer_version__layer__name",
                        hidden=True,
                        orderable=True)

        self.add_column(title="Layer branch",
                        field_name="recipe__layer_version__branch",
                        hidden=True,
                        orderable=True)

        git_rev_template = '''
        {% with vcs_ref=data.recipe.layer_version.commit %}
        {% include 'snippets/gitrev_popover.html' %}
        {% endwith %}
        '''

        self.add_column(title="Layer commit",
                        static_data_name='vcs_ref',
                        static_data_template=git_rev_template,
                        hidden=True)


class BuiltPackagesTable(BuildTablesMixin, BuiltPackagesTableBase):
    """ Show all the packages built for the selected build """
    def __init__(self, *args, **kwargs):
        super(BuiltPackagesTable, self).__init__(*args, **kwargs)
        self.title = "Packages built"
        self.default_orderby = "name"

        self.empty_state =\
            ('<strong>No packages were built.</strong> How did this happen?'
             'Well, BitBake reuses as much stuff as possible.'
             'If all of the packages needed were already built and available'
             'in your build infrastructure, BitBake'
             'will not rebuild any of them. This might be slightly confusing,'
             'but it does make everything faster.')

    def setup_columns(self, *args, **kwargs):
        super(BuiltPackagesTable, self).setup_columns(*args, **kwargs)

        def remove_dep_cols(columns):
            for column in columns:
                # We don't need these fields
                if column['static_data_name'] in ['reverse_dependencies',
                                                  'dependencies']:
                    continue

                yield column

        self.columns = list(remove_dep_cols(self.columns))


class BuiltRecipesTable(BuildTablesMixin):
    """ Table to show the recipes that have been built in this build """

    def __init__(self, *args, **kwargs):
        super(BuiltRecipesTable, self).__init__(*args, **kwargs)
        self.title = "Recipes built"
        self.default_orderby = "name"

    def setup_queryset(self, *args, **kwargs):
        build = Build.objects.get(pk=kwargs['build_id'])
        self.static_context_extra['build'] = build
        self.queryset = build.get_recipes()
        self.queryset = self.queryset.order_by(self.default_orderby)

    def setup_columns(self, *args, **kwargs):
        recipe_name_tmpl =\
            '<a href="{% url "recipe" extra.build.pk data.pk %}">'\
            '{{data.name}}'\
            '</a>'

        recipe_version_tmpl =\
            '<a href="{% url "recipe" extra.build.pk data.pk %}">'\
            '{{data.version}}'\
            '</a>'

        recipe_file_tmpl =\
            '{{data.file_path}}'\
            '{% if data.pathflags %}<i>({{data.pathflags}})</i>'\
            '{% endif %}'

        git_rev_template = '''
        {% with vcs_ref=data.layer_version.commit %}
        {% include 'snippets/gitrev_popover.html' %}
        {% endwith %}
        '''

        depends_on_tmpl = '''
        {% with deps=data.r_dependencies_recipe.all %}
        {% with count=deps|length %}
        {% if count %}
        <a class="btn" title="
        <a href='{% url "recipe" extra.build.pk data.pk %}#dependencies'>
        {{data.name}}</a> dependencies"
        data-content="<ul class='unstyled'>
        {% for dep in deps|dictsort:"depends_on.name"%}
        <li><a href='{% url "recipe" extra.build.pk dep.depends_on.pk %}'>
        {{dep.depends_on.name}}</a></li>
        {% endfor %}
        </ul>">
         {{count}}
        </a>
        {% endif %}{% endwith %}{% endwith %}
        '''

        rev_depends_tmpl = '''
        {% with revs=data.r_dependencies_depends.all %}
        {% with count=revs|length %}
        {% if count %}
        <a class="btn"
        title="
        <a href='{% url "recipe" extra.build.pk data.pk %}#brought-in-by'>
        {{data.name}}</a> reverse dependencies"
        data-content="<ul class='unstyled'>
        {% for dep in revs|dictsort:"recipe.name" %}
        <li>
        <a href='{% url "recipe" extra.build.pk dep.recipe.pk %}'>
        {{dep.recipe.name}}
        </a></li>
        {% endfor %}
        </ul>">
        {{count}}
        </a>
        {% endif %}{% endwith %}{% endwith %}
        '''

        self.add_column(title="Name",
                        field_name="name",
                        static_data_name='name',
                        orderable=True,
                        static_data_template=recipe_name_tmpl)

        self.add_column(title="Version",
                        field_name="version",
                        static_data_name='version',
                        static_data_template=recipe_version_tmpl)

        self.add_column(title="Dependencies",
                        static_data_name="dependencies",
                        static_data_template=depends_on_tmpl,
                        hidden=True)

        self.add_column(title="Reverse dependencies",
                        static_data_name="revdeps",
                        static_data_template=rev_depends_tmpl,
                        help_text='Recipe build-time reverse dependencies'
                        ' (i.e. the recipes that depend on this recipe)',
                        hidden=True)

        self.add_column(title="Recipe file",
                        field_name="file_path",
                        static_data_name="file_path",
                        static_data_template=recipe_file_tmpl)

        self.add_column(title="Section",
                        field_name="section",
                        orderable=True)

        self.add_column(title="License",
                        field_name="license",
                        help_text='Multiple license names separated by the'
                        ' pipe character indicates a choice between licenses.'
                        ' Multiple license names separated by the ampersand'
                        ' character indicates multiple licenses exist that'
                        ' cover different parts of the source',
                        orderable=True)

        self.add_column(title="Layer",
                        field_name="layer_version__layer__name",
                        orderable=True)

        self.add_column(title="Layer branch",
                        field_name="layer_version__branch",
                        orderable=True)

        self.add_column(title="Layer commit",
                        static_data_name="commit",
                        static_data_template=git_rev_template)
