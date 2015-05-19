from django.test import TestCase
from django.core.urlresolvers import reverse
from orm.models import Project, Release, BitbakeVersion, Build

class AllProjectsViewTestCase(TestCase):
    TEST_PROJECT_NAME = "test project"

    def setUp(self):
        bbv, created = BitbakeVersion.objects.get_or_create(name="test bbv", giturl="/tmp/", branch="master", dirpath="")
        release, created = Release.objects.get_or_create(name="test release", bitbake_version = bbv)
        Project.objects.create_project(name=AllProjectsViewTestCase.TEST_PROJECT_NAME, release=release)

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

        self.assertTrue("list" in data)
        self.assertTrue(AllProjectsViewTestCase.TEST_PROJECT_NAME in map(lambda x: x["name"], data["list"]))
        self.assertTrue("id" in data["list"][0])
        self.assertTrue("xhrProjectDataTypeaheadUrl" in data["list"][0])
        self.assertTrue("projectPageUrl" in data["list"][0])
        self.assertTrue("xhrProjectEditUrl" in data["list"][0])
        self.assertTrue("projectBuildUrl" in data["list"][0])
