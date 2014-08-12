from django.core.management.base import NoArgsCommand, CommandError
from django.db import transaction
from orm.models import LayerSource, ToasterSetting, Branch, Layer, Layer_Version
from orm.models import BitbakeVersion, Release, ReleaseDefaultLayer
from bldcontrol.bbcontroller import getBuildEnvironmentController, ShellCmdException
from bldcontrol.models import BuildRequest, BuildEnvironment
import os

def DN(path):
    if path is None:
        return ""
    else:
        return os.path.dirname(path)


class Command(NoArgsCommand):
    args = ""
    help = "Verifies that the configured settings are valid and usable, or prompts the user to fix the settings."

    def _reduce_canon_path(self, path):
        components = []
        for c in path.split("/"):
            if c == "..":
                del components[-1]
            elif c == ".":
                pass
            else:
                components.append(c)
        return "/".join(components)

    def _find_first_path_for_file(self, startdirectory, filename, level = 0):
        if level < 0:
            return None
        dirs = []
        for i in os.listdir(startdirectory):
            j = os.path.join(startdirectory, i)
            if os.path.isfile(j):
                if i == filename:
                    return startdirectory
            elif os.path.isdir(j):
                dirs.append(j)
        for j in dirs:
            ret = self._find_first_path_for_file(j, filename, level - 1)
            if ret is not None:
                return ret
        return None

    def _get_suggested_sourcedir(self, be):
        if be.betype != BuildEnvironment.TYPE_LOCAL:
            return ""
        return DN(DN(DN(self._find_first_path_for_file(self.guesspath, "toasterconf.json", 4))))

    def _get_suggested_builddir(self, be):
        if be.betype != BuildEnvironment.TYPE_LOCAL:
            return ""
        return DN(self._find_first_path_for_file(self.guesspath, "bblayers.conf", 3))

    def _import_layer_config(self, baselayerdir):
        filepath = os.path.join(baselayerdir, "meta/conf/toasterconf.json")
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            raise Exception("Failed to find toaster config file %s ." % filepath)

        import json, pprint
        data = json.loads(open(filepath, "r").read())

        # verify config file validity before updating settings
        for i in ['bitbake', 'releases', 'defaultrelease', 'config', 'layersources']:
            assert i in data

        # import bitbake data
        for bvi in data['bitbake']:
            bvo, created = BitbakeVersion.objects.get_or_create(name=bvi['name'])
            bvo.giturl = bvi['giturl']
            bvo.branch = bvi['branch']
            bvo.dirpath = bvi['dirpath']
            bvo.save()

        # set the layer sources
        for lsi in data['layersources']:
            assert 'sourcetype' in lsi
            assert 'apiurl' in lsi
            assert 'name' in lsi
            assert 'branches' in lsi

            if lsi['sourcetype'] == LayerSource.TYPE_LAYERINDEX or lsi['apiurl'].startswith("/"):
                apiurl = lsi['apiurl']
            else:
                apiurl = self._reduce_canon_path(os.path.join(DN(filepath), lsi['apiurl']))

            try:
                ls = LayerSource.objects.get(sourcetype = lsi['sourcetype'], apiurl = apiurl)
            except LayerSource.DoesNotExist:
                ls = LayerSource.objects.create(
                    name = lsi['name'],
                    sourcetype = lsi['sourcetype'],
                    apiurl = apiurl
                )

            layerbranches = []
            for branchname in lsi['branches']:
                bo, created = Branch.objects.get_or_create(layer_source = ls, name = branchname)
                layerbranches.append(bo)

            if 'layers' in lsi:
                for layerinfo in lsi['layers']:
                    lo, created = Layer.objects.get_or_create(layer_source = ls, name = layerinfo['name'])
                    if layerinfo['local_path'].startswith("/"):
                        lo.local_path = layerinfo['local_path']
                    else:
                        lo.local_path = self._reduce_canon_path(os.path.join(DN(filepath), layerinfo['local_path']))
                    lo.layer_index_url = layerinfo['layer_index_url']
                    if 'vcs_url' in layerinfo:
                        lo.vcs_url = layerinfo['vcs_url']
                    lo.save()

                    for branch in layerbranches:
                        lvo, created = Layer_Version.objects.get_or_create(layer_source = ls,
                                up_branch = branch,
                                commit = branch.name,
                                layer = lo)
                        lvo.dirpath = layerinfo['dirpath']
                        lvo.save()
        # set releases
        for ri in data['releases']:
            bvo = BitbakeVersion.objects.get(name = ri['bitbake'])
            assert bvo is not None

            ro, created = Release.objects.get_or_create(name = ri['name'], bitbake_version = bvo)
            ro.description = ri['description']
            ro.branch = ri['branch']
            ro.save()

            for dli in ri['defaultlayers']:
                lsi, layername = dli.split(":")
                layer, created = Layer.objects.get_or_create( 
                        layer_source = LayerSource.objects.get(name = lsi),
                        name = layername
                    )
                ReleaseDefaultLayer.objects.get_or_create( release = ro, layer = layer)

        # set default release
        if ToasterSetting.objects.filter(name = "DEFAULT_RELEASE").count() > 0:
            ToasterSetting.objects.filter(name = "DEFAULT_RELEASE").update(value = data['defaultrelease'])
        else:
            ToasterSetting.objects.create(name = "DEFAULT_RELEASE", value = data['defaultrelease'])

        # set default config variables
        for configname in data['config']:
            if ToasterSetting.objects.filter(name = "DEFCONF_" + configname).count() > 0:
                ToasterSetting.objects.filter(name = "DEFCONF_" + configname).update(value = data['config'][configname])
            else:
                ToasterSetting.objects.create(name = "DEFCONF_" + configname, value = data['config'][configname])

    def handle(self, **options):
        self.guesspath = DN(DN(DN(DN(DN(DN(DN(__file__)))))))

        # we make sure we have builddir and sourcedir for all defined build envionments
        for be in BuildEnvironment.objects.all():
            def _verify_be():
                is_changed = False
                print("Verifying the Build Environment type %s id %d." % (be.get_betype_display(), be.pk))
                if len(be.sourcedir) == 0:
                    suggesteddir = self._get_suggested_sourcedir(be)
                    be.sourcedir = raw_input(" -- Layer sources checkout directory may not be empty [guessed \"%s\"]:" % suggesteddir)
                    if len(be.sourcedir) == 0 and len(suggesteddir) > 0:
                        be.sourcedir = suggesteddir
                    is_changed = True

                if not be.sourcedir.startswith("/"):
                    be.sourcedir = raw_input(" -- Layer sources checkout directory must be an absolute path:")
                    is_changed = True

                if len(be.builddir) == 0:
                    suggesteddir = self._get_suggested_builddir(be)
                    be.builddir = raw_input(" -- Build directory may not be empty [guessed \"%s\"]:" % suggesteddir)
                    if len(be.builddir) == 0 and len(suggesteddir) > 0:
                        be.builddir = suggesteddir
                    is_changed = True

                if not be.builddir.startswith("/"):
                    be.builddir = raw_input(" -- Build directory must be an absolute path:")
                    is_changed = True



                if is_changed:
                    print "Build configuration saved"
                    be.save()

                if is_changed and be.betype == BuildEnvironment.TYPE_LOCAL:
                    baselayerdir = DN(DN(self._find_first_path_for_file(be.sourcedir, "toasterconf.json", 3)))
                    if baselayerdir:
                        i = raw_input(" -- Do you want to import basic layer configuration from \"%s\" ? (y/N):" % baselayerdir)
                        if len(i) and i.upper()[0] == 'Y':
                            self._import_layer_config(baselayerdir)
                            # we run lsupdates after config update
                            print "Updating information from the layer source, please wait."
                            from django.core.management import call_command
                            call_command("lsupdates")
                        pass

                return is_changed

            while (_verify_be()):
                pass

        # verify that default settings are there
        if ToasterSetting.objects.filter(name = 'DEFAULT_RELEASE').count() != 1:
            ToasterSetting.objects.filter(name = 'DEFAULT_RELEASE').delete()
            ToasterSetting.objects.get_or_create(name = 'DEFAULT_RELEASE', value = '')

        return 0
