#! /usr/bin/env python3
#
# BitBake Toaster Implementation
#
# SPDX-License-Identifier: GPL-2.0-only
#

"""Project pages with and without build mode (TOASTER_BUILDSERVER)."""

import os
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from orm.models import Project, Build, Variable, Layer, Layer_Version, Recipe


class ProjectPagesBase(TestCase):

    def setUp(self):
        self.project = Project.objects.create(name="test project")
        self.builds_url = reverse('projectbuilds', args=(self.project.id,))
        self.config_url = reverse('project', args=(self.project.id,))

        # a started build of an image recipe
        now = timezone.now()
        self.build = Build.objects.create(project=self.project, started_on=now,
                                          completed_on=now,
                                          outcome=Build.SUCCEEDED)
        Variable.objects.create(build=self.build, variable_name='MACHINE',
                                variable_value='qemux86-64')
        layer_version = Layer_Version.objects.create(
            build=self.build, layer=Layer.objects.create(name='meta-test'))
        Recipe.objects.create(name='core-image-test', is_image=True,
                              layer_version=layer_version)
        self.build_url = reverse('builddashboard', args=(self.build.id,))

    def projects_table_names(self):
        response = self.client.get(reverse('all-projects'), {'format': 'json'})
        self.assertEqual(response.status_code, 200)
        return [row['name'] for row in response.json()['rows']]


@mock.patch('toastergui.views.project_enable', True)
@mock.patch.dict(os.environ, {'TOASTER_BUILDSERVER': '1'})
class BuildModeTests(ProjectPagesBase):

    def test_projects_table_links_to_configuration(self):
        names = self.projects_table_names()
        self.assertTrue(any(self.config_url + '"' in n for n in names), names)

    def test_build_page_offers_new_custom_image(self):
        response = self.client.get(self.build_url)
        self.assertContains(response, 'id="menu-new-custom-image"')


@mock.patch('toastergui.views.project_enable', False)
@mock.patch.dict(os.environ, {'TOASTER_BUILDSERVER': '0'})
class NoBuildModeTests(ProjectPagesBase):

    def test_projects_tab_shown(self):
        response = self.client.get(reverse('all-builds'))
        self.assertContains(response, 'id="navbar-all-projects"')

    def test_projects_table_links_to_builds(self):
        names = self.projects_table_names()
        self.assertTrue(any(self.builds_url + '"' in n for n in names), names)
        self.assertFalse(any(self.config_url + '"' in n for n in names), names)

    def test_configuration_pages_redirect_to_builds(self):
        for url in (self.config_url,
                    reverse('projectconf', args=(self.project.id,))):
            response = self.client.get(url)
            self.assertRedirects(response, self.builds_url,
                                 fetch_redirect_response=False)

    def test_builds_page_has_no_project_topbar(self):
        response = self.client.get(self.builds_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="project-topbar"')

    def test_build_page_has_no_custom_image_actions(self):
        response = self.client.get(self.build_url)
        self.assertContains(response, 'id="menu-download-build-log"')
        self.assertNotContains(response, 'id="menu-new-custom-image"')
        self.assertNotContains(response, 'id="menu-edit-custom-image"')
