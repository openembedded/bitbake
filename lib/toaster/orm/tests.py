from django.test import TestCase
from orm.models import LocalLayerSource, LayerIndexLayerSource, LayerSource
from orm.models import Branch

class LayerSourceVerifyInheritanceSaveLoad(TestCase):
    def test_object_creation(self):
        lls = LayerSource.objects.create(name = "a1", sourcetype = LayerSource.TYPE_LOCAL, apiurl = "")
        lils = LayerSource.objects.create(name = "a1", sourcetype = LayerSource.TYPE_LAYERINDEX, apiurl = "")

        print LayerSource.objects.all()

        self.assertTrue(True in map(lambda x: isinstance(x, LocalLayerSource), LayerSource.objects.all()))
        self.assertTrue(True in map(lambda x: isinstance(x, LayerIndexLayerSource), LayerSource.objects.all()))

    def test_duplicate_error(self):
        def duplicate():
            LayerSource.objects.create(name = "a1", sourcetype = LayerSource.TYPE_LOCAL, apiurl = "")
            LayerSource.objects.create(name = "a1", sourcetype = LayerSource.TYPE_LOCAL, apiurl = "")

        self.assertRaises(Exception, duplicate)
            


class LILSUpdateTestCase(TestCase):
    def test_update(self):
        lils = LayerSource.objects.create(name = "b1", sourcetype = LayerSource.TYPE_LAYERINDEX, apiurl = "http://adamian-desk.local:8080/layerindex/api/")
        lils.update()

        # run second update
        # lils.update()

        # print vars(lils)
        #print map(lambda x: vars(x), Branch.objects.all())
