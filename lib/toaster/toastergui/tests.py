#! /usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Toaster Implementation
#
# Copyright (C) 2013-2015 Intel Corporation
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

"""Test cases for Toaster GUI and ReST."""

from django.test import TestCase
from django.core.urlresolvers import reverse
from orm.models import Project, Release, BitbakeVersion
from orm.models import ReleaseLayerSourcePriority, LayerSource, Layer
from orm.models import Layer_Version, Recipe, Machine, ProjectLayer
import json

PROJECT_NAME = "test project"

class ViewTests(TestCase):
    """Tests to verify view APIs."""

    def setUp(self):
        self.bbv = BitbakeVersion.objects.create(\
                       name="test bbv", giturl="/tmp/",
                       branch="master", dirpath="")
        self.release = Release.objects.create(\
                           name="test release", bitbake_version=self.bbv)
        self.project = Project.objects.create_project(name=PROJECT_NAME,
                                                      release=self.release)
        self.layersrc = LayerSource.objects.create(\
                               sourcetype=LayerSource.TYPE_IMPORTED)
        self.priority = ReleaseLayerSourcePriority.objects.create(\
                               release=self.release,
                               layer_source=self.layersrc)
        self.layer = Layer.objects.create(\
                         name="base-layer",
                         layer_source=self.layersrc, vcs_url="/tmp/")
        self.lver = Layer_Version.objects.create(\
                        layer=self.layer, project=self.project,
                        layer_source=self.layersrc, commit="master")

        self.recipe = Recipe.objects.create(\
                          layer_source=self.layersrc, name="base-recipe",
                          version="1.2", summary="one recipe",
                          description="recipe", layer_version=self.lver)

        self.machine = Machine.objects.create(\
                          layer_version=self.lver, name="wisk",
                          description="wisking machine")

        ProjectLayer.objects.create(project=self.project,
                                    layercommit=self.lver)

        self.assertTrue(self.lver in self.project.compatible_layerversions())

    def test_get_base_call_returns_html(self):
        """Basic test for all-projects view"""
        response = self.client.get(reverse('all-projects'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        self.assertTemplateUsed(response, "projects.html")
        self.assertTrue(PROJECT_NAME in response.content)

    def test_get_json_call_returns_json(self):
        """Test for all projects output in json format"""
        url = reverse('all-projects')
        response = self.client.get(url, {"format": "json"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('application/json'))

        data = json.loads(response.content)

        self.assertTrue("error" in data)
        self.assertEqual(data["error"], "ok")
        self.assertTrue("rows" in data)

        self.assertTrue(PROJECT_NAME in [x["name"] for x in data["rows"]])
        self.assertTrue("id" in data["rows"][0])

        self.assertEqual(sorted(data["rows"][0]),
                         ['bitbake_version_id', 'created', 'id',
                          'layersTypeAheadUrl', 'name', 'projectBuildsUrl',
                          'projectPageUrl', 'recipesTypeAheadUrl',
                          'release_id', 'short_description', 'updated',
                          'user_id'])

    def test_typeaheads(self):
        """Test typeahead ReST API"""
        layers_url = reverse('xhr_layerstypeahead', args=(self.project.id,))
        prj_url = reverse('xhr_projectstypeahead')

        urls = [layers_url,
                prj_url,
                reverse('xhr_recipestypeahead', args=(self.project.id,)),
                reverse('xhr_machinestypeahead', args=(self.project.id,)),
               ]

        def basic_reponse_check(response, url):
            """Check data structure of http response."""
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response['Content-Type'].startswith('application/json'))

            data = json.loads(response.content)

            self.assertTrue("error" in data)
            self.assertEqual(data["error"], "ok")
            self.assertTrue("results" in data)

            # We got a result so now check the fields
            if len(data['results']) > 0:
                result = data['results'][0]

                self.assertTrue(len(result['name']) > 0)
                self.assertTrue("detail" in result)
                self.assertTrue(result['id'] > 0)

                # Special check for the layers typeahead's extra fields
                if url == layers_url:
                    self.assertTrue(len(result['layerdetailurl']) > 0)
                    self.assertTrue(len(result['vcs_url']) > 0)
                    self.assertTrue(len(result['vcs_reference']) > 0)
                # Special check for project typeahead extra fields
                elif url == prj_url:
                    self.assertTrue(len(result['projectPageUrl']) > 0)

                return True

            return False

        import string

        for url in urls:
            results = False

            for typeing in list(string.ascii_letters):
                response = self.client.get(url, {'search': typeing})
                results = basic_reponse_check(response, url)
                if results:
                    break

            # After "typeing" the alpabet we should have result true
            # from each of the urls
            self.assertTrue(results)
