from django.test import TestCase, TransactionTestCase
from orm.models import LocalLayerSource, LayerIndexLayerSource, ImportedLayerSource, LayerSource
from orm.models import Branch

from orm.models import Project, Build, Layer, Layer_Version, Branch, ProjectLayer
from orm.models import Release, ReleaseLayerSourcePriority, BitbakeVersion

from django.utils import timezone

import os

# set TTS_LAYER_INDEX to the base url to use a different instance of the layer index

# tests to verify inheritance for the LayerSource proxy-inheritance classes
class LayerSourceVerifyInheritanceSaveLoad(TestCase):
    def test_object_creation(self):
        lls = LayerSource.objects.create(name = "a1", sourcetype = LayerSource.TYPE_LOCAL, apiurl = "")
        lils = LayerSource.objects.create(name = "a2", sourcetype = LayerSource.TYPE_LAYERINDEX, apiurl = "")
        imls = LayerSource.objects.create(name = "a3", sourcetype = LayerSource.TYPE_IMPORTED, apiurl = "")

        import pprint
        pprint.pprint([(x.__class__,vars(x)) for x in LayerSource.objects.all()])

        self.assertTrue(True in map(lambda x: isinstance(x, LocalLayerSource), LayerSource.objects.all()))
        self.assertTrue(True in map(lambda x: isinstance(x, LayerIndexLayerSource), LayerSource.objects.all()))
        self.assertTrue(True in map(lambda x: isinstance(x, ImportedLayerSource), LayerSource.objects.all()))

    def test_duplicate_error(self):
        def duplicate():
            LayerSource.objects.create(name = "a1", sourcetype = LayerSource.TYPE_LOCAL, apiurl = "")
            LayerSource.objects.create(name = "a1", sourcetype = LayerSource.TYPE_LOCAL, apiurl = "")

        self.assertRaises(Exception, duplicate)


class LILSUpdateTestCase(TransactionTestCase):
    def setUp(self):
        # create release
        bbv = BitbakeVersion.objects.create(name="master", giturl="git://git.openembedded.org/bitbake")
        release = Release.objects.create(name="default-release", bitbake_version = bbv, branch_name = "master")

    def test_update(self):
        layer_index_url = os.getenv("TTS_LAYER_INDEX")
        if layer_index_url == None:
            print "Using layers.openembedded.org for layer index. override with TTS_LAYER_INDEX enviroment variable"
            layer_index_url = "http://layers.openembedded.org/"

        lils = LayerSource.objects.create(name = "b1", sourcetype = LayerSource.TYPE_LAYERINDEX, apiurl = layer_index_url + "layerindex/api/")
        lils.update()

        # run asserts
        self.assertTrue(lils.branch_set.all().count() > 0, "update() needs to fetch some branches")



