#! /usr/bin/env python3
#
# BitBake Toaster Implementation
#
# SPDX-License-Identifier: GPL-2.0-only
#

"""Project of command line builds (TOASTER_PROJECT)."""

from unittest import mock

from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bb.ui.buildinfohelper import BuildInfoHelper, ORMWrapper
from bldcontrol.models import BuildRequest
from orm.models import Build, Project, Layer, Layer_Version, ToasterSetting


class CommandLineBuildProjectTests(TestCase):

    def setUp(self):
        self.orm = ORMWrapper()

    def test_default_project_without_name(self):
        for name in (None, '', '   '):
            build = self.orm.get_or_create_build_object(None, name)
            self.assertTrue(build.project.is_default)

    def test_named_project_is_created_once(self):
        ToasterSetting.objects.create(name='DEFCONF_MACHINE', value='qemux86-64')
        first = self.orm.get_or_create_build_object(None, 'poky: master')
        second = self.orm.get_or_create_build_object(None, 'poky: master')
        self.assertEqual(first.project.name, 'poky: master')
        self.assertFalse(first.project.is_default)
        self.assertEqual(first.project, second.project)
        self.assertEqual(first.project.get_variable('MACHINE'), 'qemux86-64')
        self.assertEqual(Project.objects.filter(name='poky: master').count(), 1)

    def test_existing_project_is_used(self):
        project = Project.objects.create(name='existing')
        build = self.orm.get_or_create_build_object(None, 'existing')
        self.assertEqual(build.project, project)

    def test_layers_stay_with_the_project(self):
        # like for the default project, layers of a command line build are
        # associated with its project and not added to the shared layer data
        build = self.orm.get_or_create_build_object(None, 'poky: master')
        layer_version = self.orm.get_update_layer_version_object(
            build, Layer.objects.create(name='meta-test'),
            {'branch': 'master', 'commit': 'abc', 'priority': 6,
             'local_path': '/srv/meta-test'})
        self.assertEqual(layer_version.project, build.project)
        self.assertEqual(Layer_Version.objects.get(pk=layer_version.pk).build, build)


class FakeServer:

    values = {
        'TMPDIR': '/tmp',
        'TOASTER_PROJECT': 'poky: master',
        'BUILDNAME': 'test-build',
        'MACHINE': 'qemux86-64',
        'DISTRO': 'poky',
        'DISTRO_VERSION': 'test',
        'BB_VERSION': 'test',
    }

    def runCommand(self, command):
        return self.values.get(command[1]), None


class BuildInfoHelperProjectTests(TestCase):

    def test_toaster_project_is_read_from_bitbake(self):
        helper = BuildInfoHelper(FakeServer())
        helper.store_started_build()
        build = helper.internal_state['build']
        self.assertEqual(build.project.name, 'poky: master')
        self.assertEqual(build.machine, 'qemux86-64')


class CommandLineBuildWidgetTests(TestCase):

    def test_only_managed_build_can_be_rebuilt(self):
        project = Project.objects.create(name='poky: master')
        now = timezone.now()
        cli_build = Build.objects.create(project=project, started_on=now,
                                         completed_on=now,
                                         outcome=Build.SUCCEEDED)
        managed_build = Build.objects.create(project=project, started_on=now,
                                             completed_on=now,
                                             outcome=Build.SUCCEEDED)
        BuildRequest.objects.create(project=project, build=managed_build,
                                    state=BuildRequest.REQ_COMPLETED)

        response = self.client.get(reverse('most_recent_builds'))
        self.assertEqual(response.status_code, 200)
        builds = {build['id']: build for build in response.json()}
        self.assertTrue(builds[cli_build.id]['is_cli_build'])
        self.assertFalse(builds[managed_build.id]['is_cli_build'])


@mock.patch('toastergui.views.project_enable', True)
@mock.patch.dict('os.environ', {'TOASTER_BUILDSERVER': '1'})
class CommandLineProjectPagesTests(TestCase):
    """In build mode, a project without a release only holds command line
    builds and cannot be configured or built from Toaster"""

    def setUp(self):
        self.project = ORMWrapper().get_or_create_build_object(
            None, 'poky: master').project
        self.builds_url = reverse('projectbuilds', args=(self.project.id,))

    def test_configuration_pages_redirect_to_builds(self):
        for name in ('project', 'projectconf'):
            response = self.client.get(reverse(name, args=(self.project.id,)))
            self.assertRedirects(response, self.builds_url,
                                 fetch_redirect_response=False)

    def test_builds_page_has_no_project_topbar(self):
        response = self.client.get(self.builds_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="project-topbar"')

    def test_project_url_is_builds_page(self):
        template = Template('{% load project_url_tag %}{% project_url p %}')
        self.assertEqual(template.render(Context({'p': self.project})),
                         self.builds_url)
