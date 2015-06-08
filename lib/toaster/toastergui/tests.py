from django.test import TestCase
from django.core.urlresolvers import reverse
from orm.models import Project, Release, BitbakeVersion, Build
from orm.models import ReleaseLayerSourcePriority, LayerSource, Layer, Layer_Version

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
            import json
            data = json.loads(response.content)
        except:
            self.fail("Response %s is not json-loadable" % response.content)

        self.assertTrue("error" in data)
        self.assertEqual(data["error"], "ok")
        self.assertTrue("list" in data)

        self.assertTrue(AllProjectsViewTestCase.TEST_PROJECT_NAME in map(lambda x: x["name"], data["list"]))
        self.assertTrue("id" in data["list"][0])
        self.assertTrue("projectLayersUrl" in data["list"][0])
        self.assertTrue("projectPageUrl" in data["list"][0])
        self.assertTrue("projectBuildsUrl" in data["list"][0])

class ProvisionedLayersProjectTestCase(ProvisionedProjectTestCase):
    LAYER_NAME = "base-layer"
    def setUp(self):
        super(ProvisionedLayersProjectTestCase, self).setUp()
        self.layersource, created = LayerSource.objects.get_or_create(sourcetype = LayerSource.TYPE_IMPORTED)
        self.releaselayersourcepriority, created = ReleaseLayerSourcePriority.objects.get_or_create(release = self.release, layer_source = self.layersource)
        self.layer, created = Layer.objects.get_or_create(name=XHRDataTypeAheadTestCase.LAYER_NAME, layer_source=self.layersource, vcs_url="/tmp/")
        self.lv, created = Layer_Version.objects.get_or_create(layer = self.layer, project = self.project, layer_source=self.layersource, commit="master")


class XHRDataTypeAheadTestCase(ProvisionedLayersProjectTestCase):

    def setUp(self):
        super(XHRDataTypeAheadTestCase, self).setUp()
        self.assertTrue(self.lv in self.project.compatible_layerversions())

    def test_xhr_datatypeahead_layer(self):
        response = self.client.get(reverse('xhr_datatypeahead', args=(self.project.id,)), {"type": "layerdeps"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('application/json'))

        try:
            import json
            data = json.loads(response.content)
        except:
            self.fail("Response %s is not json-loadable" % response.content)

        self.assertTrue("error" in data)
        self.assertEqual(data["error"], "ok")
        self.assertTrue("list" in data)
        self.assertTrue(len(data["list"]) > 0)

        self.assertTrue(XHRDataTypeAheadTestCase.LAYER_NAME in map(lambda x: x["name"], data["list"]))