# tests to verify layer_version priority selection
class LayerVersionEquivalenceTestCase(TestCase):
    def setUp(self):
        # create layer sources
        ls = LayerSource.objects.create(name = "dummy-layersource", sourcetype = LayerSource.TYPE_LOCAL)

        # create bitbake version
        bbv = BitbakeVersion.objects.create(name="master", giturl="git://git.openembedded.org/bitbake")
        # create release
        release = Release.objects.create(name="default-release", bitbake_version = bbv, branch_name = "master")
        # attach layer source to release
        ReleaseLayerSourcePriority.objects.create(release = release, layer_source = ls, priority = 1)


        # create layer attach
        self.layer = Layer.objects.create(name="meta-testlayer", layer_source = ls)
        # create branch
        self.branch = Branch.objects.create(name="master", layer_source = ls)

        # set a layer version for the layer on the specified branch
        self.layerversion = Layer_Version.objects.create(layer = self.layer, layer_source = ls, up_branch = self.branch)

        # create spoof layer that should not appear in the search results
        Layer_Version.objects.create(layer = Layer.objects.create(name="meta-notvalid", layer_source = ls), layer_source = ls, up_branch = self.branch)


        # create a project ...
        self.project = Project.objects.create_project(name="test-project", release = release)
        # ... and set it up with a single layer version
        ProjectLayer.objects.create(project=  self.project, layercommit = self.layerversion)

    def test_single_layersource(self):
        # when we have a single layer version, get_equivalents_wpriority() should return a list with just this layer_version
        equivalent_list = self.layerversion.get_equivalents_wpriority(self.project)
        self.assertTrue(len(equivalent_list) == 1)
        self.assertTrue(equivalent_list[0] == self.layerversion)

    def test_dual_layersource(self):
        # if we have two layers with the same name, from different layer sources, we expect both layers in, in increasing priority of the layer source
        ls2 = LayerSource.objects.create(name = "dummy-layersource2", sourcetype = LayerSource.TYPE_LOCAL, apiurl="test")

        # assign a lower priority for the second layer source
        Release.objects.get(name="default-release").releaselayersourcepriority_set.create(layer_source = ls2, priority = 2)

        # create a new layer_version for a layer with the same name coming from the second layer source
        self.layer2 = Layer.objects.create(name="meta-testlayer", layer_source = ls2)
        self.layerversion2 = Layer_Version.objects.create(layer = self.layer2, layer_source = ls2, up_branch = self.branch)

        # expect two layer versions, in the priority order
        equivalent_list = self.layerversion.get_equivalents_wpriority(self.project)
        self.assertTrue(len(equivalent_list) == 2)
        self.assertTrue(equivalent_list[0] == self.layerversion2)
        self.assertTrue(equivalent_list[1] == self.layerversion)

    def test_build_layerversion(self):
        # any layer version coming from the build should show up before any layer version coming from upstream
        build = Build.objects.create(project = self.project, started_on = timezone.now(), completed_on = timezone.now())
        self.layerversion_build = Layer_Version.objects.create(layer = self.layer, build = build, commit = "deadbeef")

        # a build layerversion must be in the equivalence list for the original layerversion
        equivalent_list = self.layerversion.get_equivalents_wpriority(self.project)
        self.assertTrue(len(equivalent_list) == 2)
        self.assertTrue(equivalent_list[0] == self.layerversion)
        self.assertTrue(equivalent_list[1] == self.layerversion_build)

        # getting the build layerversion equivalent list must return the same list as the original layer
        build_equivalent_list = self.layerversion_build.get_equivalents_wpriority(self.project)

        self.assertTrue(equivalent_list == build_equivalent_list, "%s is not %s" % (equivalent_list, build_equivalent_list))

class ProjectLVSelectionTestCase(TestCase):
    def setUp(self):
        # create layer sources
        ls = LayerSource.objects.create(name = "dummy-layersource", sourcetype = LayerSource.TYPE_LOCAL)

        # create bitbake version
        bbv = BitbakeVersion.objects.create(name="master", giturl="git://git.openembedded.org/bitbake")
        # create release
        release = Release.objects.create(name="default-release", bitbake_version = bbv, branch_name="master")
        # attach layer source to release
        ReleaseLayerSourcePriority.objects.create(release = release, layer_source = ls, priority = 1)

        # create layer attach
        self.layer = Layer.objects.create(name="meta-testlayer", layer_source = ls)
        # create branch
        self.branch = Branch.objects.create(name="master", layer_source = ls)

        # set a layer version for the layer on the specified branch
        self.layerversion = Layer_Version.objects.create(layer = self.layer, layer_source = ls, up_branch = self.branch)


        # create a project ...
        self.project = Project.objects.create_project(name="test-project", release = release)
        # ... and set it up with a single layer version
        ProjectLayer.objects.create(project=  self.project, layercommit = self.layerversion)

    def test_single_layersource(self):
        compatible_layerversions = self.project.compatible_layerversions()
        self.assertTrue(len(compatible_layerversions) == 1)
        self.assertTrue(compatible_layerversions[0] == self.layerversion)


    def test_dual_layersource(self):
         # if we have two layers with the same name, from different layer sources, we expect both layers in, in increasing priority of the layer source
        ls2 = LayerSource.objects.create(name = "dummy-layersource2", sourcetype = LayerSource.TYPE_LOCAL, apiurl="testing")

        # assign a lower priority for the second layer source
        Release.objects.get(name="default-release").releaselayersourcepriority_set.create(layer_source = ls2, priority = 2)

        # create a new layer_version for a layer with the same name coming from the second layer source
        self.layer2 = Layer.objects.create(name="meta-testlayer", layer_source = ls2)
        self.layerversion2 = Layer_Version.objects.create(layer = self.layer2, layer_source = ls2, up_branch = self.branch)

         # expect two layer versions, in the priority order
        equivalent_list = self.project.compatible_layerversions()
        self.assertTrue(len(equivalent_list) == 2)
        self.assertTrue(equivalent_list[0] == self.layerversion2)
        self.assertTrue(equivalent_list[1] == self.layerversion)
