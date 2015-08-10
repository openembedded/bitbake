from django.test import TestCase
from django.core.urlresolvers import reverse
from orm.models import Project, Release, BitbakeVersion, Build
from orm.models import ReleaseLayerSourcePriority, LayerSource, Layer, Layer_Version, Recipe, Machine, ProjectLayer
import json

class ProvisionedProjectTestCase(TestCase):
    TEST_PROJECT_NAME = "test project"

    def setUp(self):
        self.bbv, created = BitbakeVersion.objects.get_or_create(name="test bbv", giturl="/tmp/", branch="master", dirpath="")
        self.release, created = Release.objects.get_or_create(name="test release", bitbake_version = self.bbv)
        self.project = Project.objects.create_project(name=AllProjectsViewTestCase.TEST_PROJECT_NAME, release=self.release)


class AllProjectsViewTestCase(ProvisionedProjectTestCase):

    def test_get_base_call_returns_html(self):
        response = self.client.get(reverse('all-projects'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        self.assertTemplateUsed(response, "projects.html")
        self.assertTrue(AllProjectsViewTestCase.TEST_PROJECT_NAME in response.content)

    def test_get_json_call_returns_json(self):
        response = self.client.get(reverse('all-projects'), {"format": "json"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('application/json'))

        try:
            data = json.loads(response.content)
        except:
            self.fail("Response %s is not json-loadable" % response.content)

        self.assertTrue("error" in data)
        self.assertEqual(data["error"], "ok")
        self.assertTrue("rows" in data)

        self.assertTrue(AllProjectsViewTestCase.TEST_PROJECT_NAME in map(lambda x: x["name"], data["rows"]))
        self.assertTrue("id" in data["rows"][0])
        self.assertTrue("projectLayersUrl" in data["rows"][0])
        self.assertTrue("projectPageUrl" in data["rows"][0])
        self.assertTrue("projectBuildsUrl" in data["rows"][0])

class ProvisionedLayersProjectTestCase(ProvisionedProjectTestCase):
    LAYER_NAME = "base-layer"
    RECIPE_NAME = "base-recipe"


    def setUp(self):
        super(ProvisionedLayersProjectTestCase, self).setUp()
        self.layersource, created = LayerSource.objects.get_or_create(sourcetype = LayerSource.TYPE_IMPORTED)
        self.releaselayersourcepriority, created = ReleaseLayerSourcePriority.objects.get_or_create(release = self.release, layer_source = self.layersource)
        self.layer, created = Layer.objects.get_or_create(name=XHRDataTypeAheadTestCase.LAYER_NAME, layer_source=self.layersource, vcs_url="/tmp/")
        self.lv, created = Layer_Version.objects.get_or_create(layer = self.layer, project = self.project, layer_source=self.layersource, commit="master")

        self.recipe, created = Recipe.objects.get_or_create(layer_source=self.layersource, name=ProvisionedLayersProjectTestCase.RECIPE_NAME, version="1.2", summary="one recipe", description="recipe", layer_version=self.lv)

        self.machine, created = Machine.objects.get_or_create(layer_version=self.lv, name="wisk", description="wisking machine")

        ProjectLayer.objects.get_or_create(project = self.project,
                                           layercommit = self.lv)


class XHRDataTypeAheadTestCase(ProvisionedLayersProjectTestCase):

    def setUp(self):
        super(XHRDataTypeAheadTestCase, self).setUp()
        self.assertTrue(self.lv in self.project.compatible_layerversions())

    def test_typeaheads(self):
        layers_url = reverse('xhr_layerstypeahead', args=(self.project.id,))
        prj_url = reverse('xhr_projectstypeahead')

        urls = [ layers_url,
                 prj_url,
                 reverse('xhr_recipestypeahead', args=(self.project.id,)),
                 reverse('xhr_machinestypeahead', args=(self.project.id,)),
               ]

        def basic_reponse_check(reponse, url):
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response['Content-Type'].startswith('application/json'))

            try:
                data = json.loads(response.content)
            except:
                self.fail("Response %s is not json-loadable" % response.content)
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
                response = self.client.get(url, { 'search' : typeing })
                results = basic_reponse_check(response, url)
                if results:
                    break

            # After "typeing" the alpabet we should have result true
            # from each of the urls
            self.assertTrue(results)
